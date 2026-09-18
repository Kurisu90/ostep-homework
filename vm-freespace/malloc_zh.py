#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import random
from optparse import OptionParser

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

class malloc:
    def __init__(self, size, start, headerSize, policy, order, coalesce, align):
        # 空間大小
        self.size        = size

        # 假想標頭（header）的相關資訊
        self.headerSize  = headerSize

        # 初始化空閒串列
        self.freelist    = []
        self.freelist.append((start, size))

        # 記錄指標到大小的對應關係
        self.sizemap     = {}

        # 搜尋策略
        self.policy       = policy
        assert(self.policy in ['FIRST', 'BEST', 'WORST'])

        # 串列排序方式
        self.returnPolicy = order
        assert(self.returnPolicy in ['ADDRSORT', 'SIZESORT+', 'SIZESORT-', 'INSERT-FRONT', 'INSERT-BACK'])

        # 這裡做的是很陽春的「整份串列合併」，不過沒關係
        self.coalesce     = coalesce

        # 對齊大小（-1 代表不對齊）
        self.align        = align
        assert(self.align == -1 or self.align > 0)

    def addToMap(self, addr, size):
        assert(addr not in self.sizemap)
        self.sizemap[addr] = size
        # print('把', addr, '加入對應表，大小為', size)

    def malloc(self, size):
        if self.align != -1:
            left = size % self.align
            if left != 0:
                diff = self.align - left
            else:
                diff = 0
            # print('對齊：把 %d 加到 %d 上' % (diff, size))
            size += diff

        size += self.headerSize

        bestIdx  = -1
        if self.policy == 'BEST':
            bestSize = self.size + 1
        elif self.policy == 'WORST' or self.policy == 'FIRST':
            bestSize = -1

        count = 0

        for i in range(len(self.freelist)):
            eaddr, esize = self.freelist[i][0], self.freelist[i][1]
            count   += 1
            if esize >= size and ((self.policy == 'BEST'  and esize < bestSize) or
                                  (self.policy == 'WORST' and esize > bestSize) or
                                  (self.policy == 'FIRST')):
                bestAddr = eaddr
                bestSize = esize
                bestIdx  = i
                if self.policy == 'FIRST':
                    break

        if bestIdx != -1:
            if bestSize > size:
                # print('分割', bestAddr, size)
                self.freelist[bestIdx] = (bestAddr + size, bestSize - size)
                self.addToMap(bestAddr, size)
            elif bestSize == size:
                # print('完全吻合（不用分割）', bestAddr, size)
                self.freelist.pop(bestIdx)
                self.addToMap(bestAddr, size)
            else:
                abort('不應該執行到這裡')
            return (bestAddr, count)

        # print('*** 找不到合適的空間', size)
        return (-1, count)

    def free(self, addr):
        # 簡單地放回串列尾端，不做合併
        if addr not in self.sizemap:
            return -1

        size = self.sizemap[addr]
        if self.returnPolicy == 'INSERT-BACK':
            self.freelist.append((addr, size))
        elif self.returnPolicy == 'INSERT-FRONT':
            self.freelist.insert(0, (addr, size))
        elif self.returnPolicy == 'ADDRSORT':
            self.freelist.append((addr, size))
            self.freelist = sorted(self.freelist, key=lambda e: e[0])
        elif self.returnPolicy == 'SIZESORT+':
            self.freelist.append((addr, size))
            self.freelist = sorted(self.freelist, key=lambda e: e[1], reverse=False)
        elif self.returnPolicy == 'SIZESORT-':
            self.freelist.append((addr, size))
            self.freelist = sorted(self.freelist, key=lambda e: e[1], reverse=True)

        # 這裡的合併並不追求效率或真實感……
        if self.coalesce == True:
            self.newlist = []
            self.curr    = self.freelist[0]
            for i in range(1, len(self.freelist)):
                eaddr, esize = self.freelist[i]
                if eaddr == (self.curr[0] + self.curr[1]):
                    self.curr = (self.curr[0], self.curr[1] + esize)
                else:
                    self.newlist.append(self.curr)
                    self.curr = eaddr, esize
            self.newlist.append(self.curr)
            self.freelist = self.newlist

        del self.sizemap[addr]
        return 0

    def dump(self):
        print('空閒串列［大小 %d］：' % len(self.freelist), end='')
        for e in self.freelist:
            print('[ addr:%d sz:%d ]' % (e[0], e[1]), end='')
        print('')


#
# 主程式
#
parser = OptionParser()

parser.add_option('-s', '--seed',        default=0,          help='隨機種子',                                   action='store', type='int',    dest='seed')
parser.add_option('-S', '--size',        default=100,        help='堆積（heap）的大小',                          action='store', type='int',    dest='heapSize')
parser.add_option('-b', '--baseAddr',    default=1000,       help='堆積的起始位址',                              action='store', type='int',    dest='baseAddr')
parser.add_option('-H', '--headerSize',  default=0,          help='標頭（header）的大小',                        action='store', type='int',    dest='headerSize')
parser.add_option('-a', '--alignment',   default=-1,         help='將配置的單位對齊到此大小；-1 代表不對齊',      action='store', type='int',    dest='alignment')
parser.add_option('-p', '--policy',      default='BEST',     help='串列搜尋策略（BEST、WORST、FIRST）',          action='store', type='string', dest='policy')
parser.add_option('-l', '--listOrder',   default='ADDRSORT', help='串列排序方式（ADDRSORT、SIZESORT+、SIZESORT-、INSERT-FRONT、INSERT-BACK）', action='store', type='string', dest='order')
parser.add_option('-C', '--coalesce',    default=False,      help='是否合併空閒串列？',                          action='store_true',           dest='coalesce')
parser.add_option('-n', '--numOps',      default=10,         help='要產生的隨機操作數量',                        action='store', type='int',    dest='opsNum')
parser.add_option('-r', '--range',       default=10,         help='配置大小的上限',                              action='store', type='int',    dest='opsRange')
parser.add_option('-P', '--percentAlloc',default=50,         help='操作中屬於配置（alloc）的比例',                action='store', type='int',    dest='opsPAlloc')
parser.add_option('-A', '--allocList',   default='',         help='不用隨機產生，改用指定的操作清單（例如 +10,-0 等）', action='store', type='string', dest='opsList')
parser.add_option('-c', '--compute',     default=False,      help='幫我計算答案',                                action='store_true',           dest='solve')

(options, args) = parser.parse_args()

m = malloc(int(options.heapSize), int(options.baseAddr), int(options.headerSize),
           options.policy, options.order, options.coalesce, options.alignment)

print('種子(seed)', options.seed)
print('大小(size)', options.heapSize)
print('起始位址(baseAddr)', options.baseAddr)
print('標頭大小(headerSize)', options.headerSize)
print('對齊(alignment)', options.alignment)
print('策略(policy)', options.policy)
print('排序方式(listOrder)', options.order)
print('合併(coalesce)', options.coalesce)
print('操作數量(numOps)', options.opsNum)
print('範圍(range)', options.opsRange)
print('配置比例(percentAlloc)', options.opsPAlloc)
print('操作清單(allocList)', options.opsList)
print('計算答案(compute)', options.solve)
print('')

percent = int(options.opsPAlloc) / 100.0

random_seed(int(options.seed))
p = {}
L = []
assert(percent > 0)

if options.opsList == '':
    c = 0
    j = 0
    while j < int(options.opsNum):
        pr = False
        if random.random() < percent:
            size     = int(random.random() * int(options.opsRange)) + 1
            ptr, cnt = m.malloc(size)
            if ptr != -1:
                p[c] = ptr
                L.append(c)
            print('ptr[%d] = Alloc(%d)' % (c, size), end='')
            if options.solve == True:
                print(' 傳回 %d（搜尋了 %d 個元素）' % (ptr + options.headerSize, cnt))
            else:
                print(' 傳回 ?')
            c += 1
            j += 1
            pr = True
        else:
            if len(p) > 0:
                # 隨機挑一個來釋放
                d = int(random.random() * len(L))
                rc = m.free(p[L[d]])
                print('Free(ptr[%d])' % L[d], )
                if options.solve == True:
                    print('傳回 %d' % rc)
                else:
                    print('傳回 ?')
                del p[L[d]]
                del L[d]
                # print('DEBUG p', p)
                # print('DEBUG L', L)
                pr = True
                j += 1
        if pr:
            if options.solve == True:
                m.dump()
            else:
                print('串列狀態？')
            print('')
else:
    c = 0
    for op in options.opsList.split(','):
        if op[0] == '+':
            # 配置！
            size     = int(op.split('+')[1])
            ptr, cnt = m.malloc(size)
            if ptr != -1:
                p[c] = ptr
            print('ptr[%d] = Alloc(%d)' % (c, size), end='')
            if options.solve == True:
                print(' 傳回 %d（搜尋了 %d 個元素）' % (ptr, cnt))
            else:
                print(' 傳回 ?')
            c += 1
        elif op[0] == '-':
            # 釋放
            index = int(op.split('-')[1])
            if index >= len(p):
                print('無效的 Free：略過')
                continue
            print('Free(ptr[%d])' % index, )
            rc = m.free(p[index])
            if options.solve == True:
                print('傳回 %d' % rc)
            else:
                print('傳回 ?')
        else:
            abort('操作格式錯誤：必須是 +大小 或 -索引')
        if options.solve == True:
            m.dump()
        else:
            print('串列狀態？')
        print('')
