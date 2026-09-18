#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import division
try:
    from Tkinter import *
except:
    from tkinter import *
from types import *
import math, random, time, sys, os
from optparse import OptionParser

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

MAXTRACKS = 1000

# 一個請求／磁碟會經歷的狀態
STATE_NULL   = 0
STATE_SEEK   = 1
STATE_ROTATE = 2
STATE_XFER   = 3
STATE_DONE   = 4

#
# TODO（待辦）
# XXX 傳輸時間
# XXX satf
# XXX skew（偏移）
# XXX 排程視窗
# XXX sstf
# XXX 指定確切請求 vs. 在範圍中隨機產生請求
# XXX 在舊請求完成時加入新請求（飢餓問題）
# XXX 在非圖形模式下執行
# XXX 更好的圖形顯示（顯示圖例、較長的請求清單、畫面上顯示更多時間資訊）
# XXX 能夠做到「純粹」的循序存取
# XXX 在外圈磁軌加入更多區塊（zoning，分區）
# XXX 簡單的旗標，讓排程視窗變成公平性視窗（-F）
#     以及新的 scan、c-scan 磁碟演算法？
#

class Disk:
    def __init__(self, addr, addrDesc, lateAddr, lateAddrDesc,
                 policy, seekSpeed, rotateSpeed, skew, window, compute,
                 graphics, zoning):
        self.addr              = addr
        self.addrDesc          = addrDesc
        self.lateAddr          = lateAddr
        self.lateAddrDesc      = lateAddrDesc
        self.policy            = policy
        self.seekSpeed         = seekSpeed
        self.rotateSpeed       = rotateSpeed
        self.skew              = skew
        self.window            = window
        self.compute           = compute
        self.graphics          = graphics
        self.zoning            = zoning

        # 先計算出分區（zone），才能知道最大可能的請求值
        self.InitBlockLayout()

        # 計算出請求內容
        random_seed(options.seed)
        self.requests     = self.MakeRequests(self.addr, self.addrDesc)
        self.lateRequests = self.MakeRequests(self.lateAddr, self.lateAddrDesc)

        # 圖形模式的啟動設定
        self.width = 500
        if self.graphics:
            self.root = Tk()
            tmpLen = len(self.requests)
            if len(self.lateRequests) > 0:
                tmpLen += len(self.lateRequests)
            self.canvas = Canvas(self.root, width=410, height=460 + ((tmpLen / 20.0) * 20))
            self.canvas.pack()

        # 公平性相關設定
        if self.policy == 'BSATF' and self.window != -1:
            self.fairWindow = self.window
        else:
            self.fairWindow = -1

        print('請求', self.requests)
        print('')

        # 處理延遲的請求
        self.lateCount = 0
        if len(self.lateRequests) > 0:
            print('延遲的請求', self.lateRequests)
            print('')

        if self.compute == False:
            print('')
            print('請針對上面的請求，計算尋道（seek）、旋轉（rotate）、傳輸（transfer）時間。')
            print('使用 -c 或圖形模式（-G）來查看答案。')
            print('')

        # 按鍵綁定
        if self.graphics:
            self.root.bind('s', self.Start)
            self.root.bind('p', self.Pause)
            self.root.bind('q', self.Exit)

        # 磁軌資訊
        self.tracks = {}
        self.trackWidth =  40
        self.tracks[0]  = 140
        self.tracks[1]  = self.tracks[0] - self.trackWidth
        self.tracks[2]  = self.tracks[1] - self.trackWidth

        if (self.seekSpeed > 1 and self.trackWidth % self.seekSpeed != 0):
            print('尋道速度 (%d) 必須能整除磁軌寬度 (%d)' % (self.seekSpeed, self.trackWidth))
            sys.exit(1)
        if self.seekSpeed < 1:
            x = self.trackWidth / self.seekSpeed
            y = int(float(self.trackWidth) / float(self.seekSpeed))
            if float(x) != float(y):
                print('尋道速度 (%f) 必須能整除磁軌寬度 (%d)' % (self.seekSpeed, self.trackWidth))
                sys.exit(1)

        # 磁碟表面
        self.cx = self.width / 2.0
        self.cy = self.width / 2.0
        if self.graphics:
            self.canvas.create_rectangle(self.cx-175, 30, self.cx - 20, 80, fill='gray', outline='black')
        self.platterSize = 320
        ps2 = self.platterSize / 2.0
        if self.graphics:
            self.canvas.create_oval(self.cx-ps2, self.cy-ps2, self.cx+ps2, self.cy + ps2, fill='darkgray', outline='black')
        for i in range(len(self.tracks)):
            t = self.tracks[i] - (self.trackWidth / 2.0)
            if self.graphics:
                self.canvas.create_oval(self.cx - t, self.cy - t, self.cx + t, self.cy + t, fill='', outline='black', width=1.0)

        # 主軸
        self.spindleX  = self.cx
        self.spindleY  = self.cy
        if self.graphics:
            self.spindleID = self.canvas.create_oval(self.spindleX-3, self.spindleY-3, self.spindleX+3, self.spindleY+3, fill='orange', outline='black')

        # 磁碟手臂
        self.armTrack     = 0
        self.armSpeedBase = float(seekSpeed)
        self.armSpeed     = float(seekSpeed)

        distFromSpindle   = self.tracks[self.armTrack]
        self.armWidth     = 20
        self.headWidth    = 10

        self.armX         = self.spindleX - (distFromSpindle * math.cos(math.radians(0)))
        self.armX1        = self.armX - self.armWidth
        self.armX2        = self.armX + self.armWidth
        self.armY1        = 50.0
        self.armY2        = self.width / 2.0

        self.headX1       = self.armX - self.headWidth
        self.headX2       = self.armX + self.headWidth
        self.headY1       = (self.width / 2.0) - self.headWidth
        self.headY2       = (self.width / 2.0) + self.headWidth

        if self.graphics:
            self.armID        = self.canvas.create_rectangle(self.armX1, self.armY1, self.armX2, self.armY2, fill='gray', outline='black')
            self.headID       = self.canvas.create_rectangle(self.headX1, self.headY1, self.headX2, self.headY2, fill='gray', outline='black')

        self.targetSize   = 10.0
        if self.graphics:
            sz                = self.targetSize
            self.targetID     = self.canvas.create_oval(self.armX1-sz, self.armY1-sz, self.armX1+sz, self.armY1+sz, fill='orange', outline='')

        # IO 佇列
        self.queueX       = 20
        self.queueY       = 450

        self.requestCount = 0
        self.requestQueue = []
        self.requestState = []
        self.queueBoxSize = 20
        self.queueBoxID   = {}
        self.queueTxtID   = {}

        # 畫出每個方塊
        for index in range(len(self.requests)):
            self.AddQueueEntry(int(self.requests[index]), index)
        if self.graphics:
            self.canvas.create_text(self.queueX - 5, self.queueY - 20, anchor='w', text='佇列：')

        # 排程視窗
        self.currWindow = self.window

        # 畫出目前佇列的邊界
        if self.graphics:
            self.windowID = -1
            self.DrawWindow()

        # 初始排程資訊
        self.currentIndex = -1
        self.currentBlock = -1

        # 磁碟的初始狀態（相對於 seeking、rotating、transferring）
        self.state = STATE_NULL

        # 在磁軌上畫出區塊
        for bid in range(len(self.blockInfoList)):
            (track, angle, name) = self.blockInfoList[bid]
            if self.graphics:
                distFromSpindle = self.tracks[track]
                xc = self.spindleX + (distFromSpindle * math.cos(math.radians(angle)))
                yc = self.spindleY + (distFromSpindle * math.sin(math.radians(angle)))
                cid = self.canvas.create_text(xc, yc, text=name, anchor='center')
            else:
                cid = -1
            self.blockInfoList[bid] = (track, angle, name, cid)

        # 旋轉角度
        self.angle = 0.0

        # 時間資訊
        if self.graphics:
            self.timeID = self.canvas.create_text(10, 10, text='時間: 0.00', anchor='w')
            self.canvas.create_rectangle(95,0,200,18, fill='orange', outline='orange')
            self.seekID = self.canvas.create_text(100, 10, text='尋道: 0.00', anchor='w')
            self.canvas.create_rectangle(195,0,300,18, fill='lightblue', outline='lightblue')
            self.rotID  = self.canvas.create_text(200, 10, text='旋轉: 0.00', anchor='w')
            self.canvas.create_rectangle(295,0,400,18, fill='green', outline='green')
            self.xferID = self.canvas.create_text(300, 10, text='傳輸: 0.00', anchor='w')
            self.canvas.create_text(320, 40, text='按 "s" 開始', anchor='w')
            self.canvas.create_text(320, 60, text='按 "p" 暫停', anchor='w')
            self.canvas.create_text(320, 80, text='按 "q" 結束', anchor='w')
        self.timer = 0

        # 統計數據
        self.seekTotal   = 0.0
        self.rotTotal    = 0.0
        self.xferTotal   = 0.0

        # 設定動畫迴圈
        if self.graphics:
            self.doAnimate = True
        else:
            self.doAnimate = False
        self.isDone = False

    # 呼叫這個方法來開始模擬
    def Go(self):
        if options.graphics:
            self.root.mainloop()
        else:
            self.GetNextIO()
            while self.isDone == False:
                self.Animate()

    # 陽春的錯誤訊息
    def PrintAddrDescMessage(self, value):
        print('位址描述格式錯誤 (%s)' % value)
        print('位址描述必須是一個以逗號分隔、長度為三的清單，且中間不能有空格。')
        print('舉例來說，"10,100,0" 代表要產生 10 個位址，最大值為')
        print('100，最小值為 0。最大值設為 -1 表示直接使用可能產生的最大位址')
        print('作為最大值。')
        sys.exit(1)

    #
    # 分區與區塊配置
    #
    def InitBlockLayout(self):
        self.blockInfoList    = []
        self.blockToTrackMap  = {}
        self.blockToAngleMap  = {}
        self.tracksBeginEnd   = {}
        self.blockAngleOffset = []

        zones = self.zoning.split(',')
        assert(len(zones) == 3)
        for i in range(len(zones)):
            print('z', i, zones[i])
            self.blockAngleOffset.append(int(zones[i]) // 2)

        track        = 0 # 最外層磁軌
        angleOffset  = 2 * self.blockAngleOffset[track]
        for angle in range(0, 360, angleOffset):
            block = angle // angleOffset
            print(track, angleOffset, block)
            self.blockToTrackMap[block] = track
            self.blockToAngleMap[block] = angle
            self.blockInfoList.append((track, angle, block))
        self.tracksBeginEnd[track] = (0, block)
        pblock                     = block + 1

        track                      = 1 # 中間磁軌
        skew                       = self.skew
        angleOffset                = 2 * self.blockAngleOffset[track]
        for angle in range(0, 360, angleOffset):
            block = (angle // angleOffset) + pblock
            print(track, skew, angleOffset, block)
            self.blockToTrackMap[block] = track
            self.blockToAngleMap[block] = angle + (angleOffset * skew)
            self.blockInfoList.append((track, angle + (angleOffset * skew), block))
        self.tracksBeginEnd[track] = (pblock, block)
        pblock                     = block + 1

        track                      = 2 # 最內層磁軌
        skew                       = 2 * self.skew
        angleOffset                = 2 * self.blockAngleOffset[track]
        for angle in range(0, 360, angleOffset):
            block = (angle // angleOffset) + pblock
            print(track, skew, angleOffset, block)
            self.blockToTrackMap[block] = track
            self.blockToAngleMap[block] = angle + (angleOffset * skew)
            self.blockInfoList.append((track, angle + (angleOffset * skew), block))
        self.tracksBeginEnd[track] = (pblock, block)
        self.maxBlock              = pblock
        # print '最大區塊編號:', self.maxBlock

        # 調整角度到相對的起始位置
        for i in self.blockToAngleMap:
            self.blockToAngleMap[i] = (self.blockToAngleMap[i] + 180) % 360

        # print '區塊對角度對照表', self.blockToAngleMap
        # print '區塊對磁軌對照表', self.blockToTrackMap
        # print '區塊角度偏移量', self.blockAngleOffset

    def MakeRequests(self, addr, addrDesc):
        (numRequests, maxRequest, minRequest) = (0, 0, 0)
        if addr == '-1':
            # 先從描述字串中取出數值
            desc = addrDesc.split(',')
            if len(desc) != 3:
                self.PrintAddrDescMessage(addrDesc)
            (numRequests, maxRequest, minRequest) = (int(desc[0]), int(desc[1]), int(desc[2]))
            if maxRequest == -1:
                maxRequest = self.maxBlock
            # 接著建立清單
            tmpList = []
            for i in range(numRequests):
                tmpList.append(int(random.random() * maxRequest) + minRequest)
            return tmpList
        else:
            tmpList = []
            for x in addr.split(','):
                tmpList.append(int(x))
            return tmpList

    #
    # 按鈕
    #
    def Start(self, event):
        self.GetNextIO()
        self.doAnimate = True
        self.Animate()

    def Pause(self, event):
        if self.doAnimate == False:
            self.doAnimate = True
        else:
            self.doAnimate = False

    def Exit(self, event):
        sys.exit(0)

    #
    # 核心模擬與動畫
    #
    def UpdateTime(self):
        if self.graphics:
            self.canvas.itemconfig(self.timeID, text='時間: ' + str(self.timer))
            self.canvas.itemconfig(self.seekID, text='尋道: ' + str(self.seekTotal))
            self.canvas.itemconfig(self.rotID,  text='旋轉: ' + str(self.rotTotal))
            self.canvas.itemconfig(self.xferID, text='傳輸: ' + str(self.xferTotal))

    def AddRequest(self, block):
        self.AddQueueEntry(block, len(self.requestQueue))

    def QueueMap(self, index):
        numPerRow = 400 // self.queueBoxSize
        return (index % numPerRow, index // numPerRow)

    def DrawWindow(self):
        if self.window == -1:
            return
        (col, row) = self.QueueMap(self.currWindow)
        if col == 0:
            (col, row) = (20, row - 1)
        if self.windowID != -1:
            self.canvas.delete(self.windowID)
        self.windowID = self.canvas.create_line(self.queueX + (col * 20) - 10, self.queueY - 13 + (row * 20),
                                                self.queueX + (col * 20) - 10, self.queueY + 13 + (row * 20), width=2)

    def AddQueueEntry(self, block, index):
        self.requestQueue.append((block, index))
        self.requestState.append(STATE_NULL)
        if self.graphics:
            (col, row) = self.QueueMap(index)
            sizeHalf   = self.queueBoxSize / 2.0
            (cx, cy)   = (self.queueX + (col * self.queueBoxSize), self.queueY + (row * self.queueBoxSize))
            self.queueBoxID[index] = self.canvas.create_rectangle(cx - sizeHalf, cy - sizeHalf, cx + sizeHalf, cy + sizeHalf, fill='white')
            self.queueTxtID[index] = self.canvas.create_text(cx, cy, anchor='center', text=str(block))

    def SwitchColors(self, c):
        if self.graphics:
            self.canvas.itemconfig(self.queueBoxID[self.currentIndex], fill=c)
            self.canvas.itemconfig(self.targetID, fill=c)

    def SwitchState(self, newState):
        self.state                           = newState
        self.requestState[self.currentIndex] = newState

    def RadiallyCloseTo(self, a1, a2):
        if a1 > a2:
            v = a1 - a2
        else:
            v = a2 - a1
        if v < self.rotateSpeed:
            return True
        return False

    def DoneWithTransfer(self):
        angleOffset = self.blockAngleOffset[self.armTrack]
        # if int(self.angle) == (self.blockToAngleMap[self.currentBlock] + angleOffset) % 360:
        if self.RadiallyCloseTo(self.angle, float((self.blockToAngleMap[self.currentBlock] + angleOffset) % 360)):
            # print '傳輸結束', self.angle, self.timer
            self.SwitchState(STATE_DONE)
            self.requestCount += 1
            return True
        return False

    def DoneWithRotation(self):
        angleOffset = self.blockAngleOffset[self.armTrack]
        # XXX 這裡有個奇怪的 bug
        # print self.timer, '旋轉:: ', self.currentBlock, '目前角度: ', self.angle, ' - 對照角度: ', self.blockToAngleMap[self.currentBlock]
        # print '  角度偏移量  ', angleOffset
        # print '  區塊對照     ', (self.blockToAngleMap[self.currentBlock] - angleOffset) % 360
        # print '  self.angle   ', self.angle, int(self.angle)
        # if int(self.angle) == (self.blockToAngleMap[self.currentBlock] - angleOffset) % 360:
        if self.RadiallyCloseTo(self.angle, float((self.blockToAngleMap[self.currentBlock] - angleOffset) % 360)):
            self.SwitchState(STATE_XFER)
            # print ' --> 旋轉完成！', self.timer
            return True
        return False

    def PlanSeek(self, track):
        self.seekBegin = self.timer
        self.SwitchColors('orange')
        self.SwitchState(STATE_SEEK)
        if track == self.armTrack:
            self.rotBegin = self.timer
            self.SwitchColors('lightblue')
            self.SwitchState(STATE_ROTATE)
            return
        self.armTarget   = track
        self.armTargetX1 = self.spindleX - self.tracks[track] - (self.trackWidth / 2.0)
        if track >= self.armTrack:
            self.armSpeed = self.armSpeedBase
        else:
            self.armSpeed = - self.armSpeedBase

    def DoneWithSeek(self):
        # 移動磁碟手臂
        self.armX1  += self.armSpeed
        self.armX2  += self.armSpeed
        self.headX1 += self.armSpeed
        self.headX2 += self.armSpeed
        # 更新畫面上的顯示
        if self.graphics:
            self.canvas.coords(self.armID,  self.armX1,  self.armY1,  self.armX2,  self.armY2)
            self.canvas.coords(self.headID, self.headX1, self.headY1, self.headX2, self.headY2)
        # 檢查是否完成
        if (self.armSpeed > 0.0 and self.armX1 >= self.armTargetX1) or (self.armSpeed < 0.0 and self.armX1 <= self.armTargetX1):
            self.armTrack = self.armTarget
            return True
        return False

    def DoSATF(self, rList):
        minBlock = -1
        minIndex = -1
        minEst   = -1

        # print '**** DoSATF ****', rList
        for (block, index) in rList:
            if self.requestState[index] == STATE_DONE:
                # print '  跳過', index
                continue
            track = self.blockToTrackMap[block]
            angle = self.blockToAngleMap[block]
            # print '  磁軌', track, '角度', angle

            # 估計尋道時間
            dist = int(math.fabs(self.armTrack - track))
            seekEst  = (self.trackWidth / self.armSpeedBase) * dist
            # print('  距離', dist)
            # print('  預估尋道時間', seekEst)

            # 估計旋轉時間
            angleOffset = self.blockAngleOffset[track]
            # print '  角度偏移量', angleOffset
            # print '  self.angle', self.angle
            angleAtArrival = (self.angle + (seekEst * self.rotateSpeed))
            while angleAtArrival > 360.0:
                angleAtArrival -= 360.0
            # print 'self.rotateSpeed', self.rotateSpeed
            # print 'angleAtArrival', angleAtArrival
            rotDist = ((angle - angleOffset) - angleAtArrival)
            while rotDist > 360.0:
                rotDist -= 360.0
            while rotDist < 0.0:
                rotDist += 360.0
            rotEst = rotDist / self.rotateSpeed
            # print '  預估旋轉時間', rotDist, self.rotateSpeed, ' -> ', rotEst

            # 最後，計算傳輸時間
            xferEst = (angleOffset * 2.0) / self.rotateSpeed

            # print '  預估傳輸時間', xferEst

            totalEst = seekEst + rotEst + xferEst
            # print '  預估總時間', seekEst, rotEst, xferEst, ' -> ', totalEst

            # print '  --> 區塊:%d 尋道:%d 旋轉:%d 傳輸:%d 預估:%d' % (block, seekEst, rotEst, xferEst, totalEst)

            # 若發生平手（TIE），或許應該選同一磁軌上的那個
            if minEst == -1 or totalEst < minEst:
                minEst   = totalEst
                minBlock = block
                minIndex = index
                # print '  更新 minBlock', minBlock, minIndex
            # print ''
            # 迴圈結束

        # 完成後
        self.totalEst = minEst
        assert(minBlock != -1)
        assert(minIndex != -1)
        return (minBlock, minIndex)

    #
    # 其實沒有完全實作 SSTF
    # 只是找出最近磁軌上的所有區塊
    # （不管那是哪個磁軌）並把它們變成一個清單回傳
    #
    def DoSSTF(self, rList):
        minDist   = MAXTRACKS
        minBlock  = -1
        trackList = []  # 同一磁軌上的所有區塊

        for (block, index) in rList:
            if self.requestState[index] == STATE_DONE:
                continue
            track = self.blockToTrackMap[block]
            dist  = int(math.fabs(self.armTrack - track))
            if dist < minDist:
                trackList = []
                trackList.append((block, index))
                minDist = dist
            elif dist == minDist:
                trackList.append((block, index))
        assert(trackList != [])
        return trackList

    def UpdateWindow(self):
        if self.fairWindow == -1 and self.currWindow > 0 and self.currWindow < len(self.requestQueue):
            self.currWindow += 1
            if self.graphics:
                self.DrawWindow()

    # 注意：這個方法不只是「取得」視窗大小，必要時也會更新它
    # （在該更新的時候）
    def GetWindow(self):
        if self.currWindow <= -1:
            return len(self.requestQueue)
        else:
            if self.fairWindow != -1:
                # 目前有設定一個視窗 -
                # print '  目前視窗', self.currWindow, '  公平性視窗', self.fairWindow, ' 請求數量', self.requestCount
                if self.requestCount > 0 and (self.requestCount % self.fairWindow == 0):
                    self.currWindow = self.currWindow + self.fairWindow
                    # print '  -> 更新目前視窗', self.currWindow
                    if self.graphics:
                        self.DrawWindow()
                return self.currWindow
            else:
                return self.currWindow

    def GetNextIO(self):
        # 檢查是否完成：如果是，印出統計資訊並結束動畫
        if self.requestCount == len(self.requestQueue):
            self.UpdateTime()
            self.PrintStats()
            self.doAnimate = False
            self.isDone = True
            return

        # 執行排程策略：應該要設定 currentBlock
        if self.policy == 'FIFO':
            (self.currentBlock, self.currentIndex) = self.requestQueue[self.requestCount]
            self.DoSATF(self.requestQueue[self.requestCount:self.requestCount+1])
        elif self.policy == 'SATF' or self.policy == 'BSATF':
            endIndex = self.GetWindow()
            # print '  GetWindow():', endIndex
            if endIndex > len(self.requestQueue):
                endIndex = len(self.requestQueue)
            (self.currentBlock, self.currentIndex) = self.DoSATF(self.requestQueue[0:endIndex])
        elif self.policy == 'SSTF':
            # 首先，在視窗限制範圍內，找出某個磁軌上的所有區塊
            trackList = self.DoSSTF(self.requestQueue[0:self.GetWindow()])
            # 接著，對這些區塊做 SATF（否則它們的處理順序會不明顯）
            (self.currentBlock, self.currentIndex) = self.DoSATF(trackList)
        else:
            print('排程策略 (%s) 尚未實作' % self.policy)
            sys.exit(1)

        # 決定最佳區塊之後，就直接進行尋道
        self.PlanSeek(self.blockToTrackMap[self.currentBlock])

        # 要再加入另一個區塊嗎？
        if len(self.lateRequests) > 0 and self.lateCount < len(self.lateRequests):
            self.AddRequest(self.lateRequests[self.lateCount])
            self.lateCount += 1

    def Animate(self):
        if self.graphics == True and self.doAnimate == False:
            self.root.after(20, self.Animate)
            return

        # 計時器
        self.timer += 1
        self.UpdateTime()

        # 看看磁碟上有哪些區塊正在轉動
        # print('目前角度', self.angle)
        self.angle = self.angle + self.rotateSpeed
        if self.angle >= 360.0:
            self.angle = 0.0

        # 移動這些區塊
        if self.graphics:
            for (track, angle, name, cid) in self.blockInfoList:
                distFromSpindle = self.tracks[track]
                na = angle - self.angle
                xc = self.spindleX + (distFromSpindle * math.cos(math.radians(na)))
                yc = self.spindleY + (distFromSpindle * math.sin(math.radians(na)))
                if self.graphics:
                    self.canvas.coords(cid, xc, yc)
                    if self.currentBlock == name:
                        sz = self.targetSize
                        self.canvas.coords(self.targetID, xc-sz, yc-sz, xc+sz, yc+sz)

        # 移動手臂，或是等待旋轉延遲
        if self.state == STATE_SEEK:
            if self.DoneWithSeek():
                self.rotBegin   = self.timer
                self.SwitchState(STATE_ROTATE)
                self.SwitchColors('lightblue')
        if self.state == STATE_ROTATE:
            # 檢查是否可以讀取（磁碟手臂必須已經定位好）
            if self.DoneWithRotation():
                self.xferBegin = self.timer
                self.SwitchState(STATE_XFER)
                self.SwitchColors('green')
        if self.state == STATE_XFER:
            if self.DoneWithTransfer():
                self.DoRequestStats()
                self.SwitchState(STATE_DONE)
                self.SwitchColors('red')
                self.UpdateWindow()
                currentBlock = self.currentBlock
                self.GetNextIO()
                nextBlock = self.currentBlock
                if self.blockToTrackMap[currentBlock] == self.blockToTrackMap[nextBlock]:
                    if (currentBlock == self.tracksBeginEnd[self.armTrack][1] and nextBlock == self.tracksBeginEnd[self.armTrack][0]) or (currentBlock + 1 == nextBlock):
                        # 這裡需要一個特殊情況：處理持續停留在傳輸模式的狀況
                        (self.rotBegin, self.seekBegin, self.xferBegin) = (self.timer, self.timer, self.timer)
                        self.SwitchState(STATE_XFER)
                        self.SwitchColors('green')



        # 記得要讓動畫持續進行！
        if self.graphics:
            self.root.after(20, self.Animate)

    def DoRequestStats(self):
        seekTime  = self.rotBegin  - self.seekBegin
        rotTime   = self.xferBegin - self.rotBegin
        xferTime  = self.timer     - self.xferBegin
        totalTime = self.timer     - self.seekBegin

        if self.compute == True:
            print('區塊:%3d  尋道:%3d  旋轉:%3d  傳輸:%3d  總計:%4d' % (self.currentBlock, seekTime, rotTime, xferTime, totalTime))

        # if int(totalTime) != int(self.totalEst):
        #     print '內部錯誤：預估值是', self.totalEst, '但實際存取區塊花費的時間是', totalTime
        #     print '請回報這個 bug，並附上盡可能多的資訊，方便重現問題。謝謝！'

        # 更新統計數據
        self.seekTotal += seekTime
        self.rotTotal  += rotTime
        self.xferTotal += xferTime



    def PrintStats(self):
        if self.compute == True:
            print('\n總和        尋道:%3d  旋轉:%3d  傳輸:%3d  總計:%4d\n' % (self.seekTotal, self.rotTotal, self.xferTotal, self.timer))

# Disk 類別結束



#
# 主模擬程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',            default='0',         help='隨機種子',                                             action='store', type='int',    dest='seed')
parser.add_option('-a', '--addr',            default='-1',        help='請求清單（以逗號分隔）[-1 -> 使用 addrDesc]',     action='store', type='string', dest='addr')
parser.add_option('-A', '--addrDesc',        default='5,-1,0',    help='請求數量、最大請求值（-1 表示全部）、最小請求值',        action='store', type='string', dest='addrDesc')
parser.add_option('-S', '--seekSpeed',       default='1',         help='尋道速度',                                           action='store', type='string', dest='seekSpeed')
parser.add_option('-R', '--rotSpeed',        default='1',         help='旋轉速度',                                       action='store', type='string', dest='rotateSpeed')
parser.add_option('-p', '--policy',          default='FIFO',      help='排程策略（FIFO、SSTF、SATF、BSATF）',             action='store', type='string', dest='policy')
parser.add_option('-w', '--schedWindow',     default=-1,          help='排程視窗的大小（-1 表示全部）',                   action='store', type='int',    dest='window')
parser.add_option('-o', '--skewOffset',      default=0,           help='偏移量（以區塊為單位）',                              action='store', type='int',    dest='skew')
parser.add_option('-z', '--zoning',          default='30,30,30',  help='外、中、內磁軌上區塊之間的角度',      action='store', type='string', dest='zoning')
parser.add_option('-G', '--graphics',        default=False,       help='開啟圖形模式',                                        action='store_true',           dest='graphics')
parser.add_option('-l', '--lateAddr',        default='-1',        help='延遲請求：請求清單（以逗號分隔）[-1 -> 隨機]',     action='store', type='string', dest='lateAddr')
parser.add_option('-L', '--lateAddrDesc',    default='0,-1,0',    help='請求數量、最大請求值（-1 表示全部）、最小請求值',        action='store', type='string', dest='lateAddrDesc')
parser.add_option('-c', '--compute',         default=False,       help='計算答案',                                     action='store_true',           dest='compute')
(options, args) = parser.parse_args()

print('選項 種子', options.seed)
print('選項 位址', options.addr)
print('選項 位址描述', options.addrDesc)
print('選項 尋道速度', options.seekSpeed)
print('選項 旋轉速度', options.rotateSpeed)
print('選項 偏移量', options.skew)
print('選項 排程視窗', options.window)
print('選項 排程策略', options.policy)
print('選項 計算', options.compute)
print('選項 圖形模式', options.graphics)
print('選項 區塊角度', options.zoning)
print('選項 延遲位址', options.lateAddr)
print('選項 延遲位址描述', options.lateAddrDesc)
print('')

if options.window == 0:
    print('排程視窗 (%d) 必須是正整數，或是 -1（表示完整視窗）' % options.window)
    sys.exit(1)

if options.graphics and options.compute == False:
    print('\n警告：由於圖形模式已開啟，將 compute 旗標設為 True\n')
    options.compute = True

# 設定模擬器資訊
d = Disk(addr=options.addr, addrDesc=options.addrDesc, lateAddr=options.lateAddr, lateAddrDesc=options.lateAddrDesc,
         policy=options.policy, seekSpeed=float(options.seekSpeed), rotateSpeed=float(options.rotateSpeed),
         skew=options.skew, window=options.window, compute=options.compute, graphics=options.graphics, zoning=options.zoning)

# 執行模擬
d.Go()
