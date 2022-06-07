import xmlrpc.client
import sys
import string
import random
import hashlib
import threading
import queue

# Calcula total de argumentos
n = len(sys.argv)
 
# Verificação do uso correto/argumentos
if (n!=3):
    print("\nUso correto: rpcCalc_client server_address port_number.\n")
    exit(-1)

rpcServerAddr = "http://" + sys.argv[1] + ":" + sys.argv[2] + "/"
proxy = xmlrpc.client.ServerProxy(rpcServerAddr)

SIZE = 2
ClientID = 42


def minerar(chalenge, i, q):
    print(f"starting {i}")
    seed = ''.join(random.SystemRandom().choice('0123456789abcdef') for _ in range(SIZE))
    hash_object = hashlib.sha1(seed.encode('UTF-8')).hexdigest()
    while not hash_object.startswith(chalenge):
        seed = ''.join(random.SystemRandom().choice('0123456789abcdef') for _ in range(SIZE))
        hash_object = hashlib.sha1(seed.encode('UTF-8')).hexdigest()

    r = proxy.submitChallenge(transactionID, ClientID, seed)

    print(f"{i} finished {seed} | {chalenge} | {hash_object}")
    q.put((i, seed, chalenge, hash_object))
    return r

while True:
    print("""
    1- getTransactionID
    2- getChallenge
    3- getTransactionStatus
    4- getWinner
    5- getSeed
    6- Minerar
    """)
    x = str(input())

    if x == '1':
        transactionID = proxy.getTransactionID()
        print(transactionID)

    elif x == '2':
        transactionID = input()
        chalenge = proxy.getChallenge(transactionID)
        print(chalenge)
        
    elif x == '3':
        transactionID = input()
        status = proxy.getTransactionStatus(transactionID)
        print(status)
        
    elif x == '4':
        transactionID = input()
        winner = proxy.getWinner(transactionID)
        print(winner)
        
    elif x == '5':
        transactionID = input()
        seed = getSeed(transactionID)
        print(seed[1])
        
    elif x == '6':
        transactionID = proxy.getTransactionID()
        status = proxy.getTransactionStatus(transactionID)
        chalenge = proxy.getChallenge(transactionID)
            
        q = queue.Queue()
        threads = [ threading.Thread(target=minerar, args=(chalenge, i, q)) for i in range(8) ]
        for th in threads:
            th.daemon = True
            th.start()

        result = q.get()

        print("Second result: {}".format(result))