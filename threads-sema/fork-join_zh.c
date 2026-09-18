#include <stdio.h>
#include <unistd.h>
#include <pthread.h>
#include "common_threads_zh.h"

sem_t s;

void *child(void *arg) {
    printf("子執行緒\n");
    // 在這裡使用號誌（semaphore）
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t p;
    printf("父執行緒：開始\n");
    // 在這裡初始化號誌
    Pthread_create(&p, NULL, child, NULL);
    // 在這裡使用號誌
    printf("父執行緒：結束\n");
    return 0;
}

