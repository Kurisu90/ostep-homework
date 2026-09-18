
# 概述

在這份作業中，你將使用 Linux 上的一個實用工具，找出多執行緒程式碼中的問題。
這個工具叫做 `helgrind`（valgrind 除錯工具套件的一部分）。

詳情請參考 `http://valgrind.org/docs/manual/hg-manual.htm`，其中包含關於
這個工具的說明，以及如何下載安裝它（如果你的 Linux 系統上還沒有安裝的話）。

接著，你將檢視一些多執行緒 C 程式，看看如何使用這個工具來除錯有問題的
執行緒程式碼。

首先：下載並安裝 `valgrind` 以及相關的 `helgrind` 工具。

接著，輸入 `make -f Makefile_zh` 來建置所有中文版程式。可以查看
`Makefile_zh` 以了解建置的詳細方式。

然後，你會看到幾個不同的中文版 C 程式：
- `main-race_zh.c`：一個簡單的競爭條件（race condition）範例
- `main-deadlock_zh.c`：一個簡單的死結（deadlock）範例
- `main-deadlock-global_zh.c`：解決死結問題的一種方法
- `main-signal_zh.c`：一個簡單的子／父執行緒訊號範例
- `main-signal-cv_zh.c`：使用條件變數（condition variable）進行更有效率的訊號傳遞
- `common_threads_zh.h`：標頭檔，內含讓程式碼檢查錯誤並且更易讀的包裝函式（wrapper）

有了這些程式，你現在就可以回答教科書中的問題了。
