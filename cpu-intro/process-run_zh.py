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

# 行程切換的行為
# 注意：以下這些值同時也是 -S/-I 命令列選項實際接受、需要照原樣輸入
# 的字串，因此保持英文，不做翻譯
SCHED_SWITCH_ON_IO = 'SWITCH_ON_IO'
SCHED_SWITCH_ON_END = 'SWITCH_ON_END'

# IO 完成後的行為
IO_RUN_LATER = 'IO_RUN_LATER'
IO_RUN_IMMEDIATE = 'IO_RUN_IMMEDIATE'

# 行程狀態
STATE_RUNNING = '執行中'
STATE_READY = '就緒'
STATE_DONE = '結束'
STATE_WAIT = '阻塞'

# 行程結構中的欄位名稱
PROC_CODE = 'code_'
PROC_PC = 'pc_'
PROC_ID = 'pid_'
PROC_STATE = 'proc_state_'

# 行程可以執行的動作
DO_COMPUTE = 'cpu'
DO_IO = 'io'
DO_IO_DONE = 'io_done'


class scheduler:
    def __init__(self, process_switch_behavior, io_done_behavior, io_length):
        # 記錄每個行程的指令序列
        self.proc_info = {}
        self.process_switch_behavior = process_switch_behavior
        self.io_done_behavior = io_done_behavior
        self.io_length = io_length
        return

    def new_process(self):
        proc_id = len(self.proc_info)
        self.proc_info[proc_id] = {}
        self.proc_info[proc_id][PROC_PC] = 0
        self.proc_info[proc_id][PROC_ID] = proc_id
        self.proc_info[proc_id][PROC_CODE] = []
        self.proc_info[proc_id][PROC_STATE] = STATE_READY
        return proc_id

    # 程式看起來會像這樣：
    #   c7,i,c1,i
    # 意思是
    #   先計算 7 個單位，然後做 I/O，再計算 1 個單位，然後再做 I/O
    def load_program(self, program):
        proc_id = self.new_process()
        for line in program.split(','):
            opcode = line[0]
            if opcode == 'c': # 計算
                num = int(line[1:])
                for i in range(num):
                    self.proc_info[proc_id][PROC_CODE].append(DO_COMPUTE)
            elif opcode == 'i':
                self.proc_info[proc_id][PROC_CODE].append(DO_IO)
                # 額外加一個計算動作，用來處理 I/O 完成
                self.proc_info[proc_id][PROC_CODE].append(DO_IO_DONE)
            else:
                print('不合法的 opcode %s（應該要是 c 或 i）' % opcode)
                exit(1)
        return

    def load(self, program_description):
        proc_id = self.new_process()
        tmp = program_description.split(':')
        if len(tmp) != 2:
            print('描述格式錯誤（%s）：必須是 <x:y> 這種數字格式' % program_description)
            print('  其中 X 是指令的數量')
            print('  Y 是一個指令屬於 CPU（而非 IO）的機率百分比')
            exit(1)

        num_instructions, chance_cpu = int(tmp[0]), float(tmp[1])/100.0
        for i in range(num_instructions):
            if random.random() < chance_cpu:
                self.proc_info[proc_id][PROC_CODE].append(DO_COMPUTE)
            else:
                self.proc_info[proc_id][PROC_CODE].append(DO_IO)
                # 額外加一個計算動作，用來處理 I/O 完成
                self.proc_info[proc_id][PROC_CODE].append(DO_IO_DONE)
        return

    def move_to_ready(self, expected, pid=-1):
        if pid == -1:
            pid = self.curr_proc
        assert(self.proc_info[pid][PROC_STATE] == expected)
        self.proc_info[pid][PROC_STATE] = STATE_READY
        return

    def move_to_wait(self, expected):
        assert(self.proc_info[self.curr_proc][PROC_STATE] == expected)
        self.proc_info[self.curr_proc][PROC_STATE] = STATE_WAIT
        return

    def move_to_running(self, expected):
        assert(self.proc_info[self.curr_proc][PROC_STATE] == expected)
        self.proc_info[self.curr_proc][PROC_STATE] = STATE_RUNNING
        return

    def move_to_done(self, expected):
        assert(self.proc_info[self.curr_proc][PROC_STATE] == expected)
        self.proc_info[self.curr_proc][PROC_STATE] = STATE_DONE
        return

    def next_proc(self, pid=-1):
        if pid != -1:
            self.curr_proc = pid
            self.move_to_running(STATE_READY)
            return
        for pid in range(self.curr_proc + 1, len(self.proc_info)):
            if self.proc_info[pid][PROC_STATE] == STATE_READY:
                self.curr_proc = pid
                self.move_to_running(STATE_READY)
                return
        for pid in range(0, self.curr_proc + 1):
            if self.proc_info[pid][PROC_STATE] == STATE_READY:
                self.curr_proc = pid
                self.move_to_running(STATE_READY)
                return
        return

    def get_num_processes(self):
        return len(self.proc_info)

    def get_num_instructions(self, pid):
        return len(self.proc_info[pid][PROC_CODE])

    def get_instruction(self, pid, index):
        return self.proc_info[pid][PROC_CODE][index]

    def get_num_active(self):
        num_active = 0
        for pid in range(len(self.proc_info)):
            if self.proc_info[pid][PROC_STATE] != STATE_DONE:
                num_active += 1
        return num_active

    def get_num_runnable(self):
        num_active = 0
        for pid in range(len(self.proc_info)):
            if self.proc_info[pid][PROC_STATE] == STATE_READY or \
                   self.proc_info[pid][PROC_STATE] == STATE_RUNNING:
                num_active += 1
        return num_active

    def get_ios_in_flight(self, current_time):
        num_in_flight = 0
        for pid in range(len(self.proc_info)):
            for t in self.io_finish_times[pid]:
                if t > current_time:
                    num_in_flight += 1
        return num_in_flight

    def check_for_switch(self):
        return

    def space(self, num_columns):
        for i in range(num_columns):
            print('%10s' % ' ', end='')

    def check_if_done(self):
        if len(self.proc_info[self.curr_proc][PROC_CODE]) == 0:
            if self.proc_info[self.curr_proc][PROC_STATE] == STATE_RUNNING:
                self.move_to_done(STATE_RUNNING)
                self.next_proc()
        return

    def run(self):
        clock_tick = 0

        if len(self.proc_info) == 0:
            return

        # 記錄每個行程尚未完成的 I/O
        self.io_finish_times = {}
        for pid in range(len(self.proc_info)):
            self.io_finish_times[pid] = []

        # 讓第一個行程開始執行
        self.curr_proc = 0
        self.move_to_running(STATE_READY)

        # 輸出：每一欄的標題
        print('%s' % 'Time', end='')
        for pid in range(len(self.proc_info)):
            print('%14s' % ('PID:%2d' % (pid)), end='')
        print('%14s' % 'CPU', end='')
        print('%14s' % 'IOs', end='')
        print('')

        # 初始化統計數據
        io_busy = 0
        cpu_busy = 0

        while self.get_num_active() > 0:
            clock_tick += 1

            # 檢查是否有 I/O 完成
            io_done = False
            for pid in range(len(self.proc_info)):
                if clock_tick in self.io_finish_times[pid]:
                    io_done = True
                    self.move_to_ready(STATE_WAIT, pid)
                    if self.io_done_behavior == IO_RUN_IMMEDIATE:
                        # IO_RUN_IMMEDIATE
                        if self.curr_proc != pid:
                            if self.proc_info[self.curr_proc][PROC_STATE] == STATE_RUNNING:
                                self.move_to_ready(STATE_RUNNING)
                        self.next_proc(pid)
                    else:
                        # IO_RUN_LATER
                        if self.process_switch_behavior == SCHED_SWITCH_ON_END and self.get_num_runnable() > 1:
                            # 這代表發出這次 I/O 的行程應該被執行
                            self.next_proc(pid)
                        if self.get_num_runnable() == 1:
                            # 這是唯一能執行的行程：那就執行它
                            self.next_proc(pid)
                    self.check_if_done()

            # 如果目前的行程正在執行中，且還有指令，就執行它
            instruction_to_execute = ''
            if self.proc_info[self.curr_proc][PROC_STATE] == STATE_RUNNING and \
                   len(self.proc_info[self.curr_proc][PROC_CODE]) > 0:
                instruction_to_execute = self.proc_info[self.curr_proc][PROC_CODE].pop(0)
                cpu_busy += 1

            # 輸出：印出每個行程目前的狀態
            if io_done:
                print('%3d*' % clock_tick, end='')
            else:
                print('%3d ' % clock_tick, end='')
            for pid in range(len(self.proc_info)):
                if pid == self.curr_proc and instruction_to_execute != '':
                    print('%14s' % ('執行:'+instruction_to_execute), end='')
                else:
                    print('%14s' % (self.proc_info[pid][PROC_STATE]), end='')

            # CPU 欄位輸出：如果沒有指令執行，印出空白，否則印出 1
            if instruction_to_execute == '':
                print('%14s' % ' ', end='')
            else:
                print('%14s' % '1', end='')

            # IO 欄位輸出：
            num_outstanding = self.get_ios_in_flight(clock_tick)
            if num_outstanding > 0:
                print('%14s' % str(num_outstanding), end='')
                io_busy += 1
            else:
                print('%10s' % ' ', end='')
            print('')

            # 如果這是一個 IO 開始指令，就切換到等待狀態
            # 並且安排未來某個時間點完成這次 I/O
            if instruction_to_execute == DO_IO:
                self.move_to_wait(STATE_RUNNING)
                self.io_finish_times[self.curr_proc].append(clock_tick + self.io_length + 1)
                if self.process_switch_behavior == SCHED_SWITCH_ON_IO:
                    self.next_proc()

            # 收尾檢查：確認目前正在執行的行程是否已經沒有指令了
            self.check_if_done()
        return (cpu_busy, io_busy, clock_tick)

#
# 解析命令列參數
#

parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-P', '--program', default='', help='更精細地控制程式內容', action='store', type='string', dest='program')
parser.add_option('-l', '--processlist', default='', help='以逗號分隔的行程清單，格式為 X1:Y1,X2:Y2,...，其中 X 是該行程要執行的指令數量，Y 是一個指令屬於使用 CPU 或發出 IO 的機率（0 到 100）（也就是說，如果 Y 是 100，代表這個行程只會使用 CPU，完全不會發出 I/O；如果 Y 是 0，代表這個行程只會發出 I/O）', action='store', type='string', dest='process_list')
parser.add_option('-L', '--iolength', default=5, help='一次 IO 要花多久時間', action='store', type='int', dest='io_length')
parser.add_option('-S', '--switch', default='SWITCH_ON_IO', help='何時要切換行程：SWITCH_ON_IO、SWITCH_ON_END', action='store', type='string', dest='process_switch_behavior')
parser.add_option('-I', '--iodone', default='IO_RUN_LATER', help='IO 結束時的行為：IO_RUN_LATER、IO_RUN_IMMEDIATE', action='store', type='string', dest='io_done_behavior')
parser.add_option('-c', help='幫我計算答案', action='store_true', default=False, dest='solve')
parser.add_option('-p', '--printstats', help='最後印出統計數據；只有搭配 -c 旗標時才有用（否則不會印出統計數據）', action='store_true', default=False, dest='print_stats')
(options, args) = parser.parse_args()

random_seed(options.seed)

assert(options.process_switch_behavior == SCHED_SWITCH_ON_IO or options.process_switch_behavior == SCHED_SWITCH_ON_END)
assert(options.io_done_behavior == IO_RUN_IMMEDIATE or options.io_done_behavior == IO_RUN_LATER)

s = scheduler(options.process_switch_behavior, options.io_done_behavior, options.io_length)

if options.program != '':
    for p in options.program.split(':'):
        s.load_program(p)
else:
    # 範例的行程描述（10:100,10:100）
    for p in options.process_list.split(','):
        s.load(p)

assert(options.io_length >= 0)

if options.solve == False:
    print('請寫出執行這些行程時會發生的完整過程（trace）：')
    for pid in range(s.get_num_processes()):
        print('行程 %d' % pid)
        for inst in range(s.get_num_instructions(pid)):
            print('  %s' % s.get_instruction(pid, inst))
        print('')
    print('重要行為說明：')
    print('  系統會在下列情況切換行程：', end='')
    if options.process_switch_behavior == SCHED_SWITCH_ON_IO:
        print('目前行程執行完畢，或是發出了一次 IO')
    else:
        print('目前行程執行完畢')
    print('  發出 IO 之後，發出該 IO 的行程將', end='')
    if options.io_done_behavior == IO_RUN_IMMEDIATE:
        print('立刻執行')
    else:
        print('延後執行（輪到它的時候才執行）')
    print('')
    exit(0)

(cpu_busy, io_busy, clock_tick) = s.run()

if options.print_stats:
    print('')
    print('統計：總時間 %d' % clock_tick)
    print('統計：CPU 忙碌 %d（%.2f%%）' % (cpu_busy, 100.0 * float(cpu_busy)/clock_tick))
    print('統計：IO 忙碌  %d（%.2f%%）' % (io_busy, 100.0 * float(io_busy)/clock_tick))
    print('')
