#include <stdio.h>

#include "common_threads_zh.h"

int balance = 0;

void* worker(void* arg) {
    balance++; // 未受保護的存取
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t p;
    Pthread_create(&p, NULL, worker, NULL);
    balance++; // 未受保護的存取
    Pthread_join(p, NULL);
    return 0;
}
