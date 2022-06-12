struct submit {
    int transactionID;
    int ClientID;
    int seed;
};

program PROG{
    version VERSAO{
        int getTransactionID() = 1;

        int getChallenge(int transactionID) = 2;

        int getTransactionStatus(int transactionID) = 3;

        int submitChallenge(submit) = 4;

        int getWinner(int transactionID) = 5;

        int getSeed(int transactionID) = 6;

        void Minerar() = 7;
    } = 100;
} = 11111111;