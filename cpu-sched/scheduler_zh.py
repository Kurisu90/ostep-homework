#! /usr/bin/env python3
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
parser.add_option("-s", "--seed", default=0, help="隨機種子", action="store", type="int", dest="seed")
parser.add_option("-j", "--jobs", default=3, help="系統中的工作數量", action="store", type="int", dest="jobs")
parser.add_option("-l", "--jlist", default="", help="不要隨機產生工作，改用逗號分隔的執行時間清單來指定", action="store", type="string", dest="jlist")
parser.add_option("-m", "--maxlen", default=10, help="工作的最大長度", action="store", type="int", dest="maxlen")
parser.add_option("-p", "--policy", default="FIFO", help="要使用的排程策略：SJF、FIFO、RR", action="store", type="string", dest="policy")
parser.add_option("-q", "--quantum", help="RR 策略的時間片長度", default=1, action="store", type="int", dest="quantum")
parser.add_option("-c", help="幫我計算答案", action="store_true", default=False, dest="solve")

(options, args) = parser.parse_args()

random_seed(options.seed)

print('參數 policy', options.policy)
if options.jlist == '':
    print('參數 jobs', options.jobs)
    print('參數 maxlen', options.maxlen)
    print('參數 seed', options.seed)
else:
    print('參數 jlist', options.jlist)
print('')

print('以下是工作清單，附上每個工作的執行時間：')

import operator

joblist = []
if options.jlist == '':
    for jobnum in range(0,options.jobs):
        runtime = int(options.maxlen * random.random()) + 1
        joblist.append([jobnum, runtime])
        print('  工作', jobnum, '（長度 = ' + str(runtime) + ' ）')
else:
    jobnum = 0
    for runtime in options.jlist.split(','):
        joblist.append([jobnum, float(runtime)])
        jobnum += 1
    for job in joblist:
        print('  工作', job[0], '（長度 = ' + str(job[1]) + ' ）')
print('\n')

if options.solve == True:
    print('** 解答 **\n')
    if options.policy == 'SJF':
        joblist = sorted(joblist, key=operator.itemgetter(1))
        options.policy = 'FIFO'

    if options.policy == 'FIFO':
        thetime = 0
        print('執行記錄：')
        for job in joblist:
            print('  [ 時間 %3d ] 執行工作 %d，共 %.2f 秒（於 %.2f 完成）' % (thetime, job[0], job[1], thetime + job[1]))
            thetime += job[1]

        print('\n最終統計：')
        t     = 0.0
        count = 0
        turnaroundSum = 0.0
        waitSum       = 0.0
        responseSum   = 0.0
        for tmp in joblist:
            jobnum  = tmp[0]
            runtime = tmp[1]

            response   = t
            turnaround = t + runtime
            wait       = t
            print('  工作 %3d -- 反應時間：%3.2f  週轉時間 %3.2f  等待時間 %3.2f' % (jobnum, response, turnaround, wait))
            responseSum   += response
            turnaroundSum += turnaround
            waitSum       += wait
            t += runtime
            count = count + 1
        print('\n  平均 -- 反應時間：%3.2f  週轉時間 %3.2f  等待時間 %3.2f\n' % (responseSum/count, turnaroundSum/count, waitSum/count))

    if options.policy == 'RR':
        print('執行記錄：')
        turnaround = {}
        response = {}
        lastran = {}
        wait = {}
        quantum  = float(options.quantum)
        jobcount = len(joblist)
        for i in range(0,jobcount):
            lastran[i] = 0.0
            wait[i] = 0.0
            turnaround[i] = 0.0
            response[i] = -1

        runlist = []
        for e in joblist:
            runlist.append(e)

        thetime  = 0.0
        while jobcount > 0:
            job = runlist.pop(0)
            jobnum  = job[0]
            runtime = float(job[1])
            if response[jobnum] == -1:
                response[jobnum] = thetime
            currwait = thetime - lastran[jobnum]
            wait[jobnum] += currwait
            if runtime > quantum:
                runtime -= quantum
                ranfor = quantum
                print('  [ 時間 %3d ] 執行工作 %3d，共 %.2f 秒' % (thetime, jobnum, ranfor))
                runlist.append([jobnum, runtime])
            else:
                ranfor = runtime;
                print('  [ 時間 %3d ] 執行工作 %3d，共 %.2f 秒（於 %.2f 完成）' % (thetime, jobnum, ranfor, thetime + ranfor))
                turnaround[jobnum] = thetime + ranfor
                jobcount -= 1
            thetime += ranfor
            lastran[jobnum] = thetime

        print('\n最終統計：')
        turnaroundSum = 0.0
        waitSum       = 0.0
        responseSum   = 0.0
        for i in range(0,len(joblist)):
            turnaroundSum += turnaround[i]
            responseSum += response[i]
            waitSum += wait[i]
            print('  工作 %3d -- 反應時間：%3.2f  週轉時間 %3.2f  等待時間 %3.2f' % (i, response[i], turnaround[i], wait[i]))
        count = len(joblist)

        print('\n  平均 -- 反應時間：%3.2f  週轉時間 %3.2f  等待時間 %3.2f\n' % (responseSum/count, turnaroundSum/count, waitSum/count))

    if options.policy != 'FIFO' and options.policy != 'SJF' and options.policy != 'RR':
        print('錯誤：無法使用排程策略', options.policy)
        sys.exit(0)
else:
    print('請計算出每個工作的週轉時間、反應時間，以及等待時間。')
    print('算完之後，用相同的參數再執行一次這個程式，並加上 -c，')
    print('就能得到正確答案。你可以用 -s <某個數字> 或自訂工作清單')
    print('（例如 -l 10,15,20），來幫自己產生不同的練習題目。')
    print('')
