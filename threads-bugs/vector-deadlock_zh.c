#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "common_zh.h"
#include "common_threads_zh.h"

#include "main-header_zh.h"
#include "vector-header_zh.h"

void vector_add(vector_t *v_dst, vector_t *v_src) {
    Pthread_mutex_lock(&v_dst->lock);
    Pthread_mutex_lock(&v_src->lock);
    int i;
    for (i = 0; i < VECTOR_SIZE; i++) {
	v_dst->values[i] = v_dst->values[i] + v_src->values[i];
    }
    Pthread_mutex_unlock(&v_dst->lock);
    Pthread_mutex_unlock(&v_src->lock);
}

void fini() {}

#include "main-common_zh.c"
