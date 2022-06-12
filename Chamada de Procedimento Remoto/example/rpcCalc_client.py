import xmlrpc.client
import sys
 
# Calcula total de argumentos
n = len(sys.argv)
 
# Verificação do uso correto/argumentos
if (n!=5):
    print("\nUso correto: rpcCalc_client server_address port_number.\n")
    exit(-1)

#print("\nArguments passed:", end = " ")
#for i in range(1, n):
#    print(sys.argv[i], end = " ")

rpcServerAddr = "http://" + sys.argv[1] + ":" + sys.argv[2] + "/"
proxy = xmlrpc.client.ServerProxy(rpcServerAddr)

#multicall = xmlrpc.client.MultiCall(proxy)
#multicall.add(7, 3)
#multicall.subtract(7, 3)
#multicall.multiply(7, 3)
#multicall.divide(7, 3)
#result = multicall()

soma = proxy.add(int(sys.argv[3]), int(sys.argv[4]))
print("%s+%s=%s" % (sys.argv[3], sys.argv[4], soma))

sub = proxy.subtract(int(sys.argv[3]), int(sys.argv[4]))
print("%s-%s=%d" % (sys.argv[3], sys.argv[4], sub))