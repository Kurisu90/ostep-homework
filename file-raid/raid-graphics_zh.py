#! /usr/bin/env python
# -*- coding: utf-8 -*-

from Tkinter import *
from types import *
import math, random, time, sys, os
from optparse import OptionParser

# 一個請求／磁碟會經歷的狀態
STATE_NULL   = 0
STATE_SEEK   = 1
STATE_XFER   = 2
STATE_DONE   = 3

# 請求的狀態
REQ_NOT_STARTED = 0
REQ_DO_READ = 1
REQ_DO_WRITE = 2
# 給 parity（同位）請求使用
REQ_PARITY_READ_PHASE_DONE = 4
REQ_PARITY_WRITE_PHASE_BEGIN = 5
# 所有請求最後都會進入 DONE 狀態
REQ_DONE = 10

# 請求是讀取還是寫入
OP_READ = 1
OP_WRITE = 2

class Request:
    def __init__(self, logical_address, op_type):
        self.logical_address = logical_address
        assert(op_type == OP_WRITE or op_type == OP_READ)
        self.op_type = op_type
        self.disk_to_index_map = {}
        self.full_stripe_write = False
        self.full_stripe_write_parity = False
        self.start_time = -1
        return

    def MarkFullStripeWrite(self, parity=False):
        self.full_stripe_write = True
        self.full_stripe_write_parity = parity
        return

    def FullStripeWriteStatus(self):
        return (self.full_stripe_write, self.full_stripe_write_parity)

    def GetType(self):
        return self.op_type

    def GetLogicalAddress(self):
        return self.logical_address

    def GetStatus(self, index):
        return self.status[index]

    def GetStatusByDisk(self, disk):
        index = self.disk_to_index_map[disk]
        return self.status[index]

    def SetStatus(self, index, status):
        # print 'STATUS', self.phys_disk_list[index], self.PrintableStatus(status)
        self.status[index] = status

    def SetPhysicalAddress(self, disk_list, offset):
        self.phys_disk_list = disk_list
        cnt = 0
        for disk in self.phys_disk_list:
            self.disk_to_index_map[disk] = cnt
            cnt += 1
        self.phys_offset = offset
        self.status = []
        for disk in self.phys_disk_list:
            self.status.append(REQ_NOT_STARTED)
        return

    def PrintableStatus(self, status):
        if status == REQ_NOT_STARTED:
            return 'REQ_NOT_STARTED'
        if status == REQ_DO_WRITE:
            return 'REQ_DO_WRITE'
        if status == REQ_DO_READ:
            return 'REQ_DO_READ'
        if status == REQ_DONE:
            return 'REQ_DONE'
        if status == REQ_PARITY_READ_PHASE_DONE:
            return 'REQ_PARITY_READ_PHASE_DONE'
        if status == REQ_PARITY_WRITE_PHASE_BEGIN:
            return 'REQ_PARITY_WRITE_PHASE_BEGIN'
        print '狀態錯誤', status
        exit(1)
        return

    def MarkStart(self, timer):
        if self.start_time == -1:
            self.start_time = timer
        return

    def RequestLevel0Done(self, disk, timer):
        index = self.disk_to_index_map[disk]
        if self.status[index] == REQ_DO_READ or self.status[index] == REQ_DO_WRITE:
            self.status[index] = REQ_DONE
        return (True, timer - self.start_time)

    def RequestLevel1Done(self, disk, timer):
        index = self.disk_to_index_map[disk]
        if self.status[index] == REQ_DO_READ:
            self.status[index] = REQ_DONE
            return (True, timer - self.start_time)
        # 這是給 WRITE 用的（兩邊都寫完才算完成）
        assert(self.status[index] == REQ_DO_WRITE)
        self.status[index] = REQ_DONE
        if self.status[1-index] == REQ_DONE:
            return (True, timer - self.start_time)
        return (False, -1)

    # 目前這是給 RAID4 用的
    def RequestLevel4Done(self, disk, timer):
        index = self.disk_to_index_map[disk]
        # print 'Done', self.PrintableStatus(self.status[index])
        if self.op_type == OP_READ:
            return (True, timer - self.start_time)
        # 這是給 WRITE 用的（分成兩個階段）
        if self.status[index] == REQ_DO_READ:
            self.status[index] = REQ_PARITY_READ_PHASE_DONE
        elif self.status[index] == REQ_DO_WRITE:
            self.status[index] = REQ_DONE
        if self.status[index] == REQ_PARITY_READ_PHASE_DONE and self.status[1-index] == REQ_PARITY_READ_PHASE_DONE:
            self.status[0] = REQ_PARITY_WRITE_PHASE_BEGIN
            self.status[1] = REQ_PARITY_WRITE_PHASE_BEGIN
        if self.status[index] == REQ_DONE and self.status[1-index] == REQ_DONE:
            return (True, timer - self.start_time)
        return (False, -1)

    def GetPhysicalOffset(self):
        return self.phys_offset

    def GetPhysicalDiskList(self):
        return self.phys_disk_list


class Raid:
    def __init__(self, mapping, addr_desc, addr, disk_count, seek_speed, seed, balance, read_fraction, window, animate_delay):
        self.mapping = mapping
        self.disk_count = disk_count
        self.seek_speed = seek_speed
        self.addr_desc = addr_desc
        self.balance = balance
        self.addr = addr
        self.read_fraction = read_fraction
        self.window = window
        self.animate_delay = animate_delay

        random.seed(seed)

        self.root = Tk()
        self.canvas = Canvas(self.root, width=560, height=530)
        self.canvas.pack()

        # 建立各個磁碟
        disk_width = 100
        self.head_width = 10
        self.head_height = 20

        # 接下來分配各個區塊──先假設是 striping（分條）
        self.block_offset = {}

        # 給排程用的對照表
        self.offset_to_ypos = {}

        # 給「磁碟」區塊上色用的對照表
        self.disk_and_offset_to_rect_id = {}

        self.color_map = {}

        if self.mapping == 0:
            # 建立 STRIPING（分條）配置
            self.block_count = 80
            for i in range(self.block_count):
                disk = i % self.disk_count
                offset = i / self.disk_count
                rect_x = 40 + ((20 + disk_width) * disk)
                rect_y = (20 * offset) + 100
                self.color_map[(disk, offset)] = 'gray'
                rect_id = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='gray', outline='black')
                text_id = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='%s' % i, anchor='c')
                self.block_offset[i] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk, offset)] = rect_id

        elif self.mapping == 1:
            # 建立 MIRRORING（鏡像）配置
            self.block_count = 40
            effective_disks = self.disk_count / 2
            assert(self.disk_count % 2 == 0)
            for i in range(self.block_count):
                INDEX = i % effective_disks
                disk_1 = INDEX * 2
                disk_2 = disk_1 + 1
                offset = i / effective_disks
                rect_y = (20 * offset) + 100

                rect_x = 40 + ((20 + disk_width) * disk_1)
                self.color_map[(disk_1, offset)] = 'gray'
                rect_id_1 = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='gray', outline='black')
                text_id_1 = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='%s' % i, anchor='c')

                rect_x = 40 + ((20 + disk_width) * disk_2)
                self.color_map[(disk_2, offset)] = 'gray'
                rect_id_2 = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='gray', outline='black')
                text_id_2 = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='%s' % i, anchor='c')

                self.block_offset[i] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk_1, offset)] = rect_id_1
                self.disk_and_offset_to_rect_id[(disk_2, offset)] = rect_id_2

        elif self.mapping == 4:
            # 建立簡單的 PARITY（同位檢查）配置
            self.block_count_full = 80
            self.block_count = 60
            for i in range(self.block_count):
                disk = i % (self.disk_count-1)
                offset = i / (self.disk_count-1)
                rect_x = 40 + ((20 + disk_width) * disk)
                rect_y = (20 * offset) + 100
                self.color_map[(disk, offset)] = 'lightgray'
                rect_id = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='lightgray', outline='black')
                text_id = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='%s' % i, anchor='c')
                self.block_offset[i] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk, offset)] = rect_id

            # 接著建立 parity（同位）區塊
            for i in range(self.block_count_full/self.disk_count):
                disk = 3
                offset = i
                rect_x = 40 + ((20 + disk_width) * disk)
                rect_y = (20 * offset) + 100
                self.color_map[(disk, offset)] = 'darkgray'
                rect_id = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='darkgray', outline='black')
                text_id = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='P%s' % i, anchor='c')
                self.block_offset['p' + str(i)] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk, offset)] = rect_id

        elif self.mapping == 5:
            # 建立 RAID-5 配置
            self.block_count_full = 80
            self.block_count = 60
            for i in range(self.block_count):
                offset = i / (self.disk_count-1)
                if offset % 4 == 0:
                    disk = i % (self.disk_count-1)
                elif offset % 4 == 1:
                    disk = i % (self.disk_count-1)
                    if disk >= 2:
                        disk += 1
                elif offset % 4 == 2:
                    disk = i % (self.disk_count-1)
                    if disk >= 1:
                        disk += 1
                elif offset % 4 == 3:
                    disk = i % (self.disk_count-1)
                    disk += 1
                rect_x = 40 + ((20 + disk_width) * disk)
                rect_y = (20 * offset) + 100
                self.color_map[(disk, offset)] = 'gray'
                rect_id = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='gray', outline='black')
                text_id = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='%s' % i, anchor='c')
                self.block_offset[i] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk, offset)] = rect_id

            # 接著建立 parity（同位）區塊
            for i in range(self.block_count_full/self.disk_count):
                offset = i
                if offset % 4 == 0:
                    disk = 3
                elif offset % 4 == 1:
                    disk = 2
                elif offset % 4 == 2:
                    disk = 1
                elif offset % 4 == 3:
                    disk = 0
                rect_x = 40 + ((20 + disk_width) * disk)
                rect_y = (20 * offset) + 100
                self.color_map[(disk, offset)] = 'darkgray'
                rect_id = self.canvas.create_rectangle(rect_x, rect_y, rect_x+disk_width, rect_y+20, fill='darkgray', outline='black')
                text_id = self.canvas.create_text(rect_x + disk_width - disk_width/2.0, rect_y+10, text='P%s' % i, anchor='c')
                self.block_offset['p' + str(i)] = rect_y
                self.offset_to_ypos[offset] = rect_y
                self.disk_and_offset_to_rect_id[(disk, offset)] = rect_id

        else:
            print 'mapping', self.mapping, '不支援'
            exit(1)

        # 接著畫出「磁碟讀寫頭」
        self.head_ids = {}
        self.head_position = {}
        self.disk_state = {}
        for disk in range(self.disk_count):
            rect_x = 40 - self.head_width + ((20 + disk_width) * disk)
            rect_y = 100
            head_id = self.canvas.create_rectangle(rect_x, rect_y,
                                                   rect_x+self.head_width, rect_y+self.head_height,
                                                   fill='black', outline='black')
            self.head_ids[disk] = head_id
            self.head_position[disk] = {'x1':rect_x, 'y1':rect_y, 'x2':rect_x+self.head_width, 'y2':rect_y+self.head_height}
            self.disk_state[disk] = STATE_NULL

        # 尋軌目標
        self.last_target = {}
        self.current_target = {}
        self.current_optype = {}
        self.seek_delta = {}
        for disk in range(self.disk_count):
            self.last_target[disk] = -1
            self.current_target[disk] = -1
            self.current_optype[disk] = -1
            self.seek_delta[disk] = 0

        self.transfer_count = {}
        self.rotate_count = {}
        for disk in range(self.disk_count):
            self.transfer_count[disk] = -1
            self.rotate_count[disk] = -1

        # 初始的請求
        self.request_queue = {}
        self.request_count = 0

        effective_disk_count = 4
        if self.mapping == 4:
            effective_disk_count = 3

        if self.addr == '':
            # 用 'addr_desc'（要產生的數量、最大值、最小值）來產生這些請求
            tmp = self.addr_desc.split(',')
            num = int(tmp[0])
            req_max = int(tmp[1])
            if req_max == -1:
                req_max = self.block_count
            req_min = int(tmp[2])
            if self.balance:
                disk_min = num / effective_disk_count
            if req_min >= req_max:
                print 'addr_desc 不合法：最小值必須小於最大值', req_min, req_max
                exit(1)
            target_disk = 0
            for i in range(num):
                while True:
                    req = int(random.random() * req_max)
                    if req % effective_disk_count != target_disk:
                        continue
                    target_disk += 1
                    if target_disk == effective_disk_count:
                        target_disk = 0
                    # print target_disk
                    if req >= req_min:
                        if random.random() < read_fraction:
                            self.request_queue[i] = Request(req, OP_READ)
                        else:
                            self.request_queue[i] = Request(req, OP_WRITE)
                        break
        else:
            # 直接手動指定位址
            # 引數：以逗號分隔的數字清單
            tmp = self.addr.split(',')
            for i in range(len(tmp)):
                if tmp[i][0] == 'r':
                    self.request_queue[i] = Request(int(tmp[i].replace('r','')), OP_READ)
                elif tmp[i][0] == 'w':
                    self.request_queue[i] = Request(int(tmp[i].replace('w','')), OP_WRITE)
                else:
                    print '必須指定是讀取還是寫入，例如 r10 或 w6'
                    exit(1)

        self.request_count_needed = len(self.request_queue)

        # 補上請求的額外資訊
        if self.mapping == 0:
            # STRIPING（分條）
            for i in range(len(self.request_queue)):
                request = self.request_queue[i]
                logical = request.GetLogicalAddress()
                assert(logical < self.block_count)
                disk = logical % self.disk_count
                offset = logical / self.disk_count
                request.SetPhysicalAddress([disk], offset)
        elif self.mapping == 1:
            # MIRRORING（鏡像）
            for i in range(len(self.request_queue)):
                request = self.request_queue[i]
                if request.GetType() == OP_WRITE:
                    self.request_count_needed += 1
                effective_disks = self.disk_count / 2
                logical = request.GetLogicalAddress()
                assert(logical < self.block_count)
                disk_1 = 2 * (logical % effective_disks)
                disk_2 = disk_1 + 1
                offset = logical / effective_disks
                request.SetPhysicalAddress([disk_1, disk_2], offset)
        elif self.mapping == 4:
            # RAID-4（同位檢查磁碟）
            for i in range(len(self.request_queue)):
                request = self.request_queue[i]
                if request.GetType() == OP_WRITE:
                    self.request_count_needed += 3
                logical = request.GetLogicalAddress()
                assert(logical < self.block_count)
                disk = logical % (self.disk_count-1)
                offset = logical / (self.disk_count-1)
                request.SetPhysicalAddress([disk, 3], offset)

            # XXX 這其實只在「某些」示範情境下才會正確
            # （並不是通用的功能）
            for i in range(0,len(self.request_queue),3):
                if i+2 >= len(self.request_queue):
                    continue
                logical = self.request_queue[i].GetLogicalAddress()
                if self.request_queue[i+1].GetLogicalAddress() == logical + 1:
                    if self.request_queue[i+2].GetLogicalAddress() == logical + 2:
                        # 偵測到整條 stripe 的寫入：標記起來，排程時特別處理
                        for j in range(i, i+2):
                            self.request_queue[j].MarkFullStripeWrite()
                        self.request_queue[i+2].MarkFullStripeWrite(True)
                        self.request_count_needed -= 8

        elif self.mapping == 5:
            # RAID-5（輪流的同位檢查）
            for i in range(len(self.request_queue)):
                request = self.request_queue[i]
                if request.GetType() == OP_WRITE:
                    self.request_count_needed += 3
                logical = request.GetLogicalAddress()
                assert(logical < self.block_count)
                disk = logical % (self.disk_count-1)
                offset = logical / (self.disk_count-1)
                if offset % 4 == 0:
                    parity_disk = 3
                elif offset % 4 == 1:
                    parity_disk = 2
                    if disk >= 2:
                        disk += 1
                elif offset % 4 == 2:
                    parity_disk = 1
                    if disk >= 1:
                        disk += 1
                elif offset % 4 == 3:
                    parity_disk = 0
                    disk += 1

                # print 'LOGICAL', logical, 'offset', offset, 'disk', disk, 'paritydisk', parity_disk
                request.SetPhysicalAddress([disk, parity_disk], offset)


        # 畫出請求佇列
        self.request_queue_box_ids = []
        self.request_queue_text_ids = []
        self.request_queue_count_ids = []
        self.request_queue_counts = []

        x_start = 40
        x = x_start
        y = 32
        sz = 10

        font = ('Helvetica', sz+4)
        font_small = ('Helvetica', 8)

        for index in range(len(self.request_queue)):
            if x > 500:
                x = x_start
                y += (2*sz) + 2

            request = self.request_queue[index]
            logical = request.GetLogicalAddress()
            self.request_queue_box_ids.append(self.canvas.create_rectangle(x-sz,y-sz,x+sz,y+sz,fill='white',outline=''))
            self.request_queue_text_ids.append(self.canvas.create_text(x, y, text=str(logical), anchor='c', font=font))
            self.request_queue_count_ids.append(self.canvas.create_text(x+8, y+8, text=str(0), anchor='c', font=font_small))
            self.request_queue_counts.append(0)

            x += (2*sz)

        # 按鍵綁定
        self.root.bind('s', self.Start)
        self.root.bind('p', self.Pause)
        self.root.bind('q', self.Exit)

        # 畫出佇列目前的邊界
        self.windowID = -1
        self.DrawWindow()

        # 時間資訊與其他統計數據
        self.timeID = self.canvas.create_text(10, 10, text='時間：0.00', anchor='w')
        self.timer = 0

        self.logical_requests = 0
        self.latency_total = 0

        # 讀取／寫入計數
        self.count_reads = {}
        self.count_writes = {}
        self.count_reads_id = {}
        self.count_writes_id = {}
        x = disk_width - 10
        font = ('Helvetica', 14)
        for i in range(self.disk_count):
            self.count_reads[i] = 0
            self.count_writes[i] = 0
            self.canvas.create_rectangle(x-50,510,x,530, fill='orange', outline='')
            self.canvas.create_rectangle(x+50,510,x,530, fill='yellow', outline='')
            self.count_reads_id[i] = self.canvas.create_text(x-20, 520, text='R:0', anchor='c', font=font)
            self.count_writes_id[i] = self.canvas.create_text(x+20, 520, text='W:0', anchor='c', font=font)
            x += disk_width + 20


        # 設定動畫迴圈
        self.do_animate = True
        self.is_done = False
        return

    # 呼叫這個函式來開始模擬
    def Go(self):
        self.root.mainloop()
        return

    #
    # 按鍵功能
    #
    def Start(self, event):
        self.GetNextIOs()
        self.Animate()
        return

    def Pause(self, event):
        if self.do_animate == False:
            self.do_animate = True
        else:
            self.do_animate = False
        return

    def Exit(self, event):
        sys.exit(0)
        return

    #
    # 各種功能函式
    #
    def UpdateWriteCounter(self, disk, how_much):
        self.count_writes[disk] += how_much
        self.canvas.itemconfig(self.count_writes_id[disk], text='W:%d' % self.count_writes[disk])
        return

    def UpdateReadCounter(self, disk, how_much):
        self.count_reads[disk] += how_much
        self.canvas.itemconfig(self.count_reads_id[disk], text='R:%d' % self.count_reads[disk])
        return

    def UpdateTime(self):
        self.canvas.itemconfig(self.timeID, text='時間：' + str(self.timer))
        return

    def DrawWindow(self):
        return

    def BlockSetColor(self, disk, offset, color):
        block_id = self.disk_and_offset_to_rect_id[(disk, offset)]
        self.canvas.itemconfig(block_id, fill=color)
        return

    def QueueSetColor(self, index, fill_color):
        box_id = self.request_queue_box_ids[index]
        self.canvas.itemconfig(box_id, fill=fill_color)
        self.request_queue_counts[index] += 1
        count_id = self.request_queue_count_ids[index]
        self.canvas.itemconfig(count_id, text='%d' % self.request_queue_counts[index])
        return

    def SetSeekDirection(self, disk, dest_block):
        if self.GetHeadPosition(disk) < self.block_offset[dest_block]:
            self.seek_delta[disk] = self.seek_speed
        else:
            self.seek_delta[disk] = -self.seek_speed
        return

    def StartRead(self, disk, offset, logical_address, request, queue_index):
        self.current_optype[disk] = OP_READ
        self.StartRequest(disk, offset, logical_address, request, queue_index, 'orange')
        return

    def StartWrite(self, disk, offset, logical_address, request, queue_index):
        self.current_optype[disk] = OP_WRITE
        self.StartRequest(disk, offset, logical_address, request, queue_index, 'yellow')
        return

    def StartRequest(self, disk, offset, logical_address, request, queue_index, fill_color):
        self.QueueSetColor(queue_index, fill_color)
        self.disk_state[disk] = STATE_SEEK
        self.BlockSetColor(disk, offset, fill_color)
        self.SetSeekDirection(disk, logical_address)
        self.last_target[disk] = self.current_target[disk]
        self.current_target[disk] = request
        return

    def DoStripeScheduling(self, disk, index):
        request = self.request_queue[index]
        logical = request.GetLogicalAddress()
        if request.GetStatus(0) == REQ_NOT_STARTED and logical % self.disk_count == disk:
            offset = request.GetPhysicalOffset()
            request.MarkStart(self.timer)
            if request.GetType() == OP_READ:
                request.SetStatus(0, REQ_DO_READ)
                self.StartRead(disk, offset, logical, request, index)
            else:
                request.SetStatus(0, REQ_DO_WRITE)
                self.StartWrite(disk, offset, logical, request, index)
            return
        return

    def DoMirrorScheduling(self, disk, index):
        request = self.request_queue[index]
        logical = request.GetLogicalAddress()

        disks = request.GetPhysicalDiskList()
        if disks[0] == disk:
            disk_index = 0
        elif disks[1] == disk:
            disk_index = 1
        else:
            return

        if request.GetStatus(disk_index) == REQ_NOT_STARTED and (disk == disks[0] or disk == disks[1]):
            offset = request.GetPhysicalOffset()
            request.MarkStart(self.timer)
            if request.GetType() == OP_READ:
                request.SetStatus(disk_index, REQ_DO_READ)
                request.SetStatus(1 - disk_index, REQ_DONE)
                self.StartRead(disk, offset, logical, request, index)
            else:
                request.SetStatus(disk_index, REQ_DO_WRITE)
                self.StartWrite(disk, offset, logical, request, index)
            return
        return

    def DoRaid4Scheduling(self, disk, index):
        request = self.request_queue[index]
        logical = request.GetLogicalAddress()

        # 讀取：簡單情況，跟 striping 的讀取一樣
        if request.GetType() == OP_READ and request.GetStatus(0) == REQ_NOT_STARTED and logical % (self.disk_count-1) == disk:
            request.MarkStart(self.timer)
            request.SetStatus(0, REQ_DO_READ)
            offset = request.GetPhysicalOffset()
            self.StartRead(disk, offset, logical, request, index)
            return

        # 接著處理寫入：會變成兩次讀取、兩次寫入
        if request.GetType() != OP_WRITE:
            return
        disks = request.GetPhysicalDiskList()
        if disks[0] != disk and disks[1] != disk:
            return

        if disks[0] == disk:
            disk_index = 0
        elif disks[1] == disk:
            disk_index = 1

        # 檢查是否可能是「整條 stripe 的寫入」
        (full_stripe_write, do_parity) = request.FullStripeWriteStatus()
        if full_stripe_write:
            offset = request.GetPhysicalOffset()
            if do_parity == False and request.GetStatus(disk_index) == REQ_NOT_STARTED:
                # print 'doing FULL STRIPE WRITE (parity)'
                # 這種情況下，關掉兩個讀取，直接寫入 parity 磁碟
                request.MarkStart(self.timer)
                request.SetStatus(disk_index, REQ_DO_WRITE)
                request.SetStatus(1-disk_index, REQ_DONE)
                self.StartWrite(disk, offset, logical, request, index)
                return
            if do_parity == True and request.GetStatus(disk_index) == REQ_NOT_STARTED:
                # 這種情況下，關掉讀取，但確保兩次寫入都會發生
                request.MarkStart(self.timer)
                request.SetStatus(disk_index, REQ_DO_WRITE)
                # request.SetStatus(1, REQ_DO_WRITE)
                # print 'doing FULL STRIPE WRITE (non-parity)'
                self.StartWrite(disk, offset, logical, request, index)
            return

        # 一般情況：SUBTRACTIVE PARITY（減法式同位計算）處理方式
        # 處理一個尚未開始的「邏輯寫入」
        # 一開始會先做一次讀取
        if request.GetStatus(disk_index) == REQ_NOT_STARTED:
            request.MarkStart(self.timer)
            request.SetStatus(disk_index, REQ_DO_READ)
            offset = request.GetPhysicalOffset()
            self.StartRead(disk, offset, logical, request, index)
            return

        # 處理一個進行到一半的「邏輯寫入」
        # 最後會以一次寫入結束
        if request.GetStatus(disk_index) == REQ_PARITY_WRITE_PHASE_BEGIN:
            request.SetStatus(disk_index, REQ_DO_WRITE)
            offset = request.GetPhysicalOffset()
            self.StartWrite(disk, offset, logical, request, index)
            return
        return

    def DoRaid5Scheduling(self, disk, index):
        request = self.request_queue[index]
        logical = request.GetLogicalAddress()

        # 讀取：簡單情況，跟 striping 的讀取一樣
        if request.GetType() == OP_READ and request.GetStatus(0) == REQ_NOT_STARTED and request.GetPhysicalDiskList()[0] == disk:
            request.MarkStart(self.timer)
            request.SetStatus(0, REQ_DO_READ)
            offset = request.GetPhysicalOffset()
            # print 'start', disk, offset
            self.StartRead(disk, offset, logical, request, index)
            return

        # 接著處理寫入：會變成兩次讀取、兩次寫入
        if request.GetType() != OP_WRITE:
            return
        disks = request.GetPhysicalDiskList()
        if disks[0] != disk and disks[1] != disk:
            return

        if disks[0] == disk:
            disk_index = 0
        elif disks[1] == disk:
            disk_index = 1

        # 一般情況：SUBTRACTIVE PARITY（減法式同位計算）處理方式
        # 處理一個尚未開始的「邏輯寫入」
        # 一開始會先做一次讀取
        if request.GetStatus(disk_index) == REQ_NOT_STARTED:
            request.MarkStart(self.timer)
            request.SetStatus(disk_index, REQ_DO_READ)
            offset = request.GetPhysicalOffset()
            # print 'start read', logical, disk, offset
            self.StartRead(disk, offset, logical, request, index)
            return

        # 處理一個進行到一半的「邏輯寫入」
        # 最後會以一次寫入結束
        if request.GetStatus(disk_index) == REQ_PARITY_WRITE_PHASE_BEGIN:
            request.SetStatus(disk_index, REQ_DO_WRITE)
            offset = request.GetPhysicalOffset()
            # print 'start write', logical, disk, offset
            self.StartWrite(disk, offset, logical, request, index)
            return
        return


    def GetNextIOs(self):
        # 檢查是否已經完成：如果是，印出統計數據並結束動畫
        if self.request_count == self.request_count_needed:
            self.UpdateTime()
            self.PrintStats()
            self.do_animate = False
            self.is_done = True
            return

        # 排程器
        for disk in range(self.disk_count):
            count = 0
            for index in self.request_queue:
                if self.window != -1 and count >= self.window:
                    continue
                count += 1
                if self.mapping == 0:
                    if self.disk_state[disk] == STATE_NULL:
                        self.DoStripeScheduling(disk, index)
                elif self.mapping == 1:
                    if self.disk_state[disk] == STATE_NULL:
                        self.DoMirrorScheduling(disk, index)
                elif self.mapping == 4:
                    if self.disk_state[disk] == STATE_NULL:
                        self.DoRaid4Scheduling(disk, index)
                elif self.mapping == 5:
                    if self.disk_state[disk] == STATE_NULL:
                        self.DoRaid5Scheduling(disk, index)
        return

    def GetHeadPosition(self, disk):
        return self.head_position[disk]['y1']

    def MoveHead(self, disk):
        self.head_position[disk]['y1'] += self.seek_delta[disk]
        self.head_position[disk]['y2'] += self.seek_delta[disk]
        self.canvas.coords(self.head_ids[disk],
                           self.head_position[disk]['x1'], self.head_position[disk]['y1'],
                           self.head_position[disk]['x2'], self.head_position[disk]['y2'])
        return

    def DoneWithSeek(self, disk):
        request = self.current_target[disk]
        if self.GetHeadPosition(disk) == self.offset_to_ypos[request.GetPhysicalOffset()]:
            return True
        return False

    def StartTransfer(self, disk):
        offset_current = self.current_target[disk].GetPhysicalOffset()
        if self.last_target[disk] == -1:
            offset_last = -1
        else:
            # print self.last_target[disk]
            offset_last = self.last_target[disk].GetPhysicalOffset()
        if offset_current == offset_last + 1:
            self.transfer_count[disk] = 1
        else:
            self.transfer_count[disk] = 10
        return

    def DoneWithTransfer(self, disk):
        return self.transfer_count[disk] == 0

    # 當單一個 IO 完成時呼叫
    # 注意：一個 request（例如鏡像或同位檢查的寫入）可能包含多個 IO
    def MarkDone(self, disk):
        request = self.current_target[disk]
        low_level_op_type = self.current_optype[disk]

        if low_level_op_type == OP_WRITE:
            self.UpdateWriteCounter(disk, 1)
        elif low_level_op_type == OP_READ:
            self.UpdateReadCounter(disk, 1)

        # 這是用來讓 IO 在不同階段之間移動的
        if self.mapping == 4 or self.mapping == 5:
            (request_done, latency) = request.RequestLevel4Done(disk, self.timer)
        elif self.mapping == 1:
            (request_done, latency) = request.RequestLevel1Done(disk, self.timer)
        elif self.mapping == 0:
            (request_done, latency) = request.RequestLevel0Done(disk, self.timer)

        if request_done:
            self.logical_requests += 1
            self.latency_total += latency
            # print 'LATENCY', latency
            if self.window > 0:
                self.window += 1
        return

    def Animate(self):
        if self.do_animate == False:
            self.root.after(self.animate_delay, self.Animate)
            return

        # 計時器
        self.timer += 1
        self.UpdateTime()

        # 移動各個區塊
        # 接著檢查是否該有事情發生了
        for disk in range(self.disk_count):
            if self.disk_state[disk] == STATE_SEEK:
                if self.DoneWithSeek(disk):
                    self.disk_state[disk] = STATE_XFER
                    block_id = self.disk_and_offset_to_rect_id[(disk, self.current_target[disk].GetPhysicalOffset())]
                    self.StartTransfer(disk)
                else:
                    self.MoveHead(disk)
            if self.disk_state[disk] == STATE_XFER:
                self.transfer_count[disk] -= 1
                if self.DoneWithTransfer(disk):
                    offset = self.current_target[disk].GetPhysicalOffset()
                    self.MarkDone(disk)
                    self.request_count += 1
                    self.disk_state[disk] = STATE_NULL
                    self.BlockSetColor(disk, self.current_target[disk].GetPhysicalOffset(), self.color_map[(disk, offset)])
                    self.GetNextIOs()

        # 記得要讓動畫持續跑下去！
        self.root.after(self.animate_delay, self.Animate)
        return

    def DoRequestStats(self):
        return

    def PrintStats(self):
        print '總時間：      ', self.timer
        print '  請求數量：  ', self.logical_requests
        print '  平均延遲：   %.2f' % (float(self.latency_total) / float(self.logical_requests))
        return

# 結束：Disk 類別



#
# 主要模擬器
#
parser = OptionParser()
parser.add_option('-s', '--seed',            default='0',         help='隨機種子',                                                 action='store', type='int',    dest='seed')
parser.add_option('-m', '--mapping',         default='0',         help='0 代表 striping（分條），1 代表 mirroring（鏡像），4 代表 raid4，5 代表 raid5', action='store', type='int',    dest='mapping')
parser.add_option('-a', '--addr',            default='',          help='請求清單（以逗號分隔）[-1 -> 使用 addrDesc]',              action='store', type='string', dest='addr')
parser.add_option('-r', '--read_fraction',   default='0.5',       help='請求中屬於讀取的比例',                                     action='store', type='string', dest='read_fraction')
parser.add_option('-A', '--addr_desc',       default='5,-1,0',    help='請求數量、最大請求值（-1 代表全部）、最小請求值',          action='store', type='string', dest='addr_desc')
parser.add_option('-B', '--balanced',        default=True,        help='若產生隨機請求，讓各磁碟的負載平衡',                       action='store_true',           dest='balance')
parser.add_option('-S', '--seek_speed',      default='4',         help='尋軌速度（1,2,4,5,10,20）',                                action='store', type='int',    dest='seek_speed')
parser.add_option('-p', '--policy',          default='FIFO',      help='排程策略（FIFO, SSTF, SATF, BSATF）',                      action='store', type='string', dest='policy')
parser.add_option('-w', '--window',          default=-1,          help='排程視窗大小（-1 代表全部）',                              action='store', type='int',    dest='window')
parser.add_option('-D', '--delay',           default=20,          help='動畫延遲；數字越大動畫越慢',                               action='store', type='int',    dest='animate_delay')
parser.add_option('-G', '--graphics',        default=True,        help='開啟圖形顯示',                                             action='store_true',           dest='graphics')
parser.add_option('-c', '--compute',         default=False,       help='計算答案',                                                 action='store_true',           dest='compute')
parser.add_option('-P', '--print_options',   default=False,       help='印出目前的選項設定',                                       action='store_true',           dest='print_options')
(options, args) = parser.parse_args()

if options.print_options:
    print '選項 seed（隨機種子）', options.seed
    print '選項 addr（指定的請求位址）', options.addr
    print '選項 addr_desc（隨機請求描述）', options.addr_desc
    print '選項 seek_speed（尋軌速度）', options.seek_speed
    print '選項 window（排程視窗大小）', options.window
    print '選項 policy（排程策略）', options.policy
    print '選項 compute（是否計算答案）', options.compute
    print '選項 read_fraction（讀取比例）', options.read_fraction
    print '選項 graphics（是否顯示圖形）', options.graphics
    print '選項 animate_delay（動畫延遲）', options.animate_delay
    print ''

if options.window == 0:
    print '排程視窗大小（%d）必須是正數，或是 -1（代表完整視窗）' % options.window
    sys.exit(1)

# 建立模擬器所需的資訊
d = Raid(mapping=options.mapping, addr_desc=options.addr_desc, addr=options.addr,
         disk_count=4, seek_speed=options.seek_speed, seed=options.seed, balance=options.balance,
         read_fraction=float(options.read_fraction), window=options.window, animate_delay=options.animate_delay)

# 執行模擬
d.Go()
