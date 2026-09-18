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

def abort_if(condition, message):
    if condition:
        print('錯誤：', message)
        exit(1)
    return


#
# 主程式
#
parser = OptionParser()
parser.add_option("-s", "--seed", default=0, help="隨機種子", action="store", type="int", dest="seed")
parser.add_option("-A", "--addresses", default="-1", help="一組以逗號分隔的頁面，用來存取；-1 代表隨機產生", action="store", type="string", dest="addresses")
parser.add_option("-a", "--asize", default="1k", help="位址空間大小（例如 16、64k、32m、1g）", action="store", type="string", dest="asize")
parser.add_option("-p", "--physmem", default="16k", help="實體記憶體大小（例如 16、64k、32m、1g）", action="store", type="string", dest="psize")
parser.add_option("-n", "--numaddrs", default=5, help="要產生的虛擬位址數量", action="store", type="int", dest="num")
parser.add_option("-b", "--b0", default="-1", help="segment 0 base 暫存器的值", action="store", type="string", dest="base0")
parser.add_option("-l", "--l0", default="-1", help="segment 0 limit 暫存器的值", action="store", type="string", dest="len0")
parser.add_option("-B", "--b1", default="-1", help="segment 1 base 暫存器的值", action="store", type="string", dest="base1")
parser.add_option("-L", "--l1", default="-1", help="segment 1 limit 暫存器的值", action="store", type="string", dest="len1")
parser.add_option("-c", help="幫我計算答案", action="store_true", default=False, dest="solve")

(options, args) = parser.parse_args()

print('參數 隨機種子', options.seed)
print('參數 位址空間大小', options.asize)
print('參數 實體記憶體大小', options.psize)
print('')

random_seed(options.seed)
asize = convert(options.asize)
psize = convert(options.psize)
addresses = str(options.addresses)

abort_if(psize <= 4, '必須指定更大的實體記憶體大小')
abort_if(asize == 0, '必須指定一個非零的位址空間大小')
abort_if(psize <= asize, '實體記憶體大小必須大於位址空間大小（此模擬要求如此）')

#
# 需要為分段暫存器產生 base 與 bounds
#
len0 = convert(options.len0)
len1 = convert(options.len1)
base0 = convert(options.base0)
base1 = convert(options.base1)

# 若隨機產生長度，大約設為位址空間大小的 1/4 到 1/2
if len0 == -1:
    len0 = int(asize/4.0 + (asize/4.0 * random.random()))
if len1 == -1:
    len1 = int(asize/4.0 + (asize/4.0 * random.random()))

if base0 == -1 or base1 == -1:
    # 這個限制只是為了讓隨機放置的區段更容易安排位置
    abort_if(psize <= 2 * asize, '若要隨機產生 base 暫存器，實體記憶體大小必須是位址空間大小的 2 倍以上')

# 若隨機產生 base，就得幫它們找位置
if base0 == -1:
    done = 0
    while done == 0:
        base0 = int(psize * random.random())
        if (base0 + len0) < psize:
            done = 1

# 在內部，base1 指向較低的位址，base1+len1 則是較高的位址
# （這跟使用者輸入時所理解的方向不同）
if base1 == -1:
    done = 0
    while done == 0:
        base1 = int(psize * random.random())
        if (base1 + len1) < psize:
            if (base1 > (base0 + len0)) or ((base1 + len1) < base0):
                done = 1
else:
    base1 = base1 - len1

abort_if(psize < base0 + len0 - 1, 'segment 0 不在實體記憶體範圍內')
abort_if(psize < base1, 'segment 1 不在實體記憶體範圍內')

abort_if(len0 > asize/2.0, 'length0 暫存器對這個位址空間來說太大了')
abort_if(len1 > asize/2.0, 'length1 暫存器對這個位址空間來說太大了')

print('區段暫存器資訊：')
print('')
print('  Segment 0 base（向正方向成長） : 0x%08x (十進位 %d)' % (base0, base0))
print('  Segment 0 limit                : %d' % (len0))
print('')
print('  Segment 1 base（向負方向成長） : 0x%08x (十進位 %d)' % (base1+len1, base1+len1))
print('  Segment 1 limit                : %d' % (len1))
print('')

nbase1 = base1 + len1

abort_if((len0 + base0) > base1 and (base1 > base0), '兩個區段在實體記憶體中重疊了')

addrList = []
if addresses == '-1':
    # 需要自行產生位址
    for i in range(0, options.num):
        n = int(asize * random.random())
        addrList.append(n)
else:
    addrList = addresses.split(',')

#
# 現在，需要產生虛擬位址軌跡
#
print('虛擬位址軌跡')
i = 0
for vstr in addrList:
    vaddr = int(vstr)
    if vaddr < 0 or vaddr >= asize:
        print('錯誤：虛擬位址 %d 無法在大小為 %d 的位址空間中產生' % (vaddr, asize))
        exit(1)
    if options.solve == False:
        print('  VA %2d: 0x%08x (十進位: %4d) --> PA 或發生分段違規？' % (i, vaddr, vaddr))
    else:
        paddr = 0
        if (vaddr >= (asize / 2)):
            # segment 1
            #  [base1+len1]  [負向偏移量]
            paddr = nbase1 + (vaddr - asize)
            if paddr < base1:
                print('  VA %2d: 0x%08x (十進位: %4d) --> 分段違規（SEG1）' % (i, vaddr, vaddr))
            else:
                print('  VA %2d: 0x%08x (十進位: %4d) --> 在 SEG1 中合法：0x%08x (十進位: %4d)' % (i, vaddr, vaddr, paddr, paddr))
        else:
            # segment 0
            if (vaddr >= len0):
                print('  VA %2d: 0x%08x (十進位: %4d) --> 分段違規（SEG0）' % (i, vaddr, vaddr))
            else:
                paddr = vaddr + base0
                print('  VA %2d: 0x%08x (十進位: %4d) --> 在 SEG0 中合法：0x%08x (十進位: %4d)' % (i, vaddr, vaddr, paddr, paddr))
    i += 1

print('')

if options.solve == False:
    print('對於每一個虛擬位址，請寫下它轉譯後對應的實體位址，')
    print('或者寫下它是一個超出範圍的位址（也就是分段違規）。針對')
    print('這個問題，你可以假設有一個簡單的位址空間，其中包含兩個區段：')
    print('虛擬位址的最高位元可以用來判斷這個虛擬位址落在區段 0（最高位元=0）')
    print('還是區段 1（最高位元=1）。請注意，提供給你的 base/limit 組合')
    print('會依區段不同而朝不同方向成長，也就是說，區段 0 向正方向成長，')
    print('而區段 1 向負方向成長。')
    print('')
