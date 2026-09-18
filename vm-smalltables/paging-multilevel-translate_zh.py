#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
from optparse import OptionParser
import random
import math

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

def convert(size):
    length = len(size)
    lastchar = size[length-1]
    if (lastchar == 'k') or (lastchar == 'K'):
        m = 1024
        nsize = int(size[0:length-1]) * m
    elif (lastchar == 'm') or (lastchar == 'M'):
        m = 1024*1024
        nsize = int(size[0:length-1]) * m
    elif (lastchar == 'g') or (lastchar == 'G'):
        m = 1024*1024*1024
        nsize = int(size[0:length-1]) * m
    else:
        nsize = int(size)
    return nsize

def roundup(size):
    value = 1.0
    while value < size:
        value = value * 2.0
    return value


class OS:
    def __init__(self):
        # 4k 實體記憶體（128 個頁面）
        self.pageSize  = 32
        self.physPages = 128
        self.physMem   = self.pageSize * self.physPages
        self.vaPages   = 1024
        self.vaSize    = self.pageSize * self.vaPages
        self.pteSize   = 1
        self.pageBits  = 5 # 頁面大小取 log

        # 作業系統要追蹤的狀態
        self.usedPages      = []
        self.usedPagesCount = 0
        self.maxPageCount   = int(self.physMem / self.pageSize)

        # （目前）尚未使用任何頁面
        for i in range(0, self.maxPageCount):
            self.usedPages.append(0)

        # 也把記憶體內容都設為 0
        self.memory = []
        for i in range(0, self.physMem):
            self.memory.append(0)

        # 以 PID 為索引的 pdbr 關聯陣列
        self.pdbr = {}

        # 遮罩為 11111 00000 00000 --> 0111 1100 0000 0000
        self.PDE_MASK    = 0x7c00
        self.PDE_SHIFT   = 10

        # 00000 11111 00000 -> 000 0011 1110 0000
        self.PTE_MASK    = 0x03e0
        self.PTE_SHIFT   = 5

        self.VPN_MASK    = self.PDE_MASK | self.PTE_MASK
        self.VPN_SHIFT   = self.PTE_SHIFT

        # 取出虛擬位址最後五個位元
        self.OFFSET_MASK = 0x1f

    def findFree(self):
        assert(self.usedPagesCount < self.maxPageCount)
        look = int(random.random() * self.maxPageCount)
        while self.usedPages[look] == 1:
            look = int(random.random() * self.maxPageCount)
        self.usedPagesCount = self.usedPagesCount + 1
        self.usedPages[look] = 1
        return look

    def initPageDir(self, whichPage):
        whichByte = whichPage << self.pageBits
        for i in range(whichByte, whichByte + self.pageSize):
            self.memory[i] = 0x7f

    def initPageTablePage(self, whichPage):
        self.initPageDir(whichPage)

    def getPageTableEntry(self, virtualAddr, ptePage, printStuff):
        pteBits = (virtualAddr & self.PTE_MASK) >> self.PTE_SHIFT
        pteAddr = (ptePage << self.pageBits) | pteBits
        pte     = self.memory[pteAddr]
        valid   = (pte & 0x80) >> 7
        pfn     = (pte & 0x7f)
        if printStuff == True:
            print('    --> pte 索引:0x%x [十進位 %d] pte 內容:0x%x (valid %d, pfn 0x%02x [十進位 %d])' % (pteBits, pteBits, pte, valid, pfn, pfn))
        return (valid, pfn, pteAddr)

    def getPageDirEntry(self, pid, virtualAddr, printStuff):
        pageDir = self.pdbr[pid]
        pdeBits = (virtualAddr & self.PDE_MASK) >> self.PDE_SHIFT
        pdeAddr = (pageDir << self.pageBits) | pdeBits
        pde     = self.memory[pdeAddr]
        valid   = (pde & 0x80) >> 7
        ptPtr   = (pde & 0x7f)
        if printStuff == True:
            print('  --> pde 索引:0x%x [十進位 %d] pde 內容:0x%x (valid %d, pfn 0x%02x [十進位 %d])' % (pdeBits, pdeBits, pde, valid, ptPtr, ptPtr))
        return (valid, ptPtr, pdeAddr)

    def setPageTableEntry(self, pteAddr, physicalPage):
        self.memory[pteAddr] = 0x80 | physicalPage

    def setPageDirEntry(self, pdeAddr, physicalPage):
        self.memory[pdeAddr] = 0x80 | physicalPage

    def allocVirtualPage(self, pid, virtualPage, physicalPage):
        # 把它轉成虛擬位址，因為程式其他地方都是用虛擬位址（而不是 VPN）
        virtualAddr = virtualPage << self.pageBits
        (valid, ptPtr, pdeAddr) = self.getPageDirEntry(pid, virtualAddr, False)
        if valid == 0:
            # 現在必須配置一頁頁表，並讓 PD 指向它
            assert(ptPtr == 127)
            ptePage = self.findFree()
            self.setPageDirEntry(pdeAddr, ptePage)
            self.initPageTablePage(ptePage)
        else:
            # 否則，只需取出頁表所在頁面的頁碼
            ptePage = ptPtr
        # 現在，也查詢頁表項目，將其標示為有效並填入轉譯結果
        (valid, pfn, pteAddr) = self.getPageTableEntry(virtualAddr, ptePage, False)
        assert(valid == 0)
        assert(pfn == 127)
        self.setPageTableEntry(pteAddr, physicalPage)

    # -2 代表 PTE 錯誤，-1 代表 PDE 錯誤
    def translate(self, pid, virtualAddr):
        (valid, ptPtr, pdeAddr) = self.getPageDirEntry(pid, virtualAddr, True)
        if valid == 1:
            ptePage = ptPtr
            (valid, pfn, pteAddr) = self.getPageTableEntry(virtualAddr, ptePage, True)
            if valid == 1:
                offset = (virtualAddr & self.OFFSET_MASK)
                paddr  = (pfn << self.pageBits) | offset
		# print('     --> pfn 值: %02x  offset 值: %x' % (pfn, offset))
                return paddr
            else:
                return -2
        return -1

    def fillPage(self, whichPage):
        for j in range(0, self.pageSize):
            self.memory[(whichPage * self.pageSize) + j] = int(random.random() * 31)

    def procAlloc(self, pid, numPages):
        # 需要一個 PDBR：在記憶體中找一個位置
        pageDir = self.findFree()
        # print('**配置** 頁目錄', pageDir)
        self.pdbr[pid] = pageDir
        self.initPageDir(pageDir)

        used = {}
        for vp in range(0, self.vaPages):
            used[vp] = 0
        allocatedVPs = []

        for vp in range(0, numPages):
            vp = int(random.random() * self.vaPages)
            while used[vp] == 1:
                vp = int(random.random() * self.vaPages)
            assert(used[vp] == 0)
            used[vp] = 1
            allocatedVPs.append(vp)
            pp = self.findFree()
            # print('**配置** 頁面', pp)
            # print('  嘗試把 vp:%08x 對應到 pp:%08x' % (vp, pp))
            self.allocVirtualPage(pid, vp, pp)
            self.fillPage(pp)
        return allocatedVPs

    def dumpPage(self, whichPage):
        i = whichPage
        for j in range(0, self.pageSize):
            print(self.memory[(i * self.pageSize) + j], end='')
        print('')

    def memoryDump(self):
        for i in range(0, int(self.physMem / self.pageSize)):
            print('頁面 %3d：' %  i, end='')
            for j in range(0, self.pageSize):
                print('%02x' % self.memory[(i * self.pageSize) + j], end='')
            print('')

    def getPDBR(self, pid):
        return self.pdbr[pid]

    def getValue(self, addr):
        return self.memory[addr]

# 在記憶體中配置一些行程
# 在記憶體中配置一些多層頁表
# 製造一點懸疑感：
# 可以檢查 PDBR（目前行程的 page directory 所在的 PFN）
# 可以檢查任何一個頁面的內容
# 也會把頁面填入一些值
# 問題是：給定
#   LOAD VA, R1
# 最後會把什麼值載入 R1？

#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-a', '--allocated', default=64, help='配置的虛擬頁面數量',
                  action='store', type='int', dest='allocated')
parser.add_option('-n', '--addresses', default=10, help='要產生的虛擬位址數量',
                  action='store', type='int', dest='num')
parser.add_option('-c', '--solve', help='幫我計算答案', action='store_true', default=False, dest='solve')


(options, args) = parser.parse_args()

print('參數 隨機種子', options.seed)
print('參數 已配置頁面數',  options.allocated)
print('參數 位址數量',  options.num)
print('')

random_seed(options.seed)

# 開始進行實際的工作
os = OS()
used = os.procAlloc(1, options.allocated)

os.memoryDump()

print('\nPDBR：', os.getPDBR(1), '（十進位）［代表頁目錄存放在這個頁面裡］\n')

for i in range(0, options.num):
    if (random.random() * 100) > 50.0 or i >= len(used):
        vaddr = int(random.random() * 1024 * 32)
    else:
        vaddr = (used[i] << 5) | int(random.random() * 32)
    if options.solve == True:
        print('虛擬位址 0x%04x：' % vaddr)
        r = os.translate(1, vaddr)
        if r > -1:
            print('      --> 轉譯為實體位址 0x%03x --> 值：0x%02x' % (r, os.getValue(r)))
        elif r == -1:
            print('      --> 發生錯誤（page directory 項目無效）')
        else:
            print('      --> 發生錯誤（page table 項目無效）')
    else:
        print('虛擬位址 %04x：會轉譯成哪個實體位址（並讀到什麼值）？還是會發生錯誤？' % vaddr)

print('')

exit(0)
