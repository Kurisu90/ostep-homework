
# 概觀

`malloc.py` 這個程式讓你觀察一個簡單的記憶體配置器（memory allocator）如何運作。以下是它可以使用的選項：

```sh
  -h, --help            顯示說明訊息並離開
  -s SEED, --seed=SEED  隨機種子
  -S HEAPSIZE, --size=HEAPSIZE
                        堆積（heap）的大小
  -b BASEADDR, --baseAddr=BASEADDR
                        堆積的起始位址
  -H HEADERSIZE, --headerSize=HEADERSIZE
                        標頭（header）的大小
  -a ALIGNMENT, --alignment=ALIGNMENT
                        將配置的單位對齊到此大小；-1 代表不對齊
  -p POLICY, --policy=POLICY
                        串列搜尋策略（BEST、WORST、FIRST）
  -l ORDER, --listOrder=ORDER
                        串列排序方式（ADDRSORT、SIZESORT+、SIZESORT-、INSERT-FRONT、INSERT-BACK）
  -C, --coalesce        是否合併空閒串列？
  -n OPSNUM, --numOps=OPSNUM
                        要產生的隨機操作數量
  -r OPSRANGE, --range=OPSRANGE
                        配置大小的上限
  -P OPSPALLOC, --percentAlloc=OPSPALLOC
                        操作中屬於配置（alloc）的比例
  -A OPSLIST, --allocList=OPSLIST
                        不用隨機產生，改用指定的操作清單（例如 +10,-0 等）
  -c, --compute         幫我計算答案
```

其中一種用法是讓程式隨機產生一連串配置（allocate）/釋放（free）操作，然後由你自己判斷空閒串列（free list）會長成什麼樣子，以及每個操作是成功還是失敗。

以下是一個簡單的例子：

```sh
prompt> ./malloc_zh.py -S 100 -b 1000 -H 4 -a 4 -l ADDRSORT -p BEST -n 5

種子(seed) 0
大小(size) 100
起始位址(baseAddr) 1000
標頭大小(headerSize) 4
對齊(alignment) 4
策略(policy) BEST
排序方式(listOrder) ADDRSORT
合併(coalesce) False
操作數量(numOps) 5
範圍(range) 10
配置比例(percentAlloc) 50
操作清單(allocList) 
計算答案(compute) False

ptr[0] = Alloc(3) 傳回 ?
串列狀態？

Free(ptr[0])
傳回 ?
串列狀態？

ptr[1] = Alloc(5) 傳回 ?
串列狀態？

Free(ptr[1])
傳回 ?
串列狀態？

ptr[2] = Alloc(8) 傳回 ?
串列狀態？
```

在這個例子中，我們指定堆積大小為 100 位元組（`-S 100`），起始位址為 1000（`-b 1000`）。我們指定每個配置區塊額外要有 4 位元組的標頭（`-H 4`），並讓每個配置空間的大小無條件進位到最接近的 4 位元組空閒區塊（`-a 4`）。我們也指定空閒串列要依位址（由小到大）保持排序。最後，我們指定使用「最佳配適（best fit）」的空閒串列搜尋策略（`-p BEST`），並要求產生 5 個隨機操作（`-n 5`）。執行結果如上；你的任務是算出每一個配置／釋放操作會傳回什麼值，以及每次操作後空閒串列的狀態。

接著我們用 `-c` 選項來看正確答案：

```sh
prompt> ./malloc_zh.py -S 100 -b 1000 -H 4 -a 4 -l ADDRSORT -p BEST -n 5 -c

種子(seed) 0
大小(size) 100
起始位址(baseAddr) 1000
標頭大小(headerSize) 4
對齊(alignment) 4
策略(policy) BEST
排序方式(listOrder) ADDRSORT
合併(coalesce) False
操作數量(numOps) 5
範圍(range) 10
配置比例(percentAlloc) 50
操作清單(allocList) 
計算答案(compute) True

ptr[0] = Alloc(3) 傳回 1004（搜尋了 1 個元素）
空閒串列［大小 1］：[ addr:1008 sz:92 ]

Free(ptr[0])
傳回 0
空閒串列［大小 2］：[ addr:1000 sz:8 ][ addr:1008 sz:92 ]

ptr[1] = Alloc(5) 傳回 1012（搜尋了 2 個元素）
空閒串列［大小 2］：[ addr:1000 sz:8 ][ addr:1020 sz:80 ]

Free(ptr[1])
傳回 0
空閒串列［大小 3］：[ addr:1000 sz:8 ][ addr:1008 sz:12 ][ addr:1020 sz:80 ]

ptr[2] = Alloc(8) 傳回 1012（搜尋了 3 個元素）
空閒串列［大小 2］：[ addr:1000 sz:8 ][ addr:1020 sz:80 ]

如你所見，第一個操作（一次配置）傳回了以下結果：

ptr[0] = Alloc(3) 傳回 1004（搜尋了 1 個元素）
空閒串列［大小 1］：[ addr:1008 sz:92 ]
```

因為空閒串列一開始只有一個大區塊，所以很容易猜到 `Alloc(3)` 這個請求會成功。而且它會直接回傳這個區塊最前面的部分，並把剩下的空間變成新的空閒串列。傳回的指標會落在標頭之後（位址 1004），配置的空間會無條件進位到 4 位元組的倍數，於是空閒串列剩下從 1008 開始、共 92 位元組的空間。

下一個操作是釋放（Free）`ptr[0]`，也就是儲存前一個配置結果的變數。可以預期這次釋放會成功（因此傳回 `0`），而空閒串列現在看起來稍微複雜一點了：

```sh
Free(ptr[0])
傳回 0
空閒串列［大小 2］：[ addr:1000 sz:8 ][ addr:1008 sz:92 ]
```

的確，因為我們「沒有」合併空閒串列，所以現在串列上有兩個元素：第一個是 8 位元組大，裝的是剛釋放的空間；第二個則是 92 位元組的區塊。

我們可以透過 `-C` 旗標把合併（coalescing）功能打開，結果會是這樣：

```sh
prompt> ./malloc_zh.py -S 100 -b 1000 -H 4 -a 4 -l ADDRSORT -p BEST -n 5 -c -C

種子(seed) 0
大小(size) 100
起始位址(baseAddr) 1000
標頭大小(headerSize) 4
對齊(alignment) 4
策略(policy) BEST
排序方式(listOrder) ADDRSORT
合併(coalesce) True
操作數量(numOps) 5
範圍(range) 10
配置比例(percentAlloc) 50
操作清單(allocList) 
計算答案(compute) True

ptr[0] = Alloc(3) 傳回 1004（搜尋了 1 個元素）
空閒串列［大小 1］：[ addr:1008 sz:92 ]

Free(ptr[0])
傳回 0
空閒串列［大小 1］：[ addr:1000 sz:100 ]

ptr[1] = Alloc(5) 傳回 1004（搜尋了 1 個元素）
空閒串列［大小 1］：[ addr:1012 sz:88 ]

Free(ptr[1])
傳回 0
空閒串列［大小 1］：[ addr:1000 sz:100 ]

ptr[2] = Alloc(8) 傳回 1004（搜尋了 1 個元素）
空閒串列［大小 1］：[ addr:1012 sz:88 ]
```

可以看到，當釋放操作發生時，空閒串列會如預期般被合併起來。

還有一些值得探索的選項：

* `-p BEST` 或 `-p WORST` 或 `-p FIRST`：這個選項讓你選用三種不同的策略，在配置請求發生時尋找適合的記憶體區塊。
* `-l ADDRSORT` 或 `-l SIZESORT+` 或 `-l SIZESORT-` 或 `-l INSERT-FRONT` 或 `-l INSERT-BACK`：這個選項可以讓空閒串列依照特定順序排列，例如依空閒區塊的位址排序、依空閒區塊大小排序（用 `+` 表示由小到大、`-` 表示由大到小），或是單純把釋放的區塊放到串列最前面（`INSERT-FRONT`）或最後面（`INSERT-BACK`）。
* `-A 操作清單`：這個選項讓你自己指定一連串確切的請求，而不是隨機產生。舉例來說，用 `-A +10,+10,+10,-0,-2` 執行，會配置三個 10 位元組（外加標頭）大小的區塊，然後釋放第一個（`-0`）和第三個（`-2`）。這時空閒串列會長成什麼樣子呢？

以上是基本用法，可以用課本章節裡的問題來進一步探索，或者自己動手設計新的、有趣的問題，藉此更了解配置器（allocator）的運作方式。

---

補充說明：這份文件與 `malloc_zh.py` 只翻譯了介面文字（命令列選項說明、執行時印出的訊息，以及程式內的註解），`-p`／`-l` 選項本身接受的策略名稱（`BEST`、`WORST`、`FIRST`、`ADDRSORT`、`SIZESORT+`、`SIZESORT-`、`INSERT-FRONT`、`INSERT-BACK`）維持英文不變，因為這些是必須原樣輸入在命令列上的固定值。排程／配置邏輯本身與原始的 `malloc.py` 完全一致，兩者對相同的參數與亂數種子會算出完全相同的結果，只是顯示的語言不同。原始英文版本仍保留在 `malloc.py` 與 `README.md` 中，未做任何更動。
