#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
from optparse import OptionParser
import random
import math

def mustbepowerof2(bits, size, msg):
    if math.pow(2,bits) != size:
        print('引數錯誤：%s' % msg)
        sys.exit(1)

def mustbemultipleof(bignum, num, msg):
    if (int(float(bignum)/float(num)) != (int(bignum) / int(num))):
        print('引數錯誤：%s' % msg)
        sys.exit(1)

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
parser.add_option('-A', '--addresses', default='-1',
                  help='一組以逗號分隔的頁面，用來存取；-1 代表隨機產生',
                  action='store', type='string', dest='addresses')
parser.add_option('-s', '--seed',    default=0,     help='隨機種子',                                       action='store', type='int', dest='seed')
parser.add_option('-a', '--asize',   default='16k', help='位址空間大小（例如 16、64k、32m、1g）',         action='store', type='string', dest='asize')
parser.add_option('-p', '--physmem', default='64k', help='實體記憶體大小（例如 16、64k、32m、1g）',       action='store', type='string', dest='psize')
parser.add_option('-P', '--pagesize', default='4k', help='頁面大小（例如 4k、8k 等）',                     action='store', type='string', dest='pagesize')
parser.add_option('-n', '--numaddrs',  default=5,  help='要產生的虛擬位址數量',                            action='store', type='int', dest='num')
parser.add_option('-u', '--used',       default=50, help='虛擬位址空間中已使用的百分比',                   action='store', type='int', dest='used')
parser.add_option('-v',                             help='詳細模式',                                       action='store_true', default=False, dest='verbose')
parser.add_option('-c',                             help='幫我計算答案',                                   action='store_true', default=False, dest='solve')


(options, args) = parser.parse_args()

print('參數 隨機種子',           options.seed)
print('參數 位址空間大小',       options.asize)
print('參數 實體記憶體大小',     options.psize)
print('參數 頁面大小',           options.pagesize)
print('參數 詳細模式',           options.verbose)
print('參數 位址清單',           options.addresses)
print('')

random.seed(options.seed)

asize    = convert(options.asize)
psize    = convert(options.psize)
pagesize = convert(options.pagesize)
addresses = str(options.addresses)

if psize <= 1:
    print('錯誤：必須指定一個非零的實體記憶體大小。')
    exit(1)

if asize < 1:
    print('錯誤：必須指定一個非零的位址空間大小。')
    exit(1)

if psize <= asize:
    print('錯誤：實體記憶體大小必須大於位址空間大小（此模擬要求如此）')
    exit(1)

if psize >= convert('1g') or asize >= convert('1g'):
    print('錯誤：此模擬要求使用較小的大小（小於 1 GB）。')
    exit(1)

mustbemultipleof(asize, pagesize, '位址空間大小必須是頁面大小的倍數')
mustbemultipleof(psize, pagesize, '實體記憶體大小必須是頁面大小的倍數')

# 印出一些有用的資訊，像是頁表本身
pages = int(psize / pagesize);
import array
used = array.array('i')
pt   = array.array('i')
for i in range(0,pages):
    used.insert(i,0)
vpages = int(asize / pagesize)

# 現在，替虛擬位址空間的各個頁面分配對應
vabits   = int(math.log(float(asize))/math.log(2.0))
mustbepowerof2(vabits, asize, '位址空間大小必須是 2 的次方')
pagebits = int(math.log(float(pagesize))/math.log(2.0))
mustbepowerof2(pagebits, pagesize, '頁面大小必須是 2 的次方')
vpnbits  = vabits - pagebits
pagemask = (1 << pagebits) - 1

# import ctypes
# vpnmask  = ctypes.c_uint32(~pagemask).value
vpnmask = 0xFFFFFFFF & ~pagemask
#if vpnmask2 != vpnmask:
#    print 'ERROR'
#    exit(1)
# print 'va:%d page:%d vpn:%d -- %08x %08x' % (vabits, pagebits, vpnbits, vpnmask, pagemask)

print('')
print('頁表的格式很簡單：')
print('最高位（最左邊）的那個位元是「有效位元（VALID bit）」。')
print('  若該位元為 1，代表這個項目其餘的部分就是 PFN。')
print('  若該位元為 0，代表這個頁面是無效的。')
print('如果你想在頁表的每個項目旁邊都印出它的 VPN 編號，')
print('可以使用詳細模式（-v）。')
print('')

print('頁表（從第 0 個項目一路列到最大大小）')
for v in range(0,vpages):
    done = 0
    while done == 0:
        if ((random.random() * 100.0) > (100.0 - float(options.used))):
            u = int(pages * random.random())
            if used[u] == 0:
                used[u] = 1
                done = 1
                # print('%8d - %d' % (v, u))
                if options.verbose == True:
                    print('  [%8d]  ' % v, end='')
                else:
                    print('  ', end='')
                print('0x%08x' % (0x80000000 | u))
                pt.insert(v,u)
        else:
            # print('%8d - not valid' % v)
            if options.verbose == True:
                print('  [%8d]  ' % v, end='')
            else:
                print('  ', end='')
            print('0x%08x' % 0)
            pt.insert(v,-1)
            done = 1
print(''            )


#
# 現在，需要產生虛擬位址軌跡
#

addrList = []
if addresses == '-1':
    # 需要自行產生位址
    for i in range(0, options.num):
        n = int(asize * random.random())
        addrList.append(n)
else:
    addrList = addresses.split(',')


print('虛擬位址軌跡')
for vStr in addrList:
    # vaddr = int(asize * random.random())
    vaddr = int(vStr)
    if options.solve == False:
        print('  VA 0x%08x (十進位: %8d) --> PA 或無效位址？' % (vaddr, vaddr))
    else:
        paddr = 0
        # 把 vaddr 拆成 VPN 與 offset
        vpn = (vaddr & vpnmask) >> pagebits
        if pt[vpn] < 0:
            print('  VA 0x%08x (十進位: %8d) -->  無效（VPN %d 並非有效）' % (vaddr, vaddr, vpn))
        else:
            pfn    = pt[vpn]
            offset = vaddr & pagemask
            paddr  = (pfn << pagebits) | offset
            print('  VA 0x%08x (十進位: %8d) --> %08x (十進位 %8d) [VPN %d]' % (vaddr, vaddr, paddr, paddr, vpn))
print('')

if options.solve == False:
    print('對於每一個虛擬位址，請寫下它轉譯後對應的實體位址，')
    print('或者寫下它是一個超出範圍的位址（例如發生 segfault）。')
    print('')
