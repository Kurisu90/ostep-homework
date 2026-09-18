
# 總覽

這一節要介紹的是 `raid_zh.py`（`raid.py` 的中文版本），一個簡單的
RAID 模擬器，可以用來鞏固你對 RAID 系統運作方式的理解。它有不少
選項，如下所示：

```sh
prompt> ./raid_zh.py -h
Usage: raid_zh.py [options]

Options:
  -h, --help            show this help message and exit
  -s SEED, --seed=SEED  隨機種子
  -D NUMDISKS, --numDisks=NUMDISKS
                        RAID 中的磁碟數量
  -C CHUNKSIZE, --chunkSize=CHUNKSIZE
                        RAID 的 chunk 大小
  -n NUMREQUESTS, --numRequests=NUMREQUESTS
                        要模擬的請求數量
  -S SIZE, --reqSize=SIZE
                        請求的大小
  -W WORKLOAD, --workload=WORKLOAD
                        工作負載類型，"rand"（隨機）或 "seq"（循序）
  -w WRITEFRAC, --writeFrac=WRITEFRAC
                        寫入比例（100 代表全部寫入，0 代表全部讀取）
  -R RANGE, --randRange=RANGE
                        請求的位址範圍（使用 "rand" 工作負載時適用）
  -L LEVEL, --level=LEVEL
                        RAID 等級（0、1、4、5）
  -5 RAID5TYPE, --raid5=RAID5TYPE
                        RAID-5 的配置方式："LS"（左對稱）或 "LA"（左不對稱）
  -r, --reverse         不顯示邏輯操作，改成顯示實體操作
  -t, --timing          使用計時模式，而不是對應模式
  -c, --compute         幫我計算答案
```

在最基本的模式下，你可以用它來理解不同的 RAID 等級如何把邏輯區塊
對應到底層的磁碟與 offset。舉例來說，假設我們想看看一個有四顆磁碟的
簡單 striping（分條）RAID（RAID-0）是怎麼做這個對應的。

```sh
prompt> ./raid_zh.py -n 5 -L 0 -R 20 
...
邏輯讀取從 addr:16 size:4096
  實際的實體讀寫操作是？

邏輯讀取從 addr:8 size:4096
  實際的實體讀寫操作是？

邏輯讀取從 addr:10 size:4096
  實際的實體讀寫操作是？

邏輯讀取從 addr:15 size:4096
  實際的實體讀寫操作是？

邏輯讀取從 addr:9 size:4096
  實際的實體讀寫操作是？
```

在這個例子中，我們模擬了五個請求（-n 5），指定 RAID 等級為 0
（-L 0），並把隨機請求的範圍限制在 RAID 最前面的 20 個區塊
（-R 20）。結果就是對 RAID 最前面 20 個區塊發出一連串的隨機讀取；
模擬器接著要你猜猜看，為了服務每一次邏輯讀取，實際存取了底層的
哪個磁碟、哪個 offset。

在這個例子裡，要算出答案並不難：回想一下，在 RAID-0 中，服務某個
請求所用的底層磁碟與 offset，是透過取餘數（modulo）運算算出來的：

```sh
disk   = address % number_of_disks
offset = address / number_of_disks
```

因此，第一個對位址 16 的請求，應該會由磁碟 0、offset 4 來服務，
以此類推。跟平常一樣，等你自己算完之後，可以用方便的 `-c` 旗標
來看答案：

```sh
prompt> ./raid_zh.py -R 20 -n 5 -L 0 -c
...
邏輯讀取從 addr:16 size:4096
  read  [disk 0, offset 4]  

邏輯讀取從 addr:8 size:4096
  read  [disk 0, offset 2]  

邏輯讀取從 addr:10 size:4096
  read  [disk 2, offset 2]  

邏輯讀取從 addr:15 size:4096
  read  [disk 3, offset 3]  

邏輯讀取從 addr:9 size:4096
  read  [disk 1, offset 2]  
```

因為好玩，你也可以用 `-r` 旗標反過來玩這個遊戲。用這種方式執行
模擬器，會顯示低階的磁碟讀寫操作，然後要你反推出到底是哪個邏輯
請求，才會讓 RAID 做出這些底層操作：

```sh
prompt> ./raid_zh.py -R 20 -n 5 -L 0 -r
...
邏輯操作是 ?
  read  [disk 0, offset 4]  

邏輯操作是 ?
  read  [disk 0, offset 2]  

邏輯操作是 ?
  read  [disk 2, offset 2]  

邏輯操作是 ?
  read  [disk 3, offset 3]  

邏輯操作是 ?
  read  [disk 1, offset 2]  
```

你一樣可以用 -c 來顯示答案。想要更多變化的話，可以指定不同的
隨機種子（-s）。

透過檢視不同的 RAID 等級，還能有更多變化。這個模擬器支援
RAID-0（區塊分條）、RAID-1（鏡像）、RAID-4（區塊分條再加一顆同位
檢查磁碟），以及 RAID-5（區塊分條加上輪流轉移的同位檢查）。

接下來這個例子，我們示範怎麼在鏡像模式下執行模擬器。為了節省
篇幅，直接顯示答案：

```sh
prompt> ./raid_zh.py -R 20 -n 5 -L 1 -c
...
邏輯讀取從 addr:16 size:4096
  read  [disk 0, offset 8]  

邏輯讀取從 addr:8 size:4096
  read  [disk 0, offset 4]  

邏輯讀取從 addr:10 size:4096
  read  [disk 1, offset 5]  

邏輯讀取從 addr:15 size:4096
  read  [disk 3, offset 7]  

邏輯讀取從 addr:9 size:4096
  read  [disk 2, offset 4]  
```

從這個例子中，你可能會注意到幾件事。第一，這個鏡像 RAID-1 假設
使用分條式的配置（有些人會稱之為 RAID-10，也就是「鏡像的分條」），
邏輯區塊 0 對應到磁碟 0 與磁碟 1 的第 0 個區塊，邏輯區塊 1 對應到
磁碟 2 與磁碟 3 的第 0 個區塊，以此類推（在這個四顆磁碟的例子裡）。
第二，當要從一個鏡像 RAID 系統讀取單一個區塊時，RAID 可以在兩份
副本之間做選擇。在這個模擬器裡，我們用一種相當簡陋的方式：偶數
編號的邏輯區塊，RAID 會選擇這一對磁碟中編號為偶數的那一顆；奇數
編號的邏輯區塊則使用編號為奇數的那一顆。這樣做是為了讓每次執行的
結果都容易猜（而不是像真正隨機選擇那樣難以預測）。

我們也可以用 -w 旗標探索寫入的行為（而不只是讀取），這個旗標用來
指定工作負載的「寫入比例」，也就是請求中屬於寫入的比例。預設值是
零，因此到目前為止的例子都是 100% 的讀取。我們來看看，當引入一些
寫入之後，我們的鏡像 RAID 會發生什麼事：

```sh
prompt> ./raid_zh.py -R 20 -n 5 -L 1 -w 100 -c
... 
邏輯寫入到  addr:16 size:4096
  write [disk 0, offset 8]    write [disk 1, offset 8]  

邏輯寫入到  addr:8 size:4096
  write [disk 0, offset 4]    write [disk 1, offset 4]  

邏輯寫入到  addr:10 size:4096
  write [disk 0, offset 5]    write [disk 1, offset 5]  

邏輯寫入到  addr:15 size:4096
  write [disk 2, offset 7]    write [disk 3, offset 7]  

邏輯寫入到  addr:9 size:4096
  write [disk 2, offset 4]    write [disk 3, offset 4]  
```

有了寫入之後，RAID 當然不能只產生一次低階磁碟操作，而是必須同時
更新兩顆磁碟，因此會發出兩次寫入。RAID-4 與 RAID-5 還會發生更多有
趣的事情，這部分就留給你在後面的題目中自己去探索。

其餘的選項可以透過 help 旗標查到，內容如下：

```sh
Options:
  -h, --help            show this help message and exit
  -s SEED, --seed=SEED  隨機種子
  -D NUMDISKS, --numDisks=NUMDISKS
                        RAID 中的磁碟數量
  -C CHUNKSIZE, --chunkSize=CHUNKSIZE
                        RAID 的 chunk 大小
  -n NUMREQUESTS, --numRequests=NUMREQUESTS
                        要模擬的請求數量
  -S SIZE, --reqSize=SIZE
                        請求的大小
  -W WORKLOAD, --workload=WORKLOAD
                        工作負載類型，"rand"（隨機）或 "seq"（循序）
  -w WRITEFRAC, --writeFrac=WRITEFRAC
                        寫入比例（100 代表全部寫入，0 代表全部讀取）
  -R RANGE, --randRange=RANGE
                        請求的位址範圍（使用 "rand" 工作負載時適用）
  -L LEVEL, --level=LEVEL
                        RAID 等級（0、1、4、5）
  -5 RAID5TYPE, --raid5=RAID5TYPE
                        RAID-5 的配置方式："LS"（左對稱）或 "LA"（左不對稱）
  -r, --reverse         不顯示邏輯操作，改成顯示實體操作
  -t, --timing          使用計時模式，而不是對應模式
  -c, --compute         幫我計算答案
```

`-C` 旗標可以讓你設定 RAID 的 chunk 大小，而不使用預設的每個 chunk
一個 4-KB 區塊。每個請求的大小也可以用 `-S` 旗標做類似的調整。
預設的工作負載會存取隨機的區塊；用 `-W seq` 可以探索循序存取的
行為。在 RAID-5 中，有兩種不同的排列方式可以選擇：left-symmetric
（左對稱）與 left-asymmetric（左不對稱）；用 `-5 LS` 或 `-5 LA`
就可以在 RAID-5（`-L 5`）上分別試試看這兩種方式。

最後，在計時模式（`-t`）下，模擬器會用一個極度簡化的磁碟模型，
估計一組請求大概要花多久時間，而不是只專注在對應關係上。在這個
模式下，一次隨機請求要花 10 毫秒，一次循序請求則只要 0.1 毫秒。
這裡假設磁碟每條磁軌只有很少的區塊數（100），磁軌數量也很少
（100）。因此你可以用這個模擬器，估計 RAID 在不同工作負載下的
效能表現。

---

補充說明：這份文件與 `raid_zh.py` 只翻譯了介面文字（命令列選項
說明、執行時印出的訊息，以及程式內的註解），RAID 對應與計時模擬的
邏輯本身與原始的 `raid.py` 完全一致，兩者對相同的參數與亂數種子
會算出完全相同的結果，只是顯示的語言不同。原始英文版本仍保留在
`raid.py` 與 `README.md` 中，未做任何更動。

這個目錄裡還有一個 `raid-graphics.py`，是用 Tkinter 畫出動畫效果的
舊版圖形化 RAID 模擬器；本次也一併提供了對應的中文版
`raid-graphics_zh.py`（同樣只翻譯註解、說明文字與畫面上的文字標籤，
邏輯完全不變）。不過這個檔案是用 Python 2 的語法寫的（例如不加括號
的 `print` 陳述式），且依賴 `Tkinter` 圖形介面，在目前只有 Python 3、
且用來驗證的環境中沒有 Python 2 直譯器可以直接執行；因此它的正確性
是透過逐一比對兩份檔案的程式碼記號（token）來驗證的，確認除了字串
與註解的內容以外，其餘所有程式碼記號都完全相同，而不是像 `raid.py`
一樣直接執行比對數字輸出。原始的 `raid-graphics.py` 同樣未做任何
更動。
