
# 概觀

本目錄中包含了一些骨架程式碼片段，你可以把它們補完，
用來解決各種同步（synchronization）問題。

另外也可以參考 Allen Downey 的著作《A Little Book of
Semaphores》，裡面有更多有趣的內容，而且是免費的！

若要編譯其中任何一個檔案（例如某個叫做 `foo_zh.c` 的檔案）：

```sh
prompt> gcc -o foo_zh foo_zh.c -Wall -pthread
```

接著執行它：

```sh
prompt> ./foo_zh
```

（也可以視情況加上一些選用的參數）

