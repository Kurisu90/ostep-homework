#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
from optparse import OptionParser
import random

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子',              action='store', type='int', dest='seed')
parser.add_option('-j', '--jobs', default=3, help='系統中的工作數量', action='store', type='int', dest='jobs')
parser.add_option('-l', '--jlist', default='', help='不要隨機產生工作，改用逗號分隔的執行時間與票數清單來指定（例如 10:100,20:100 代表有兩個工作，執行時間分別是 10 和 20，各自擁有 100 張票）',  action='store', type='string', dest='jlist')
parser.add_option('-m', '--maxlen',  default=10,  help='工作的最大長度',         action='store', type='int', dest='maxlen')
parser.add_option('-T', '--maxticket', default=100, help='隨機分配時，票數的最大值',          action='store', type='int', dest='maxticket')
parser.add_option('-q', '--quantum', default=1,   help='時間片長度', action='store', type='int', dest='quantum')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true', default=False, dest='solve')

(options, args) = parser.parse_args()

random_seed(options.seed)

print('參數 jlist', options.jlist)
print('參數 jobs', options.jobs)
print('參數 maxlen', options.maxlen)
print('參數 maxticket', options.maxticket)
print('參數 quantum', options.quantum)
print('參數 seed', options.seed)
print('')

print('以下是工作清單，附上每個工作的執行時間：')

import operator


tickTotal = 0
runTotal  = 0
joblist = []
if options.jlist == '':
    for jobnum in range(0,options.jobs):
        runtime = 0
        while runtime == 0:
            runtime = int(options.maxlen * random.random())
        tickets = 0
        while tickets == 0:
            tickets = int(options.maxticket * random.random())
        runTotal += runtime
        tickTotal += tickets
        joblist.append([jobnum, runtime, tickets])
        print('  工作 %d （長度 = %d，票數 = %d）' % (jobnum, runtime, tickets))
else:
    jobnum = 0
    for entry in options.jlist.split(','):
        (runtime, tickets) = entry.split(':')
        joblist.append([jobnum, int(runtime), int(tickets)])
        runTotal += int(runtime)
        tickTotal += int(tickets)
        jobnum += 1
    for job in joblist:
        print('  工作 %d （長度 = %d，票數 = %d）' % (job[0], job[1], job[2]))
print('\n')

if options.solve == False:
    print('以下是你（最多）會需要用到的亂數清單：')
    for i in range(runTotal):
        r = int(random.random() * 1000001)
        print('亂數', r)

if options.solve == True:
    print('** 解答 **\n')

    jobs  = len(joblist)
    clock = 0
    for i in range(runTotal):
        r = int(random.random() * 1000001)
        winner = int(r % tickTotal)

        current = 0
        for (job, runtime, tickets) in joblist:
            current += tickets
            if current > winner:
                (wjob, wrun, wtix) = (job, runtime, tickets)
                break

        print('亂數', r, '-> 中獎的票是 %d（共 %d 張）-> 執行工作 %d' % (winner, tickTotal, wjob))
        # print('中獎的票是 %d（共 %d 張）-> 執行工作 %d' % (winner, tickTotal, wjob))

        print('  工作：',)
        for (job, runtime, tickets) in joblist:
            if wjob == job:
                wstr = '*'
            else:
                wstr = ' '

            if runtime > 0:
                tstr = tickets
            else:
                tstr = '---'
            print(' (%s 工作:%d 剩餘時間:%d 票數:%s ) ' % (wstr, job, runtime, tstr), end='')
        print('')

        # 接下來進行帳務計算
        if wrun >= options.quantum:
            wrun -= options.quantum
        else:
            wrun = 0

        clock += options.quantum

        # 工作完成！
        if wrun == 0:
            print('--> 工作 %d 於時間 %d 完成' % (wjob, clock))
            tickTotal -= wtix
            wtix = 0
            jobs -= 1

        # 更新工作清單
        joblist[wjob] = (wjob, wrun, wtix)

        if jobs == 0:
            print('')
            break
