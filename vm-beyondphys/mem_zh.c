#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/time.h>

// 簡單的函式,用來回傳絕對時間(單位為秒)。
double Time_GetSeconds() {
    struct timeval t;
    int rc = gettimeofday(&t, NULL);
    assert(rc == 0);
    return (double) ((double)t.tv_sec + (double)t.tv_usec / 1e6);
}

// 這個程式會配置一個指定大小的整數陣列,
// 然後在迴圈中不斷更新陣列裡的每一個整數,永不停止。
int main(int argc, char *argv[]) {
    if (argc != 2) {
	fprintf(stderr, "用法: spin <記憶體大小 (MB)>\n");
	exit(1);
    }
    long long int size = (long long int) atoi(argv[1]);
    long long int size_in_bytes = size * 1024 * 1024;

    printf("配置 %lld 個位元組 (%.2f MB)\n",
	   size_in_bytes, size_in_bytes / (1024 * 1024.0));

    // 這裡進行大量的記憶體配置
    int *x = malloc(size_in_bytes);
    if (x == NULL) {
	fprintf(stderr, "記憶體配置失敗\n");
	exit(1);
    }

    long long int num_ints = size_in_bytes / sizeof(int);
    printf("  陣列中的整數個數: %lld\n", num_ints);

    // 現在進入主要迴圈:每次經過都會存取每一個整數
    // (並將它的值加一)。
    long long int i = 0;
    double time_since_last_print = 2.0;
    double t = Time_GetSeconds();
    int loop_count = 0;
    while (1) {
	x[i++] += 1; // 迴圈的主要工作在這裡完成。

	// 如果已經跑完整個陣列,就重設一些狀態,
	// 然後(視情況)印出一些統計資訊。
	if (i == num_ints) {
	    double delta_time = Time_GetSeconds() - t;
	    time_since_last_print += delta_time;
	    if (time_since_last_print >= 0.2) { // 每 0.2 秒才印一次
		printf("第 %d 輪耗時 %.2f 毫秒 (頻寬: %.2f MB/s)\n",
		       loop_count, 1000 * delta_time,
		       size_in_bytes / (1024.0*1024.0*delta_time));
		time_since_last_print = 0;
	    }

	    i = 0;
	    t = Time_GetSeconds();
	    loop_count++;
	}
    }

    return 0;
}

