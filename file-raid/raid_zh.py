#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import math
import random
from optparse import OptionParser

# 讓 Python2 與 Python3 的行為一致 -- 有夠蠢的作法
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

# 傳輸到 RAID 的最小單位
BLOCKSIZE = 4096

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

class disk:
    def __init__(self, seekTime=10, xferTime=0.1, queueLen=8):
        # 這兩個都是毫秒
        # seek 是尋軌的時間（單純的固定值）
        # transfer 是讀取一個區塊所需的時間
        self.seekTime = seekTime
        self.xferTime = xferTime

        # 排程佇列的長度
        self.queueLen = queueLen

        # 目前的位置：故意設成負的，這樣不論第一次
        # 讀取的位址是什麼，都一定會觸發一次尋軌
        self.currAddr = -10000

        # 佇列
        self.queue    = []

        # 磁碟的幾何配置
        self.numTracks      = 100
        self.blocksPerTrack = 100
        self.blocksPerDisk  = self.numTracks * self.blocksPerTrack

        # 統計數據
        self.countIO   = 0
        self.countSeq  = 0
        self.countNseq = 0
        self.countRand = 0
        self.utilTime  = 0

    def stats(self):
        return (self.countIO, self.countSeq, self.countNseq, self.countRand, self.utilTime)

    def enqueue(self, addr):
        assert(addr < self.blocksPerDisk)
        self.countIO += 1

        # 檢查這次存取是在同一條磁軌上，還是不同的磁軌
        currTrack = int(self.currAddr / self.numTracks)
        newTrack  = int(addr / self.numTracks)

        # 絕對值差距
        diff = addr - self.currAddr
        if diff < 0:
            diff = -diff

        # 如果在同一條磁軌上……
        if currTrack == newTrack or diff < self.blocksPerTrack:
            if diff == 1:
                self.countSeq += 1
            else:
                self.countNseq += 1
            self.utilTime += (diff * self.xferTime)
        else:
            self.countRand += 1
            self.utilTime += (self.seekTime + self.xferTime)
        self.currAddr = addr

    def go(self):
        return self.utilTime

class raid:
    def __init__(self, chunkSize='4k', numDisks=4, level=0, timing=False, reverse=False, solve=False, raid5type='LS'):
        chunkSize      = int(convert(chunkSize))
        self.chunkSize = int(chunkSize / BLOCKSIZE)
        self.numDisks  = numDisks
        self.raidLevel = level
        self.timing    = timing
        self.reverse   = reverse
        self.solve     = solve
        self.raid5type = raid5type

        if (chunkSize % BLOCKSIZE) != 0:
            print('chunk 大小 (%d) 必須是 block 大小 (%d) 的倍數：%d' % (chunkSize, BLOCKSIZE, self.chunkSize % BLOCKSIZE))
            exit(1)
        if self.raidLevel == 1 and numDisks % 2 != 0:
            print('raid1：磁碟數量 (%d) 必須是 2 的倍數' % numDisks)
            exit(1)

        if self.raidLevel == 4:
            self.blocksInStripe = (self.numDisks - 1) * self.chunkSize
            self.pdisk = self.numDisks - 1
        if self.raidLevel == 5:
            self.blocksInStripe = (self.numDisks - 1) * self.chunkSize
            self.pdisk = -1

        self.disks = []
        for i in range(self.numDisks):
            self.disks.append(disk())

    # 印出每個磁碟的統計數據
    def stats(self, totalTime):
        for d in range(self.numDisks):
            s = self.disks[d].stats()
            if totalTime > 0.0:
                util = (100.0*float(s[4])/totalTime)
            else:
                util = 0.0
            if s[4] == totalTime:
                print('磁碟:%d  忙碌: %.2f  I/Os: %5d (循序:%d 近似:%d 隨機:%d)' % (d, util, s[0], s[1], s[2], s[3]))
            elif s[4] == 0:
                print('磁碟:%d  忙碌:   %.2f  I/Os: %5d (循序:%d 近似:%d 隨機:%d)' % (d, util, s[0], s[1], s[2], s[3]))
            else:
                print('磁碟:%d  忙碌:  %.2f  I/Os: %5d (循序:%d 近似:%d 隨機:%d)' % (d, util, s[0], s[1], s[2], s[3]))

    # 全域的 enqueue 函式
    def enqueue(self, addr, size, isWrite):
        # 要不要印出邏輯操作？
        if self.timing == False:
            if self.solve or self.reverse==False:
                if isWrite:
                    print('邏輯寫入到  addr:%d size:%d' % (addr, size * BLOCKSIZE))
                else:
                    print('邏輯讀取從 addr:%d size:%d' % (addr, size * BLOCKSIZE))
                if self.solve == False:
                    print('  實際的實體讀寫操作是？\n')
            else:
                print('邏輯操作是 ?')

        # 要不要印出實體操作？
        if self.timing == False and (self.solve or self.reverse==True):
            self.printPhysical = True
        else:
            self.printPhysical = False

        if self.raidLevel == 0:
            self.enqueue0(addr, size, isWrite)
        elif self.raidLevel == 1:
            self.enqueue1(addr, size, isWrite)
        elif self.raidLevel == 4 or self.raidLevel == 5:
            self.enqueue45(addr, size, isWrite)

    # 依序處理每個磁碟的工作負載，回傳最後的完成時間
    def go(self):
        tmax = 0
        for d in range(self.numDisks):
            t = self.disks[d].go()
            if t > tmax:
                tmax = t
        return tmax

    # 輔助函式
    def doSingleRead(self, disk, off, doNewline=False):
        if self.printPhysical:
            print('  read  [disk %d, offset %d]  ' % (disk, off), end='')
            if doNewline:
                print('')
        self.disks[disk].enqueue(off)

    def doSingleWrite(self, disk, off, doNewline=False):
        if self.printPhysical:
            print('  write [disk %d, offset %d]  ' % (disk, off), end='')
            if doNewline:
                print('')
        self.disks[disk].enqueue(off)

    #
    # RAID 0（striping，分條）的對應方式
    #
    def bmap0(self, bnum):
        cnum = int(bnum / self.chunkSize)
        coff = bnum % self.chunkSize
        return (cnum % self.numDisks, int(int(cnum / self.numDisks) * self.chunkSize + coff))

    def enqueue0(self, addr, size, isWrite):
        # 可以忽略 isWrite，因為 striping 的 I/O 模式讀寫都一樣
        for b in range(addr, addr+size):
            (disk, off) = self.bmap0(b)
            if isWrite:
                self.doSingleWrite(disk, off, True)
            else:
                self.doSingleRead(disk, off, True)
        if self.timing == False and self.printPhysical:
            print('')

    #
    # RAID 1（mirroring，鏡像）的對應方式
    #
    def bmap1(self, bnum):
        cnum = int(bnum / self.chunkSize)
        coff = bnum % self.chunkSize
        disk = int(2 * (cnum % int(self.numDisks / 2)))
        return (disk, disk + 1, int(int(cnum / int(self.numDisks / 2))) * self.chunkSize + coff)

    def enqueue1(self, addr, size, isWrite):
        for b in range(addr, addr+size):
            (disk1, disk2, off) = self.bmap1(b)
            # print 'enqueue:', addr, size, '-->', m
            if isWrite:
                self.doSingleWrite(disk1, off, False)
                self.doSingleWrite(disk2, off, True)
            else:
                # RAID-1 的讀取平衡演算法就在這裡；
                # 其實可以做得更聰明一點──
                # 但這裡只是單純根據磁碟的 offset 來決定，
                # 這樣結果才容易重現
                if off % 2 == 0:
                    self.doSingleRead(disk1, off, True)
                else:
                    self.doSingleRead(disk2, off, True)
        if self.timing == False and self.printPhysical:
            print('')

    #
    # RAID 4（同位檢查磁碟）的對應方式
    #
    # 目前假設只有一顆同位檢查磁碟
    #
    def bmap4(self, bnum):
        cnum = int(bnum / self.chunkSize)
        coff = bnum % self.chunkSize
        return (cnum % (self.numDisks - 1), int(cnum / (self.numDisks - 1)) * self.chunkSize + coff)

    def pmap4(self, snum):
        return self.pdisk

    #
    # RAID 5（輪流的同位檢查）的對應方式
    #
    def __bmap5(self, bnum):
        cnum = int(bnum / self.chunkSize)
        coff = bnum % self.chunkSize
        ddsk = int(cnum / (self.numDisks - 1))
        doff = (ddsk * self.chunkSize) + coff
        disk = cnum % (self.numDisks - 1)
        col = (ddsk % self.numDisks)
        pdisk = (self.numDisks - 1) - col

        # 支援 left-asymmetric 與 left-symmetric 兩種排列方式
        if self.raid5type == 'LA':
            if disk >= pdisk:
                disk += 1
        elif self.raid5type == 'LS':
            disk = (disk - col) % (self.numDisks)
        else:
            print('錯誤：沒有這種 RAID 配置方式')
            exit(1)
        assert(disk != pdisk)
        return (disk, pdisk, doff)

    # 沒錯，這樣寫很懶（重複呼叫 __bmap5 完全是偷懶的行為）
    def bmap5(self, bnum):
        (disk, pdisk, off) = self.__bmap5(bnum)
        return (disk, off)

    # 這裡也一樣懶（重複呼叫 __bmap5 完全是偷懶的行為）
    def pmap5(self, snum):
        (disk, pdisk, off) = self.__bmap5(snum * self.blocksInStripe)
        return pdisk

    # RAID 4/5 用來把某個 stripe 裡的部分區塊寫出去的輔助函式
    def doPartialWrite(self, stripe, begin, end, bmap, pmap):
        numWrites = end - begin
        pdisk     = pmap(stripe)
        if (numWrites + 1) <= (self.blocksInStripe - numWrites):
            # 減法式同位計算（SUBTRACTIVE PARITY）
            # print '減法式'
            offList = []
            for voff in range(begin, end):
                (disk, off) = bmap(voff)
                self.doSingleRead(disk, off)
                if off not in offList:
                    offList.append(off)
            for i in range(len(offList)):
                self.doSingleRead(pdisk, offList[i], i == (len(offList) - 1))
        else:
            # 加法式同位計算（ADDITIVE PARITY）
            # print '加法式'
            stripeBegin = stripe * self.blocksInStripe
            stripeEnd   = stripeBegin + self.blocksInStripe
            for voff in range(stripeBegin, begin):
                (disk, off) = bmap(voff)
                self.doSingleRead(disk, off, (voff == (begin - 1)) and (end == stripeEnd))
            for voff in range(end, stripeEnd):
                (disk, off) = bmap(voff)
                self.doSingleRead(disk, off, voff == (stripeEnd - 1))

        # 寫入：不論減法式或加法式同位計算，這部分都一樣
        offList = []
        for voff in range(begin, end):
            (disk, off) = bmap(voff)
            self.doSingleWrite(disk, off)
            if off not in offList:
                offList.append(off)
        for i in range(len(offList)):
            self.doSingleWrite(pdisk, offList[i], i == (len(offList) - 1))

    # RAID 4/5 的 enqueue 函式
    def enqueue45(self, addr, size, isWrite):
        if self.raidLevel == 4:
            (bmap, pmap) = (self.bmap4, self.pmap4)
        elif self.raidLevel == 5:
            (bmap, pmap) = (self.bmap5, self.pmap5)

        if isWrite == False:
            for b in range(addr, addr+size):
                (disk, off) = bmap(b)
                self.doSingleRead(disk, off)
        else:
            # 一次處理一個 stripe 的寫入請求
            initStripe     = int((addr)            / self.blocksInStripe)
            finalStripe    = int((addr + size - 1) / self.blocksInStripe)

            left  = size
            begin = addr
            for stripe in range(initStripe, finalStripe + 1):
                endOfStripe = (stripe * self.blocksInStripe) + self.blocksInStripe

                if left >= self.blocksInStripe:
                    end = begin + self.blocksInStripe
                else:
                    end = begin + left

                if end >= endOfStripe:
                    end = endOfStripe

                self.doPartialWrite(stripe, begin, end, bmap, pmap)

                left -= (end - begin)
                begin = end

        # 不論哪種情況，都印出這個，讓對應模式下的輸出好看一點
        if self.timing == False and self.printPhysical:
            print('')

#
# 主程式
#
parser = OptionParser()

parser.add_option('-s', '--seed',        default=0,      help='隨機種子',                                             action='store',       type='int',    dest='seed')
parser.add_option('-D', '--numDisks',    default=4,      help='RAID 中的磁碟數量',                                    action='store',       type='int',    dest='numDisks')
parser.add_option('-C', '--chunkSize',   default='4k',   help='RAID 的 chunk 大小',                                   action='store',       type='string', dest='chunkSize')
parser.add_option('-n', '--numRequests', default=10,     help='要模擬的請求數量',                                     action='store',       type='int',    dest='numRequests')
parser.add_option('-S', '--reqSize',     default='4k',   help='請求的大小',                                           action='store',       type='string', dest='size')
parser.add_option('-W', '--workload',    default='rand', help='工作負載類型，"rand"（隨機）或 "seq"（循序）',        action='store',       type='string', dest='workload')
parser.add_option('-w', '--writeFrac',   default=0,      help='寫入比例（100 代表全部寫入，0 代表全部讀取）',        action='store',       type='int',    dest='writeFrac')
parser.add_option('-R', '--randRange',   default=10000,  help='請求的位址範圍（使用 "rand" 工作負載時適用）',        action='store',       type='int',    dest='range')
parser.add_option('-L', '--level',       default=0,      help='RAID 等級（0、1、4、5）',                              action='store',       type='int',    dest='level')
parser.add_option('-5', '--raid5',       default='LS',   help='RAID-5 的配置方式："LS"（左對稱）或 "LA"（左不對稱）', action='store',       type='string', dest='raid5type')
parser.add_option('-r', '--reverse',     default=False,  help='不顯示邏輯操作，改成顯示實體操作',                     action='store_true',                 dest='reverse')
parser.add_option('-t', '--timing',      default=False,  help='使用計時模式，而不是對應模式',                         action='store_true',                 dest='timing')
parser.add_option('-c', '--compute',     default=False,  help='幫我計算答案',                                         action='store_true',                 dest='solve')

(options, args) = parser.parse_args()

print('參數 blockSize（區塊大小）',       BLOCKSIZE)
print('參數 seed（隨機種子）',            options.seed)
print('參數 numDisks（磁碟數量）',        options.numDisks)
print('參數 chunkSize（chunk 大小）',     options.chunkSize)
print('參數 numRequests（模擬請求數量）', options.numRequests)
print('參數 reqSize（請求大小）',         options.size)
print('參數 workload（工作負載類型）',    options.workload)
print('參數 writeFrac（寫入比例）',       options.writeFrac)
print('參數 randRange（隨機請求範圍）',   options.range)
print('參數 level（RAID 等級）',          options.level)
print('參數 raid5（RAID-5 配置類型）',    options.raid5type)
print('參數 reverse（反向模式）',         options.reverse)
print('參數 timing（計時模式）',          options.timing)
print('')

writeFrac = float(options.writeFrac) / 100.0
assert(writeFrac >= 0.0 and writeFrac <= 1.0)

random_seed(options.seed)

size = convert(options.size)
if size % BLOCKSIZE != 0:
    print('錯誤：請求大小 (%d) 必須是 BLOCKSIZE (%d) 的倍數' % (size, BLOCKSIZE))
    exit(1)
size = int(size / BLOCKSIZE)

if options.workload == 'seq' or options.workload == 's' or options.workload == 'sequential':
    workloadIsSequential = True
elif options.workload == 'rand' or options.workload == 'r' or options.workload == 'random':
    workloadIsSequential = False
else:
    print('錯誤：workload 必須是 r/rand/random 或 s/seq/sequential 其中之一')
    exit(1)

assert(options.level == 0 or options.level == 1 or options.level == 4 or options.level == 5)
if options.level != 0 and options.numDisks < 2:
    print('RAID-4 與 RAID-5 需要一個以上的磁碟')
    exit(1)

if options.level == 5 and options.raid5type != 'LA' and options.raid5type != 'LS':
    print('RAID-5 只支援兩種類型：left-asymmetric（LA，左不對稱）與 left-symmetric（LS，左對稱）（%s 不是這兩種之一）' % options.raid5type)
    exit(1)

# 建立 RAID 實體
r = raid(chunkSize=options.chunkSize, numDisks=options.numDisks, level=options.level, timing=options.timing,
         reverse=options.reverse, solve=options.solve, raid5type=options.raid5type)

# 產生請求
off = 0
for i in range(options.numRequests):
    if workloadIsSequential == True:
        blk = off
        off += size
    else:
        blk = int(random.random() * options.range)
    if random.random() < writeFrac:
        print(blk, size)
        r.enqueue(blk, size, True)
    else:
        print(blk, size)
        r.enqueue(blk, size, False)

# 處理請求
t = r.go()

# 如有需要，印出最後的資訊
if options.timing == False:
    print('')
    exit(0)

if options.solve:
    print('')
    r.stats(t)
    print('')
    print('統計 總時間', t)
    print('')
else:
    print('')
    print('請估計這個工作負載大概需要多久才能完成。')
    print('- 每個磁碟大約會收到多少個請求？')
    print('- 有多少個請求是隨機的，多少個是循序的？')
    print('')
