# Laboratório IV – Comunicação Indireta, Eleição e Coordenação Distribuída

Leandro Furlam, Isauflânia Ribeiro, Allan Fermao

## Identificador

Gerado com [UUID](https://en.wikipedia.org/wiki/Universally_unique_identifier). Quando gerados de acordo com os métodos padrão, os UUIDs são, para fins práticos, únicos. Sua singularidade não depende de uma autoridade central de registro ou coordenação entre as partes que as geram, ao contrário da maioria dos outros esquemas de numeração. Embora a probabilidade de um UUID ser duplicado não seja zero, é perto o suficiente de zero para ser insignificante. Para fins de implementação, foi convertido para inteiro, [mantendo os conceitos](https://stackoverflow.com/questions/3530294/how-to-generate-unique-64-bits-integers-from-python).


## Troca de mensagens

Via Fanout Exchange: a mensagem recebida é encaminhada para todas as filas que estão vinculadas à troca.

<img src="https://www.cloudamqp.com/img/blog/fanout-exchange.png" alt="fanout" width="200px"/>

As trocas de fanout podem ser úteis quando a mesma mensagem precisa ser enviada para uma ou mais filas com consumidores que podem processar a mesma mensagem de maneiras diferentes.

| exchange | descrição | elementos |
|---|---|---|
| entrance | anúncio de entrada na rede | id |
| election | eleição do líder que gerará o desafio | id, ticket |
| challenge | anúncio do desafio | id,transaction_id, challenge |
| submit | submissão do desafio | id, transaction_id, seed |
| ballotbox | votação para a validade do desafio | id, node_id, transaction_id, seed |

onde:

* *id*: identificador do nó ao qual está enviando a mensagem, gerado com uuid.
* *ticket*: número aleatório entre 0 e 1 para eleição do líder. O maior dos valores será o líder. Em caso de empate, o primeiro a enviar a mensagem.
* *transaction_id*: identificador da rodada, iniciando em 0.
* *challenge*: desafio. Inteiro representando a quantidade de bits mais significativos que o hash deverá se igualar.
* *seed*: string encontrada que solucione o desafio gerado.
* *node_id*: identificador do dono da solução submetida.

Um mesmo callback para o recebimento de todas as exchanges é utilizado, sendo encaminhado para os devidos fins de acordo com os itens presentes na mensagem.

todas as mensagens são enviadas via json serializado.

## Inicialização

Para entrar na rede, basta submeter o identificador na exchange *entrance*. Cada nó, ao perceber a entrada de um novo integrante, também volta a anunciar o próprio identificador, para que os novos nós consigam visualizar os nós antigos.

## Eleição e Geração do desafio

A eleição do líder se dá através da exchange *election*, onde cada um enviará um número aleatório (inicialmente entre 0 e 1 - confiamos nos integrantes). O dono do maior número é o líder, que gerará o desafio com um nível `CHALLENGE_LEVEL`, aleatório para cada nó, entre 5 e 9, representando o desafio. Em seguida o desafio será publicado na *challenge*. Junto com o desafio é também enviado o identificador do líder, para conferência.

## Mineração

Com o desafio recebido - todos devem obter o desafio da fila de mensagens, e não da própria geração local - inicia-se a mineração. A mineração se dá em `JOBS_SIZE` subprocessos, objetivando aproveitar os núcleos de processamento. Veja que os subprocessos funcionam como ''zombies´´, pois o programa não permanece no mesmo estado aguardando suas respostas.

Utilizamos `Process`, do pacote `multiprocessing`, e `Pipe`s para comunicação (envio da solução encontrada) entre o processo principal e os zombies mineradores. Para avisar ao processo principal um  dos filhos finalizaram, utilizou-se sinais (pacote `signal`). Como construímos no windows, o processo filho ao finalizar envia um `CTRL_BREAK_EVENT` (`SIGBREAK`), cujo handler definido no pai é (1) enviar a solução na exchenge *submit*, e (2) finalizar todos os processos filhos. Em outros sistemas basta alterar o sinal.

Nesse meio tempo o processo pai pode receber uma mensagem contendo a solução de algum outro processo. Caso isso ocorra, ele verifica se (1) o desafio encontra-se em aberto e (2) se a solução está correta. Estando correta, ele verifica se a quantidade de votos que os demais nós da rede enviaram (via exchange *ballotbox*) é maioria dentre os integrantes. Sendo maioria, ele para de minerar, se ainda estiver minerando, e atualiza a tabela de desafios. Enfatizamos que ele só pára se a solução estiver correta, se estiver errada ele continua, na tentativa de ser o vencedor.

Em seguida, retorna à etapa de eleição.