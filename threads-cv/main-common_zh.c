// 常用的 usage() 函式，用來印出指令列說明
void usage() {
    fprintf(stderr, "用法: \n");
    fprintf(stderr, "  -l <每個生產者要產生的項目數量>\n");
    fprintf(stderr, "  -m <生產者/消費者共用緩衝區的大小>\n");
    fprintf(stderr, "  -p <生產者的數量>\n");
    fprintf(stderr, "  -c <消費者的數量>\n");
    fprintf(stderr, "  -P <睡眠字串：每個生產者在執行過程中各個時間點應該睡眠多久>\n");
    fprintf(stderr, "  -C <睡眠字串：每個消費者在執行過程中各個時間點應該睡眠多久>\n");
    fprintf(stderr, "  -v [ 追蹤旗標：追蹤目前發生的狀況並印出來 ]\n");
    fprintf(stderr, "  -t [ 計時旗標：計算整個執行時間並印出總時間 ]\n");
    exit(1);
}

// 所有四個程式共用的 main()
// - 進行參數解析
// - 啟動生產者與消費者
// - 當生產者全部結束後，把 END_OF_STREAM
//   標記放入共用佇列，藉此通知消費者結束
// - 接著等待消費者結束，並印出一些最終資訊
int main(int argc, char *argv[]) {
    loops = 1;
    max = 1;
    consumers = 1;
    producers = 1;

    char *producer_pause_string = NULL;
    char *consumer_pause_string = NULL;

    opterr = 0;
    int c;
    while ((c = getopt (argc, argv, "l:m:p:c:P:C:vt")) != -1) {
	switch (c) {
	case 'l':
	    loops = atoi(optarg);
	    break;
	case 'm':
	    max = atoi(optarg);
	    break;
	case 'p':
	    producers = atoi(optarg);
	    break;
	case 'c':
	    consumers = atoi(optarg);
	    break;
	case 'P':
	    producer_pause_string = optarg;
	    break;
	case 'C':
	    consumer_pause_string = optarg;
	    break;
	case 'v':
	    do_trace = 1;
	    break;
	case 't':
	    do_timing = 1;
	    break;
	default:
	    usage();
	}
    }

    assert(loops > 0);
    assert(max > 0);
    assert(producers <= MAX_THREADS);
    assert(consumers <= MAX_THREADS);

    if (producer_pause_string != NULL)
	parse_pause_string(producer_pause_string, "生產者", producers, producer_pause_times);
    if (consumer_pause_string != NULL)
	parse_pause_string(consumer_pause_string, "消費者", consumers, consumer_pause_times);

    // 配置共用緩衝區的空間，並將其初始化...
    buffer = (int *) Malloc(max * sizeof(int));
    int i;
    for (i = 0; i < max; i++) {
	buffer[i] = EMPTY;
    }

    do_print_headers();

    double t1 = Time_GetSeconds();

    // 啟動所有執行緒；順序在此無關緊要
    pthread_t pid[MAX_THREADS], cid[MAX_THREADS];
    int thread_id = 0;
    for (i = 0; i < producers; i++) {
	Pthread_create(&pid[i], NULL, producer, (void *) (long long) thread_id);
	thread_id++;
    }
    for (i = 0; i < consumers; i++) {
	Pthread_create(&cid[i], NULL, consumer, (void *) (long long) thread_id);
	thread_id++;
    }

    // 現在等待所有「生產者」結束
    for (i = 0; i < producers; i++) {
	Pthread_join(pid[i], NULL);
    }

    // 結束情境：當所有生產者都完成之後
    // - 在佇列中放入「消費者數量」個 END_OF_STREAM
    // - 消費者只要看到 -1，就結束執行
    for (i = 0; i < consumers; i++) {
	Mutex_lock(&m);
	while (num_full == max)
	    Cond_wait(empty_cv, &m);
	do_fill(END_OF_STREAM);
	do_eos();
	Cond_signal(fill_cv);
	Mutex_unlock(&m);
    }

    // 現在可以等待所有消費者結束了
    int counts[consumers];
    for (i = 0; i < consumers; i++) {
	Pthread_join(cid[i], (void *) &counts[i]);
    }

    double t2 = Time_GetSeconds();

    if (do_trace) {
	printf("\n消費者消費狀況：\n");
	for (i = 0; i < consumers; i++) {
	    printf("  C%d -> %d\n", i, counts[i]);
	}
	printf("\n");
    }

    if (do_timing) {
	printf("總執行時間：%.2f 秒\n", t2-t1);
    }

    return 0;
}

