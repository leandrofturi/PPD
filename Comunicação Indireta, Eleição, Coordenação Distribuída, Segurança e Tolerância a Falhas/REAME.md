# Laboratório VI – Comunicação Indireta, Eleição, Coordenação Distribuída, Segurança e Tolerância a Falhas (Trabalho Final)

Leandro Furlam, Isauflânia Ribeiro, Allan Fermao

[Video (16/07/2022)](https://drive.google.com/file/d/1vzsqXTEsMnqs4J2i_-FyfzS4k-6xFLT3/view?usp=sharing)

## Identificador

Gerado com [UUID](https://en.wikipedia.org/wiki/Universally_unique_identifier). Quando gerados de acordo com os métodos padrão, os UUIDs são, para fins práticos, únicos. Sua singularidade não depende de uma autoridade central de registro ou coordenação entre as partes que as geram, ao contrário da maioria dos outros esquemas de numeração. Embora a probabilidade de um UUID ser duplicado não seja zero, é perto o suficiente de zero para ser insignificante. Devido a especificação, **foi convertido para inteiro de 32 bits**, [mantendo os conceitos](https://stackoverflow.com/questions/3530294/how-to-generate-unique-64-bits-integers-from-python).


## Troca de mensagens

Via Fanout Exchange: a mensagem recebida é encaminhada para todas as filas que estão vinculadas à troca.

<img src="https://www.cloudamqp.com/img/blog/fanout-exchange.png" alt="fanout" width="200px"/>

As trocas de fanout podem ser úteis quando a mesma mensagem precisa ser enviada para uma ou mais filas com consumidores que podem processar a mesma mensagem de maneiras diferentes.

| exchange | descrição | elementos |
|---|---|---|
| ppd/init | anúncio de entrada na rede | NodeId |
| ppd/pubkey | chave pública do nó | NodeId,PubKey |
| ppd/election | eleição do líder que gerará o desafio | NodeId,ElectionNumber |
| ppd/challenge | anúncio do desafio | NodeId,TransactionNumber, Challenge,Sign |
| ppd/submit | submissão do desafio | NodeId,TransactionNumber,Seed,Sign |
| ppd/voting | votação para a validade do desafio | NodeId, SolutionId,TransactionNumber,Seed,Vote,Sign |

onde:

* *NodeId*: identificador do nó ao qual está enviando a mensagem, gerado com uuid.
* *ElectionNumber*: número aleatório entre 0 e 1 para eleição do líder. O maior dos valores será o líder. Em caso de empate, o primeiro a enviar a mensagem.
* *TransactionNumber*: identificador da rodada, iniciando em 0.
* *Challenge*: desafio. Inteiro representando a quantidade de bits mais significativos que o hash deverá se igualar.
* *Seed*: string encontrada que solucione o desafio gerado.
* *SolutionId*: identificador do dono da solução submetida.
* *Sign*: assinatura da informação apresentada, conforme descrito na especificação estendida do trabalho.

Um mesmo callback para o recebimento de todas as exchanges é utilizado, sendo encaminhado para os devidos fins de acordo com os itens presentes na mensagem.

Todas as mensagens são enviadas via json serializado.

## Inicialização

Para entrar na rede, basta submeter o identificador na exchange *ppd/init*. Cada nó, ao perceber a entrada de um novo integrante, também volta a anunciar o próprio identificador, para que os novos nós consigam visualizar os nós antigos.

## Troca de Chaves

Após todos estarem na rede, é realizada a troca de chaves públicas de cada nó, na exchange *ppd/pubkey*, sendo salvas em um dicionário no próprio nó. Como os testes são realizados na mesma máquina, salvamos (apenas para segurança) as chaves públicas a privadas na pasta `keys`, com a nomenclatura `{id}-private/public.key"`. No caso da execução as chaves são armazenadas em memória.

A não ser nas exchanges *ppd/init* e *ppd/pubkey*, todas as demais possuem mensagem assinadas pelo autor (`NodeId`). Logo, sempre é realizada a verificação da veracidade da informação, (1) obtendo a respectiva chave já armazenada em memória, (2) destacando-se à mensagem original do conjunto recebido, (3) verificando a veracidade da mensagem.

## Eleição e Geração do desafio

A eleição do líder se dá através da exchange *ppd/election*, onde cada um enviará um número aleatório (inicialmente entre 0 e 1 - confiamos nos integrantes). O dono do maior número é o líder, que gerará o desafio com um nível, aleatório para cada nó, entre `CHALLENGE_LEVEL_RANGE`, representando o desafio. Em seguida o desafio será publicado na *ppd/challenge*. Junto com o desafio é também enviado o identificador do líder, para conferência.

## Mineração

A geração da string aleatória deu-se através da técnica mais rápida encontrada, através da string hexadecimal gerada pelo comando `os.urandom(size)`, cujo `size` definido foi de 64. Para conversão utilizou-se a biblioteca `binascii`, que converte entre binário e ASCII, através do comando `binascii.hexlify(os.urandom(SEED_SIZE))`

Com o desafio recebido - todos devem obter o desafio da fila de mensagens, e não da própria geração local - inicia-se a mineração. A mineração se dá em `JOBS_SIZE` subprocessos, objetivando aproveitar os núcleos de processamento. Veja que os subprocessos funcionam como ''zombies´´, pois o programa não permanece no mesmo estado aguardando suas respostas.

Utilizamos `Process`, do pacote `multiprocessing`, e `Pipe`s para comunicação (envio da solução encontrada) entre o processo principal e os zombies mineradores. Para avisar ao processo principal um  dos filhos finalizaram, utilizou-se sinais (pacote `signal`). O processo filho ao finalizar envia um `SIGBREAK` (win32) ou `SIGCHLD` (unix), cujo handler definido no pai é (1) enviar a solução na exchenge *ppd/submit*, e (2) finalizar todos os processos filhos. Em outros sistemas basta alterar o sinal.

Nesse meio tempo o processo pai pode receber uma mensagem contendo a solução de algum outro processo. Caso isso ocorra, ele verifica se (1) o desafio encontra-se em aberto e (2) se a solução está correta. Estando correta, ele verifica se a quantidade de votos que os demais nós da rede enviaram (via exchange *ppd/voting*) é maioria dentre os integrantes. Sendo maioria, ele para de minerar, se ainda estiver minerando, e atualiza a tabela de desafios. Enfatizamos que ele só pára se a solução estiver correta, se estiver errada ele continua, na tentativa de ser o vencedor.

Em seguida, retorna à etapa de eleição.


## Execução do código

`python .\node.py`