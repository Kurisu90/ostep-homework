#include <stdio.h>
#include <unistd.h>
#include "common_threads_zh.h"

// 如果做得正確，每個子執行緒都應該先印出自己的「之前」訊息，
// 然後才會有任何一個子執行緒印出「之後」訊息。可以在不同位置
// 加入 sleep(1) 來測試這件事。

sem_t s1, s2;

void *child_1(void *arg) {
    printf("子執行緒 1：之前\n");
    // 這裡應該寫什麼？
    printf("子執行緒 1：之後\n");
    return NULL;
}

void *child_2(void *arg) {
    printf("子執行緒 2：之前\n");
    // 這裡應該寫什麼？
    printf("子執行緒 2：之後\n");
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t p1, p2;
    printf("父執行緒：開始\n");
    // 在這裡初始化號誌
    Pthread_create(&p1, NULL, child_1, NULL);
    Pthread_create(&p2, NULL, child_2, NULL);
    Pthread_join(p1, NULL);
    Pthread_join(p2, NULL);
    printf("父執行緒：結束\n");
    return 0;
}

