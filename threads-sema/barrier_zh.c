#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include "common_threads_zh.h"

// 如果做得正確，每個子執行緒都應該先印出自己的「之前」訊息，
// 然後才會有任何一個子執行緒印出「之後」訊息。可以在不同位置
// 加入 sleep(1) 來測試這件事。

// 你很可能需要兩個號誌（semaphore）才能正確完成這件事，
// 另外還需要一些整數變數來追蹤狀態。

typedef struct __barrier_t {
    // 在這裡加入號誌與其他資訊
} barrier_t;


// 本程式使用的唯一一個屏障（barrier）
barrier_t b;

void barrier_init(barrier_t *b, int num_threads) {
    // 初始化程式碼寫在這裡
}

void barrier(barrier_t *b) {
    // 屏障的程式碼寫在這裡
}

//
// XXX：以下的程式碼不要更動（直接執行就好！）
//
typedef struct __tinfo_t {
    int thread_id;
} tinfo_t;

void *child(void *arg) {
    tinfo_t *t = (tinfo_t *) arg;
    printf("子執行緒 %d：之前\n", t->thread_id);
    barrier(&b);
    printf("子執行緒 %d：之後\n", t->thread_id);
    return NULL;
}


// 執行時請帶一個引數，代表你想要建立的執行緒數量（1 或以上）
int main(int argc, char *argv[]) {
    assert(argc == 2);
    int num_threads = atoi(argv[1]);
    assert(num_threads > 0);

    pthread_t p[num_threads];
    tinfo_t t[num_threads];

    printf("父執行緒：開始\n");
    barrier_init(&b, num_threads);

    int i;
    for (i = 0; i < num_threads; i++) {
	t[i].thread_id = i;
	Pthread_create(&p[i], NULL, child, &t[i]);
    }

    for (i = 0; i < num_threads; i++)
	Pthread_join(p[i], NULL);

    printf("父執行緒：結束\n");
    return 0;
}

