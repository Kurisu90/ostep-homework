#! /usr/bin/env python
# -*- coding: utf-8 -*-

# 每個工作都有一個工作集大小（working-set size）
# 如果它「在快取內」執行，速度是 X
#            「不在快取內」執行，速度是 Y（比 X 慢）
# 排程策略
# - 集中式（centralized）
#   只有一個佇列
# - 分散式（distributed）
#   每顆 CPU 各自一個佇列

from __future__ import print_function
from collections import *
from optparse import OptionParser
import random

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

# 輔助函式：用來把輸出依照 CPU 編號做欄位排版
def print_cpu(cpu, str):
    print((' ' * cpu * 35) + str)
    return

#
# Job 結構：記錄每個工作的所有資訊
#
Job = namedtuple('Job', ['name', 'run_time', 'working_set_size', 'affinity', 'time_left'])

#
# cache 類別
#
# 關鍵問題：快取是怎麼「熱起來」（warmed）的？
# 這裡用的是簡化模型：
# - 在 CPU 上執行滿 'cache_warmup_time' 這麼久
# - 執行滿這段時間之後，快取就對你來說是「熱」的了
# 快取容量有限，所以同一時間只能有一定數量的工作是「熱」的
#
class cache:
    def __init__(self, cpu_id, jobs, cache_size, cache_rate_cold, cache_rate_warm, cache_warmup_time):
        self.cpu_id = cpu_id
        self.jobs = jobs
        self.cache_size = cache_size
        self.cache_rate_cold = cache_rate_cold
        self.cache_rate_warm = cache_rate_warm
        self.cache_warmup_time = cache_warmup_time

        # cache_contents
        # - 應該要記錄哪些工作的工作集目前在快取裡
        # - 這是一份 job_name 的清單，滿足以下其中一種情況：
        #   * 長度 >= 1，且所有工作集大小的「總和」能放進快取裡
        # 或是
        #   * 長度 = 1，但這一個工作的工作集本身可能就太大了
        self.cache_contents = []

        # cache_warming(cpu)
        # - 目前正在為這顆 CPU 的快取「熱身」的工作名稱清單
        # cache_warming_counter(cpu, job)
        # - 每個工作各自的計數器，代表還要多久快取才會對它變熱
        self.cache_warming = []
        self.cache_warming_counter = {}
        return

    def new_job(self, job_name):
        if job_name not in self.cache_contents and job_name not in self.cache_warming:
            # print_cpu(self.cpu_id, '*新的快取*')
            if self.cache_warmup_time == 0:
                # 特例（沒辦法）：不用熱身，直接放進快取
                self.cache_contents.insert(0, job_name)
                self.adjust_size()
            else:
                self.cache_warming.append(job_name)
                self.cache_warming_counter[job_name] = cache_warmup_time
        return

    def total_working_set(self):
        cache_sum = 0
        for job_name in self.cache_contents:
            cache_sum += self.jobs[job_name].working_set_size
        return cache_sum

    def adjust_size(self):
        working_set_total = self.total_working_set()
        while working_set_total > self.cache_size:
            last_entry = len(self.cache_contents) - 1
            job_gone = self.cache_contents[last_entry]
            # print_cpu(self.cpu_id, '踢出 %s' % job_gone)
            del self.cache_contents[last_entry]
            self.cache_warming.append(job_gone)
            self.cache_warming_counter[job_gone] = cache_warmup_time
            working_set_total -= self.jobs[job_gone].working_set_size
        return

    def get_cache_state(self, job_name):
        if job_name in self.cache_contents:
            return 'w'
        else:
            return ' '

    def get_rate(self, job_name):
        if job_name in self.cache_contents:
            return self.cache_rate_warm
        else:
            return self.cache_rate_cold

    def update_warming(self, job_name):
        if job_name in self.cache_warming:
            self.cache_warming_counter[job_name] -= 1
            if self.cache_warming_counter[job_name] <= 0:
                self.cache_warming.remove(job_name)
                self.cache_contents.insert(0, job_name)
                self.adjust_size()
                # print_cpu(self.cpu_id, '*快取變熱*')
        return

#
# scheduler 類別
#
# 模擬一個多 CPU 排程器
#
class scheduler:
    def __init__(self, job_list, per_cpu_queues, affinity, peek_interval,
                 job_num, max_run, max_wset,
                 num_cpus, time_slice, random_order,
                 cache_size, cache_rate_cold, cache_rate_warm, cache_warmup_time,
                 solve, trace, trace_time_left, trace_cache, trace_sched):

        if job_list == '':
            # 這代表要隨機產生工作
            for j in range(job_num):
                run_time = int((random.random() * max_run)/10.0) * 10
                working_set = int((random.random() * max_wset)/10.0) * 10
                if job_list == '':
                    job_list = '%s:%d:%d' % (str(j), run_time, working_set)
                else:
                    job_list += (',%s:%d:%d' % (str(j), run_time, working_set))

        # 只記錄工作名稱
        self.job_name_list = []

        # 每個工作的詳細資訊
        self.jobs = {}

        for entry in job_list.split(','):
            tmp = entry.split(':')
            if len(tmp) != 3:
                print('不合法的工作描述 [%s]：格式必須是 name:runtime:working_set_size 三元組' % entry)
                exit(1)
            job_name, run_time, working_set_size = tmp[0], int(tmp[1]), int(tmp[2])
            self.jobs[job_name] = Job(name=job_name, run_time=run_time, working_set_size=working_set_size, affinity=[], time_left=[run_time])
            print('工作名稱:%s 執行時間:%d 工作集大小:%d' % (job_name, run_time, working_set_size))
            # self.sched_queue.append(job_name)
            if job_name in self.job_name_list:
                print('重複的工作名稱 %s' % job_name)
                exit(1)
            self.job_name_list.append(job_name)
        print('')

        # 解析 affinity（親和性）清單
        if affinity != '':
            for entry in affinity.split(','):
                # 格式是 'job_name:cpu.cpu.cpu'
                # 其中 job_name 是某個已存在工作的名稱
                # cpu 是某顆特定 CPU 的編號（0 ... max_cpus-1）
                tmp = entry.split(':')
                if len(tmp) != 2:
                    print('不合法的 affinity 設定 %s' % affinity)
                    exit(1)
                job_name = tmp[0]
                if job_name not in self.job_name_list:
                    print('affinity 清單中的工作名稱 %s 不存在' % job_name)
                    exit(1)
                for cpu in tmp[1].split('.'):
                    self.jobs[job_name].affinity.append(int(cpu))
                    if int(cpu) < 0 or int(cpu) >= num_cpus:
                        print('affinity %s 中指定了不合法的 cpu %d' % (int(cpu), affinity))
                        exit(1)

        # 接著，把工作全部分配到同一個佇列，或是以 RR 的方式分配到各自的佇列
        # （會受到 affinity 設定的限制）
        self.per_cpu_queues = per_cpu_queues

        self.per_cpu_sched_queue = {}

        if self.per_cpu_queues:
            for cpu in range(num_cpus):
                self.per_cpu_sched_queue[cpu] = []
            # 現在把工作分配到這些佇列中
            jobs_not_assigned = list(self.job_name_list)
            while len(jobs_not_assigned) > 0:
                for cpu in range(num_cpus):
                    assigned = False
                    for job_name in jobs_not_assigned:
                        if len(self.jobs[job_name].affinity) == 0 or cpu in self.jobs[job_name].affinity:
                            self.per_cpu_sched_queue[cpu].append(job_name)
                            jobs_not_assigned.remove(job_name)
                            assigned = True
                        if assigned:
                            break

            for cpu in range(num_cpus):
                print('排程器 CPU %d 佇列：%s' % (cpu, self.per_cpu_sched_queue[cpu]))
            print('')

        else:
            # 全部分配到同一個佇列
            self.single_sched_queue = []
            for job_name in self.job_name_list:
                self.single_sched_queue.append(job_name)
            for cpu in range(num_cpus):
                self.per_cpu_sched_queue[cpu] = self.single_sched_queue

            print('排程器集中佇列：%s\n' % (self.single_sched_queue))

        self.num_jobs = len(self.job_name_list)


        self.peek_interval = peek_interval

        self.num_cpus = num_cpus
        self.time_slice = time_slice
        self.random_order = random_order

        self.solve = solve

        self.trace = trace
        self.trace_time_left = trace_time_left
        self.trace_cache = trace_cache
        self.trace_sched = trace_sched

        # 記錄每顆 CPU：目前是閒置還是正在執行工作
        self.STATE_IDLE = 1
        self.STATE_RUNNING = 2

        # 每顆 CPU 的排程器狀態（RUNNING 或 IDLE）
        self.sched_state = {}
        for cpu in range(self.num_cpus):
            self.sched_state[cpu] = self.STATE_IDLE

        # 如果某顆 CPU 正在執行工作，記錄是哪一個工作
        self.sched_current = {}
        for cpu in range(self.num_cpus):
            self.sched_current[cpu] = ''

        # 一些統計數據
        self.stats_ran = {}
        self.stats_ran_warm = {}
        for cpu in range(self.num_cpus):
            self.stats_ran[cpu] = 0
            self.stats_ran_warm[cpu] = 0

        # 排程器（因為它負責跑整個模擬）同時也會建立並更新每顆 CPU 的快取
        self.caches = {}
        for cpu in range(self.num_cpus):
            self.caches[cpu] = cache(cpu, self.jobs, cache_size, cache_rate_cold, cache_rate_warm, cache_warmup_time)

        return

    def handle_one_interrupt(self, interrupt, cpu):
        # 處理：在這裡處理中斷，這樣工作才不會多跑一個時間刻度
        if interrupt and self.sched_state[cpu] == self.STATE_RUNNING:
            self.sched_state[cpu] = self.STATE_IDLE
            job_name = self.sched_current[cpu]
            self.sched_current[cpu] = ''
            # print_cpu(cpu, '工作 %s 的這個時間片結束' % job_name)
            self.per_cpu_sched_queue[cpu].append(job_name)
        return

    def handle_interrupts(self):
        if self.system_time % self.time_slice == 0 and self.system_time > 0:
            interrupt = True
            # num_to_print = 時間欄位 + 每顆 CPU 的資訊 + 每個工作的快取狀態 - 最後多餘的空白
            num_to_print = 8 + (7 * self.num_cpus) - 5
            if self.trace_time_left:
                num_to_print += 6 * self.num_cpus
            if self.trace_cache:
                num_to_print += 8 * self.num_cpus + self.num_jobs * (self.num_cpus)
            if self.trace:
                print('-' * num_to_print)
        else:
            interrupt = False

        if self.trace:
            print(' %3d   ' % self.system_time, end='')

        # 先處理中斷：這可能會讓某個工作被剝奪 CPU，放回可執行佇列
        for cpu in range(self.num_cpus):
            self.handle_one_interrupt(interrupt, cpu)
        return

    def get_job(self, cpu, sched_queue):
        # 取得下一個工作？
        for job_index in range(len(sched_queue)):
            job_name = sched_queue[job_index]
            # len(affinity) == 0 是特例，代表「任何」CPU 都可以執行它
            if len(self.jobs[job_name].affinity) == 0 or cpu in self.jobs[job_name].affinity:
                # 把工作從可執行佇列中取出，放進這顆 CPU 的本地結構中
                sched_queue.pop(job_index)
                self.sched_state[cpu] = self.STATE_RUNNING
                self.sched_current[cpu] = job_name
                self.caches[cpu].new_job(job_name)
                # print('拿到工作 %s' % job_name)
                return
        return

    def assign_jobs(self):
        if self.random_order:
            cpu_list = list(range(self.num_cpus))
            random.shuffle(cpu_list)
        else:
            cpu_list = range(self.num_cpus)
        for cpu in cpu_list:
            if self.sched_state[cpu] == self.STATE_IDLE:
                self.get_job(cpu, self.per_cpu_sched_queue[cpu])

    def print_sched_queues(self):
        # 印出佇列資訊
        if not self.trace_sched:
            return
        if self.per_cpu_queues:
            for cpu in range(self.num_cpus):
                print('佇列%d: ' % cpu, end='')
                for job_name in self.per_cpu_sched_queue[cpu]:
                    print('%s ' % job_name, end='')
                print('  ', end='')
            print('    ', end='')
        else:
            print('佇列: ', end='')
            for job_name in self.single_sched_queue:
                print('%s ' % job_name, end='')
            print('    ', end='')
        return

    def steal_jobs(self):
        if not self.per_cpu_queues or self.peek_interval <= 0:
            return

        # 如果現在該來「偷」工作了
        if self.system_time > 0 and self.system_time % self.peek_interval == 0:
            for cpu in range(self.num_cpus):
                if len(self.per_cpu_sched_queue[cpu]) == 0:
                    # 從其他某顆 CPU 的佇列中找出可偷的工作
                    other_cpu_list = list(range(self.num_cpus))
                    other_cpu_list.remove(cpu)
                    other_cpu = random.choice(other_cpu_list)
                    # print('cpu %d 是閒置的' % cpu)
                    # print('-> 看看 %d' % other_cpu)

                    for job_name in self.per_cpu_sched_queue[other_cpu]:
                        # print('---> 檢查工作 %s' % job_name)
                        if len(self.jobs[job_name].affinity) == 0 or cpu in self.jobs[job_name]:
                           self.per_cpu_sched_queue[other_cpu].remove(job_name)
                           self.per_cpu_sched_queue[cpu].append(job_name)
                           # print('把工作 %s 從 %d 偷到 %d' % (job_name, other_cpu, cpu))
                           break
        return

    def run_one_tick(self, cpu):
        job_name = self.sched_current[cpu]
        job = self.jobs[job_name]

        # 利用 cache_contents 判斷快取是冷還是熱
        # （用 list 搭配 time_left 欄位：這是為了繞過 namedtuple 不可變動的限制而用的小技巧）
        current_rate = self.caches[cpu].get_rate(job_name)
        self.stats_ran[cpu] += 1
        if current_rate > 1:
            self.stats_ran_warm[cpu] += 1
        time_left = job.time_left.pop() - current_rate
        if time_left < 0:
            time_left = 0
        job.time_left.append(time_left)

        if self.trace:
            print('%s ' % job.name, end='')
            if self.trace_time_left:
                print('[%3d] ' % job.time_left[0], end='')

        # 更新：快取熱身進度
        self.caches[cpu].update_warming(job_name)

        if time_left <= 0:
            self.sched_state[cpu] = self.STATE_IDLE
            job_name = self.sched_current[cpu]
            self.sched_current[cpu] = ''
            # 注意：現在雖然是時間 X，但工作跑完了這一個時間刻度，所以是在 X + 1 完成
            # print_cpu(cpu, '%s 於時間 %d 完成' % (job_name, self.system_time + 1))
            self.jobs_finished += 1
        return

    def run_jobs(self):
        for cpu in range(self.num_cpus):
            if self.sched_state[cpu] == self.STATE_RUNNING:
                self.run_one_tick(cpu)
            elif self.trace:
                print('- ', end='')
                if self.trace_time_left:
                    print('[   ] ', end='')

            # 印出快取狀態
            cache_string = ''
            for job_name in self.job_name_list:
                # cache_string += '%s%s ' % (job_name, self.caches[cpu].get_cache_state(job_name))
                cache_string += '%s' % self.caches[cpu].get_cache_state(job_name)
            if self.trace:
                if self.trace_cache:
                    print('cache[%s]' % cache_string, end='')
                print('     ', end='')
        return

    #
    # 主要模擬邏輯
    #
    def run(self):
        # 要追蹤的狀態
        self.system_time = 0
        self.jobs_finished = 0

        while self.jobs_finished < self.num_jobs:
            # 中斷：可能會讓某個時間片提早結束，讓工作可以被排到別的地方執行
            self.handle_interrupts()

            # 如果時間到了，就做一些工作竊取（job stealing）
            self.steal_jobs()

            # 把（新的）工作分配給各顆 CPU（這可能每個時間刻度都會發生）
            self.assign_jobs()

            # 讓每顆 CPU 執行一個時間片，並處理工作可能結束的情況
            self.run_jobs()

            self.print_sched_queues()

            # 在所有工作的更新資訊之後加上換行
            if self.trace:
                print('')

            # 時鐘持續跳動
            self.system_time += 1

        if self.solve:
            print('\n完成時間 %d\n' % self.system_time)
            print('各 CPU 統計數據')
            for cpu in range(self.num_cpus):
                print('  CPU %d  使用率 %3.2f [ 熱快取 %3.2f ]' % (cpu, 100.0 * float(self.stats_ran[cpu])/float(self.system_time),
                                                                      100.0 * float(self.stats_ran_warm[cpu])/float(self.system_time)))
            print('')
        return

#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',        default=0,     help='隨機種子',                        action='store', type='int', dest='seed')
parser.add_option('-j', '--job_num',     default=3,     help='系統中的工作數量',           action='store', type='int', dest='job_num')
parser.add_option('-R', '--max_run',     default=100,   help='隨機產生工作時的最大執行時間',        action='store', type='int', dest='max_run')
parser.add_option('-W', '--max_wset',    default=200,   help='隨機產生工作時的最大工作集大小',     action='store', type='int', dest='max_wset')
parser.add_option('-L', '--job_list',    default='',    help='提供一份以逗號分隔的 job_name:run_time:working_set_size 清單（例如 a:10:100,b:10:50 代表 2 個工作，執行時間都是 10，第一個 (a) 的工作集大小是 100，第二個 (b) 的工作集大小是 50）', action='store', type='string', dest='job_list')
parser.add_option('-p', '--per_cpu_queues', default=False, help='每顆 CPU 各自使用獨立的排程佇列（而非共用一個）', action='store_true',        dest='per_cpu_queues')
parser.add_option('-A', '--affinity',    default='',    help='指定哪些工作可以在哪些 CPU 上執行的清單（例如 a:0.1.2,b:0.1 代表工作 a 可以在 CPU 0、1、2 上執行，但 b 只能在 CPU 0 和 1 上執行）', action='store', type='string', dest='affinity')
parser.add_option('-n', '--num_cpus',    default=2,     help='CPU 的數量',                         action='store', type='int', dest='num_cpus')
parser.add_option('-q', '--quantum',     default=10,    help='時間片長度',                   action='store', type='int', dest='time_slice')
parser.add_option('-P', '--peek_interval', default=30,  help='使用各 CPU 獨立佇列時，多久去偷看一次別的排程佇列；設為 0 代表關閉此功能', action='store', type='int', dest='peek_interval')
parser.add_option('-w', '--warmup_time', default=10,    help='快取熱身需要花的時間',            action='store', type='int', dest='warmup_time')
parser.add_option('-r', '--warm_rate', default=2,     help='快取變熱之後，執行速度會快多少倍', action='store', type='int', dest='warm_rate')
parser.add_option('-M', '--cache_size',  default=100,   help='快取大小',                             action='store', type='int', dest='cache_size')
parser.add_option('-o', '--rand_order',  default=False, help='讓各顆 CPU 以隨機順序取得工作',      action='store_true',        dest='random_order')
parser.add_option('-t', '--trace',       default=False, help='開啟基本追蹤（顯示哪些工作被排入執行）',      action='store_true',        dest='trace')
parser.add_option('-T', '--trace_time_left', default=False, help='追蹤每個工作剩餘的時間',       action='store_true',        dest='trace_time_left')
parser.add_option('-C', '--trace_cache', default=False, help='同時追蹤快取狀態（熱/冷）',     action='store_true',        dest='trace_cache')
parser.add_option('-S', '--trace_sched', default=False, help='追蹤排程器狀態',                  action='store_true',        dest='trace_sched')
parser.add_option('-c', '--compute',     default=False, help='幫我計算答案',                 action='store_true',        dest='solve')

(options, args) = parser.parse_args()

random_seed(options.seed)

print('參數 seed %s' % options.seed)
print('參數 job_num %s' % options.job_num)
print('參數 max_run %s' % options.max_run)
print('參數 max_wset %s' % options.max_wset)
print('參數 job_list %s' % options.job_list)
print('參數 affinity %s' % options.affinity)
print('參數 per_cpu_queues %s' % options.per_cpu_queues)
print('參數 num_cpus %s' % options.num_cpus)
print('參數 quantum %s' % options.time_slice)
print('參數 peek_interval %s' % options.peek_interval)
print('參數 warmup_time %s' % options.warmup_time)
print('參數 cache_size %s' % options.cache_size)
print('參數 random_order %s' % options.random_order)
print('參數 trace %s' % options.trace)
print('參數 trace_time %s' % options.trace_time_left)
print('參數 trace_cache %s' % options.trace_cache)
print('參數 trace_sched %s' % options.trace_sched)
print('參數 compute %s' % options.solve)
print('')

#
# 工作
#
job_list = options.job_list
job_num = int(options.job_num)
max_run = int(options.max_run)
max_wset = int(options.max_wset)

#
# 機器
#
num_cpus = int(options.num_cpus)
time_slice = int(options.time_slice)

#
# 快取
#
cache_size = int(options.cache_size)
cache_rate_warm = int(options.warm_rate)
cache_warmup_time = int(options.warmup_time)

do_trace = options.trace
if options.trace_time_left or options.trace_cache or options.trace_sched:
    do_trace = True

#
# 排程器（同時也是模擬器）
#
S = scheduler(job_list=job_list, affinity=options.affinity, per_cpu_queues=options.per_cpu_queues, peek_interval=options.peek_interval,
              job_num=job_num, max_run=max_run, max_wset=max_wset,
              num_cpus=num_cpus, time_slice=time_slice, random_order=options.random_order,
              cache_size=cache_size, cache_rate_cold=1, cache_rate_warm=cache_rate_warm,
              cache_warmup_time=cache_warmup_time, solve=options.solve,
              trace=do_trace, trace_time_left=options.trace_time_left, trace_cache=options.trace_cache,
              trace_sched=options.trace_sched)

# 最後，……
S.run()
