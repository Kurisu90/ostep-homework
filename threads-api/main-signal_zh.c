#include <stdio.h>

#include "common_threads_zh.h"

int done = 0;

void* worker(void* arg) {
    printf("這應該先印出來\n");
    done = 1;
    return NULL;
}

int main(int argc, char *argv[]) {
    pthread_t p;
    Pthread_create(&p, NULL, worker, NULL);
    while (done == 0)
	;
    printf("這應該最後印出來\n");
    return 0;
}
