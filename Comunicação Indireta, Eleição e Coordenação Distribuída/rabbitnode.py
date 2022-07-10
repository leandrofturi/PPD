import sys, os, time, json
import uuid
import pika
import random

from threading import Thread


N = 2
SLEEP = 0

CHALENGE_MAP = {d: bin(int("".join(map(str, [1] * d)), 2)) for d in range(1, 128)}

CHALENGE = 8  # 1 to 128
CHALENGE_TABLE = [[0, CHALENGE, None, -1]]

id = str(
    uuid.uuid4()
)  # 128-bit label. while the probability that a UUID will be duplicated is not zero, it is close enough to zero to be negligible
print(id)
participants = set()
electors = {}
threads = {}


def init_send():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/entrance")

    while len(participants) < N:
        channel.basic_publish(
            exchange="", routing_key="ppd/entrance", body=json.dumps({"id": id})
        )
        time.sleep(SLEEP)
    return


def init_listen():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/entrance")

    def callback(ch, method, properties, body):
        r = json.loads(body.decode("utf-8"))
        if r["id"] in participants:
            channel.basic_publish(exchange="", routing_key="ppd/entrance", body=body)

        participants.add(r["id"])
        print(f"{r['id']} inside chain! {len(participants)} participants.")

        if len(participants) >= N:
            print(f"STARTED!")

            threads["election_listen"] = Thread(target=election_listen)
            threads["election_listen"].start()

            threads["election_send"] = Thread(target=election_send)
            threads["election_send"].start()

            channel.stop_consuming()

    channel.basic_consume(
        queue="ppd/entrance", on_message_callback=callback, auto_ack=True
    )
    channel.start_consuming()


def election_send():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/election")

    ticket = random.random()
    electors[id] = ticket

    while len(electors) < N:
        channel.basic_publish(
            exchange="",
            routing_key="ppd/election",
            body=json.dumps({"id": id, "ticket": ticket}),
        )
        time.sleep(SLEEP)
    return


def election_listen():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/election")

    def callback(ch, method, properties, body):
        r = json.loads(body.decode("utf-8"))
        if r["id"] in electors.keys():
            channel.basic_publish(exchange="", routing_key="ppd/election", body=body)

        if r["id"] not in participants:
            print(f"Invalid id {r['id']}")
            return

        electors[r["id"]] = r["ticket"]

        if len(electors) >= N:
            leader = max(electors, key=electors.get)
            print(f"Leader is {leader}")

            channel.stop_consuming()

    channel.basic_consume(
        queue="ppd/election", on_message_callback=callback, auto_ack=True
    )
    channel.start_consuming()


def main():
    threads["init_listen"] = Thread(target=init_listen)
    threads["init_listen"].start()

    threads["init_send"] = Thread(target=init_send)
    threads["init_send"].start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted!")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
