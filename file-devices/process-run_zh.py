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
SCHED_SWITCH_ON_IO = 'SWITCH_ON_IO'
SCHED_SWITCH_ON_END = 'SWITCH_ON_END'

# IO 完成後的行為
IO_RUN_LATER = 'IO_RUN_LATER'
IO_RUN_IMMEDIATE = 'IO_RUN_IMMEDIATE'

# 行程狀態
STATE_RUNNING = '執行中'
STATE_READY = '就緒'
STATE_DONE = '完成'
STATE_WAIT = '等待中'

# 行程結構中的成員
PROC_CODE = 'code_'
PROC_PC = 'pc_'
PROC_ID = 'pid_'
PROC_STATE = 'proc_state_'

# 一個行程可以做的事
DO_COMPUTE = '計算'
DO_IO = 'I/O'
DO_PROGRAMMED_IO = '輪詢I/O'


class scheduler:
    def __init__(self, process_switch_behavior, io_done_behavior, io_length, interrupt_overhead):
        # 保存每個行程各自的指令集合
        self.proc_info = {}
        self.process_switch_behavior = process_switch_behavior
        self.io_done_behavior = io_done_behavior
        self.io_length = io_length
        self.interrupt_overhead = interrupt_overhead
        return

    def new_process(self):
        proc_id = len(self.proc_info)
        self.proc_info[proc_id] = {}
        self.proc_info[proc_id][PROC_PC] = 0
        self.proc_info[proc_id][PROC_ID] = proc_id
        self.proc_info[proc_id][PROC_CODE] = []
        self.proc_info[proc_id][PROC_STATE] = STATE_READY
        return proc_id

    # 這是死碼（dead code）嗎？為什麼會在這裡？沒人知道……
    def load_file(self, progfile):
        fd = open(progfile)
        proc_id = self.new_process()

        for line in fd:
            tmp = line.split()
            if len(tmp) == 0:
                continue
            opcode = tmp[0]
            if opcode == 'compute':
                assert(len(tmp) == 2)
                for i in range(int(tmp[1])):
                    self.proc_info[proc_id][PROC_CODE].append(DO_COMPUTE)
            elif opcode == 'io':
                assert(len(tmp) == 1)
                self.proc_info[proc_id][PROC_CODE].append(DO_IO)
        fd.close()
        return

    # 程式描述看起來像這樣：
    #   c7,i,c1,i
    # 意思是
    #   先計算 7 個單位，然後做一次 I/O，再計算 1 個單位，再做一次 I/O
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
            elif opcode == 'p':
                for i in range(self.io_length):
                    self.proc_info[proc_id][PROC_CODE].append(DO_PROGRAMMED_IO)
            else:
                print('不合法的指令代碼 %s（應該是 c 或 i）' % opcode)
                exit(1)
        return

    def load(self, program_description):
        proc_id = self.new_process()
        tmp = program_description.split(':')
        if len(tmp) != 2:
            print('描述格式錯誤 (%s)：必須是 <x:y> 這種數字格式' % program_description)
            print('  其中 X 是指令的數量')
            print('  Y 則是指令屬於 CPU（而非 IO）的機率百分比')
            exit(1)

        num_instructions, chance_cpu = int(tmp[0]), float(tmp[1])/100.0
        for i in range(num_instructions):
            if random.random() < chance_cpu:
                self.proc_info[proc_id][PROC_CODE].append(DO_COMPUTE)
            else:
                self.proc_info[proc_id][PROC_CODE].append(DO_IO)
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

    #
    # 所有的工作都在這裡完成，一次一個時間刻度（tick）
    #
    def run(self):
        clock_tick = 0

        if len(self.proc_info) == 0:
            return

        # 記錄每個行程尚未完成的 IO
        self.io_finish_times = {}
        for pid in range(len(self.proc_info)):
            self.io_finish_times[pid] = []

        # 讓第一個行程開始執行
        self.curr_proc = 0
        self.move_to_running(STATE_READY)

        # 輸出：每一欄的標題
        print('%s' % '時間', end='')
        for pid in range(len(self.proc_info)):
            print('%10s' % ('PID:%2d' % (pid)), end='')
        print('%10s' % 'CPU', end='')
        print('%10s' % 'IOs', end='')
        print('')

        # 初始化統計數據
        io_busy = 0
        cpu_busy = 0

        while self.get_num_active() > 0:
            clock_tick += 1

            # 檢查是否有 IO 完成
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
                            # 這表示發出這個 IO 的行程應該要被執行
                            self.next_proc(pid)
                        if self.get_num_runnable() == 1:
                            # 這是目前唯一能執行的行程：所以就執行它
                            self.next_proc(pid)
                    self.check_if_done()

            # 如果目前的行程處於執行中狀態，且還有指令可以執行，就執行它
            instruction_to_execute = ''
            if self.proc_info[self.curr_proc][PROC_STATE] == STATE_RUNNING and \
                   len(self.proc_info[self.curr_proc][PROC_CODE]) > 0:
                instruction_to_execute = self.proc_info[self.curr_proc][PROC_CODE].pop(0)
                cpu_busy += 1

            # 輸出：印出目前每個行程在做什麼
            if io_done:
                print('%3d*' % clock_tick, end='')
            else:
                print('%3d ' % clock_tick, end='')
            for pid in range(len(self.proc_info)):
                if pid == self.curr_proc and instruction_to_execute != '':
                    print('%10s' % ('執行:'+instruction_to_execute), end='')
                else:
                    print('%10s' % (self.proc_info[pid][PROC_STATE]), end='')
            if instruction_to_execute == '':
                print('%10s' % ' ', end='')
            else:
                print('%10s' % 1, end='')
            num_outstanding = self.get_ios_in_flight(clock_tick)
            if num_outstanding > 0:
                print('%10s' % str(num_outstanding), end='')
                io_busy += 1
            else:
                print('%10s' % ' ', end='')
            print('')

            # 如果這是一個 IO 指令，切換到等待狀態
            # 並且排定未來某個時間點完成這個 IO
            if instruction_to_execute == DO_IO:
                self.move_to_wait(STATE_RUNNING)
                self.io_finish_times[self.curr_proc].append(clock_tick + self.io_length)
                if self.process_switch_behavior == SCHED_SWITCH_ON_IO:
                    self.next_proc()

            # 結束判斷：檢查目前執行中的行程是否已經沒有指令了
            self.check_if_done()
        return (cpu_busy, io_busy, clock_tick)

#
# 解析參數
#

parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-P', '--program', default='', help='更精確地控制程式內容', action='store', type='string', dest='program')
parser.add_option('-l', '--processlist', default='', help='以逗號分隔的行程清單，格式為 X1:Y1,X2:Y2,...，其中 X 是該行程要執行的指令數量，Y 是每個指令使用 CPU（而非發出 IO）的機率（0 到 100）', action='store', type='string', dest='process_list')
parser.add_option('-L', '--iolength', default=5, help='一次 IO 要花多久時間', action='store', type='int', dest='io_length')
parser.add_option('-o', '--interrupt_overhead', default=5, help='處理一次中斷要花多久時間', action='store', type='int', dest='interrupt_overhead')
parser.add_option('-S', '--switch', default='SWITCH_ON_IO', help='什麼時候要在行程之間切換：SWITCH_ON_IO、SWITCH_ON_END', action='store', type='string', dest='process_switch_behavior')
parser.add_option('-I', '--iodone', default='IO_RUN_LATER', help='IO 結束時的行為類型：IO_RUN_LATER、IO_RUN_IMMEDIATE', action='store', type='string', dest='io_done_behavior')
parser.add_option('-c', help='幫我計算答案', action='store_true', default=False, dest='solve')
parser.add_option('-p', '--printstats', help='結束時印出統計資訊；只有搭配 -c 旗標才有用（否則不會印出統計資訊）', action='store_true', default=False, dest='print_stats')
(options, args) = parser.parse_args()

random_seed(options.seed)

assert(options.process_switch_behavior == SCHED_SWITCH_ON_IO or options.process_switch_behavior == SCHED_SWITCH_ON_END)
assert(options.io_done_behavior == IO_RUN_IMMEDIATE or options.io_done_behavior == IO_RUN_LATER)

s = scheduler(options.process_switch_behavior, options.io_done_behavior, options.io_length, options.interrupt_overhead)

if options.program != '':
    for p in options.program.split(':'):
        s.load_program(p)
else:
    # 範例的行程描述 (10:100,10:100)
    for p in options.process_list.split(','):
        s.load(p)

if options.solve == False:
    print('請算出執行這些行程時會發生的執行記錄：')
    for pid in range(s.get_num_processes()):
        print('行程 %d' % pid)
        for inst in range(s.get_num_instructions(pid)):
            print('  %s' % s.get_instruction(pid, inst))
        print('')
    print('重要行為：')
    print('  系統會在', end='')
    if options.process_switch_behavior == SCHED_SWITCH_ON_IO:
        print('目前行程執行完畢或發出 IO 時切換')
    else:
        print('目前行程執行完畢時切換')
    print('  IO 結束後，發出該 IO 的行程會', end='')
    if options.io_done_behavior == IO_RUN_IMMEDIATE:
        print('立即執行')
    else:
        print('稍後（輪到它的時候）才執行')
    print('')
    exit(0)

(cpu_busy, io_busy, clock_tick) = s.run()

if options.print_stats:
    print('')
    print('統計：總時間 %d' % clock_tick)
    print('統計：CPU 忙碌 %d（%.2f%%）' % (cpu_busy, 100.0 * float(cpu_busy)/clock_tick))
    print('統計：IO 忙碌  %d（%.2f%%）' % (io_busy, 100.0 * float(io_busy)/clock_tick))
    print('')
