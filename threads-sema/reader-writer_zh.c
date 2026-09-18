#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "common_threads_zh.h"

//
// 你的程式碼要寫在下面的結構與函式當中
//

typedef struct __rwlock_t {
} rwlock_t;


void rwlock_init(rwlock_t *rw) {
}

void rwlock_acquire_readlock(rwlock_t *rw) {
}

void rwlock_release_readlock(rwlock_t *rw) {
}

void rwlock_acquire_writelock(rwlock_t *rw) {
}

void rwlock_release_writelock(rwlock_t *rw) {
}

//
// 以下的程式碼不要更動（直接使用就好！）
//

int loops;
int value = 0;

rwlock_t lock;

void *reader(void *arg) {
    int i;
    for (i = 0; i < loops; i++) {
	rwlock_acquire_readlock(&lock);
	printf("讀取 %d\n", value);
	rwlock_release_readlock(&lock);
    }
    return NULL;
}

void *writer(void *arg) {
    int i;
    for (i = 0; i < loops; i++) {
	rwlock_acquire_writelock(&lock);
	value++;
	printf("寫入 %d\n", value);
	rwlock_release_writelock(&lock);
    }
    return NULL;
}

int main(int argc, char *argv[]) {
    assert(argc == 4);
    int num_readers = atoi(argv[1]);
    int num_writers = atoi(argv[2]);
    loops = atoi(argv[3]);

    pthread_t pr[num_readers], pw[num_writers];

    rwlock_init(&lock);

    printf("開始\n");

    int i;
    for (i = 0; i < num_readers; i++)
	Pthread_create(&pr[i], NULL, reader, NULL);
    for (i = 0; i < num_writers; i++)
	Pthread_create(&pw[i], NULL, writer, NULL);

    for (i = 0; i < num_readers; i++)
	Pthread_join(pr[i], NULL);
    for (i = 0; i < num_writers; i++)
	Pthread_join(pw[i], NULL);

    printf("結束：數值為 %d\n", value);

    return 0;
}

