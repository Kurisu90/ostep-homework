#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from collections import *
from optparse import OptionParser
import random
import string

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

def random_randint(low, hi):
    return int(low + random.random() * (hi - low + 1))

def random_choice(L):
    return L[random_randint(0, len(L)-1)]




class ssd:
    def __init__(self, ssd_type, num_logical_pages, num_blocks, pages_per_block,
                 block_erase_time, page_program_time, page_read_time,
                 high_water_mark, low_water_mark, trace_gc, show_state):
        # 類型
        self.TYPE_DIRECT = 1
        self.TYPE_LOGGING = 2
        self.TYPE_IDEAL = 3

        if ssd_type == 'direct':
            self.ssd_type = self.TYPE_DIRECT
        elif ssd_type == 'log':
            self.ssd_type = self.TYPE_LOGGING
        elif ssd_type == 'ideal':
            self.ssd_type = self.TYPE_IDEAL
        else:
            print('不合法的 SSD 類型 (%s)' % ssd_type)
            exit(1)

        # 大小
        self.num_logical_pages = num_logical_pages
        self.num_blocks = num_blocks
        self.pages_per_block = pages_per_block

        # 參數
        self.block_erase_time = block_erase_time
        self.page_program_time = page_program_time
        self.page_read_time = page_read_time

        # 把每個區塊裡的每個分頁初始化為 INVALID（無效）
        self.STATE_INVALID = 1
        self.STATE_ERASED = 2
        self.STATE_VALID = 3
        
        self.num_pages = self.num_blocks * self.pages_per_block
        self.state = {}
        for i in range(self.num_pages):
            self.state[i] = self.STATE_INVALID

        # 資料本身
        self.data = {}
        for i in range(self.num_pages):
            self.data[i] = ' '

        # 日誌式（LOGGING）相關
        # 反向對映：對每個實體分頁而言，是哪個邏輯分頁指向它？
        # 現在該寫到哪一個分頁？
        self.current_page = -1
        self.current_block = 0

        # gc 計數
        self.gc_count = 0
        self.gc_current_block = 0
        self.gc_high_water_mark = high_water_mark
        self.gc_low_water_mark = low_water_mark

        self.gc_trace = trace_gc
        self.show_state = show_state

        # 可以拿來當作日誌區塊使用
        self.gc_used_blocks = {}
        for i in range(self.num_blocks):
            self.gc_used_blocks[i] = 0

        # 用來輔助 GC 判斷的計數
        self.live_count = {}
        for i in range(self.num_blocks):
            self.live_count[i] = 0

        # FTL
        self.forward_map = {}
        for i in range(self.num_logical_pages):
            self.forward_map[i] = -1

        self.reverse_map = {}
        for i in range(self.num_pages):
            self.reverse_map[i] = -1

        # 統計數據
        self.physical_erase_count = {}
        self.physical_read_count = {}
        self.physical_write_count = {}

        for i in range(self.num_blocks):
            self.physical_erase_count[i] = 0
            self.physical_read_count[i] = 0
            self.physical_write_count[i] = 0

        self.physical_erase_sum = 0
        self.physical_write_sum = 0
        self.physical_read_sum = 0

        self.logical_trim_sum = 0
        self.logical_write_sum = 0
        self.logical_read_sum = 0

        self.logical_trim_fail_sum = 0
        self.logical_write_fail_sum = 0
        self.logical_read_fail_sum = 0
        return

    def blocks_in_use(self):
        used = 0
        for i in range(self.num_blocks):
            used += self.gc_used_blocks[i]
        return used

    def physical_erase(self, block_address):
        page_begin = block_address * self.pages_per_block
        page_end = page_begin + self.pages_per_block - 1
        
        for page in range(page_begin, page_end + 1):
            self.data[page] = ' '
            self.state[page] = self.STATE_ERASED

        # 現在絕對是「未使用」狀態了
        self.gc_used_blocks[block_address] = 0

        # 統計數據
        self.physical_erase_count[block_address] += 1
        self.physical_erase_sum += 1
        return

    def physical_program(self, page_address, data):
        self.data[page_address] = data
        self.state[page_address] = self.STATE_VALID
        # 統計數據
        self.physical_write_count[int(page_address / self.pages_per_block)] += 1
        self.physical_write_sum += 1
        return

    def physical_read(self, page_address):
        # 統計數據
        self.physical_read_count[int(page_address / self.pages_per_block)] += 1
        self.physical_read_sum += 1
        return self.data[page_address]

    def read_direct(self, address):
        return self.physical_read(address)

    def write_direct(self, page_address, data):
        block_address = int(page_address / self.pages_per_block)
        page_begin = block_address * self.pages_per_block
        page_end = page_begin + self.pages_per_block - 1

        old_list = []
        for old_page in range(page_begin, page_end + 1):
            if self.state[old_page] == self.STATE_VALID:
                old_data = self.physical_read(old_page)
                old_list.append((old_page, old_data))

        self.physical_erase(block_address)
        for (old_page, old_data) in old_list:
            if old_page == page_address:
                continue
            self.physical_program(old_page, old_data)
            
        self.physical_program(page_address, data)
        self.forward_map[page_address] = page_address
        self.reverse_map[page_address] = page_address
        return '成功'

    def write_ideal(self, page_address, data):
        self.physical_program(page_address, data)
        self.forward_map[page_address] = page_address
        self.reverse_map[page_address] = page_address
        return '成功'

    def is_block_free(self, block):
        first_page = block * self.pages_per_block
        if self.state[first_page] == self.STATE_INVALID or self.state[first_page] == self.STATE_ERASED:
            if self.state[first_page] == self.STATE_INVALID:
                self.physical_erase(block)
            self.current_block = block
            self.current_page = first_page
            self.gc_used_blocks[block] = 1
            return True
        return False

    def get_cursor(self):
        if self.current_page == -1:
            for block in range(self.current_block, self.num_blocks):
                if self.is_block_free(block):
                    return 0
            for block in range(0, self.current_block):
                if self.is_block_free(block):
                    return 0
            return -1
        return 0

    def update_cursor(self):
        self.current_page += 1
        if self.current_page % self.pages_per_block == 0:
            self.current_page = -1
        return

    def write_logging(self, page_address, data, is_gc_write=False):
        if self.get_cursor() == -1:
            self.logical_write_fail_sum += 1
            return '失敗：裝置已滿'
        # 一般模式的寫入
        assert(self.state[self.current_page] == self.STATE_ERASED)
        self.physical_program(self.current_page, data)
        self.forward_map[page_address] = self.current_page
        self.reverse_map[self.current_page] = page_address
        self.update_cursor()
        return '成功'

    def garbage_collect(self):
        blocks_cleaned = 0
        # for block in range(self.gc_current_block, self.num_blocks) + range(0, self.gc_current_block):
        # 這是個有點取巧的展開生成器運算式的寫法 (https://stackoverflow.com/questions/18317913/how-can-i-combine-range-functions)
        for block in (x for y in (range(self.gc_current_block, self.num_blocks), range(0, self.gc_current_block)) for x in y):
            # 不要 GC 目前正在寫入的區塊
            if block == self.current_block:
                continue

            # 開始尋找存活分頁的起始位置
            page_start = block * self.pages_per_block

            # 這個分頁（以及整個區塊）是否已經被抹除過了？若是，就不用管它
            if self.state[page_start] == self.STATE_ERASED:
                continue

            # 收集這個區塊中所有仍然存活的實體分頁
            live_pages = []
            for page in range(page_start, page_start + self.pages_per_block):
                logical_page = self.reverse_map[page]
                if logical_page != -1 and self.forward_map[logical_page] == page:
                    live_pages.append(page)

            # 如果整個區塊都是存活的分頁，就不用清理它！（何必多此一舉搬移呢？）
            if len(live_pages) == self.pages_per_block:
                continue

            # 存活的分頁要被複製到目前的寫入位置
            for page in live_pages:
                # 存活：所以把它複製到別的地方
                if self.gc_trace:
                    print('gc %d:: 讀取（實體分頁=%d）' % (self.gc_count, page))
                    print('gc %d:: 寫入()' % self.gc_count)
                data = self.physical_read(page)
                self.write(self.reverse_map[page], data)

            # 最後，抹除這個區塊，並檢查是否已經完成
            blocks_cleaned += 1
            self.physical_erase(block)

            if self.gc_trace:
                print('gc %d:: 抹除（區塊=%d）' % (self.gc_count, block))
                if self.show_state:
                    print('')
                    self.dump()
                    print('')

            if self.blocks_in_use() <= self.gc_low_water_mark:
                # 完成了！記錄下停止的位置，然後返回
                self.gc_current_block = block
                self.gc_count += 1
                return

        # 結束：區塊迭代完畢
        return

    def upkeep(self):
        # 垃圾回收（GARBAGE COLLECTION）
        if self.blocks_in_use() >= self.gc_high_water_mark:
            self.garbage_collect()
        # 磨損平衡（WEAR LEVELING）：留待未來實作
        return

    def trim(self, address):
        self.logical_trim_sum += 1
        if address < 0 or address >= self.num_logical_pages:
            self.logical_trim_fail_sum += 1
            return '失敗：不合法的 trim 位址'
        if self.forward_map[address] == -1:
            self.logical_trim_fail_sum += 1
            return '失敗：尚未初始化就進行 trim'
        self.forward_map[address] = -1
        return '成功'

    def read(self, address):
        self.logical_read_sum += 1
        if address < 0 or address >= self.num_logical_pages:
            self.logical_read_fail_sum += 1
            return '失敗：不合法的讀取位址'
        if self.forward_map[address] == -1:
            self.logical_read_fail_sum += 1
            return '失敗：尚未初始化就進行讀取'
        # DIRECT、LOGGING、IDEAL 三種類型都會用到
        return self.read_direct(self.forward_map[address])

    def write(self, address, data):
        self.logical_write_sum += 1
        if address < 0 or address >= self.num_logical_pages:
            self.logical_write_fail_sum += 1
            return '失敗：不合法的寫入位址'
        if self.ssd_type == self.TYPE_DIRECT:
            return self.write_direct(address, data)
        elif self.ssd_type == self.TYPE_IDEAL:
            return self.write_ideal(address, data)
        else:
            return self.write_logging(address, data)

    def printable_state(self, s):
        if s == self.STATE_INVALID:
            return 'i'
        elif s == self.STATE_ERASED:
            return 'E'
        elif s == self.STATE_VALID:
            return 'v'
        else:
            print('不合法的狀態 %d' % s)
            exit(1)

    def stats(self):
        print('每個區塊的實體操作次數')
        print('抹除   ', end='')
        for i in range(self.num_blocks):
            print('%3d        ' % self.physical_erase_count[i], end='')
        print('  總計：%d' % self.physical_erase_sum)

        print('寫入   ', end='')
        for i in range(self.num_blocks):
            print('%3d        ' % self.physical_write_count[i], end='')
        print('  總計：%d' % self.physical_write_sum)

        print('讀取   ', end='')
        for i in range(self.num_blocks):
            print('%3d        ' % self.physical_read_count[i], end='')
        print('  總計：%d' % self.physical_read_sum)
        print('')
        print('邏輯操作總計')
        print('  寫入次數 %d（失敗 %d 次）' % (self.logical_write_sum, self.logical_write_fail_sum))
        print('  讀取次數 %d（失敗 %d 次）' % (self.logical_read_sum, self.logical_read_fail_sum))
        print('  trim 次數 %d（失敗 %d 次）' % (self.logical_trim_sum, self.logical_trim_fail_sum))
        print('')
        print('時間')
        print('  抹除時間 %.2f' % (self.physical_erase_sum * self.block_erase_time))
        print('  寫入時間 %.2f' % (self.physical_write_sum * self.page_program_time))
        print('  讀取時間 %.2f' % (self.physical_read_sum * self.page_read_time))
        total_time = self.physical_erase_sum * self.block_erase_time + self.physical_write_sum * self.page_program_time + self.physical_read_sum * self.page_read_time
        print('  總時間   %.2f' % total_time)
        return

    def dump(self):
        # FTL
        print('FTL   ', end='')
        count = 0
        ftl_columns = int((self.pages_per_block * self.num_blocks) / 7)
        for i in range(self.num_logical_pages):
            if self.forward_map[i] == -1:
                continue
            count += 1
            print('%3d:%3d ' % (i, self.forward_map[i]), end='')
            if count > 0 and count % ftl_columns == 0:
                print('\n      ', end='')
        if count == 0:
            print('（空）', end='')
        print('')

        # 快閃記憶體本身
        print('區塊  ', end='')
        for i in range(self.num_blocks):
            out_str = '%d' % i
            print(out_str + ' ' * (self.pages_per_block - len(out_str) + 1), end='')
        print('')

        max_len = len(str(self.num_pages))
        for n in range(max_len, 0, -1):
            if n == max_len:
                print('頁面  ', end='')
            else:
                print('      ', end='')
            for i in range(self.num_pages):
                out_str = str(i).zfill(max_len)[max_len - n]
                print(out_str, end='')
                if i > 0 and (i+1) % 10 == 0:
                    print(end=' ')
            print('')

        print('狀態  ', end='')
        for i in range(self.num_pages):
            print('%s' % self.printable_state(self.state[i]), end='')
            if i > 0 and (i+1) % 10 == 0:
                print(end=' ')
        print('')

        # 資料
        print('資料  ', end='')
        for i in range(self.num_pages):
            if self.state[i] == self.STATE_VALID:
                print('%s' % self.data[i], end='')
            else:
                print(' ', end='')
            if i > 0 and (i+1) % 10 == 0:
                print(end=' ')
        print('')

        # 存活
        print('存活  ', end='')
        for i in range(self.num_pages):
            if self.state[i] == self.STATE_VALID and self.forward_map[self.reverse_map[i]] == i:
                print('+', end='')
            else:
                print(' ', end='')
            if i > 0 and (i+1) % 10 == 0:
                print(end=' ')
        print('')
        return




#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',            default=0,          help='隨機種子',                                     action='store', type='int',    dest='seed')
parser.add_option('-n', '--num_cmds',        default=10,         help='要隨機產生的指令數量',                          action='store', type='int',    dest='num_cmds')
parser.add_option('-P', '--op_percentages',  default='40/50/10', help='若隨機產生，讀取/寫入/trim 各自所佔的百分比',  action='store', type='string', dest='op_percentages')
parser.add_option('-K', '--skew',            default='',         help='若非空字串，代表要做偏移（skew），例如 80/20：80% 的操作集中在 20% 的區塊上', action='store', type='string', dest='skew')
parser.add_option('-k', '--skew_start',      default=0,          help='若有指定 --skew，代表要在幾次寫入之後才開始偏移', action='store', type='int',    dest='skew_start')
parser.add_option('-r', '--read_fails',      default=0,          help='若隨機產生，讀取失敗的百分比',                  action='store', type='int',    dest='read_fail')
parser.add_option('-L', '--cmd_list',        default='',         help='以逗號分隔的指令清單（例如 r10,w20:a）',        action='store', type='string', dest='cmd_list')
parser.add_option('-T', '--ssd_type',        default='direct',   help='SSD 類型：ideal（理想）、direct（直接對映）、log（日誌式）', action='store', type='string', dest='ssd_type')
parser.add_option('-l', '--logical_pages',   default=50,         help='介面中邏輯分頁的數量',                          action='store', type='int',    dest='num_logical_pages')
parser.add_option('-B', '--num_blocks',      default=7,          help='SSD 中實體區塊的數量',                          action='store', type='int',    dest='num_blocks')
parser.add_option('-p', '--pages_per_block', default=10,         help='每個實體區塊中的分頁數量',                      action='store', type='int',    dest='pages_per_block')
parser.add_option('-G', '--high_water_mark', default=10,         help='觸發 GC 前允許使用的區塊數量（高水位）',        action='store', type='int',    dest='high_water_mark')
parser.add_option('-g', '--low_water_mark',  default=8,          help='GC 停止前的目標區塊使用量（低水位）',           action='store', type='int',    dest='low_water_mark')
parser.add_option('-R', '--read_time',       default=10,         help='分頁讀取時間（微秒）',                          action='store', type='int',    dest='read_time')
parser.add_option('-W', '--program_time',    default=40,         help='分頁程式化（program）時間（微秒）',             action='store', type='int',    dest='program_time')
parser.add_option('-E', '--erase_time',      default=1000,       help='分頁抹除時間（微秒）',                          action='store', type='int',    dest='erase_time')
parser.add_option('-J', '--show_gc',         default=False,      help='顯示垃圾回收器的行為',                          action='store_true',           dest='show_gc')
parser.add_option('-F', '--show_state',      default=False,      help='顯示 Flash 的狀態',                             action='store_true',           dest='show_state')
parser.add_option('-C', '--show_cmds',       default=False,      help='顯示每一道指令',                                action='store_true',           dest='show_cmds')
parser.add_option('-q', '--quiz_cmds',       default=False,      help='隨堂測驗模式（隱藏指令內容）',                  action='store_true',           dest='quiz_cmds')
parser.add_option('-S', '--show_stats',      default=False,      help='顯示統計資訊',                                  action='store_true',           dest='show_stats')
parser.add_option('-c', '--compute',         default=False,      help='幫我計算答案',                                  action='store_true',           dest='solve')

(options, args) = parser.parse_args()

random_seed(options.seed)

print('參數 亂數種子(seed) %s' % options.seed)
print('參數 指令數量(num_cmds) %s' % options.num_cmds)
print('參數 讀寫trim比例(op_percentages) %s' % options.op_percentages)
print('參數 偏移設定(skew) %s' % options.skew)
print('參數 偏移起始點(skew_start) %s' % options.skew_start)
print('參數 讀取失敗機率(read_fail) %s' % options.read_fail)
print('參數 指令清單(cmd_list) %s' % options.cmd_list)
print('參數 SSD類型(ssd_type) %s' % options.ssd_type)
print('參數 邏輯分頁數量(num_logical_pages) %s' % options.num_logical_pages)
print('參數 實體區塊數量(num_blocks) %s' % options.num_blocks)
print('參數 每區塊分頁數(pages_per_block) %s' % options.pages_per_block)
print('參數 GC高水位(high_water_mark) %s' % options.high_water_mark)
print('參數 GC低水位(low_water_mark) %s' % options.low_water_mark)
print('參數 抹除時間(erase_time) %s' % options.erase_time)
print('參數 程式化時間(program_time) %s' % options.program_time)
print('參數 讀取時間(read_time) %s' % options.read_time)
print('參數 顯示GC行為(show_gc) %s' % options.show_gc)
print('參數 顯示狀態(show_state) %s' % options.show_state)
print('參數 顯示指令(show_cmds) %s' % options.show_cmds)
print('參數 隨堂測驗模式(quiz_cmds) %s' % options.quiz_cmds)
print('參數 顯示統計資訊(show_stats) %s' % options.show_stats)
print('參數 計算答案(compute) %s' % options.solve)
print('')

s = ssd(ssd_type=options.ssd_type,
        num_logical_pages=options.num_logical_pages, num_blocks=options.num_blocks, pages_per_block=options.pages_per_block,
        block_erase_time=float(options.erase_time), page_program_time=float(options.program_time), page_read_time=float(options.read_time),
        high_water_mark=options.high_water_mark, low_water_mark=options.low_water_mark, trace_gc=options.show_gc, show_state=options.show_state)

#
# 產生指令（若沒有透過 cmd_list 傳入的話）
#
hot_cold = False
skew_start = options.skew_start
if options.skew != '':
    hot_cold = True
    skew = options.skew.split('/')
    if len(skew) != 2:
        print('偏移（skew）設定格式錯誤，應該是像 80/20 這樣的格式')
        exit(1)
    hot_percent = int(skew[0])/100.0
    hot_target = int(skew[1])/100.0

if options.cmd_list == '':
    max_page_addr = int(options.num_logical_pages)
    
    num_cmds = int(options.num_cmds)
    p = options.op_percentages.split('/')
    assert(len(p) == 3)
    percent_reads, percent_writes, percent_trims = int(p[0]), int(p[1]), int(p[2])
    if percent_writes <= 0:
        print('至少要有一些寫入操作，不然 SSD 裡什麼資料都沒有！')
        exit(1)
    
    printable = string.digits + string.ascii_lowercase + string.ascii_uppercase

    cmd_list = []
    valid_addresses = []
    while len(cmd_list) < num_cmds:
        which_cmd = int(random.random() * 100.0)
        if which_cmd < percent_reads:
            # 讀取
            if random_randint(0, 99) < int(options.read_fail):
                address = random_randint(0, max_page_addr - 1)
            else:
                if len(valid_addresses) < 2:
                    continue
                address = random_choice(valid_addresses)
            cmd_list.append('r%d' % address)
        elif which_cmd < percent_reads + percent_writes:
            # 寫入
            if skew_start == 0 and hot_cold and random.random() < hot_percent:
                address = random_randint(0, int(hot_target * (max_page_addr - 1)))
            else:
                address = random_randint(0, max_page_addr - 1)
            if address not in valid_addresses:
                valid_addresses.append(address)
            data = random_choice(list(printable))
            cmd_list.append('w%d:%s' % (address, data))
            if skew_start > 0:
                skew_start -= 1
        else:
            # trim（清除）
            if len(valid_addresses) < 1:
                continue
            address = random_choice(valid_addresses)
            cmd_list.append('t%d' % address)
            valid_addresses.remove(address)
        
else:
    cmd_list = options.cmd_list.split(',')

s.dump()
print('')

show_state = options.show_state
show_cmds = options.show_cmds
quiz_cmds = options.quiz_cmds

if quiz_cmds:
    show_state = True

op = 0
for cmd in cmd_list:
    if cmd == '':
        break
    if cmd[0] == 'r':
        # r10
        address = int(cmd.split('r')[1])
        data = s.read(address)
        if show_cmds or (quiz_cmds and options.solve):
            print('cmd %3d:: 讀取(%d) -> %s' % (op, address, data))
        elif quiz_cmds:
            print('cmd %3d:: 讀取(%d) -> ??' % (op, address))
        op += 1
    elif cmd[0] == 'w':
        # w80:b
        parts = cmd.split(':')
        address = int(parts[0].split('w')[1])
        data = parts[1]
        rc = s.write(address, data)
        if show_cmds or (quiz_cmds and options.solve):
            print('cmd %3d:: 寫入(%d, %s) -> %s' % (op, address, data, rc))
        elif quiz_cmds:
            print('cmd %3d:: 指令(??) -> ??' % op)
        op += 1
    elif cmd[0] == 't':
        address = int(cmd.split('t')[1])
        rc = s.trim(address)
        if show_cmds or (quiz_cmds and options.solve):
            print('cmd %3d:: trim(%d) -> %s' % (op, address, rc))
        elif quiz_cmds:
            print('cmd %d:: 指令(??) -> ??' % op)
        op += 1

    if show_state:
        print('')
        s.dump()
        print('')

    # 是否該進行 GC？
    s.upkeep()

if not show_state:
    print('')
    s.dump()
print('')
if options.show_stats:
    s.stats()
    print('')

