# Chamada de Processamento Remoto

@leandrofturi, @IsaRibeirot, @allanfermao


| Método                 | Parâmetro                                 | Significado                                                                                                                                                                                                                                              |
|------------------------|-------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| getTransactionID()     |                                           | Retorna o valor atual <int> da transação com desafio ainda pendente de solução.                                                                                                                                                                          |
| getChallenge()         | int transactionID                         | Se a transactionID for válido, retorne o valor do desafio associado a ele. Retorne -1 se p transactionID for válido.                                                                                                                                     |
| getTransactionStatus() | int transactionID                         | Se transactionID for válido, retorne 0 se o desafio associado a essa transação já foi resolvido, retorne 1 caso a transação ainda possua desafio pendente. Retorne -1 se a transactionID for inválida.                                                   |
| submitChallenge()      | int transactionID, int ClientID, int seed | Submete uma semente (seed) para o hashing SHA-1 que resolve o desafio proposto para a referida transactionID. Retorne 1 se a seed para o desafio for válido, 0 se for inválido, 2 se o desafio já foi solucionado, e -1 se a transactionID for inválida. |
| getWinner()            | int transactionID                         | Retorna o clientID do vencedor da transação transactionID. Retorne 0 se a transactionID ainda não tem vencedor e -1 se a transactionID for inválida.                                                                                                     |
| getSeed()              | int transactionID                         | Retorna uma estrutura de dados (ou uma tupla) com o status, a seed e o desafio associado à transactionID.                                                                                                                                                |

## C
Para rodar o programa na linguagem C, é  necessária a biblioteca **openssl**, que no Ubuntu, pode ser instalada com a seguinte linha de comando:

`sudo apt-get install openssl`

A inclusão da biblioteca e as flags necessárias para rodar o programa já estão incluídas no código e no Makefile. Uma vez antentido esse requisito, basta rodar o comando `make` para gerar os arquivos necessários. Em seguida, basta dois comandos em terminais distintos para rodar o programa.
No servidor:
`./c/crypto_server`

No cliente:
`./c/crypto_client localhost`


## Python

No servidor
`python .\py\rpc_server.py`

No Cliente
`python .\py\rpc_client.py 127.0.0.1 8000`
