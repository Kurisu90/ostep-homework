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

def hfunc(index):
    if index == -1:
        return '失誤'
    else:
        return '命中'

def vfunc(victim):
    if victim == -1:
        return '-'
    else:
        return str(victim)

#
# 主程式
#
parser = OptionParser()
parser.add_option('-a', '--addresses', default='-1',   help='要存取的分頁清單，以逗號分隔；-1 代表隨機產生',  action='store', type='string', dest='addresses')
parser.add_option('-f', '--addressfile', default='',   help='一個內含大量位址的檔案',                                action='store', type='string', dest='addressfile')
parser.add_option('-n', '--numaddrs', default='10',    help='若 -a（--addresses）為 -1，這是要產生的位址數量',    action='store', type='string', dest='numaddrs')
parser.add_option('-p', '--policy', default='FIFO',    help='置換策略：FIFO、LRU、OPT、UNOPT、RAND、CLOCK',                action='store', type='string', dest='policy')
parser.add_option('-b', '--clockbits', default=2,      help='CLOCK 策略要使用幾個時鐘位元（clock bits）',                          action='store', type='int', dest='clockbits')
parser.add_option('-C', '--cachesize', default='3',    help='分頁快取的大小（以分頁數為單位）',                                      action='store', type='string', dest='cachesize')
parser.add_option('-m', '--maxpage', default='10',     help='若隨機產生分頁存取，這是最大的分頁編號',     action='store', type='string', dest='maxpage')
parser.add_option('-s', '--seed', default='0',         help='隨機數種子',                                                    action='store', type='string', dest='seed')
parser.add_option('-N', '--notrace', default=False,    help='不要印出詳細的執行記錄',                                     action='store_true', dest='notrace')
parser.add_option('-c', '--compute', default=False,    help='幫我計算答案',                                                action='store_true', dest='solve')

(options, args) = parser.parse_args()

print('參數 位址清單(addresses)', options.addresses)
print('參數 位址檔案(addressfile)', options.addressfile)
print('參數 位址數量(numaddrs)', options.numaddrs)
print('參數 置換策略(policy)', options.policy)
print('參數 時鐘位元數(clockbits)', options.clockbits)
print('參數 快取大小(cachesize)', options.cachesize)
print('參數 最大分頁編號(maxpage)', options.maxpage)
print('參數 隨機種子(seed)', options.seed)
print('參數 不顯示記錄(notrace)', options.notrace)
print('')

addresses   = str(options.addresses)
addressFile = str(options.addressfile)
numaddrs    = int(options.numaddrs)
cachesize   = int(options.cachesize)
seed        = int(options.seed)
maxpage     = int(options.maxpage)
policy      = str(options.policy)
notrace     = options.notrace
clockbits   = int(options.clockbits)

random_seed(seed)

addrList = []
if addressFile != '':
    fd = open(addressFile)
    for line in fd:
        addrList.append(int(line))
    fd.close()
else:
    if addresses == '-1':
        # 需要自行產生位址
        for i in range(0,numaddrs):
            n = int(maxpage * random.random())
            addrList.append(n)
    else:
        addrList = addresses.split(',')

if options.solve == False:
    print('假設置換策略為 %s，快取大小為 %d 個分頁，' % (policy, cachesize))
    print('請判斷以下每一次分頁參照是命中還是未命中')
    print('分頁快取。\n')

    for n in addrList:
        print('存取：%d  命中/未命中？  記憶體狀態？' % int(n))
    print('')

else:
    if notrace == False:
        print('計算中...\n')

    # 初始化記憶體結構
    count = 0
    memory = []
    hits = 0
    miss = 0

    if policy == 'FIFO':
        leftStr = '最早進'
        riteStr = '最晚進'
    elif policy == 'LRU':
        leftStr = 'LRU'
        riteStr = 'MRU'
    elif policy == 'MRU':
        leftStr = 'LRU'
        riteStr = 'MRU'
    elif policy == 'OPT' or policy == 'RAND' or policy == 'UNOPT' or policy == 'CLOCK':
        leftStr = '左側'
        riteStr = '右側'
    else:
        print('尚未實作策略 %s' % policy)
        exit(1)

    # 追蹤 clock 演算法所用的參照位元
    ref   = {}

    cdebug = False

    # 需要產生位址
    addrIndex = 0
    for nStr in addrList:
        # 先查找
        n = int(nStr)
        try:
            idx = memory.index(n)
            hits = hits + 1
            if policy == 'LRU' or policy == 'MRU':
                update = memory.remove(n)
                memory.append(n) # puts it on MRU side
        except:
            idx = -1
            miss = miss + 1

        victim = -1
        if idx == -1:
            # 未命中，需要置換嗎？
            # print('BUG count, cachesize:', count, cachesize)
            if count == cachesize:
                # 必須置換
                if policy == 'FIFO' or policy == 'LRU':
                    victim = memory.pop(0)
                elif policy == 'MRU':
                    victim = memory.pop(count-1)
                elif policy == 'RAND':
                    victim = memory.pop(int(random.random() * count))
                elif policy == 'CLOCK':
                    if cdebug:
                        print('參照到分頁', n)
                        print('記憶體 ', memory)
                        print('參照位元（前）', ref)

                    # 暫時的權宜做法：先用隨機挑選
                    # victim = memory.pop(int(random.random() * count))
                    victim = -1
                    while victim == -1:
                        page = memory[int(random.random() * count)]
                        if cdebug:
                            print('  掃描分頁:', page, ref[page])
                        if ref[page] >= 1:
                            ref[page] -= 1
                        else:
                            # 就是這一個受害者（victim）
                            victim = page
                            memory.remove(page)
                            break

                    # 移除舊分頁的參照計數
                    if page in memory:
                        assert('BROKEN')
                    del ref[victim]
                    if cdebug:
                        print('受害者(VICTIM)', page)
                        print('長度(LEN)', len(memory))
                        print('記憶體(MEM)', memory)
                        print('參照位元（後）', ref)

                elif policy == 'OPT':
                    maxReplace  = -1
                    replaceIdx  = -1
                    replacePage = -1
                    # print('OPT: access %d, memory %s' % (n, memory) )
                    # print('OPT: replace from FUTURE (%s)' % addrList[addrIndex+1:])
                    for pageIndex in range(0,count):
                        page = memory[pageIndex]
                        # 現在，記憶體中索引 pageIndex 處的分頁是 page
                        whenReferenced = len(addrList)
                        # whenReferenced 告訴我們這個分頁未來何時會被參照
                        for futureIdx in range(addrIndex+1,len(addrList)):
                            futurePage = int(addrList[futureIdx])
                            if page == futurePage:
                                whenReferenced = futureIdx
                                break
                        # print('OPT: page %d is referenced at %d' % (page, whenReferenced))
                        if whenReferenced >= maxReplace:
                            # print('OPT: ??? updating maxReplace (%d %d %d)' % (replaceIdx, replacePage, maxReplace))
                            replaceIdx  = pageIndex
                            replacePage = page
                            maxReplace  = whenReferenced
                            # print('OPT: --> updating maxReplace (%d %d %d)' % (replaceIdx, replacePage, maxReplace))
                    victim = memory.pop(replaceIdx)
                    # print('OPT: replacing page %d (idx:%d) because I saw it in future at %d' % (victim, replaceIdx, whenReferenced))
                elif policy == 'UNOPT':
                    minReplace  = len(addrList) + 1
                    replaceIdx  = -1
                    replacePage = -1
                    for pageIndex in range(0,count):
                        page = memory[pageIndex]
                        # 現在，記憶體中索引 pageIndex 處的分頁是 page
                        whenReferenced = len(addrList)
                        # whenReferenced 告訴我們這個分頁未來何時會被參照
                        for futureIdx in range(addrIndex+1,len(addrList)):
                            futurePage = int(addrList[futureIdx])
                            if page == futurePage:
                                whenReferenced = futureIdx
                                break
                        if whenReferenced < minReplace:
                            replaceIdx  = pageIndex
                            replacePage = page
                            minReplace  = whenReferenced
                    victim = memory.pop(replaceIdx)
            else:
                # 未命中，但不需要置換（快取尚未滿）
                victim = -1
                count = count + 1

            # 現在把它加入記憶體
            memory.append(n)
            if cdebug:
                print('長度（後）', len(memory))
            if victim != -1:
                assert(victim not in memory)

        # 處理完未命中之後，更新參照位元
        if n not in ref:
            ref[n] = 1
        else:
            ref[n] += 1
            if ref[n] > clockbits:
                ref[n] = clockbits

        if cdebug:
            print('參照位元（後）', ref)

        if notrace == False:
            print('存取：%d  %s %s -> %12s <- %s 置換:%s [命中:%d 未命中:%d]' % (n, hfunc(idx), leftStr, memory, riteStr, vfunc(victim), hits, miss))
        addrIndex = addrIndex + 1

    print('')
    print('最終統計 命中 %d   未命中 %d   命中率 %.2f' % (hits, miss, (100.0*float(hits))/(float(hits)+float(miss))))
    print('')



    
    
    







