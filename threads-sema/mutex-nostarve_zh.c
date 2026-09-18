#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include "common_threads_zh.h"

//
// 這裡幾乎所有的程式碼都要由你自己完成。噢不！
// 你要如何證明，當某個執行緒嘗試取得你所建構的這個互斥鎖時，
// 它不會發生飢餓（starve）呢？
//

typedef __ns_mutex_t {
} ns_mutex_t;

void ns_mutex_init(ns_mutex_t *m) {
}

void ns_mutex_acquire(ns_mutex_t *m) {
}

void ns_mutex_release(ns_mutex_t *m) {
}


void *worker(void *arg) {
    return NULL;
}

int main(int argc, char *argv[]) {
    printf("父執行緒：開始\n");
    printf("父執行緒：結束\n");
    return 0;
}

