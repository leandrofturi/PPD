# Comunicação Indireta

@leandrofturi, @IsaRibeirot, @allanfermao

Dando continuidade a nosso minerador tipo bitcoin, desta vez utilizando o broker RabbitMQ para gerenciamento da fila de mensagens.

Para geração da seed utilizou-se a biblioteca uuid e para o paralelismo, concurrent.futures.

Acerca do formato das codificações entre as mensagens, utilizou-se o formato json, com a codificação/decodificação json <> bytes com o auxílio da biblioteca json.

## Python

No servidor
`python .\rabbitsub.py`

No Cliente
`python .\rabbitpub.py`
