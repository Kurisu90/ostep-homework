
# 概觀

`process-run_zh.py` 是 `process-run.py` 的中文版本，功能完全相同，
只是把所有的說明文字、命令列選項說明，以及執行時印出的訊息都換成了
中文，方便你觀察一個行程在 CPU 上執行時，它的狀態是如何變化的。就
像課本內文所描述的，行程可以處於幾種不同的狀態：

```sh
執行中（RUNNING）- 這個行程目前正在使用 CPU
就緒（READY）  - 這個行程現在「可以」使用 CPU
          但（很遺憾）CPU 正被別的行程佔用
阻塞（BLOCKED）- 這個行程正在等待 I/O
          （例如，它對磁碟發出了一個請求）
結束（DONE）    - 這個行程已經執行完畢
```

在這份作業中，我們會觀察程式執行時這些行程狀態是如何變化的，藉此
更進一步了解這些機制實際上是怎麼運作的。

要執行程式並看到它的選項，輸入：

```sh
prompt> ./process-run_zh.py -h
```

如果這樣不能執行，在指令前面加上 `python`，像這樣：

```sh
prompt> python process-run_zh.py -h
```

你應該會看到這樣的內容：

```sh
Usage: process-run_zh.py [options]

Options:
  -h, --help            show this help message and exit
  -s SEED, --seed=SEED  隨機種子
  -P PROGRAM, --program=PROGRAM
                        更精細地控制程式內容
  -l PROCESS_LIST, --processlist=PROCESS_LIST
                        以逗號分隔的行程清單，格式為 X1:Y1,X2:Y2,...，其中 X 是該行程要執行的指令數量，Y
                        是一個指令屬於使用 CPU 或發出 IO 的機率（0 到 100）（也就是說，如果 Y 是
                        100，代表這個行程只會使用 CPU，完全不會發出 I/O；如果 Y 是 0，代表這個行程只會發出 I/O）
  -L IO_LENGTH, --iolength=IO_LENGTH
                        一次 IO 要花多久時間
  -S PROCESS_SWITCH_BEHAVIOR, --switch=PROCESS_SWITCH_BEHAVIOR
                        何時要切換行程：SWITCH_ON_IO、SWITCH_ON_END
  -I IO_DONE_BEHAVIOR, --iodone=IO_DONE_BEHAVIOR
                        IO 結束時的行為：IO_RUN_LATER、IO_RUN_IMMEDIATE
  -c                    幫我計算答案
  -p, --printstats      最後印出統計數據；只有搭配 -c 旗標時才有用（否則不會印出統計數據）
```

（`-h, --help` 那一行是 optparse 套件內建、寫死的英文文字，無法從程
式裡改成中文，因此保留原樣；其餘每一項選項的說明都已翻譯成中文。）

最重要、最需要理解的選項是 PROCESS_LIST（透過 `-l` 或
`--processlist` 旗標指定），它精確地定義了每一個要執行的程式（也就
是「行程」）會做些什麼。一個行程是由一連串指令組成的，而每一條指令
只能做兩件事情之一：
- 使用 CPU
- 發出一次 I/O（然後等待它完成）

當一個行程只使用 CPU（完全不做 I/O）時，它應該只會在「執行中
（RUNNING）」與「就緒（READY，等著被排到 CPU）」這兩個狀態之間來回
切換。舉例來說，下面是一個很簡單的例子：只執行一個程式，而且這個程
式只使用 CPU（完全不做 I/O）。

```sh
prompt> ./process-run_zh.py -l 5:100
請寫出執行這些行程時會發生的完整過程（trace）：
行程 0
  cpu
  cpu
  cpu
  cpu
  cpu

重要行為說明：
  系統會在下列情況切換行程：目前行程執行完畢，或是發出了一次 IO
  發出 IO 之後，發出該 IO 的行程將延後執行（輪到它的時候才執行）

prompt>
```

這裡我們指定的行程是「5:100」，代表它由 5 條指令組成，而且每條指令
是 CPU 指令的機率是 100%。

你可以加上 `-c` 旗標，讓程式直接幫你算出答案，看看這個行程實際上會
發生什麼事：

```sh
prompt> ./process-run_zh.py -l 5:100 -c
Time        PID: 0           CPU           IOs
  1         執行:cpu             1          
  2         執行:cpu             1          
  3         執行:cpu             1          
  4         執行:cpu             1          
  5         執行:cpu             1          
```

這個結果不算太有趣：這個行程單純處於「執行中」狀態直到結束，整個
過程都在使用 CPU、讓 CPU 保持忙碌，完全沒有發出任何 I/O。

讓我們把情況弄得稍微複雜一點，改成同時執行兩個行程：

```sh
prompt> ./process-run_zh.py -l 5:100,5:100
請寫出執行這些行程時會發生的完整過程（trace）：
行程 0
  cpu
  cpu
  cpu
  cpu
  cpu

行程 1
  cpu
  cpu
  cpu
  cpu
  cpu

重要行為說明：
  系統會在下列情況切換行程：目前行程執行完畢，或是發出了一次 IO
  發出 IO 之後，發出該 IO 的行程將延後執行（輪到它的時候才執行）

```

這次會執行兩個不同的行程，兩者一樣都只使用 CPU。那作業系統實際上
會怎麼執行它們呢？來看看結果：

```sh
prompt> ./process-run_zh.py -l 5:100,5:100 -c
Time        PID: 0        PID: 1           CPU           IOs
  1         執行:cpu            就緒             1          
  2         執行:cpu            就緒             1          
  3         執行:cpu            就緒             1          
  4         執行:cpu            就緒             1          
  5         執行:cpu            就緒             1          
  6             結束        執行:cpu             1          
  7             結束        執行:cpu             1          
  8             結束        執行:cpu             1          
  9             結束        執行:cpu             1          
 10             結束        執行:cpu             1          
```

如上所示，一開始「行程編號」（或稱「PID」）為 0 的行程先執行，行程
1 則處於「就緒」狀態，等待著、直到 0 執行完畢。當 0 完成後，它會進入
「結束」狀態，接著換 1 開始執行。等到 1 也完成之後，整個 trace 就結
束了。

在進入習題之前，我們再看最後一個例子。在這個例子中，行程只會不斷
發出 I/O 請求。這裡我們用 `-L` 旗標指定每次 I/O 需要花費 5 個時間單
位才能完成。

```sh
prompt> ./process-run_zh.py -l 3:0 -L 5
請寫出執行這些行程時會發生的完整過程（trace）：
行程 0
  io
  io_done
  io
  io_done
  io
  io_done

重要行為說明：
  系統會在下列情況切換行程：目前行程執行完畢，或是發出了一次 IO
  發出 IO 之後，發出該 IO 的行程將延後執行（輪到它的時候才執行）

```

你覺得這個執行過程（trace）會長什麼樣子呢？來看看結果：

```sh
prompt> ./process-run_zh.py -l 3:0 -L 5 -c
Time        PID: 0           CPU           IOs
  1          執行:io             1          
  2             阻塞                           1
  3             阻塞                           1
  4             阻塞                           1
  5             阻塞                           1
  6             阻塞                           1
  7*    執行:io_done             1          
  8          執行:io             1          
  9             阻塞                           1
 10             阻塞                           1
 11             阻塞                           1
 12             阻塞                           1
 13             阻塞                           1
 14*    執行:io_done             1          
 15          執行:io             1          
 16             阻塞                           1
 17             阻塞                           1
 18             阻塞                           1
 19             阻塞                           1
 20             阻塞                           1
 21*    執行:io_done             1          
```

如你所見，這個程式只是連續發出三次 I/O。每次發出 I/O 時，行程就會
進入「阻塞」狀態，而在裝置忙著處理這次 I/O 的期間，CPU 是閒置的。

為了處理 I/O 完成後的後續動作，模擬器會再多執行一個 CPU 動作。要注
意的是，用單一條指令同時代表「發起」與「完成」I/O 並不完全寫實，這
裡只是為了簡化而這樣設計。

我們印出一些統計數據來看看（跟上面同樣的指令，只是多加上 `-p`
旗標），觀察整體的行為：

```sh
prompt> ./process-run_zh.py -l 3:0 -L 5 -c -p
...
統計：總時間 21
統計：CPU 忙碌 6（28.57%）
統計：IO 忙碌  15（71.43%）
```

如你所見，這個 trace 總共花了 21 個時脈刻度（clock tick），但 CPU
忙碌的時間卻不到 30%；相對地，I/O 裝置反而相當忙碌。一般來說，我們
希望所有裝置都能盡量保持忙碌，這樣資源運用才會比較有效率。

還有幾個其他重要的旗標：
```sh
  -s SEED, --seed=SEED  隨機種子
    這讓你可以隨機產生出各式各樣不同的工作負載

  -L IO_LENGTH, --iolength=IO_LENGTH
    決定 I/O 要花多久時間才能完成（預設是 5 個時脈刻度）

  -S PROCESS_SWITCH_BEHAVIOR, --switch=PROCESS_SWITCH_BEHAVIOR
                        何時要切換行程：SWITCH_ON_IO、SWITCH_ON_END
    決定何時要切換到另一個行程：
    - SWITCH_ON_IO：當行程發出一次 IO 時就切換
    - SWITCH_ON_END：只有在目前行程結束時才切換

  -I IO_DONE_BEHAVIOR, --iodone=IO_DONE_BEHAVIOR
                        IO 結束時的行為：IO_RUN_LATER、IO_RUN_IMMEDIATE
    決定一個行程發出 IO 之後，什麼時候會被排入執行：
    - IO_RUN_IMMEDIATE：立刻切換去執行這個行程
    - IO_RUN_LATER：等到自然輪到它的時候才執行
      （實際情況要看行程切換的行為設定而定）
```

現在請你去回答本章章節後面的習題，藉此學到更多相關知識吧。

---

補充說明：這份文件與 `process-run_zh.py` 只翻譯了介面文字（命令列選
項說明、執行時印出的訊息，以及程式內的註解），排程邏輯本身與原始的
`process-run.py` 完全一致，兩者對相同的參數與亂數種子會算出完全相
同的結果，只是顯示的語言不同（部分表格欄位因中文字元較寬，視覺上
的對齊可能與英文版略有落差，但數值內容完全相同）。原始英文版本仍
保留在 `process-run.py` 與 `README.md` 中，未做任何更動。
