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

# 找出目前非空、優先度最高的佇列
# 若全部都是空的則傳回 -1
def FindQueue():
    q = hiQueue
    while q > 0:
        if len(queue[q]) > 0:
            return q
        q -= 1
    if len(queue[0]) > 0:
        return 0
    return -1

def Abort(str):
    sys.stderr.write(str + '\n')
    exit(1)


#
# 解析命令列參數
#

parser = OptionParser()
parser.add_option('-s', '--seed', help='隨機種子',
                  default=0, action='store', type='int', dest='seed')
parser.add_option('-n', '--numQueues',
                  help='MLFQ 中的佇列數量（若未使用 -Q）',
                  default=3, action='store', type='int', dest='numQueues')
parser.add_option('-q', '--quantum', help='時間片長度（若未使用 -Q）',
                  default=10, action='store', type='int', dest='quantum')
parser.add_option('-a', '--allotment', help='允許時長（若未使用 -A）',
                  default=1, action='store', type='int', dest='allotment')
parser.add_option('-Q', '--quantumList',
                  help='各佇列層級的時間片長度，格式為 ' + \
                  'x,y,z,...，其中 x 是最高優先度佇列的時間片長度，' + \
                  'y 是次高優先度的，依此類推',
                  default='', action='store', type='string', dest='quantumList')
parser.add_option('-A', '--allotmentList',
                  help='各佇列層級的允許時長，格式為 ' + \
                  'x,y,z,...，其中 x 是最高優先度佇列可用的時間片數，' + \
                  'y 是次高優先度的，依此類推',
                  default='', action='store', type='string', dest='allotmentList')
parser.add_option('-j', '--numJobs', default=3, help='系統中的工作數量',
                  action='store', type='int', dest='numJobs')
parser.add_option('-m', '--maxlen', default=100, help='隨機產生工作時，' +
                  '作業的最大執行時間', action='store', type='int',
                  dest='maxlen')
parser.add_option('-M', '--maxio', default=10,
                  help='隨機產生工作時，作業的最大 I/O 頻率',
                  action='store', type='int', dest='maxio')
parser.add_option('-B', '--boost', default=0,
                  help='多久將所有作業的優先度提升回最高優先度一次',
                  action='store', type='int', dest='boost')
parser.add_option('-i', '--iotime', default=5,
                  help='一次 I/O 要花多久時間（固定常數）',
                  action='store', type='int', dest='ioTime')
parser.add_option('-S', '--stay', default=False,
                  help='發出 I/O 時，重設並停留在同一優先度層級',
                  action='store_true', dest='stay')
parser.add_option('-I', '--iobump', default=False,
                  help='若指定此項，完成 I/O 的作業會立即移到 ' + \
                  '目前佇列的最前面',
                  action='store_true', dest='iobump')
parser.add_option('-l', '--jlist', default='',
                  help='以逗號分隔的工作清單，格式為 ' + \
                  'x1,y1,z1:x2,y2,z2:...，其中 x 是開始時間，y 是執行 ' + \
                  '時間，z 是該作業發出 I/O 請求的頻率',
                  action='store', type='string', dest='jlist')
parser.add_option('-c', help='幫我計算答案', action='store_true',
                  default=False, dest='solve')

(options, args) = parser.parse_args()

random.seed(options.seed)

# MLFQ：要用幾個佇列
numQueues = options.numQueues

quantum = {}
if options.quantumList != '':
    # 改由此處取出佇列數量與各自的時間片長度
    quantumLengths = options.quantumList.split(',')
    numQueues = len(quantumLengths)
    qc = numQueues - 1
    for i in range(numQueues):
        quantum[qc] = int(quantumLengths[i])
        qc -= 1
else:
    for i in range(numQueues):
        quantum[i] = int(options.quantum)

allotment = {}
if options.allotmentList != '':
    allotmentLengths = options.allotmentList.split(',')
    if numQueues != len(allotmentLengths):
        print('指定的允許時長數量必須與時間片數量相符')
        exit(1)
    qc = numQueues - 1
    for i in range(numQueues):
        allotment[qc] = int(allotmentLengths[i])
        if qc != 0 and allotment[qc] <= 0:
            print('允許時長必須是正整數')
            exit(1)
        qc -= 1
else:
    for i in range(numQueues):
        allotment[i] = int(options.allotment)

hiQueue = numQueues - 1

# MLFQ：I/O 模型
# 每次 I/O 花費的時間：用單一固定值不太理想，但先這樣吧
ioTime = int(options.ioTime)

# 記錄 I/O 與其他中斷何時完成
ioDone = {}

# 儲存所有工作的資訊
job = {}

# 設定亂數種子
random_seed(options.seed)

# jlist 格式：'startTime,runTime,ioFreq:startTime,runTime,ioFreq:...'
jobCnt = 0
if options.jlist != '':
    allJobs = options.jlist.split(':')
    for j in allJobs:
        jobInfo = j.split(',')
        if len(jobInfo) != 3:
            print('工作字串格式錯誤，應為 x1,y1,z1:x2,y2,z2:...')
            print('其中 x 是開始時間，y 是執行時間，z 是 I/O 頻率。')
            exit(1)
        assert(len(jobInfo) == 3)
        startTime = int(jobInfo[0])
        runTime   = int(jobInfo[1])
        ioFreq    = int(jobInfo[2])
        job[jobCnt] = {'currPri':hiQueue, 'ticksLeft':quantum[hiQueue],
                       'allotLeft':allotment[hiQueue], 'startTime':startTime,
                       'runTime':runTime, 'timeLeft':runTime, 'ioFreq':ioFreq, 'doingIO':False,
                       'firstRun':-1}
        if startTime not in ioDone:
            ioDone[startTime] = []
        ioDone[startTime].append((jobCnt, '工作進入系統'))
        jobCnt += 1
else:
    # 隨機產生工作
    for j in range(options.numJobs):
        startTime = 0
        runTime   = int(random.random() * (options.maxlen - 1) + 1)
        ioFreq    = int(random.random() * (options.maxio - 1) + 1)

        job[jobCnt] = {'currPri':hiQueue, 'ticksLeft':quantum[hiQueue],
                       'allotLeft':allotment[hiQueue], 'startTime':startTime,
                       'runTime':runTime, 'timeLeft':runTime, 'ioFreq':ioFreq, 'doingIO':False,
                       'firstRun':-1}
        if startTime not in ioDone:
            ioDone[startTime] = []
        ioDone[startTime].append((jobCnt, '工作進入系統'))
        jobCnt += 1


numJobs = len(job)

print('以下是輸入的內容：')
print('選項 工作數量',            numJobs)
print('選項 佇列數量',            numQueues)
for i in range(len(quantum)-1,-1,-1):
    print('選項 佇列 %2d 的允許時長為 %3d' % (i, allotment[i]))
    print('選項 佇列 %2d 的時間片長度為 %3d' % (i, quantum[i]))
print('選項 boost（優先度提升週期）',      options.boost)
print('選項 ioTime（I/O 時長）',          options.ioTime)
print('選項 stayAfterIO（I/O 後停留原佇列）', options.stay)
print('選項 iobump（I/O 完成後插隊佇列前端）', options.iobump)

print('\n')
print('每個工作都有三個定義特徵：')
print('  startTime（開始時間）：工作進入系統的時間')
print('  runTime  （執行時間）：工作完成所需的總 CPU 時間')
print('  ioFreq   （I/O 頻率）：工作每執行 ioFreq 個時間單位就會發出一次 I/O')
print('              （這次 I/O 需要花費 ioTime 個時間單位才能完成）\n')

print('工作清單：')
for i in range(numJobs):
    print('  工作 %2d：startTime %3d − runTime %3d − ioFreq %3d' % (i, job[i]['startTime'], job[i]['runTime'], job[i]['ioFreq']))
print('')

if options.solve == False:
    print('請計算出這些工作負載的執行記錄。')
    print('如果你願意，也可以順便算出每個工作的')
    print('反應時間（response time）與週轉時間（turnaround time）。')
    print('')
    print('算完後，加上 -c 旗標即可取得正確答案。\n')
    exit(0)

# 初始化 MLFQ 的各個佇列
queue = {}
for q in range(numQueues):
    queue[q] = []

# 時間是這裡的核心
currTime = 0

# 用來判斷模擬何時結束
totalJobs    = len(job)
finishedJobs = 0

print('\n執行記錄：\n')

while finishedJobs < totalJobs:
    # 找出優先度最高的工作
    # 讓它一直執行，直到
    # (a) 用完自己的時間片，或
    # (b) 發出 I/O 請求

    # 檢查是否該做優先度提升（priority boost）
    if options.boost > 0 and currTime != 0:
        if currTime % options.boost == 0:
            print('[ 時間 %d ] 優先度提升（每 %d 個時間單位一次）' % (currTime, options.boost))
            # 把所有工作（除了正在做 I/O 的）從各佇列移除，放進最高優先度佇列
            for q in range(numQueues-1):
                for j in queue[q]:
                    if job[j]['doingIO'] == False:
                        queue[hiQueue].append(j)
                queue[q] = []

            # 把優先度改為最高
            # 重設所有工作剩餘的時間片（是否只需針對低優先度工作？）
            # 加入最高優先度佇列（若沒有在做 I/O）
            for j in range(numJobs):
                # print('-> 提升 %d（剩餘時間 %d）' % (j, job[j]['timeLeft']))
                if job[j]['timeLeft'] > 0:
                    # print('-> 最終提升 %d（剩餘時間 %d）' % (j, job[j]['timeLeft']))
                    job[j]['currPri']   = hiQueue
                    job[j]['ticksLeft'] = quantum[hiQueue]
                    job[j]['allotLeft'] = allotment[hiQueue]
                    # print('  提升', j, ' 時間片:', job[j]['ticksLeft'], ' 允許次數:', job[j]['allotLeft'])
            # print('提升結束後，各佇列狀態為：', queue)

    # 檢查是否有 I/O 完成
    if currTime in ioDone:
        for (j, type) in ioDone[currTime]:
            q = job[j]['currPri']
            job[j]['doingIO'] = False
            print('[ 時間 %d ] %s（工作 %d）' % (currTime, type, j))
            if options.iobump == False or type == '工作進入系統':
                queue[q].append(j)
            else:
                queue[q].insert(0, j)

    # 找出目前優先度最高的佇列
    currQueue = FindQueue()
    if currQueue == -1:
        print('[ 時間 %d ] 閒置（IDLE）' % (currTime))
        currTime += 1
        continue

    # 至少有一個可執行的工作，因此……
    currJob = queue[currQueue][0]
    if job[currJob]['currPri'] != currQueue:
        Abort('currPri[%d] 與 currQueue[%d] 不一致' % (job[currJob]['currPri'], currQueue))

    job[currJob]['timeLeft']  -= 1
    job[currJob]['ticksLeft'] -= 1

    if job[currJob]['firstRun'] == -1:
        job[currJob]['firstRun'] = currTime

    runTime   = job[currJob]['runTime']
    ioFreq    = job[currJob]['ioFreq']
    ticksLeft = job[currJob]['ticksLeft']
    allotLeft = job[currJob]['allotLeft']
    timeLeft  = job[currJob]['timeLeft']

    print('[ 時間 %d ] 執行工作 %d，優先度 %d ［剩餘時間片 %d，剩餘允許次數 %d，剩餘時間 %d（共 %d）］' % \
          (currTime, currJob, currQueue, ticksLeft, allotLeft, timeLeft, runTime))

    if timeLeft < 0:
        Abort('錯誤：剩餘時間不應該小於 0')


    # 更新時間
    currTime += 1

    # 檢查工作是否已經結束
    if timeLeft == 0:
        print('[ 時間 %d ] 工作 %d 已完成' % (currTime, currJob))
        finishedJobs += 1
        job[currJob]['endTime'] = currTime
        # print('彈出前', queue)
        done = queue[currQueue].pop(0)
        # print('彈出後', queue)
        assert(done == currJob)
        continue

    # 檢查是否該發出 I/O
    issuedIO = False
    if ioFreq > 0 and (((runTime - timeLeft) % ioFreq) == 0):
        # 該發出 I/O 了！
        print('[ 時間 %d ] I/O 開始（工作 %d）' % (currTime, currJob))
        issuedIO = True
        desched = queue[currQueue].pop(0)
        assert(desched == currJob)
        job[currJob]['doingIO'] = True
        # 這是會被「玩弄」的舊規則──發出 I/O 時重設此層級的時間
        if options.stay == True:
            job[currJob]['ticksLeft'] = quantum[currQueue]
            job[currJob]['allotLeft'] = allotment[currQueue]
        # 加入 I/O 完成事件：但要放進哪個時間點？
        futureTime = currTime + ioTime
        if futureTime not in ioDone:
            ioDone[futureTime] = []
        print('I/O 完成時間已排定')
        ioDone[futureTime].append((currJob, 'I/O 完成'))

    # 檢查此層級的時間片是否用盡（但別忘了，允許時長可能還有剩）
    if ticksLeft == 0:
        if issuedIO == False:
            # 沒有發出 I/O（因此要從佇列中移除）
            desched = queue[currQueue].pop(0)
        assert(desched == currJob)

        job[currJob]['allotLeft'] = job[currJob]['allotLeft'] - 1

        if job[currJob]['allotLeft'] == 0:
            # 這個工作在此層級已經用完額度，該往下移動
            if currQueue > 0:
                # 這種情況下，必須改變工作的優先度
                job[currJob]['currPri']   = currQueue - 1
                job[currJob]['ticksLeft'] = quantum[currQueue-1]
                job[currJob]['allotLeft'] = allotment[currQueue-1]
                if issuedIO == False:
                    queue[currQueue-1].append(currJob)
            else:
                job[currJob]['ticksLeft'] = quantum[currQueue]
                job[currJob]['allotLeft'] = allotment[currQueue]
                if issuedIO == False:
                    queue[currQueue].append(currJob)
        else:
            # 這個工作在此層級還有剩餘額度，放到佇列尾端就好
            job[currJob]['ticksLeft'] = quantum[currQueue]
            if issuedIO == False:
                queue[currQueue].append(currJob)




# 印出統計資訊
print('')
print('最終統計：')
responseSum   = 0
turnaroundSum = 0
for i in range(numJobs):
    response   = job[i]['firstRun'] - job[i]['startTime']
    turnaround = job[i]['endTime'] - job[i]['startTime']
    print('  工作 %2d：startTime %3d − response（反應時間） %3d − turnaround（週轉時間） %3d' % (i, job[i]['startTime'], response, turnaround))
    responseSum   += response
    turnaroundSum += turnaround

print('\n  平均 %2d：startTime 無 − response（反應時間） %.2f − turnaround（週轉時間） %.2f' % (i, float(responseSum)/numJobs, float(turnaroundSum)/numJobs))
print('\n')
