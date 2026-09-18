#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import math
import sys
from optparse import OptionParser
import random

class file_system:
    def __init__(self, num_groups, blocks_per_group, inodes_per_group,
                 large_file_exception, spread_inodes,
                 contig_allocation_policy, spread_data_blocks, allocate_faraway,
                 show_block_addresses, do_per_file_stats, show_file_ops,
                 show_symbol_map, compute):
        self.num_groups = num_groups
        self.blocks_per_group = blocks_per_group
        self.inodes_per_group = inodes_per_group
        self.large_file_exception = large_file_exception
        self.spread_inodes = spread_inodes
        self.contig_allocation_policy = contig_allocation_policy
        self.spread_data_blocks = spread_data_blocks
        self.allocate_faraway = allocate_faraway
        self.show_block_addresses = show_block_addresses
        self.do_per_file_stats = do_per_file_stats
        self.show_file_ops = show_file_ops
        self.show_symbol_map = show_symbol_map
        self.compute = compute

        self.group_size = self.inodes_per_group + self.blocks_per_group

        self.BITMAP_FREE = '__FREE__'

        self.data_bitmap = []
        self.inode_bitmap = []
        for i in range(self.num_groups):
            self.inode_bitmap.append([])
            self.data_bitmap.append([])
            for j in range(self.blocks_per_group):
                self.data_bitmap[i].append(self.BITMAP_FREE)
            for j in range(self.inodes_per_group):
                self.inode_bitmap[i].append(self.BITMAP_FREE)

        self.init_symbols()

        self.total_data_free   = blocks_per_group * num_groups
        self.total_inodes_free = inodes_per_group * num_groups

        # 建立根目錄
        self.inode_bitmap[0][0] = 0
        self.data_bitmap[0][0] = 0 # 所有目錄共用這一個資料區塊
        self.allocate_symbol(0, '/')

        self.total_data_free -= 1
        self.total_inodes_free -= 1

        # 每個目錄的資料，以 inode 編號為索引
        self.dir_data = {}
        self.dir_data[0] = [('.', 0), ('..', 0)]

        # inode 的資料：每個 inode 的類型資訊
        self.inode_type = {}
        self.inode_type[0] = '目錄'

        # 以及組成這個檔案的區塊有哪些
        self.inode_blocks = {}
        self.inode_blocks[0] = [0]

        # 把名稱對應到 inode 編號
        self.name_to_inode_map = {}
        self.name_to_inode_map['/'] = 0
        return

    def vprint(self, msg):
        if self.show_file_ops:
            print(msg, end='')
        return

    def get_parent(self, path):
        index_of_last_slash = path.rfind('/')
        if index_of_last_slash == 0:
            return '/', path[index_of_last_slash+1:len(path)]
        return path[0:index_of_last_slash], path[index_of_last_slash+1:len(path)]

    def name_to_inode(self, path):
        if path not in self.name_to_inode_map:
            return -1
        else:
            return self.name_to_inode_map[path]

    def set_name_to_inode(self, path, inode_num):
        if path in self.name_to_inode_map:
            print('中止：這個路徑已經存在於對照表中（內部錯誤）')
            exit(1)
        self.name_to_inode_map[path] = inode_num
        return

    def get_free_count(self, group, bitmap):
        cnt = 0
        for b in bitmap:
            if b == self.BITMAP_FREE:
                cnt += 1
        return cnt

    def get_free_inode_count(self, group):
        return self.get_free_count(group, self.inode_bitmap[group])

    def get_free_data_count(self, group):
        return self.get_free_count(group, self.data_bitmap[group])

    def find_most_free_inodes(self, starting_point):
        free_inodes_max = 0
        target_group = -1
        for g in range(starting_point, self.num_groups):
            free_inodes_in_group = self.get_free_inode_count(g)
            if free_inodes_in_group > free_inodes_max:
                free_inodes_max = free_inodes_in_group
                target_group = g
        for g in range(0, starting_point):
            free_inodes_in_group = self.get_free_inode_count(g)
            if free_inodes_in_group > free_inodes_max:
                free_inodes_max = free_inodes_in_group
                target_group = g
        return target_group

    def find_free_inodes_in_range(self, group, how_many):
        sum_free = 0
        for g in range(group, group + how_many):
            g_curr = g % self.num_groups
            free_inodes_in_group = self.get_free_inode_count(g_curr)
            sum_free += free_inodes_in_group
        return sum_free

    def find_most_free_inodes_multiple(self, starting_point, how_many):
        free_inodes_max = 0
        target_group = -1
        for g in range(starting_point, self.num_groups, how_many):
            sum_free = self.find_free_inodes_in_range(g, how_many)
            if sum_free > free_inodes_max:
                free_inodes_max = sum_free
                target_group = g
        for g in range(0, starting_point, how_many):
            sum_free = self.find_free_inodes_in_range(g, how_many)
            if sum_free > free_inodes_max:
                free_inodes_max = sum_free
                target_group = g
        assert(target_group != -1)
        return target_group

    def find_free_inodes_near(self, target_group):
        grower = (target_group + 1) % self.num_groups
        shrinker = (target_group - 1) % self.num_groups
        for i in range(self.num_groups - 1):
            if i % 2 == 0:
                current_group = grower
                grower = (grower + 1) % self.num_groups
            else:
                current_group = shrinker
                shrinker = (shrinker - 1) % self.num_groups
            if self.get_free_inode_count(current_group) > 0:
                return current_group
        return 1

    def pick_group(self, parent, filename, type):
        if type == '一般檔案' and self.spread_inodes == False:
            # FFS 的策略：根據父目錄來選擇
            parent_inode_number = self.name_to_inode(parent)
            target_group = int(parent_inode_number / self.inodes_per_group)
            # 確保這個群組還有空的 inode……（那空的資料區塊呢？）
            num_free_inodes = self.get_free_inode_count(target_group)
            if num_free_inodes == 0:
                target_group = self.find_free_inodes_near(target_group)
            return target_group
        elif type == '目錄' or self.spread_inodes == True:
            # 找出擁有最多空閒 inode 的群組
            return self.find_most_free_inodes_multiple(0, self.allocate_faraway)
        else:
            print('中止：不合法的檔案類型 [%s]（內部錯誤）' % type)
            exit(1)
        return 0

    def range_free(self, group, index, needed, chunks_free):
        if needed < chunks_free:
            chunks_free = needed

        # 建立一份要檢查是否空閒的區塊清單
        index_begin = index
        index_end = index + chunks_free - 1
        if index_end >= self.blocks_per_group:
            return False

        for i in range(index_begin, index_end+1):
            if self.data_bitmap[group][i] != self.BITMAP_FREE:
                return False
        return True

        if self.data_bitmap[group][index] == self.BITMAP_FREE:
            return True
        return False

    # group 只是 inode 所在的群組
    # size 則是總共需要多少個區塊
    def allocate_blocks(self, target_group, size, inode_number):
        assert(size <= self.total_data_free)
        allocated = []
        index = 0
        allocated_in_group = 0
        current_group = target_group
        chunks_free = self.contig_allocation_policy
        while True:
            if self.range_free(current_group, index, size-len(allocated), chunks_free):
                # print('  區域配置', current_group, index)
                assert(self.data_bitmap[current_group][index] == self.BITMAP_FREE)
                self.data_bitmap[current_group][index] = inode_number
                allocated_in_group += 1
                allocated.append((current_group, index))
            index += 1

            if len(allocated) == size:
                # print('完成', allocated)
                break

            # 需要的時候，把配置的注意力移到下一個群組
            # 也就是說，當你已經搜尋完整個群組，或是
            #       已經用完大檔案例外（large file exception）的額度時
            if index == self.blocks_per_group or \
               (self.large_file_exception > 0 and \
                allocated_in_group == self.large_file_exception):
                allocated_in_group = 0
                index = 0
                current_group = (current_group + 1) % self.num_groups
                if current_group == target_group:
                    chunks_free = 1

        return allocated

    def find_free_inode(self, group):
        inode_number = -1
        for i in range(self.inodes_per_group):
            if self.inode_bitmap[group][i] == self.BITMAP_FREE:
                inode_number = i
                break
        # 應該不會發生這種情況，不過保險起見……
        if inode_number == -1:
            self.vprint('[找不到空閒的 inode]')
            return -1
        return inode_number

    def find_min_data_usage(self):
        min_group = -1
        min_usage = 0
        for g in range(self.num_groups):
            data_free = self.get_free_data_count(g)
            if data_free > min_usage:
                min_usage = data_free
                min_group = g
        return min_group

    def mark_inode_used(self, group, inode_index):
        self.inode_bitmap[group][inode_index] = inode_index + \
                                                (group * self.inodes_per_group)
        return

    def do_delete(self, path):
        parent, filename = self.get_parent(path)

        # 接著，在父目錄中找出這個檔案
        parent_inode_number = self.name_to_inode(parent)
        if parent_inode_number == -1:
            self.vprint('[找不到父目錄的 inode %s]' % parent)
            return -1

        del_index = -1
        for i in range(len(self.dir_data[parent_inode_number])):
            name, inode_number = self.dir_data[parent_inode_number][i]
            if name == filename:
                del_index = i
                break

        if del_index == -1:
            self.vprint('[找不到 %s（在目錄 %s 中）]' % (filename, parent))
            return -1

        if self.inode_type[inode_number] == '目錄':
            self.vprint('[無法刪除目錄]')
            return -1

        self.dir_data[parent_inode_number].remove((name, inode_number))

        for b in self.inode_blocks[inode_number]:
            data_group = int(b / self.num_groups)
            data_index = b % self.num_groups
            self.data_bitmap[data_group][data_index] = self.BITMAP_FREE

        inode_group = int(inode_number / self.num_groups)
        inode_index = inode_number % self.num_groups
        self.inode_bitmap[inode_group][inode_index] = self.BITMAP_FREE
        self.free_symbol(inode_number)

        del self.name_to_inode_map[path]

        self.total_inodes_free += 1
        self.total_data_free += len(self.inode_blocks[inode_number])

        self.inode_type[inode_number] = ''
        self.inode_blocks[inode_number] = []

        return 0

    def do_create(self, path, size, type):
        parent, filename = self.get_parent(path)

        # 在這裡做一些全域性的檢查
        if self.total_inodes_free == 0:
            self.vprint('[inode 用完了]')
            return -1
        if self.total_data_free < size:
            self.vprint('[磁碟空間用完了]')
            return -1

        # 檢查這個檔案是否已經存在
        parent_inode_number = self.name_to_inode(parent)
        if parent_inode_number == -1:
            self.vprint('[找不到父目錄 %s]' % parent)
            return -1
        for (name, __inode_number) in self.dir_data[parent_inode_number]:
            if name == filename:
                self.vprint('[檔案 %s 已經存在於目錄 %s 中]' % (filename, parent))
                return -1

        # 配置新的 inode：要選哪個群組？
        group = self.pick_group(parent, filename, type)

        # 現在挑選 inode：這裡可以保證這個群組一定會有空的 inode
        # 這都要歸功於 pick_group()……
        inode_index = self.find_free_inode(group)

        # 計算全域的 inode 編號
        inode_number = inode_index + (group * self.inodes_per_group)

        # 檔案配置策略：有可能會失敗
        # allocated = self.allocate_blocks(group, size, inode_number)
        if self.spread_data_blocks:
            dest_block_group = self.find_min_data_usage()
            print('配置目標', dest_block_group)
            allocated = self.allocate_blocks(dest_block_group, size, inode_number)
        else:
            allocated = self.allocate_blocks(group, size, inode_number)
        if len(allocated) == 0:
            # 配置失敗：檔案系統中沒有足夠空間
            return -1

        # 現在開始進行所有的配置工作：從這裡開始不會再失敗了
        self.mark_inode_used(group, inode_index)
        self.dir_data[parent_inode_number].append((filename, inode_number))

        # 接著，配置一些資料區塊
        self.inode_type[inode_number] = type
        self.inode_blocks[inode_number] = []

        for (selected_group, index) in allocated:
            global_block_number = index + (selected_group * self.blocks_per_group)
            # print '全域配置', global_block_number
            self.inode_blocks[inode_number].append(global_block_number)

        # 記錄名稱到 inode 編號的對應，供之後查詢用
        self.set_name_to_inode(path, inode_number)
        self.allocate_symbol(inode_number, filename)

        # 必須填入空目錄的內容
        if type == '目錄':
            self.dir_data[inode_number] = [('.', 0), ('..', 0)]

        # 全域的統計計算
        self.total_inodes_free -= 1
        self.total_data_free -= size

        return 0

    def init_symbols(self):
        self.symbol_map = {}
        self.used_symbols = []
        self.available_symbols = ['a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z','A','B','C','D','E','F','G','H','I','J','K','L','M','O','P','Q','R','S','T','U','V','W','X','Y','Z','0','1','2','3','4','5','6','7','8','9','!','@','#','%','^','&','*','(',')','[',']','{','}','/','.','<','>','|']
        return

    def allocate_symbol(self, inode_number, suggested_name):
        if suggested_name not in self.used_symbols \
               and suggested_name in self.available_symbols:
            choice = suggested_name
        else:
            assert(len(self.available_symbols) > 0)
            choice = self.available_symbols[0]
        # print '符號', suggested_name, '->', choice
        self.used_symbols.append(choice)
        self.available_symbols.remove(choice)
        self.symbol_map[inode_number] = choice
        return

    def free_symbol(self, inode_number):
        symbol = self.symbol_map[inode_number]
        del self.symbol_map[inode_number]
        self.used_symbols.remove(symbol)
        self.available_symbols.append(symbol)
        return

    def get_symbol(self, inode_number):
        return self.symbol_map[inode_number]

    def print_success_or_fail(self, rc):
        if self.show_file_ops:
            if rc == 0:
                print('成功')
            else:
                print('失敗')
        return

    def do_verify(self):
        data_used = 0
        inodes_used = 0
        for g in range(self.num_groups):
            for i in range(self.blocks_per_group):
                if self.data_bitmap[g][i] != self.BITMAP_FREE:
                    data_used += 1
            for i in range(self.inodes_per_group):
                if self.inode_bitmap[g][i] != self.BITMAP_FREE:
                    inodes_used += 1
        assert(data_used + self.total_data_free == (self.num_groups * self.blocks_per_group))
        assert(inodes_used + self.total_inodes_free == (self.num_groups * self.inodes_per_group))

        for f in self.name_to_inode_map:
            inode_number = self.name_to_inode_map[f]
            blocks = self.inode_blocks[inode_number]
            for b in blocks:
                data_group = int(b / self.blocks_per_group)
                data_index = b % self.blocks_per_group
                assert(self.data_bitmap[data_group][data_index] == inode_number)
        return

    def create(self, path, size):
        self.vprint('操作 create %s [大小:%d] ->' % (path, size))
        rc = self.do_create(path, size, '一般檔案')
        self.print_success_or_fail(rc)
        return rc

    def mkdir(self, path):
        self.vprint('操作 mkdir %s ->' % path)
        rc = self.do_create(path, 1, '目錄')
        self.print_success_or_fail(rc)
        return rc

    def delete(self, path):
        self.vprint('操作 delete %s ->' % path)
        rc = self.do_delete(path)
        self.print_success_or_fail(rc)
        return


    def read_input(self, filename):
        fd = open(filename)
        for line in fd:
            in_line = line.strip('\n')
            line_len = len(in_line)
            if line_len == 0:
                continue
            tmp = in_line.split()
            if len(tmp) == 0:
                continue
            if tmp[0] == 'file':
                assert(len(tmp) == 3)
                name, size = tmp[1], int(tmp[2])
                self.create(name, size)
            elif tmp[0] == 'dir':
                assert(len(tmp) == 2)
                name = tmp[1]
                self.mkdir(name)
            elif tmp[0] == 'delete':
                assert(len(tmp) == 2)
                name = tmp[1]
                self.delete(name)
            elif tmp[0] == 'dump':
                assert(len(tmp) == 1)
                self.dump()
            else:
                print('無法識別的指令', tmp[0])
                exit(1)
            self.do_verify()
        fd.close()
        return

    def list_to_string(self, bitmap):
        out_str = ''
        for i in range(len(bitmap)):
            if i > 0 and i % 10 == 0:
                out_str += ' '
            if bitmap[i] == self.BITMAP_FREE:
                out_str += '-'
            else:
                out_str += '%s' % self.get_symbol(bitmap[i])
        return out_str

    def do_numeric_header(self, power_level, how_many):
        power = int(math.pow(10, power_level))
        counter = 0
        value = 0
        out_str = ''
        for i in range(how_many):
            if i > 0 and i % 10 == 0:
                out_str += ' '
            out_str += '%d' % (value % 10)
            counter += 1
            if counter == power:
                value += 1
                counter = 0
        print(out_str, end='')
        return

    def dump(self):
        print('')
        print('群組數量:         ', self.num_groups)
        print('每組 inode 數:    ', self.inodes_per_group)
        print('每組區塊數:       ', self.blocks_per_group)
        print('')
        print('空閒資料區塊: %d（共 %d）' % (self.total_data_free, (self.num_groups * self.blocks_per_group)))
        print('空閒 inode 數: %d（共 %d）' % (self.total_inodes_free, (self.num_groups * self.inodes_per_group)))
        print('')
        print('是否分散 inode？ ', self.spread_inodes)
        print('是否分散資料？   ', self.spread_data_blocks)
        print('連續配置需求:    ', self.contig_allocation_policy)
        print('')

        inode_power = len('%s' % self.inodes_per_group) - 1
        data_power = len('%s' % self.blocks_per_group) - 1

        if inode_power > data_power:
            max_power = inode_power
        else:
            max_power = data_power

        while max_power >= 0:
            print('     ', end='') # inode 印出前的間距
            if inode_power >= max_power:
                self.do_numeric_header(max_power, self.inodes_per_group)
            else:
                out_str = ' ' * self.inodes_per_group
                print(out_str, end='')

            if data_power >= max_power:
                self.do_numeric_header(max_power, self.blocks_per_group)
            else:
                out_str = ' ' * self.inodes_per_group
                print(out_str, end='')

            print('')
            max_power -= 1

        print('\n群組 %s' % ('inodes'[0:self.inodes_per_group]), end='')
        out_str = ''
        for i in range(self.inodes_per_group - len('inodes')):
            out_str += ' '
        print('%sdata' % out_str)

        count = 0

        for i in range(self.num_groups):
            # print '  %3d inode %s' % (i, self.list_to_string(self.inode_bitmap[i]))
            # print '        data %s' % (self.list_to_string(self.data_bitmap[i]))
            if self.compute:
                print('  %3d %s %s' % (i,
                                       self.list_to_string(self.inode_bitmap[i]),
                                       self.list_to_string(self.data_bitmap[i])), end='')
                if self.show_block_addresses:
                    print('  [%4d-%4d]' % (count, count + self.group_size - 1))
                else:
                    print('')
            else:
                print('  %3d %s %s' % (i,
                                       '?' * self.inodes_per_group,
                                       '?' * self.blocks_per_group))

            count += self.group_size

        if self.do_per_file_stats:
            self.show_symbol_map = True

        if self.show_symbol_map == False:
            print('')
            return

        print('\n符號    inode#  檔名         檔案類型 ', end='')
        if self.do_per_file_stats:
            print('  區塊位址')
        else:
            print('')
        # sorted(student_tuples, key=lambda student: student[2])

        for name in sorted(self.name_to_inode_map):
            inode_number = self.name_to_inode_map[name]
            file_type = self.inode_type[inode_number]
            print('%-6s  %6d  %-11s  %-10s ' % \
                  (self.get_symbol(inode_number), inode_number, name, file_type), end='')
            if self.do_per_file_stats:
                for i in self.inode_blocks[inode_number]:
                    print(i, end=' ')
                print('')
            else:
                print('')
        print('')
        return

    def get_dist(self, a, b):
        if a > b:
            return a - b
        else:
            return b - a

    def get_spans(self, path):
        inode_number = self.name_to_inode(path)

        inode_group = int(inode_number / self.inodes_per_group)
        inode_index = inode_number % self.inodes_per_group
        inode_address = inode_index + inode_group * self.group_size

        # 現在找出所有的資料區塊
        min_address = 1 + (self.num_groups * self.group_size)
        max_address = -1

        data_blocks = self.inode_blocks[inode_number]

        for d in data_blocks:
            data_group = int(d / self.blocks_per_group)
            data_index = d % self.blocks_per_group
            data_address = data_index + (data_group * self.group_size) + self.inodes_per_group

            if data_address > max_address: max_address = data_address
            if data_address < min_address: min_address = data_address

        return inode_number, inode_address, min_address, max_address

    def do_all_spans(self):
        current = 0
        total_dist = 0

        min_group = 1e6
        max_group = -1

        print('跨距：檔案')
        span_results = {}
        filespan_sum = 0
        filespan_cnt = 0
        for f in self.name_to_inode_map:
            inode_number, inode_address, min_address, max_address = self.get_spans(f)
            if self.inode_type[inode_number] == '目錄':
                continue

            data_span = max_address - min_address
            abs_min, abs_max = min_address, max_address
            if inode_address < abs_min:
                abs_min = inode_address
            if inode_address > abs_max:
                abs_max = inode_address
            file_span = abs_max - abs_min

            assert(inode_number not in span_results)
            span_results[inode_number] = (inode_address, min_address, max_address)

            if options.solve:
                print('  檔案: %10s  檔案跨距: %3d' % (f, file_span))
            else:
                print('  檔案: %10s  檔案跨距: %s' % (f, '?'))

            filespan_sum += file_span
            filespan_cnt += 1

        if filespan_cnt > 0:
            filespan_avg = '%3.2f' % (float(filespan_sum)/float(filespan_cnt))
            if options.solve:
                print('               平均  檔案跨距: %6s' % (filespan_avg))
            else:
                print('               平均  檔案跨距: ?')


        print('\n跨距：目錄')
        dirspan_sum = 0
        dirspan_cnt = 0
        for f in self.name_to_inode_map:
            all_addresses = []
            inode_number, inode_address, min_address, max_address = self.get_spans(f)
            if self.inode_type[inode_number] != '目錄':
                continue
            for address in [inode_address, min_address, max_address]:
                all_addresses.append(address)

            for entry_name, entry_inode_number in self.dir_data[inode_number]:
                if entry_name == '.' or entry_name == '..':
                    continue
                if self.inode_type[entry_inode_number] == '目錄':
                    continue
                for i in range(3):
                    all_addresses.append(span_results[entry_inode_number][i])
            all_sorted = sorted(all_addresses)
            # print '目錄跨距', f, all_sorted[len(all_sorted)-1], all_sorted[0]
            dirspan = all_sorted[len(all_sorted)-1] - all_sorted[0]
            dirspan_sum += dirspan
            dirspan_cnt += 1
            if options.solve:
                print('  目錄: %10s  目錄跨距: %3d' % (f, dirspan))
            else:
                print('  目錄: %10s  目錄跨距: ?' % (f))

        dirspan_avg = '%3.2f' % (float(dirspan_sum)/float(dirspan_cnt))
        if options.solve:
            print('               平均  目錄跨距: %6s' % (dirspan_avg))
        else:
            print('               平均  目錄跨距: ?')


        print('')
        return




#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子',
                  action='store', type='int', dest='seed')
parser.add_option('-n', '--num_groups', default=10, help='區塊群組（block group）的數量',
                  action='store', type='int', dest='num_groups')
parser.add_option('-d', '--datablocks_per_groups', default=30,
                  help='每個群組的資料區塊數量', action='store',
                  type='int', dest='blocks_per_group')
parser.add_option('-i', '--inodes_per_group', default=10, help='每個群組的 inode 數量',
                  action='store', type='int', dest='inodes_per_group')
parser.add_option('-L', '--large_file_exception', default=30,
                  help='0 表示關閉；N>0 表示：檔案在群組中配置多少個區塊後，才會分散到下一個群組',
                  action='store', type='int', dest='large_file_exception')
parser.add_option('-f', '--input_file', default='/no/such/file', help='指令檔案',
                  action='store', type='string', dest='input_file')
parser.add_option('-I', '--spread_inodes', default=False,
                  help='不把檔案的 inode 放在父目錄所在的群組，而是平均分散到所有群組中',
                  action='store_true', dest='spread_inodes')
parser.add_option('-D', '--spread_data', default=False,
                  help='不把資料放在 inode 附近，而是平均分散到所有群組中',
                  action='store_true', dest='spread_data_blocks')
parser.add_option('-A', '--allocate_faraway', default=1,
                  help='選擇群組時，一次檢查這麼多個群組',
                  action='store', dest='allocate_faraway', type='int')
parser.add_option('-C', '--contig_allocation_policy', default=1,
                  help='配置時需要的連續空閒區塊數量',
                  action='store', type='int', dest='contig_allocation_policy')
parser.add_option('-T', '--show_spans', help='顯示檔案與目錄的跨距（span）',
                  default=False, action='store_true', dest='show_spans')
parser.add_option('-M', '--show_symbol_map', help='顯示符號對照表',
                  default=False, action='store_true', dest='show_symbol_map')
parser.add_option('-B', '--show_block_addresses',
                  help='在群組旁顯示區塊位址',
                  action='store_true', default=False, dest='show_block_addresses')
parser.add_option('-S', '--do_per_file_stats',
                  help='印出詳細的 inode 統計資訊',
                  action='store_true', default=False, dest='do_per_file_stats')
parser.add_option('-v', '--show_file_ops',
                  help='印出每個操作詳細的成功/失敗資訊',
                  action='store_true', default=False, dest='show_file_ops')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true',
                  default=False, dest='solve')

(options, args) = parser.parse_args()

random.seed(options.seed)

fs = file_system(num_groups=options.num_groups,
                 blocks_per_group=options.blocks_per_group,
                 inodes_per_group=options.inodes_per_group,
                 large_file_exception=options.large_file_exception,
                 spread_inodes=options.spread_inodes,
                 contig_allocation_policy=options.contig_allocation_policy,
                 spread_data_blocks=options.spread_data_blocks,
                 allocate_faraway=options.allocate_faraway,
                 show_block_addresses=options.show_block_addresses,
                 do_per_file_stats=options.do_per_file_stats,
                 show_file_ops=options.show_file_ops,
                 show_symbol_map=options.show_symbol_map,
                 compute=options.solve)

fs.read_input(options.input_file)

fs.dump()

if options.show_spans:
    fs.do_all_spans()
