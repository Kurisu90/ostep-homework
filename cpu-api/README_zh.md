
# 概觀

這一章相關的模擬器現在有兩個。第一個是 `fork.py`（中文版：
`fork_zh.py`），是一個簡單的工具，用來顯示行程被建立與結束時，
「行程樹」長什麼樣子。詳細說明請見[這裡](README-fork_zh.md)。

第二個是 `generator.py`（中文版：`generator_zh.py`），它會產生真正
會用到 `fork()`、`wait()`、`exit()` 的 C 程式，讓你看看 `fork` 在實
際執行的程式中是怎麼運作的。詳細說明請見[這裡](README-generator_zh.md)。

---

補充說明：`README_zh.md`、`README-fork_zh.md`、`README-generator_zh.md`
以及 `fork_zh.py`、`generator_zh.py`，都只是把介面文字（說明文件、
命令列選項說明、執行時印出的訊息、程式內的註解）翻譯成中文，程式邏
輯與原始的 `fork.py`、`generator.py` 完全一致。原始英文檔案（
`README.md`、`README-fork.md`、`README-generator.md`、`fork.py`、
`generator.py`）皆未做任何更動。
