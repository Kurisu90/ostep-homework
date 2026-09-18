#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "common_zh.h"
#include "common_threads_zh.h"

#include "main-header_zh.h"
#include "vector-header_zh.h"

int retry = 0;

void vector_add(vector_t *v_dst, vector_t *v_src) {
  top:
    if (pthread_mutex_trylock(&v_dst->lock) != 0) {
	goto top;
    }
    if (pthread_mutex_trylock(&v_src->lock) != 0) {
	retry++;
	Pthread_mutex_unlock(&v_dst->lock);
	goto top;
    }
    int i;
    for (i = 0; i < VECTOR_SIZE; i++) {
	v_dst->values[i] = v_dst->values[i] + v_src->values[i];
    }
    Pthread_mutex_unlock(&v_dst->lock);
    Pthread_mutex_unlock(&v_src->lock);
}

void fini() {
    printf("重試次數: %d\n", retry);
}

#include "main-common_zh.c"
