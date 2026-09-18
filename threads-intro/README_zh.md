
# 概觀

歡迎使用這個模擬器！它的目的是讓你透過觀察執行緒如何交錯執行，來熟悉
執行緒（thread）的概念；`x86_zh.py` 這個模擬器可以幫助你建立這樣的理解。

`x86_zh.py` 是 `x86.py` 的中文版本，功能與底層的模擬邏輯完全相同，只是把
所有的說明文字、命令列選項說明，以及執行時印出的訊息都換成了中文。

這個模擬器模擬了多個執行緒執行一小段組合語言指令序列的過程。要注意的
是，實際上會執行的 OS 程式碼（例如，執行 context switch 時的程式碼）
並*不會*顯示出來；因此，你看到的只是使用者程式碼的交錯執行過程。

這裡執行的組合語言以 x86 為基礎，但做了一些簡化。在這個指令集中，有
四個通用暫存器（%ax、%bx、%cx、%dx）、一個程式計數器（PC），以及一小
組足夠我們使用的指令。

以下是一個我們可以執行的範例程式碼片段：

```sh
.main
mov 2000, %ax   # get the value at the address
add $1, %ax     # increment it
mov %ax, 2000   # store it back
halt
```

這段程式碼很容易理解。第一道指令，也就是 x86 的「mov」，只是把位址
2000 處的值載入到暫存器 %ax 中。在這個簡化版的 x86 指令集裡，位址可以
是以下幾種形式：

- `2000`：這個數字（2000）本身就是位址
- `(%cx)`：括號中暫存器的內容就是位址
- `1000(%dx)`：數字加上暫存器的內容組成位址
- `10(%ax,%bx)`：數字加上暫存器 1、暫存器 2 的內容組成位址

要儲存一個值，一樣是用 `mov` 指令，只是這次引數的順序相反，例如：

```sh
mov %ax, 2000
```

上面那段程式碼中的 `add` 指令應該很好理解：它把一個立即值（由 `$1`
指定）加到第二個引數所指定的暫存器上（也就是 `%ax = %ax + 1`）。

因此，我們現在可以理解上面這段程式碼了：它先載入位址 2000 處的值，
把它加 1，然後再把結果存回位址 2000。

那個有點虛構的 `halt` 指令，功能就是停止執行目前這個執行緒。

讓我們實際執行看看，看看整體是怎麼運作的！假設上面那段程式碼放在檔案
`simple-race.s` 中。

```sh
prompt> ./x86_zh.py -p simple-race.s -t 1 

      執行緒 0          
1000 mov 2000(%bx), %ax
1001 add $1, %ax
1002 mov %ax, 2000(%bx)
1003 halt

prompt> 
```

（提醒：目前 repo 中 `simple-race.s` 的實際內容用的是 `2000(%bx)` 這種
定址方式，因此輸出會如上所示；這裡的輸出是直接執行 `x86_zh.py` 得到的
真實結果。）

這裡用到的引數分別指定了程式（`-p`）、執行緒數量（`-t 1`），以及中斷
間隔（也就是排程器多久會被喚醒一次，並執行切換到另一個工作）。因為這
個範例中只有一個執行緒，所以這個間隔在此並不重要。

輸出很容易閱讀：模擬器印出程式計數器（這裡從 1000 到 1003）以及被執行
的指令。要注意的是，我們（不太寫實地）假設每一道指令在記憶體中都只
佔一個位元組；而在真正的 x86 中，指令長度是可變的，會佔用一到數個
位元組不等。

我們可以用更詳細的追蹤方式，更清楚地了解機器狀態在執行過程中是如何
變化的：

```sh
prompt> ./x86_zh.py -p simple-race.s -t 1 -M 2000 -R ax,bx

 2000      ax    bx         執行緒 0          
    ?       ?     ?   
    ?       ?     ?   1000 mov 2000(%bx), %ax
    ?       ?     ?   1001 add $1, %ax
    ?       ?     ?   1002 mov %ax, 2000(%bx)
    ?       ?     ?   1003 halt

哎呀！忘記加上 -c 旗標了（這個旗標才會真的幫你把答案算出來）。

prompt> ./x86_zh.py -p simple-race.s -t 1 -M 2000 -R ax,bx -c

 2000      ax    bx         執行緒 0          
    0       0     0   
    0       0     0   1000 mov 2000(%bx), %ax
    0       1     0   1001 add $1, %ax
    1       1     0   1002 mov %ax, 2000(%bx)
    1       1     0   1003 halt
```

透過 `-M` 旗標，我們可以追蹤記憶體位址（用逗號分隔的清單可以追蹤多個，
例如 2000,3000）；透過 `-R` 旗標，我們可以追蹤特定暫存器內的值。

左邊顯示的數值，是右邊那道指令「執行完之後」的記憶體／暫存器內容。
舉例來說，`add` 指令執行後，你可以看到 %ax 已經被加到了 1；第二個 `mov`
指令（在 PC=1002 處）執行後，你可以看到位址 2000 處的記憶體內容也同樣
被加了 1。

還有幾個指令你需要認識，現在就來介紹。以下是一段迴圈的程式碼片段：

```sh
.main
.top
sub  $1,%dx
test $0,%dx     
jgte .top         
halt
```

這裡介紹了幾個新東西。第一個是 `test` 指令。這個指令接受兩個引數並
比較它們；接著它會設定一組隱含的「條件碼」（有點像是 1 位元的暫存器），
供後續指令使用。

在這個例子中，另一個新指令是「跳躍（jump）」指令（在這裡是 `jgte`，
代表「大於等於則跳躍」）。這個指令會在 test 的第二個值大於等於第一個
值時發生跳躍。

最後一點：要讓這段程式碼真的能動起來，`dx` 必須被初始化為 1 或更大
的值。

因此，我們這樣執行這個程式：

```sh
prompt> ./x86_zh.py -p loop.s -t 1 -a dx=3 -R dx -C -c

   dx   >= >  <= <  != ==       執行緒 0          
    3   0  0  0  0  0  0  
    2   0  0  0  0  0  0  1000 sub  $1,%dx
    2   1  1  0  0  1  0  1001 test $0,%dx
    2   1  1  0  0  1  0  1002 jgte .top
    1   1  1  0  0  1  0  1000 sub  $1,%dx
    1   1  1  0  0  1  0  1001 test $0,%dx
    1   1  1  0  0  1  0  1002 jgte .top
    0   1  1  0  0  1  0  1000 sub  $1,%dx
    0   1  0  1  0  0  1  1001 test $0,%dx
    0   1  0  1  0  0  1  1002 jgte .top
   -1   1  0  1  0  0  1  1000 sub  $1,%dx
   -1   0  0  1  1  1  0  1001 test $0,%dx
   -1   0  0  1  1  1  0  1002 jgte .top
   -1   0  0  1  1  1  0  1003 halt
```

`-R dx` 旗標追蹤 %dx 的值；`-C` 旗標追蹤 test 指令所設定的各個條件碼
的值。最後，`-a dx=3` 旗標把 `%dx` 暫存器的初始值設為 3。

從追蹤結果可以看到，`sub` 指令逐漸把 %dx 的值降低。前幾次呼叫 `test`
時，只有「>=」、「>」、「!=」這三個條件會被設定。然而，追蹤紀錄中
最後一次 `test` 發現 %dx 與 0 相等，因此接下來的跳躍「不會」發生，
程式最終停止（halt）。

現在，終於要進入更有趣的案例了，也就是多個執行緒之間的競爭條件
（race condition）。讓我們先看看程式碼：

```sh
.main
.top
# critical section
mov 2000, %ax       # get the value at the address
add $1, %ax         # increment it
mov %ax, 2000       # store it back

# see if we're still looping
sub  $1, %bx
test $0, %bx
jgt .top

halt
```

這段程式碼有一個臨界區（critical section），會先載入某個變數的值
（位於位址 2000），然後把值加 1，再存回去。

後面那段程式碼只是遞減一個迴圈計數器（存在 %bx 中），檢查它是否大於
等於零，如果是的話，就跳回最上面，再次執行臨界區。

```sh
prompt> ./x86_zh.py -p looping-race-nolock.s -t 2 -a bx=1 -M 2000 -c

 2000         執行緒 0                執行緒 1          
    0   
    0   1000 mov 2000, %ax
    0   1001 add $1, %ax
    1   1002 mov %ax, 2000
    1   1003 sub  $1, %bx
    1   1004 test $0, %bx
    1   1005 jgt .top
    1   1006 halt
    1   ----- 結束並切換(Halt;Switch) -----  ----- 結束並切換(Halt;Switch) -----  
    1                            1000 mov 2000, %ax
    1                            1001 add $1, %ax
    2                            1002 mov %ax, 2000
    2                            1003 sub  $1, %bx
    2                            1004 test $0, %bx
    2                            1005 jgt .top
    2                            1006 halt
```

在這裡你可以看到每個執行緒各執行了一次，也各自把位於位址 2000 的
共享變數更新了一次，因此最後那裡的值變成了 2。

當某個執行緒 halt、必須切換到另一個執行緒時，就會印出
「結束並切換（Halt;Switch）」這一行。

最後一個範例：執行同樣的程式，但把中斷頻率調小。結果看起來會是這樣：

```sh
prompt> ./x86_zh.py -p looping-race-nolock.s -t 2 -a bx=1 -M 2000 -i 2

 2000         執行緒 0                執行緒 1          
    ?   
    ?   1000 mov 2000, %ax
    ?   1001 add $1, %ax
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1000 mov 2000, %ax
    ?                            1001 add $1, %ax
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1002 mov %ax, 2000
    ?   1003 sub  $1, %bx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1002 mov %ax, 2000
    ?                            1003 sub  $1, %bx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1004 test $0, %bx
    ?   1005 jgt .top
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1004 test $0, %bx
    ?                            1005 jgt .top
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1006 halt
    ?   ----- 結束並切換(Halt;Switch) -----  ----- 結束並切換(Halt;Switch) -----  
    ?                            1006 halt
```

如你所見，透過 `-i 2` 這個旗標，每個執行緒每執行 2 道指令就會被中斷
一次。在整個執行過程中，記憶體位址 2000 的值分別是多少？照理說「應該」
是多少？

現在，讓我們再多介紹一些這個模擬器可以模擬的內容。完整的暫存器
集合是：%ax、%bx、%cx、%dx，以及 PC。在這個版本中，並不支援「堆疊」
（stack），也沒有 call 與 return 指令。

模擬器支援的完整指令集如下：

```sh
mov immediate, register     # 把立即值移到暫存器
mov memory, register        # 從記憶體載入到暫存器
mov register, register      # 把值從一個暫存器移到另一個
mov register, memory        # 把暫存器內容存到記憶體
mov immediate, memory       # 把立即值存到記憶體

add immediate, register     # register  = register  + immediate
add register1, register2    # register2 = register2 + register1
sub immediate, register     # register  = register  - immediate
sub register1, register2    # register2 = register2 - register1

test immediate, register    # 比較立即值與暫存器（設定條件碼）
test register, immediate    # 同上，但比較暫存器與立即值
test register, register     # 同上，但比較暫存器與暫存器

jne                         # 若比較結果不相等則跳躍
je                          #                 ... 相等
jlt                         #     ... 第二個值小於第一個
jlte                        #               ... 小於等於
jgt                         #            ... 大於
jgte                        #               ... 大於等於

xchg register, memory       # 原子交換（atomic exchange）：
                            #   把暫存器的值放進記憶體
                            #   並把記憶體原本的內容傳回暫存器
                            # 這兩件事會原子性地一起完成

nop                         # 無作用（no op）
```

補充說明：
- 'immediate'（立即值）的格式是 $數字
- 'memory'（記憶體）的格式是 'number' 或 '(reg)' 或 'number(reg)' 或
  'number(reg,reg)'（如前面所述）
- 'register'（暫存器）是 %ax、%bx、%cx、%dx 其中之一

最後，用 `-h` 旗標可以看到模擬器完整的選項清單：

```sh
Usage: x86_zh.py [options]

Options:
  -h, --help            show this help message and exit
  -s SEED, --seed=SEED  隨機種子
  -t NUMTHREADS, --threads=NUMTHREADS
                        執行緒數量
  -p PROGFILE, --program=PROGFILE
                        原始程式（.s 檔）
  -i INTFREQ, --interrupt=INTFREQ
                        中斷頻率
  -r, --randints        中斷時機是否隨機決定
  -a ARGV, --argv=ARGV  以逗號分隔的各執行緒引數（例如 ax=1,ax=2 會把執行緒
                        0 的 ax 暫存器設為 1，執行緒 1 的 ax 暫存器設為
                        2）；同一個執行緒若要設定多個暫存器，用冒號分隔
                        （例如 ax=1:bx=2,cx=3 會設定執行緒 0 的 ax 與
                        bx，以及執行緒 1 的 cx）
  -L LOADADDR, --loadaddr=LOADADDR
                        程式碼載入的位址
  -m MEMSIZE, --memsize=MEMSIZE
                        位址空間大小（KB）
  -M MEMTRACE, --memtrace=MEMTRACE
                        以逗號分隔的待追蹤位址清單（例如
                        20000,20001）
  -R REGTRACE, --regtrace=REGTRACE
                        以逗號分隔的待追蹤暫存器清單（例如
                        ax,bx,cx,dx）
  -C, --cctrace         是否要追蹤條件碼
  -S, --printstats      印出一些額外的統計資訊
  -c, --compute         幫我計算答案
```

大部分選項都相當直觀。使用 `-r` 會開啟隨機中斷（由 `-i` 指定的
intfreq 為上限，介於 1 到 intfreq 之間隨機取值），這樣寫作業時可以
增加一點趣味。

- `-L` 指定程式碼要載入到位址空間的哪個位置。
- `-m` 指定位址空間的大小（以 KB 為單位）。
- `-S` 印出一些額外的統計資訊。
- `-c` 其實不太常用（跟本書大部分的模擬器不同）；請善用追蹤或條件碼
  的輸出。

現在你已經掌握了基本用法；接著請閱讀章節最後的問題，更深入研究這個
競爭條件與相關議題。

---

補充說明：這份文件與 `x86_zh.py` 只翻譯了介面文字（命令列選項說明、
執行時印出的訊息，以及程式內的註解），模擬邏輯本身與原始的 `x86.py`
完全一致，兩者對相同的參數與亂數種子會算出完全相同的結果，只是顯示
的語言不同。原始英文版本仍保留在 `x86.py` 與 `README.md` 中，未做任何
更動。
