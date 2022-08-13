import os
import sys
import json
import time
import math
import uuid
import pika
import shutil
import random
import signal
import hashlib
import binascii

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from multiprocessing import Process, Pipe

N = 4
JOBS_SIZE = 1
SEED_SIZE = 64
CHALLENGE_LEVEL_RANGE = (7, 7)
SEED_VALID = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~"


class Node:
    def __init__(self, verbose=False):
        self.state = 1
        self.verbose = verbose
        # states
        #  1: starting
        #  2: exchanging keys
        #  3: electing leader
        #  4: waiting challenge
        #  5: mining
        #  6: mine is done, awaiting voting
        # -1: error

        self.id = uuid.uuid4().int >> 96  # integer 32 bits
        print(self.id)
        self.nodes = {self.id}
        self.pub_keys = {}

        self.private_key = None
        self.public_key = None
        self.signer = None

        # generate pub/priv keys
        self.generate_key()

        self.jobs = []
        self.conn_receive, self.conn_send = Pipe()
        self.pid = os.getpid()

        if sys.platform.startswith("win"):
            signal.signal(signal.SIGBREAK, self.handler)
        else:
            signal.signal(signal.SIGCHLD, self.handler)

        self.challenge_table = {}
        self.election = {}
        self.leader = None
        self.ballotbox = {}

        self.connection = None
        self.channel = None

        # queues ########
        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(host="localhost")
        )
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(queue="", durable=True)  # self queue
        queue = result.method.queue

        # entrance
        self.channel.exchange_declare(
            exchange="ppd/init", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/init", queue=queue)  # broker subscribe

        # pubkeys
        self.channel.exchange_declare(
            exchange="ppd/pubkey", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/pubkey", queue=queue)

        # election
        self.channel.exchange_declare(
            exchange="ppd/election", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/election", queue=queue)

        # challenge
        self.channel.exchange_declare(
            exchange="ppd/challenge", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/challenge", queue=queue)

        # submit
        self.channel.exchange_declare(
            exchange="ppd/solution", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/solution", queue=queue)

        # ballotbox
        self.channel.exchange_declare(
            exchange="ppd/voting", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ppd/voting", queue=queue)

        self.channel.basic_consume(on_message_callback=self.callback, queue=queue)

    def join(self):
        self.state = 1
        self.announce()
        self.channel.start_consuming()

    def callback(self, ch, method, properties, body):
        # defines callback function by args
        r = json.loads(body.decode("ascii"))

        keys = set(r.keys())

        if set(["NodeId"]) == keys:  # ppd/init
            self.callback_entrance(r)

        elif set(["NodeId", "PubKey"]) == keys:  # ppd/pubkey
            self.callback_pubkeys(r)

        elif set(["NodeId", "ElectionNumber", "Sign"]) == keys:  # ppd/election
            sig = r["Sign"]
            del r["Sign"]
            r_dump = json.dumps(r, indent=None, ensure_ascii=True)
            if self.verify_sign(r_dump, sig, r["NodeId"]):
                self.callback_election(r)

        elif (
            set(["NodeId", "TransactionNumber", "Challenge", "Sign"]) == keys
        ):  # ppd/challenge
            sig = r["Sign"]
            del r["Sign"]
            r_dump = json.dumps(r, indent=None, ensure_ascii=True)
            if self.verify_sign(r_dump, sig, r["NodeId"]):
                self.callback_challenge(r)

        elif (
            set(["NodeId", "TransactionNumber", "Seed", "Sign"]) == keys
        ):  # ppd/solution
            sig = r["Sign"]
            del r["Sign"]
            r_dump = json.dumps(r, indent=None, ensure_ascii=True)
            if self.verify_sign(r_dump, sig, r["NodeId"]):
                self.callback_submit(r)

        elif (
            set(["NodeId", "SolutionId", "TransactionNumber", "Seed", "Vote", "Sign"])
            == keys
        ):  # ppd/voting
            sig = r["Sign"]
            del r["Sign"]
            r_dump = json.dumps(r, indent=None, ensure_ascii=True)

            if self.verify_sign(r_dump, sig, r["NodeId"]):
                self.callback_ballotbox(r)

    def callback_entrance(self, r):
        if r["NodeId"] not in self.nodes:
            self.nodes.add(r["NodeId"])
            if self.verbose:
                print(f"{r['NodeId']} inside chain! {len(self.nodes)} participants.")

            self.announce()  # keeping the message

        if (len(self.nodes) >= N) and (self.state == 1):
            if self.verbose:
                print(f"STARTED!")
            self.exchange_keys()

    def callback_pubkeys(self, r):
        if r["NodeId"] not in self.pub_keys.keys():
            self.pub_keys[r["NodeId"]] = r["PubKey"]

            if self.verbose:
                print(f"{r['NodeId']} {len(self.pub_keys)} pub_keys.")
            self.exchange_keys()

        if (len(self.pub_keys) >= N) and (self.state == 2):
            if self.id not in self.election.keys():
                self.apply()

    def callback_election(self, r):
        if self.state != 3:
            return

        if r["NodeId"] not in self.nodes:
            if self.verbose:
                print(f"Invalid id {r['NodeId']}")
            return

        self.election[r["NodeId"]] = r["ElectionNumber"]

        if len(self.election) >= N:
            # max ticket or arrival order
            self.leader = max(self.election, key=self.election.get)
            self.state = 4
            if self.leader == self.id:
                self.generate_challenge()
                if self.verbose:
                    print(f"Leader is me")
            else:
                if self.verbose:
                    print(f"Leader is {self.leader}")

    def callback_challenge(self, r):
        if self.state != 4:
            return

        if r["NodeId"] != self.leader:
            if self.verbose:
                print(f"Invalid leader {r['NodeId']}")
            return

        self.challenge_table[r["TransactionNumber"]] = {
            "Challenge": int(r["Challenge"]),
            "Seed": None,
            "Winner": None,
        }
        self.state = 5

        print("##########")
        print(self.challenge_table)
        print("##########\n")

        self.mine(r["TransactionNumber"], r["Challenge"])

    def callback_submit(self, r):
        if self.state < 5:
            return

        node_id = r["NodeId"]
        transaction_id = r["TransactionNumber"]
        seed = r["Seed"]
        verified = int(self.verify(node_id, transaction_id, seed))

        data = {
            "NodeId": self.id,
            "SolutionId": node_id,
            "TransactionNumber": transaction_id,
            "Seed": seed,
            "Vote": verified,
        }

        data["Sign"] = self.sign(json.dumps(data, indent=None, ensure_ascii=True))

        self.channel.basic_publish(
            exchange="ppd/voting",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def callback_ballotbox(self, r):
        voter_id = r["NodeId"]
        node_id = r["SolutionId"]
        transaction_id = r["TransactionNumber"]
        seed = r["Seed"]

        if not self.challenge_table[transaction_id]["Winner"] and r["Vote"]:
            if self.ballotbox.get(node_id):  # already have votes:
                if self.ballotbox[node_id].get(voter_id):
                    return  # repeated vote

                self.ballotbox[node_id][voter_id] = 1
            else:
                self.ballotbox[node_id] = {voter_id: 1}

            if len(self.ballotbox[node_id]) > N // 2:
                if self.verbose:
                    print(f"{node_id} solved!")
                self.challenge_table[transaction_id]["Winner"] = node_id
                self.challenge_table[transaction_id]["Challenge"] = str(seed)
                print("##########")
                print(self.challenge_table)
                print("##########\n")

                self.state = 3
                self.apply()

    def generate_key(self):
        if not os.path.exists("keys"):
            os.makedirs("keys")

        key = RSA.generate(1024)
        with open(f"keys/{self.id}-private.key", "wb") as f:
            os.chmod(f"keys/{self.id}-private.key", 0o0600)
            f.write(key.exportKey("PEM"))

        pubkey = key.publickey()
        with open(f"keys/{self.id}-public.key", "wb") as f:
            f.write(pubkey.exportKey("OpenSSH"))

        self.private_key = key.exportKey("PEM")
        self.public_key = pubkey.exportKey("OpenSSH").decode()
        self.signer = PKCS1_v1_5.new(key)

    def sign(self, msg):
        digest = SHA256.new()
        digest.update(str(msg).encode("ascii"))
        sig = self.signer.sign(digest)

        return sig.hex()

    def verify_sign(self, msg, sig, id):
        sig = bytes.fromhex(sig)

        digest = SHA256.new()
        digest.update(msg.encode("ascii"))

        public_key = RSA.importKey(self.pub_keys[id])
        verifier = PKCS1_v1_5.new(public_key)
        verified = verifier.verify(digest, sig)

        if not verified:
            print(f"FAKE message send by {id}")

        return verified

    def announce(self):
        data = {"NodeId": self.id}
        self.channel.basic_publish(
            exchange="ppd/init",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )  # make message persistent

    def exchange_keys(self):
        self.state = 2

        data = {"NodeId": self.id, "PubKey": self.public_key}
        self.channel.basic_publish(
            exchange="ppd/pubkey",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def apply(self):
        self.state = 3

        self.clean_election()
        ticket = uuid.uuid4().int >> 96
        self.election[self.id] = ticket
        if self.verbose:
            print(f"voting with ticket {ticket}")

        data = {"NodeId": self.id, "ElectionNumber": ticket}
        data["Sign"] = self.sign(json.dumps(data, indent=None, ensure_ascii=True))
        self.channel.basic_publish(
            exchange="ppd/election",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def clean_election(self):
        self.election = {}
        self.leader = None
        self.ballotbox = {}

    def generate_challenge(self):
        i = 0 if not self.challenge_table else max(self.challenge_table.keys()) + 1

        challenge_level = random.randint(
            CHALLENGE_LEVEL_RANGE[0], CHALLENGE_LEVEL_RANGE[1]
        )

        data = {"NodeId": self.id, "TransactionNumber": i, "Challenge": challenge_level}
        data["Sign"] = self.sign(json.dumps(data, indent=None, ensure_ascii=True))
        self.channel.basic_publish(
            exchange="ppd/challenge",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def search(transaction_id, challenge, pid, conn_send):
        # https://stackoverflow.com/questions/27455978/python-generate-random-uuid-v-md5-v-random-which-is-most-efficient-or-ineffi
        seed = binascii.hexlify(os.urandom(SEED_SIZE)) # ascii
        seed_ciph = hashlib.sha1(seed).hexdigest()
        solution = int(seed_ciph, 16) >> (160 - challenge)  # SHA has 160 bit

        while solution != 0:
            seed = binascii.hexlify(os.urandom(SEED_SIZE))  # ascii
            seed_ciph = hashlib.sha1(seed).hexdigest()
            solution = int(seed_ciph, 16) >> (160 - challenge)

        conn_send.send(
            {
                "TransactionNumber": transaction_id,
                "Challenge": challenge,
                "Seed": seed.decode("ascii"),
            }
        )

        if sys.platform.startswith("win"):
            os.kill(pid, signal.CTRL_BREAK_EVENT)
        else:
            os.kill(pid, signal.SIGCHLD)

    def mine(self, transaction_id, challenge):
        # multiprocess
        self.jobs = []

        for i in range(JOBS_SIZE):
            p = Process(
                target=Node.search,
                args=(transaction_id, challenge, self.pid, self.conn_send),
                daemon=True,
            )
            self.jobs.append(p)
            p.start()

    def handler(self, signum, frame):
        r = self.conn_receive.recv()
        transaction_id, challenge, seed = (
            r["TransactionNumber"],
            r["Challenge"],
            r["Seed"],
        )

        if self.verbose:
            print(f"found {seed} for challenge {challenge}")
        data = {
            "NodeId": self.id,
            "TransactionNumber": transaction_id,
            "Seed": seed,
        }
        data["Sign"] = self.sign(json.dumps(data, indent=None, ensure_ascii=True))
        self.channel.basic_publish(
            exchange="ppd/solution",
            routing_key="",
            body=json.dumps(data, indent=None, ensure_ascii=True),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        self.state = 6

        # terminate jobs
        for i in range(len(self.jobs)):
            try:
                process = self.jobs[i]
                process.terminate()
            except:
                pass
        self.jobs = []

    def verify(self, node_id, transaction_id, seed):
        # if node_id == id:
        #     return True

        chalenge = self.challenge_table[transaction_id]["Challenge"]
        seed_ciph = hashlib.sha1(seed.encode("ascii")).hexdigest()
        solution = int(seed_ciph, 16) >> (160 - chalenge)

        # s = bin(int(seed_ciph, 16))[2:] # remove "0b"
        # s = s[::-1]
        # gp = [s[i:i+8] for i in range(0, len(s), 8)]
        # el = gp[-1] # last element
        # el[::-1].zfill(8) # unreverse

        if solution == 0:
            if self.jobs:
                # terminate jobs
                for i in range(len(self.jobs)):
                    try:
                        process = self.jobs[i]
                        process.terminate()
                    except:
                        pass
                self.jobs = []

            return True
        return False


if __name__ == "__main__":
    try:
        Node().join()
    except KeyboardInterrupt:
        if os.path.exists("keys"):
            shutil.rmtree("keys")
        print("Interrupted!")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
