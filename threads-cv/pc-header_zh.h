#ifndef __pc_header_h__
#define __pc_header_h__

#define MAX_THREADS (100)  // 生產者/消費者的最大數量

int producers = 1;         // 生產者的數量
int consumers = 1;         // 消費者的數量

int *buffer;               // 緩衝區本身：在 main() 中配置記憶體
int max;                   // 生產者/消費者共用緩衝區的大小

int use_ptr  = 0;          // 追蹤下一次消費應該從哪裡取值
int fill_ptr = 0;          // 追蹤下一次生產應該放到哪裡
int num_full = 0;          // 計算緩衝區中已滿的項目數量

int loops;                 // 每個生產者要產生的項目數量

#define EMPTY         (-2) // 緩衝區位置是空的
#define END_OF_STREAM (-1) // 拿到這個標記的消費者應該結束

#endif // __pc_header_h__
