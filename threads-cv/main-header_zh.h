#ifndef __main_header_h__
#define __main_header_h__

// 以下內容都是為了作業所需

int do_trace = 0;
int do_timing = 0;

#define p0 do_pause(id, 1, 0, "p0");
#define p1 do_pause(id, 1, 1, "p1");
#define p2 do_pause(id, 1, 2, "p2");
#define p3 do_pause(id, 1, 3, "p3");
#define p4 do_pause(id, 1, 4, "p4");
#define p5 do_pause(id, 1, 5, "p5");
#define p6 do_pause(id, 1, 6, "p6");

#define c0 do_pause(id, 0, 0, "c0");
#define c1 do_pause(id, 0, 1, "c1");
#define c2 do_pause(id, 0, 2, "c2");
#define c3 do_pause(id, 0, 3, "c3");
#define c4 do_pause(id, 0, 4, "c4");
#define c5 do_pause(id, 0, 5, "c5");
#define c6 do_pause(id, 0, 6, "c6");

int producer_pause_times[MAX_THREADS][7];
int consumer_pause_times[MAX_THREADS][7];

// 需要這個鎖是為了避免多個執行緒的輸出彼此交錯
pthread_mutex_t print_lock = PTHREAD_MUTEX_INITIALIZER;

void do_print_headers() {
    if (do_trace == 0)
	return;
    int i;
    printf("%3s ", "NF");
    for (i = 0; i < max; i++) {
	printf(" %3s ", "   ");
    }
    printf("  ");

    for (i = 0; i < producers; i++)
	printf("P%d ", i);
    for (i = 0; i < consumers; i++)
	printf("C%d ", i);
    printf("\n");
}

void do_print_pointers(int index) {
    if (use_ptr == index && fill_ptr == index) {
	printf("*");
    } else if (use_ptr == index) {
	printf("u");
    } else if (fill_ptr == index) {
	printf("f");
    } else {
	printf(" ");
    }
}

void do_print_buffer() {
    int i;
    printf("%3d [", num_full);
    for (i = 0; i < max; i++) {
	do_print_pointers(i);
	if (buffer[i] == EMPTY) {
	    printf("%3s ", "---");
	} else if (buffer[i] == END_OF_STREAM) {
	    printf("%3s ", "EOS");
	} else {
	    printf("%3d ", buffer[i]);
	}
    }
    printf("] ");
}

void do_eos() {
    if (do_trace) {
	Mutex_lock(&print_lock);
	do_print_buffer();
	//printf("%3d [已加入串流結束標記]\n", num_full);
	printf("[main: 已加入串流結束標記]\n");
	Mutex_unlock(&print_lock);
    }
}

void do_pause(int thread_id, int is_producer, int pause_slot, char *str) {
    int i;
    if (do_trace) {
	Mutex_lock(&print_lock);
	do_print_buffer();

	// 跳過其他執行緒所佔用的欄位
	for (i = 0; i < thread_id; i++) {
	    printf("   ");
	}
	printf("%s\n", str);
	Mutex_unlock(&print_lock);
    }

    int local_id = thread_id;
    int pause_time;
    if (is_producer) {
	pause_time = producer_pause_times[local_id][pause_slot];
    } else {
	local_id = thread_id - producers;
	pause_time = consumer_pause_times[local_id][pause_slot];
    }
    // printf("暫停 %d\n", pause_time);
    sleep(pause_time);
}

void ensure(int expression, char *msg) {
    if (expression == 0) {
	fprintf(stderr, "%s\n", msg);
	exit(1);
    }
}

void parse_pause_string(char *str, char *name, int expected_pieces,
			int pause_array[MAX_THREADS][7]) {

    // 字串的格式應該長這樣：
    //   1,2,0:2,3,4,5
    //   如果有 n 個生產者/消費者，就會有 n-1 個冒號
    //   每個生產者或消費者的睡眠時間以逗號分隔
    int index = 0;

    char *copy_entire = strdup(str);
    char *outer_marker;
    int colon_count = 0;
    char *p = strtok_r(copy_entire, ":", &outer_marker);
    while (p) {
	// 初始化陣列：預設睡眠時間為 0
	int i;
	for (i = 0; i < 7; i++)
	    pause_array[index][i] = 0;

	// 每個片段以逗號分隔
	char *inner_marker;
	char *copy_piece = strdup(p);
	char *c = strtok_r(copy_piece, ",", &inner_marker);
	int comma_count = 0;

	int inner_index = 0;
	while (c) {
	    int pause_amount = atoi(c);
	    ensure(inner_index < 7, "你指定的睡眠字串格式不正確...（以逗號分隔的參數太多了）");
	    // printf("正在將 %s 的第 %d 個睡眠點設為 %d\n", name, inner_index, pause_amount);
	    pause_array[index][inner_index] = pause_amount;
	    inner_index++;

	    c = strtok_r(NULL, ",", &inner_marker);
	    comma_count++;
	}
	free(copy_piece);
	index++;

	// 繼續處理以冒號分隔的清單
	p = strtok_r(NULL, ":", &outer_marker);
	colon_count++;
    }

    free(copy_entire);
    if (expected_pieces != colon_count) {
	fprintf(stderr, "錯誤：睡眠規格中預期應有 %d 個%s，但實際得到 %d 個\n", expected_pieces, name, colon_count);
	exit(1);
    }
}


#endif // __main_header_h__
