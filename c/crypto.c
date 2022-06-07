#include <stdio.h>
#include <stdlib.h>

int getTransactionID(){
    // return transaction atual ainda não resolvido
}

int getChallenge(int transactionID){
    // se existe, retorna challenge
    // senão, retorna -1
}

int getTransactionStatus(int transactionID){
    // 0 se já resolvido
    // 1 se aberto
    // -1 se inválido
}

int submitChallenge(int transactionID, int ClientID, int seed){
    // 1 se resolve
    // 0 se não resolve
    // 2 se já resolvido
    // -1 se inválido
}

int getWinner(int transactionID){
    // ClientID
    // 0 se não possui
    // -1 se inválido
}

void Minerar(){

}

int main(int argc, char* argv[]){

}