import hashlib
import random
from xmlrpc.server import SimpleXMLRPCServer

SIZE = 2

# [TransactionID, Challenge, Seed, Winner]
CHALENGE_TABLE = [[0, ''.join(random.SystemRandom().choice('0123456789abcdef') for _ in range(SIZE)), None, -1]]


def getTransactionID():
    row = CHALENGE_TABLE[-1]
    if row[3] < 0:
        return row[0]
    CHALENGE_TABLE.append([row[0] + 1, ''.join(random.SystemRandom().choice('0123456789abcdef') for _ in range(SIZE)), None, -1])
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


def submitChallenge(transactionID, ClientID, seed):
    print(ClientID)
    if transactionID < len(CHALENGE_TABLE):
        chalenge = CHALENGE_TABLE[transactionID][1]
        hash_object = hashlib.sha1(seed.encode('UTF-8')).hexdigest()
        if hash_object.startswith(chalenge):
            CHALENGE_TABLE[transactionID][3] = ClientID
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
        return (CHALENGE_TABLE[transactionID][3], CHALENGE_TABLE[transactionID][2], CHALENGE_TABLE[transactionID][1])
    return (-1, '-1', '-1')


server = SimpleXMLRPCServer(("127.0.0.1", 8000))
print("Listening on port 8000...")
server.register_multicall_functions()
server.register_function(getTransactionID, "getTransactionID")
server.register_function(getChallenge, "getChallenge")
server.register_function(getTransactionStatus, "getTransactionStatus")
server.register_function(submitChallenge, "submitChallenge")
server.register_function(getWinner, "getWinner")
server.register_function(getSeed, "getSeed")
server.serve_forever()
