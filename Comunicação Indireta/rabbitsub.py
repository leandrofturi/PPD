import pika, sys, os
import json
import hashlib
from pprint import pprint

CHALENGE = 8  # 1 to 128
CHALENGE_MAP = {d: bin(int("".join(map(str, [1] * d)), 2)) for d in range(1, 128)}

# [TransactionID, Challenge, Seed, Winner]
CHALENGE_TABLE = [[0, CHALENGE, None, -1]]


def getTransactionID():
    row = CHALENGE_TABLE[-1]
    if row[3] < 0:
        return row[0]
    CHALENGE_TABLE.append([row[0] + 1, CHALENGE, None, -1])
    pprint(CHALENGE_TABLE)
    return CHALENGE_TABLE[-1][0]


def getChallenge(transactionID):
    if transactionID < len(CHALENGE_TABLE):
        return CHALENGE_TABLE[transactionID][1]
    return -1


def getTransactionStatus(transactionID):
    if transactionID < len(CHALENGE_TABLE):
        value = CHALENGE_TABLE[transactionID][3]
        if value < 0:
            return 1
        else:
            return 0
    return -1


def submitChallenge(transactionID, clientID, seed):
    if transactionID < len(CHALENGE_TABLE):
        chalenge = CHALENGE_TABLE[transactionID][1]
        chalenge_str = CHALENGE_MAP[chalenge]

        hash_object = bin(int(hashlib.sha1(seed.encode("UTF-8")).hexdigest(), 16))

        if hash_object.startswith(chalenge_str):  # equals to one
            CHALENGE_TABLE[transactionID][2] = seed
            CHALENGE_TABLE[transactionID][3] = clientID
            pprint(CHALENGE_TABLE)
            return 1
        else:
            return 0
    return -1


def getWinner(transactionID):
    if transactionID < len(CHALENGE_TABLE):
        winner = CHALENGE_TABLE[transactionID][2]
        if winner:
            return winner
        else:
            return 0
    return -1


def getSeed(transactionID):
    if transactionID < len(CHALENGE_TABLE):
        return (
            CHALENGE_TABLE[transactionID][3],
            CHALENGE_TABLE[transactionID][2],
            CHALENGE_TABLE[transactionID][1],
        )
    return (-1, "-1", "-1")


def main():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host="localhost"))
    channel = connection.channel()

    channel.queue_declare(queue="ppd/seed")
    channel.queue_declare(queue="ppd/result")
    channel.queue_declare(queue="ppd/challenge")

    transactionID = getTransactionID()
    chalenge = getChallenge(transactionID)
    print(f"Publishing in challenge {transactionID}/{chalenge}")
    data = {
        "transactionID": transactionID,
        "chalenge": chalenge,
    }
    obj = json.dumps(data)

    channel.basic_publish(exchange="", routing_key="ppd/challenge", body=obj)

    def callback(ch, method, properties, body):
        print(f"Consuming from seed {body.decode('utf-8')}")

        resp = json.loads(body.decode("utf-8"))
        clientID, transactionID, seed = (
            resp["clientID"],
            resp["transactionID"],
            resp["seed"],
        )
        # clientID, transactionID, seed = body.decode("utf-8").split("/")
        # clientID, transactionID = int(clientID), int(transactionID)

        result = submitChallenge(transactionID, clientID, seed)
        print(result)
        if result == 1:
            print(f"Publishing in result {transactionID}/{clientID}/{seed}")
            data = {
                "transactionID": transactionID,
                "clientID": clientID,
                "seed": seed,
            }
            obj = json.dumps(data)

            channel.basic_publish(
                exchange="",
                routing_key="ppd/result",
                body=obj,
            )
        if result != -1:
            transactionID = getTransactionID()
            chalenge = getChallenge(transactionID)
            print(f"Publishing in challenge {transactionID}/{chalenge}")
            data = {
                "transactionID": transactionID,
                "chalenge": chalenge,
            }
            obj = json.dumps(data)

            channel.basic_publish(
                exchange="",
                routing_key="ppd/challenge",
                body=obj,
            )

    channel.basic_consume(queue="ppd/seed", on_message_callback=callback, auto_ack=True)

    # print("Waiting for messages. To exit press CTRL+C")
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
