
# 概觀

歡迎使用這個模擬器！它的目的是讓你透過觀察執行緒如何交錯執行，來熟悉
執行緒（thread）的概念；`x86_zh.py` 這個模擬器可以幫助你建立這樣的理解。

`x86_zh.py` 是 `x86.py` 的中文版本，功能與底層的模擬邏輯完全相同，只是把
所有的說明文字、命令列選項說明，以及執行時印出的訊息都換成了中文。這個
版本的模擬器比 `threads-intro` 目錄中的版本多支援了 `%ex`、`%fx` 兩個
額外的通用暫存器、堆疊指標 `%sp`、`lea`／`neg`／`mul` 等指令，以及
`-P`（手動排程）與 `-H`（重印表頭）兩個新旗標，方便用來模擬鎖
（lock）相關的演算法。

這個模擬器模擬了多個執行緒執行一小段組合語言指令序列的過程。要注意的
是，實際上會執行的 OS 程式碼（例如，執行 context switch 時的程式碼）
並不會顯示出來；因此，你看到的只是使用者程式碼的交錯執行過程。

這裡執行的組合語言以 x86 為基礎，但做了一些簡化。在這個指令集中，有
四個通用暫存器（`%ax, %bx, %cx, %dx`）、一個程式計數器（PC），以及一小
組足夠我們使用的指令。我們還額外加入了兩個通用暫存器（`%ex, %fx`），
在真正的 x86 中並沒有完全對應的東西（不過這樣也無妨，對吧？）。

以下是一個我們可以執行的範例程式碼片段：

```
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
- `10(%ax,%bx,4)`：數字加上暫存器 1，再加上（暫存器 2 乘上縮放係數）
  組成位址

要儲存一個值，一樣是用 `mov` 指令，只是這次引數的順序相反，例如：

```
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

1000 mov 2000, %ax
1001 add $1, %ax
1002 mov %ax, 2000
1003 halt

prompt>
```

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
    ?       ?     ?   1000 mov 2000, %ax
    ?       ?     ?   1001 add $1, %ax
    ?       ?     ?   1002 mov %ax, 2000
    ?       ?     ?   1003 halt
```

哎呀！忘記加上 `-c` 旗標了（這個旗標才會真的幫你把答案算出來）。

```sh
prompt> ./x86_zh.py -p simple-race.s -t 1 -M 2000 -R ax,bx -c

 2000      ax    bx         執行緒 0          

    0       0     0   
    0       0     0   1000 mov 2000, %ax
    0       1     0   1001 add $1, %ax
    1       1     0   1002 mov %ax, 2000
    1       1     0   1003 halt
```

透過 `-M` 旗標，我們可以追蹤記憶體位址（用逗號分隔的清單可以追蹤多個，
例如 2000,3000）；透過 `-R` 旗標，我們可以追蹤特定暫存器內的值。

左邊顯示的數值，是右邊那道指令「執行完之後」的記憶體／暫存器內容。
舉例來說，`add` 指令執行後，你可以看到 %ax 已經被加到了 1；第二個 `mov`
指令（在 PC=1002 處）執行後，你可以看到位址 2000 處的記憶體內容也同樣
被加了 1。

還有幾個指令你需要認識，現在就來介紹。以下是一段迴圈的程式碼片段
（來自 `loop.s`）：

```
.main
.top
sub  $1,%dx
test $0,%dx     
jgt .top         
halt
```

這裡介紹了幾個新東西。第一個是 `test` 指令。這個指令接受兩個引數並
比較它們；接著它會設定一組隱含的「條件碼」（有點像是 1 位元的暫存器），
供後續指令使用。

在這個例子中，另一個新指令是「跳躍（jump）」指令（在這裡是 `jgt`，
代表「大於則跳躍」）。這個指令會在 test 的第二個值大於第一個值時發生
跳躍。

最後一點：要讓這段程式碼真的能動起來，`dx` 必須被初始化為 1 或更大
的值。

因此，我們這樣執行這個程式：

```sh
prompt> ./x86_zh.py -p loop.s -t 1 -a dx=3 -R dx -C -c

   dx   >= >  <= <  != ==       執行緒 0          

    3   0  0  0  0  0  0  
    2   0  0  0  0  0  0  1000 sub  $1,%dx
    2   1  1  0  0  1  0  1001 test $0,%dx
    2   1  1  0  0  1  0  1002 jgt .top
    1   1  1  0  0  1  0  1000 sub  $1,%dx
    1   1  1  0  0  1  0  1001 test $0,%dx
    1   1  1  0  0  1  0  1002 jgt .top
    0   1  1  0  0  1  0  1000 sub  $1,%dx
    0   1  0  1  0  0  1  1001 test $0,%dx
    0   1  0  1  0  0  1  1002 jgt .top
    0   1  0  1  0  0  1  1003 halt
```

`-R dx` 旗標追蹤 %dx 的值；`-C` 旗標追蹤 test 指令所設定的各個條件碼
的值。最後，`-a dx=3` 旗標把 `%dx` 暫存器的初始值設為 3。

從追蹤結果可以看到，`sub` 指令逐漸把 %dx 的值降低。前幾次呼叫 `test`
時，只有「>=」、「>」、「!=」這三個條件會被設定。然而，追蹤紀錄中
最後一次 `test` 發現 %dx 已經等於 0，因此接下來的跳躍（jgt，「大於則
跳躍」）不再發生，程式最終停止（halt）。

現在，終於要進入更有趣的案例：多個執行緒共享一個臨界區（critical
section），並用「鎖」來保護它。讓我們先看看 `looping-race-withlock-
withcallret.s` 這個程式（為了對應這個目錄的主題——鎖，這裡用的是已經
加上鎖保護的範例，而不是完全沒有保護的版本）：

```
.var mutex
.var count

.main
.top	
push mutex
call .lock
pop

# critical section
mov  count, %ax     # get the value at the address
add  $1, %ax        # increment it
mov  %ax, count     # store it back

# release lock
push mutex
call .unlock
pop

# see if we're still looping
sub  $1, %bx
test $0, %bx
jgt .top	

halt

.lock
.acquire
mov  -4(%sp), %ax   # get addr of flag
mov  $1, %cx        # 
xchg %cx, (%ax)     # atomic swap of 1 and flag
test $0, %cx        # if we get 0 back: lock is free!
jne  .acquire       # if not, try again
ret

.unlock
mov  -4(%sp), %ax   # all done: release lock by clearing it
mov  $0, (%ax)      # 
ret
```

這段程式碼在進入臨界區之前，會先把 `mutex` 的位址推入堆疊，然後呼叫
`.lock` 函式，用 `xchg`（原子交換）指令實作忙碌等待鎖（spin lock）；
臨界區載入 `count` 的值、把它加 1、再存回去；離開臨界區之後，再呼叫
`.unlock` 釋放鎖。之後遞減迴圈計數器（存在 `%bx` 中），檢查是否還要
繼續迴圈。

```sh
prompt> ./x86_zh.py -p looping-race-withlock-withcallret.s -t 2 -a bx=1 -M count -c

count         執行緒 0                執行緒 1          

    0   
    0   1000 push mutex
    0   1001 call .lock
    0   1013 mov  -4(%sp), %ax
    0   1014 mov  $1, %cx
    0   1015 xchg %cx, (%ax)
    0   1016 test $0, %cx
    0   1017 jne  .acquire
    0   1018 ret
    0   1002 pop
    0   1003 mov  count, %ax
    0   1004 add  $1, %ax
    1   1005 mov  %ax, count
    1   1006 push mutex
    1   1007 call .unlock
    1   1019 mov  -4(%sp), %ax
    1   1020 mov  $0, (%ax)
    1   1021 ret
    1   1008 pop
    1   1009 sub  $1, %bx
    1   1010 test $0, %bx
    1   1011 jgt .top
    1   1012 halt
    1   ----- 結束並切換(Halt;Switch) -----  ----- 結束並切換(Halt;Switch) -----  
    1                            1000 push mutex
    1                            1001 call .lock
    1                            1013 mov  -4(%sp), %ax
    1                            1014 mov  $1, %cx
    1                            1015 xchg %cx, (%ax)
    1                            1016 test $0, %cx
    1                            1017 jne  .acquire
    1                            1018 ret
    1                            1002 pop
    1                            1003 mov  count, %ax
    1                            1004 add  $1, %ax
    2                            1005 mov  %ax, count
    2                            1006 push mutex
    2                            1007 call .unlock
    2                            1019 mov  -4(%sp), %ax
    2                            1020 mov  $0, (%ax)
    2                            1021 ret
    2                            1008 pop
    2                            1009 sub  $1, %bx
    2                            1010 test $0, %bx
    2                            1011 jgt .top
    2                            1012 halt
```

在這裡你可以看到每個執行緒各執行了一次臨界區，因為有鎖保護，兩次
對 `count` 的遞增完全不會互相干擾，最後 `count` 正確地變成 2。

「結束並切換（Halt;Switch）」這一行，是在某個執行緒 halt、必須切換到
另一個執行緒時才會印出來的。

最後一個範例：執行同樣的程式，但把中斷頻率調小，這樣可以看到執行緒
在鎖內部也可能被中斷、交錯執行：

```sh
prompt> ./x86_zh.py -p looping-race-withlock-withcallret.s -t 2 -a bx=1 -M count -i 2

count         執行緒 0                執行緒 1          

    ?   
    ?   1000 push mutex
    ?   1001 call .lock
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1000 push mutex
    ?                            1001 call .lock
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1013 mov  -4(%sp), %ax
    ?   1014 mov  $1, %cx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1013 mov  -4(%sp), %ax
    ?                            1014 mov  $1, %cx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1015 xchg %cx, (%ax)
    ?   1016 test $0, %cx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?                            1015 xchg %cx, (%ax)
    ?                            1016 test $0, %cx
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ?   1017 jne  .acquire
    ?   1018 ret
    ?   ------ 中斷(Interrupt) ------  ------ 中斷(Interrupt) ------  
    ...（以下省略，可自行執行查看完整輸出）
```

如你所見，透過 `-i 2` 這個旗標，每個執行緒每執行 2 道指令就會被中斷
一次。你可以自己動手追蹤 `count` 與 `mutex` 的值，驗證鎖是否確實避免
了兩個執行緒同時進入臨界區。

現在，讓我們再多介紹一些這個模擬器可以模擬的內容。完整的暫存器
集合是：`%ax, %bx, %cx, %dx, %ex, %fx`，加上 PC 以及堆疊指標 `%sp`。

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

neg register                # 對暫存器的內容取負號

test immediate, register    # 比較立即值與暫存器（設定條件碼）
test register, immediate    # 同上，但比較暫存器與立即值
test register, register     # 同上，但比較暫存器與暫存器

jne                         # 若比較結果不相等則跳躍
je                          #                 ... 相等
jlt                         #     ... 第二個值小於第一個
jlte                        #               ... 小於等於
jgt                         #            ... 大於
jgte                        #               ... 大於等於

push memory or register     # 把記憶體或暫存器中的值推入堆疊
                            # 堆疊由 sp 暫存器定義
pop [register]              # 從堆疊彈出一個值（可選擇存進暫存器）
call label                  # 呼叫標籤所在的函式

xchg register, memory       # 原子交換（atomic exchange）：
                            #   把暫存器的值放進記憶體
                            #   並把記憶體原本的內容傳回暫存器
                            # 這兩件事會原子性地一起完成

yield                       # 切換到就緒佇列中的下一個執行緒

nop                         # 無作用（no op）
```

補充說明：
- 'immediate'（立即值）的格式是 `$數字`
- 'memory'（記憶體）的格式是 'number' 或 '(reg)' 或 'number(reg)' 或
  'number(reg,reg)' 或 'number(reg,reg,scale)'（如前面所述）
- 'register'（暫存器）是 %ax、%bx、%cx、%dx、%ex、%fx、%sp 其中之一

最後，用 `-h` 旗標可以看到模擬器完整的選項清單：

```sh
prompt> ./x86_zh.py -h

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
  -P PROCSCHED, --procsched=PROCSCHED
                        精確控制哪個執行緒在何時執行
  -r, --randints        中斷時機是否隨機決定
  -a ARGV, --argv=ARGV  以逗號分隔的各執行緒引數（例如 ax=1,ax=2 會把執行緒 0 的
                        ax 暫存器設為 1，執行緒 1 的 ax 暫存器設為 2）；同一個
                        執行緒若要設定多個暫存器，用冒號分隔（例如 ax=1:bx=2,cx=3
                        會設定執行緒 0 的 ax 與 bx，以及執行緒 1 的 cx）
  -L LOADADDR, --loadaddr=LOADADDR
                        程式碼載入的位址
  -m MEMSIZE, --memsize=MEMSIZE
                        位址空間大小（KB）
  -M MEMTRACE, --memtrace=MEMTRACE
                        以逗號分隔的待追蹤位址清單（例如 20000,20001）
  -R REGTRACE, --regtrace=REGTRACE
                        以逗號分隔的待追蹤暫存器清單（例如 ax,bx,cx,dx）
  -C, --cctrace         是否要追蹤條件碼
  -S, --printstats      印出一些額外的統計資訊
  -v, --verbose         印出一些額外的詳細資訊
  -H HEADERCOUNT, --headercount=HEADERCOUNT
                        多久重印一次表頭
  -c, --compute         幫我計算答案
```

大部分選項都相當直觀。使用 `-r` 會開啟隨機中斷（由 `-i` 指定的
intfreq 為上限，介於 1 到 intfreq 之間隨機取值），這樣寫作業時可以
增加一點趣味。

- `-P` 讓你精確指定哪個執行緒在何時執行；例如 `11000` 代表先讓執行緒
  1 執行 2 道指令，再讓執行緒 0 執行 3 道指令，然後重複這個順序
- `-L` 指定程式碼要載入到位址空間的哪個位置。
- `-m` 指定位址空間的大小（以 KB 為單位）。
- `-S` 印出一些額外的統計資訊。
- `-c` 可以讓你看到被追蹤的暫存器或記憶體的實際數值（否則只會顯示
  問號）。
- `-H` 讓你指定多久重印一次表頭（在追蹤紀錄很長的時候很好用）。

現在你已經掌握了基本用法；接著請閱讀章節最後的問題，更深入研究鎖
與相關議題。

---

補充說明：這份文件與 `x86_zh.py` 只翻譯了介面文字（命令列選項說明、
執行時印出的訊息，以及程式內的註解），模擬邏輯本身與原始的 `x86.py`
完全一致，兩者對相同的參數與亂數種子會算出完全相同的結果，只是顯示
的語言不同。原始 `README.md` 中示範「無鎖競爭」情境時所用的
`looping-race-nolock.s`，在這個目錄底下實際上並不存在（可能是文件
沿用自 `threads-intro` 目錄時未同步更新），因此本文改用目錄中實際
存在、且更切合本章主題的 `looping-race-withlock-withcallret.s` 來
示範（一個用鎖保護臨界區的版本）；除此之外的所有範例指令與輸出，
皆為直接執行 `x86_zh.py` 得到的真實結果。原始英文版本仍保留在
`x86.py` 與 `README.md` 中，未做任何更動。
