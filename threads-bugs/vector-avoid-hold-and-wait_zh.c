#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <unistd.h>

#include "common_zh.h"
#include "common_threads_zh.h"

#include "main-header_zh.h"
#include "vector-header_zh.h"

// 用這個鎖確保「取得鎖」這個動作本身是原子性（ATOMIC）的
pthread_mutex_t global = PTHREAD_MUTEX_INITIALIZER;

void vector_add(vector_t *v_dst, vector_t *v_src) {
    // 在所有取得鎖的動作外層，包上一個全域鎖……
    Pthread_mutex_lock(&global);
    Pthread_mutex_lock(&v_dst->lock);
    Pthread_mutex_lock(&v_src->lock);
    Pthread_mutex_unlock(&global);
    int i;
    for (i = 0; i < VECTOR_SIZE; i++) {
	v_dst->values[i] = v_dst->values[i] + v_src->values[i];
    }
    Pthread_mutex_unlock(&v_dst->lock);
    Pthread_mutex_unlock(&v_src->lock);
}

void fini() {}

#include "main-common_zh.c"

