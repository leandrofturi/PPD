import os
import sys
import json
import time
import uuid
import pika
import random
import signal
import hashlib

from multiprocessing import Process, Pipe

N = 4
JOBS_SIZE = 1
CHALENGE_MAP = {d: bin(int("".join(map(str, [1] * d)), 2)) for d in range(1, 128)}

CHALLENGE_LEVEL = random.randint(5, 9)


def tabulate(dict_table):
    print(f"transaction id\t|\tchallenge\t|\tseed\t|\twinner")
    for k, v in dict_table.items():
        print(f"{k}\t|\t{v['challenge']}\t|\t{v['seed']}\t|\t{v['winner']}")
    print()


class Node:
    def __init__(self, speed=0):
        self.speed = speed
        self.state = 1
        # states
        #  1: starting
        #  2: electing leader
        #  3: waiting challenge
        #  4: mining
        #  5: mine is done, awaiting voting
        # -1: error

        self.id = uuid.uuid4().int >> 64
        self.nodes = {self.id}
        print(self.id)
        self.jobs = []
        self.conn_receive, self.conn_send = Pipe()
        self.pid = os.getpid()
        signal.signal(signal.SIGBREAK, self.handler) # SIGCHLD unix

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
            exchange="entrance", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="entrance", queue=queue)  # broker subscribe

        # election
        self.channel.exchange_declare(
            exchange="election", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="election", queue=queue)

        # challenge
        self.channel.exchange_declare(
            exchange="challenge", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="challenge", queue=queue)

        # submit
        self.channel.exchange_declare(
            exchange="submit", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="submit", queue=queue)

        # ballotbox
        self.channel.exchange_declare(
            exchange="ballotbox", exchange_type="fanout", auto_delete=False
        )
        self.channel.queue_bind(exchange="ballotbox", queue=queue)

        self.channel.basic_consume(on_message_callback=self.callback, queue=queue)

        # joining
        self.state = 1
        self.announce()
        self.channel.start_consuming()

    def callback(self, ch, method, properties, body):
        # defines callback function by args
        r = json.loads(body.decode("utf-8"))
        keys = r.keys()

        if "vote" in keys:
            self.callback_ballotbox(r)
        elif "seed" in keys:
            self.callback_submit(r)
        elif "challenge" in keys:
            self.callback_challenge(r)
        elif "ticket" in keys:
            self.callback_election(r)
        elif "id" in keys:
            self.callback_entrance(r)

    def callback_entrance(self, r):
        if r["id"] not in self.nodes:
            self.nodes.add(r["id"])
            # print(f"{r['id']} inside chain! {len(self.nodes)} participants.")

            self.announce()

        if (len(self.nodes) >= N) and (self.state == 1):
            # print(f"STARTED!")

            if self.id not in self.election.keys():
                self.apply()

    def callback_election(self, r):
        if self.state != 2:
            return

        if r["id"] not in self.nodes:
            # print(f"Invalid id {r['id']}")
            return

        self.election[r["id"]] = r["ticket"]

        if len(self.election) >= N:
            # max ticket or arrival order
            self.leader = max(self.election, key=self.election.get)
            self.state = 3
            if self.leader == self.id:
                self.generate_challenge()
                # print(f"Leader is me")
            # else:
            # print(f"Leader is {self.leader}")

    def callback_challenge(self, r):
        if self.state != 3:
            return

        if r["id"] != self.leader:
            # print(f"Invalid leader {r['id']}")
            return

        self.challenge_table[r["transaction_id"]] = {
            "challenge": r["challenge"],
            "seed": None,
            "winner": None,
        }
        self.state = 4
        print("##########")
        tabulate(self.challenge_table)
        print("##########")
        self.mine(r["transaction_id"], r["challenge"])

    def callback_submit(self, r):
        if self.state < 4:
            return

        node_id = r["id"]
        transaction_id = r["transaction_id"]
        seed = r["seed"]

        if self.verify(node_id, transaction_id, seed):
            data = {
                "id": self.id,
                "node_id": node_id,
                "transaction_id": transaction_id,
                "seed": seed,
                "vote": True,
            }
        else:
            data = {
                "id": self.id,
                "node_id": node_id,
                "transaction_id": transaction_id,
                "seed": seed,
                "vote": False,
            }

        self.channel.basic_publish(
            exchange="ballotbox",
            routing_key="",
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def callback_ballotbox(self, r):
        voter_id = r["id"]
        node_id = r["node_id"]
        transaction_id = r["transaction_id"]
        seed = r["seed"]

        if not self.challenge_table[transaction_id]["winner"] and r["vote"]:
            if self.ballotbox.get(node_id):  # already have votes:
                if self.ballotbox[node_id].get(voter_id):
                    return  # repeated vote

                self.ballotbox[node_id][voter_id] = 1
            else:
                self.ballotbox[node_id] = {voter_id: 1}

            if len(self.ballotbox[node_id]) > N // 2:
                # print(f"{node_id} solved!")
                self.challenge_table[transaction_id]["winner"] = node_id
                self.challenge_table[transaction_id]["seed"] = seed
                print("##########")
                tabulate(self.challenge_table)
                print("##########")

                self.state = 2
                self.apply()

    def announce(self):
        data = {"id": self.id}
        self.channel.basic_publish(
            exchange="entrance",
            routing_key="",
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2),
        )  # make message persistent

    def apply(self):
        self.state = 2

        self.clean_election()
        ticket = random.random()
        self.election[self.id] = ticket
        # print(f"voting with ticket {ticket}")

        data = {"id": self.id, "ticket": ticket}
        self.channel.basic_publish(
            exchange="election",
            routing_key="",
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def clean_election(self):
        self.election = {}
        self.leader = None
        self.ballotbox = {}

    def generate_challenge(self):
        i = 0 if not self.challenge_table else max(self.challenge_table.keys()) + 1

        data = {"id": self.id, "transaction_id": i, "challenge": CHALLENGE_LEVEL}
        self.channel.basic_publish(
            exchange="challenge",
            routing_key="",
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def search(transaction_id, challenge, pid, conn_send, speed):
        chalenge_str = CHALENGE_MAP[challenge]
        if speed:
            # print(f"sleeping for {speed}s")
            time.sleep(speed)

        seed = str(uuid.uuid4())
        hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))
        while not hash_object.startswith(chalenge_str):  # equals to one
            if speed:
                # print(f"sleeping for {speed}s")
                time.sleep(speed)

            seed = str(uuid.uuid4())
            hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))

        conn_send.send(
            {"transaction_id": transaction_id, "challenge": challenge, "seed": seed}
        )

        os.kill(pid, signal.CTRL_BREAK_EVENT) # SIGCHLD unix

    def mine(self, transaction_id, challenge):
        # multiprocess
        self.jobs = []

        for i in range(JOBS_SIZE):
            p = Process(
                target=Node.search,
                args=(transaction_id, challenge, self.pid, self.conn_send, self.speed),
                daemon=True,
            )
            self.jobs.append(p)
            p.start()

    def handler(self, signum, frame):
        r = self.conn_receive.recv()
        transaction_id, challenge, seed = r["transaction_id"], r["challenge"], r["seed"]

        # print(f"found {seed} for challenge {challenge}")
        data = {
            "id": self.id,
            "transaction_id": transaction_id,
            "seed": seed,
        }
        self.channel.basic_publish(
            exchange="submit",
            routing_key="",
            body=json.dumps(data),
            properties=pika.BasicProperties(delivery_mode=2),
        )

        self.state = 5

        # terminate jobs
        for i in range(len(self.jobs)):
            try:
                process = self.jobs[i]
                process.terminate()
            except:
                pass
        self.jobs = []

    def verify(self, node_id, transaction_id, seed):
        if node_id == id:
            return True

        chalenge = self.challenge_table[transaction_id]["challenge"]
        chalenge_str = CHALENGE_MAP[chalenge]
        hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))
        if hash_object.startswith(chalenge_str):
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
        print("Interrupted!")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
