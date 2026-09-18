#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <assert.h>
#include <pthread.h>
#include <sys/time.h>
#include <string.h>

#include "common_zh.h"
#include "common_threads_zh.h"
#include "pc-header_zh.h"

pthread_cond_t empty  = PTHREAD_COND_INITIALIZER;
pthread_cond_t fill   = PTHREAD_COND_INITIALIZER;
pthread_mutex_t m     = PTHREAD_MUTEX_INITIALIZER;

#include "main-header_zh.h"

void do_fill(int value) {
    // 使用前先確認是空的
    ensure(buffer[fill_ptr] == EMPTY, "錯誤：試圖填入一個非空的緩衝區");
    buffer[fill_ptr] = value;
    fill_ptr = (fill_ptr + 1) % max;
    num_full++;
}

int do_get() {
    int tmp = buffer[use_ptr];
    ensure(tmp != EMPTY, "錯誤：試圖從空的緩衝區取值");
    buffer[use_ptr] = EMPTY;
    use_ptr = (use_ptr + 1) % max;
    num_full--;
    return tmp;
}

void *producer(void *arg) {
    int id = (int) arg;
    // 確保每個生產者產生的數值都是唯一的
    int base = id * loops;
    int i;
    for (i = 0; i < loops; i++) {   p0;
	Mutex_lock(&m);             p1;
	if (num_full == max) {      p2;
	    Cond_wait(&empty, &m);  p3;
	}
	do_fill(base + i);          p4;
	Cond_signal(&fill);         p5;
	Mutex_unlock(&m);           p6;
    }
    return NULL;
}

void *consumer(void *arg) {
    int id = (int) arg;
    int tmp = 0;
    int consumed_count = 0;
    while (tmp != END_OF_STREAM) { c0;
	Mutex_lock(&m);            c1;
	if (num_full == 0) {       c2;
	    Cond_wait(&fill, &m);  c3;
        }
	tmp = do_get();            c4;
	Cond_signal(&empty);       c5;
	Mutex_unlock(&m);          c6;
	consumed_count++;
    }

    // 回傳 consumed_count-1，因為 END_OF_STREAM 不計入
    return (void *) (long long) (consumed_count - 1);
}

// 若要使用 "main-common_zh.c"，必須適當地設定以下這些
pthread_cond_t *fill_cv = &fill;
pthread_cond_t *empty_cv = &empty;

// 所有版本都共用這份程式碼來啟動生產者/消費者
// 以及其他相關的處理
#include "main-common_zh.c"

