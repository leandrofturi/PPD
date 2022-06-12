import pika, sys, os
import json
import uuid
import hashlib
import concurrent.futures

POLL_SIZE = 4
CLIENTID = 42
CHALENGE_MAP = {d: bin(int("".join(map(str, [1] * d)), 2)) for d in range(1, 128)}


def mine(chalenge_str):
    seed = str(uuid.uuid4())
    hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))
    while not hash_object.startswith(chalenge_str):  # equals to one
        seed = str(uuid.uuid4())
        hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))
    return seed


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/seed")
    channel.queue_declare(queue="ppd/challenge")

    executor = None

    def callback(ch, method, properties, body):
        print(f"Consuming from challenge {body.decode('utf-8')}")

        # transactionID, chalenge = body.decode("utf-8").split("/")
        # transactionID, chalenge = int(transactionID), int(chalenge)
        resp = json.loads(body.decode("utf-8"))
        transactionID, chalenge = resp["transactionID"], resp["chalenge"]

        chalenge_str = CHALENGE_MAP[chalenge]

        executor = concurrent.futures.ThreadPoolExecutor()
        future_tasks = {
            executor.submit(mine, chalenge_str): i for i in range(POLL_SIZE)
        }
        for future in concurrent.futures.as_completed(future_tasks):
            i = future_tasks[future]
            try:
                seed = future.result()
                print(f"Publishing in seed {CLIENTID}/{transactionID}/{seed}")
                data = {
                    "clientID": CLIENTID,
                    "transactionID": transactionID,
                    "seed": seed,
                }
                obj = json.dumps(data)
                channel.basic_publish(
                    exchange="",
                    routing_key="ppd/seed",
                    body=obj,
                )

            except Exception as exc:
                raise Exception("%r generated an exception: %s" % (i, exc))

    def callback_result(ch, method, properties, body):
        print(f"Consuming from result {body.decode('utf-8')}")

        resp = json.loads(body.decode("utf-8"))
        transactionID, clientID, seed = (
            resp["transactionID"],
            resp["clientID"],
            resp["seed"],
        )
        # transactionID, clientID, seed = body.decode("utf-8").split("/")
        # transactionID, clientID = int(transactionID), int(clientID)

        # stop threads
        if executor:
            try:
                executor.shutdown(wait=False)
            except Exception as exc:
                print("Not able to shutdown")
                print(exc)

        if clientID != CLIENTID:
            print(f"Another solved! {clientID}")

    channel.basic_consume(
        queue="ppd/challenge", on_message_callback=callback, auto_ack=True
    )
    channel.basic_consume(
        queue="ppd/result", on_message_callback=callback_result, auto_ack=True
    )
    channel.start_consuming()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
