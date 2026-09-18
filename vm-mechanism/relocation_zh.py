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


#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',      default=0,     help='隨機種子',                                          action='store', type='int', dest='seed')
parser.add_option('-a', '--asize',     default='1k',  help='位址空間大小（例如 16、64k、32m、1g）',            action='store', type='string', dest='asize')
parser.add_option('-p', '--physmem',   default='16k', help='實體記憶體大小（例如 16、64k、32m、1g）',          action='store', type='string', dest='psize')
parser.add_option('-n', '--addresses', default=5,     help='要產生的虛擬位址數量',                              action='store', type='int', dest='num')
parser.add_option('-b', '--b',         default='-1',  help='base 暫存器的值',                                   action='store', type='string', dest='base')
parser.add_option('-l', '--l',         default='-1',  help='limit 暫存器的值',                                  action='store', type='string', dest='limit')
parser.add_option('-c', '--compute',   default=False, help='幫我計算答案',                                      action='store_true', dest='solve')


(options, args) = parser.parse_args()

print('')
print('參數 隨機種子', options.seed)
print('參數 位址空間大小', options.asize)
print('參數 實體記憶體大小', options.psize)
print('')

random_seed(options.seed)
asize = convert(options.asize)
psize = convert(options.psize)

if psize <= 1:
    print('錯誤：必須指定一個非零的實體記憶體大小。')
    exit(1)

if asize == 0:
    print('錯誤：必須指定一個非零的位址空間大小。')
    exit(1)

if psize <= asize:
    print('錯誤：實體記憶體大小必須大於位址空間大小（此模擬要求如此）')
    exit(1)

#
# 需要為分段暫存器產生 base 與 bounds
#
limit = convert(options.limit)
base  = convert(options.base)

if limit == -1:
    limit = int(asize/4.0 + (asize/4.0 * random.random()))

# 接著要為它們找到容身之處
if base == -1:
    done = 0
    while done == 0:
        base = int(psize * random.random())
        if (base + limit) < psize:
            done = 1

print('Base 與 Bounds 暫存器資訊：')
print('')
print('  Base（基底）  : 0x%08x (十進位 %d)' % (base, base))
print('  Limit（界限） : %d' % (limit))
print('')

if base + limit > psize:
    print('錯誤：以這樣的 base/bounds 值，位址空間無法放進實體記憶體中。')
    print('Base + Limit：', base + limit, '  Psize：', psize)
    exit(1)

#
# 現在，需要產生虛擬位址軌跡
#
print('虛擬位址軌跡')
for i in range(0,options.num):
    vaddr = int(asize * random.random())
    if options.solve == False:
        print('  VA %2d: 0x%08x (十進位: %4d) --> PA 或發生分段違規？' % (i, vaddr, vaddr))
    else:
        paddr = 0
        if (vaddr >= limit):
            print('  VA %2d: 0x%08x (十進位: %4d) --> 分段違規（SEGMENTATION VIOLATION）' % (i, vaddr, vaddr))
        else:
            paddr = vaddr + base
            print('  VA %2d: 0x%08x (十進位: %4d) --> 合法：0x%08x (十進位: %4d)' % (i, vaddr, vaddr, paddr, paddr))

print('')

if options.solve == False:
    print('對於每一個虛擬位址，請寫下它轉譯後對應的實體位址，')
    print('或者寫下它是一個超出範圍的位址（也就是分段違規）。針對')
    print('這個問題，你可以假設有一個給定大小的簡單虛擬位址空間。')
    print('')
