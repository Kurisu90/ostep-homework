#! /usr/bin/env python
# -*- coding: utf-8 -*-

#
# lfs_zh.py
#
# 一個模擬 LFS 行為的簡易模擬器。
#
# 做了很多簡化假設，包括像是：
# - 所有實體都恰好佔用一個區塊
# - 不使用 segment，寫入也不會在記憶體中緩衝
# - 還有很多其他簡化
#

from __future__ import print_function
import math
import sys
from optparse import OptionParser
import random
import copy

# 讓 Python2 與 Python3 的行為一致 -- 有夠蠢的作法
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

# 固定位址
ADDR_CHECKPOINT_BLOCK = 0

# 這些目前還不能被使用者調整
NUM_IMAP_PTRS_IN_CR       = 16
NUM_INODES_PER_IMAP_CHUNK = 16
NUM_INODE_PTRS            = 8

NUM_INODES = NUM_IMAP_PTRS_IN_CR * NUM_INODES_PER_IMAP_CHUNK

# 區塊型別
BLOCK_TYPE_CHECKPOINT     = 'type_cp'
BLOCK_TYPE_DATA_DIRECTORY = 'type_data_dir'
BLOCK_TYPE_DATA_BLOCK     = 'type_data'
BLOCK_TYPE_INODE          = 'type_inode'
BLOCK_TYPE_IMAP           = 'type_imap'

# inode 型別
INODE_DIRECTORY           = 'dir'
INODE_REGULAR             = 'reg'

# 依照 Unix 慣例，根目錄的 inode 編號是眾所皆知的（well known）
ROOT_INODE                = 0

# 配置策略
ALLOCATE_SEQUENTIAL       = 1
ALLOCATE_RANDOM           = 2

#
# 模擬器的核心邏輯都在這裡
#
class LFS:
    def __init__(self, use_disk_cr=False, no_force_checkpoints=False,
                 inode_policy=ALLOCATE_SEQUENTIAL, solve=False):
        # 是否要從磁碟讀取檢查點區域與 imap 片段（若為 True）
        # 否則就只使用「記憶體內」的 inode map
        self.use_disk_cr          = use_disk_cr

        # 是否強制在每次寫入後都更新檢查點區域
        self.no_force_checkpoints = no_force_checkpoints

        # inode 配置策略
        assert(inode_policy == ALLOCATE_SEQUENTIAL or inode_policy == ALLOCATE_RANDOM)
        self.inode_policy = inode_policy

        # 是否要顯示「答案」
        self.solve                = solve

        # 輔助 dump 用的欄位
        self.dump_last            = 1

        # 所有區塊都存在「磁碟」裡
        self.disk = []

        # 檢查點區域（第一個區塊）
        self.cr    = [3,-1,-1,-1,
                      -1,-1,-1,-1,
                      -1,-1,-1,-1,
                      -1,-1,-1,-1]
        assert(len(self.cr) == NUM_IMAP_PTRS_IN_CR)

        # 建立第一個檢查點區域
        self.log({'block_type':BLOCK_TYPE_CHECKPOINT, 'entries': self.cr})
        assert(len(self.disk) == 1)

        # 初始化根目錄資料
        self.log(self.make_new_dirblock(ROOT_INODE, ROOT_INODE))
        assert(len(self.disk) == 2)

        # 根目錄的 inode
        root_inode = self.make_inode(itype=INODE_DIRECTORY, size=1, refs=2)
        root_inode['pointers'][0] = 1
        root_inode_address = self.log(root_inode)
        assert(len(self.disk) == 3)

        # 初始化記憶體內的 imap
        self.inode_map = {}
        for i in range(NUM_INODES):
            self.inode_map[i] = -1
        self.inode_map[ROOT_INODE] = root_inode_address

        # imap 片段
        self.log(self.make_imap_chunk(ROOT_INODE))
        assert(len(self.disk) == 4)

        # 錯誤代碼追蹤
        self.error_clear()
        return

    def make_data_block(self, data):
        return {'block_type':BLOCK_TYPE_DATA_BLOCK, 'contents':data}

    def make_inode(self, itype, size, refs):
        return {'block_type':BLOCK_TYPE_INODE, 'type':itype, 'size':size, 'refs':refs,
                'pointers':[-1,-1,-1,-1,-1,-1,-1,-1]}

    def make_new_dirblock(self, parent_inum, current_inum):
        dirblock = self.make_empty_dirblock()
        dirblock['entries'][0] = ('.', current_inum)
        dirblock['entries'][1] = ('..', parent_inum)
        return dirblock

    def make_empty_dirblock(self):
        return {'block_type':BLOCK_TYPE_DATA_DIRECTORY,
                'entries': [('-',-1), ('-',-1), ('-',-1), ('-',-1),
                            ('-',-1), ('-',-1), ('-',-1), ('-',-1)]}

    def make_imap_chunk(self, cnum):
        imap_chunk = {}
        imap_chunk['block_type'] = BLOCK_TYPE_IMAP
        imap_chunk['entries'] = list()
        start = cnum * NUM_INODES_PER_IMAP_CHUNK
        for i in range(start, start + NUM_INODES_PER_IMAP_CHUNK):
            imap_chunk['entries'].append(self.inode_map[i])
        return imap_chunk

    def make_random_blocks(self, num):
        contents = []
        for i in range(num):
            L = chr(ord('a') + int(random.random() * 26))
            contents.append(str(16 * ('%s%d' % (L, i))))
        return contents

    def inum_to_chunk(self, inum):
        return int(inum / NUM_INODES_PER_IMAP_CHUNK)

    def determine_liveness(self):
        # 首先，假設全部都是死的（未存活）
        self.live = {}
        for i in range(len(self.disk)):
            self.live[i] = False

        # 檢查點區域
        self.live[0] = True

        # 接著把最新的 imap 片段標記為存活
        for ptr in self.cr:
            if ptr == -1:
                continue
            self.live[ptr] = True

        # 走訪 imap，找出存活的 inode 及其位址
        # 依定義，最新的 inode 全部都是存活的
        inodes = []
        for i in range(len(self.inode_map)):
            if self.inode_map[i] == -1:
                continue
            self.live[self.inode_map[i]] = True
            inodes.append(i)

        # 走訪存活的 inode，找出各自指向的區塊
        for i in inodes:
            inode = self.disk[self.inode_map[i]]
            for ptr in inode['pointers']:
                self.live[ptr] = True
        return

    def error_log(self, s):
        self.error_list.append(s)
        return

    def error_clear(self):
        self.error_list = []
        return

    def error_dump(self):
        for i in self.error_list:
            print('  %s' % i)
        return

    def dump_partial(self, show_liveness, show_checkpoint):
        if show_checkpoint or not self.no_force_checkpoints:
            self.__dump(0, 1, show_liveness)
        if not self.no_force_checkpoints:
            print('...')
        self.__dump(self.dump_last, len(self.disk), show_liveness)
        self.dump_last = len(self.disk)
        return

    def dump(self, show_liveness):
        self.__dump(0, len(self.disk), show_liveness)
        return

    def __dump(self, start, end, show_liveness):
        self.determine_liveness()

        for i in range(start, end):
            # 印出磁碟上的位址
            b = self.disk[i]
            block_type = b['block_type']
            print('[ %3d ]' % i, end='')

            # 印出存活狀態
            if show_liveness or self.solve:
                if self.live[i]:
                    print(' 存活', end=' ')
                else:
                    print('     ', end=' ')
            else:
                print(' ?   ', end=' ')


            if block_type == BLOCK_TYPE_CHECKPOINT:
                print('檢查點：', end=' ')
                for e in b['entries']:
                    if e != -1:
                        print(e,  end=' ')
                    else:
                        print('--', end=' ')
                print('')
            elif block_type == BLOCK_TYPE_DATA_DIRECTORY:
                for e in b['entries']:
                    if e[1] != -1:
                        print('[%s,%s]' % (str(e[0]), str(e[1])), end=' ')
                    else:
                        print('--', end=' ')
                print('')
            elif block_type == BLOCK_TYPE_DATA_BLOCK:
                print (b['contents'])
            elif block_type == BLOCK_TYPE_INODE:
                print('型別:'+b['type'], '大小:'+str(b['size']), '參照:'+str(b['refs']), '指標:',  end=' ')
                for p in b['pointers']:
                    if p != -1:
                        print('%s' % p, end=' ')
                    else:
                        print('--', end=' ')
                print('')
            elif block_type == BLOCK_TYPE_IMAP:
                print('imap 區塊:', end=' ')
                for e in b['entries']:
                    if e != -1:
                        print(e, end=' ')
                    else:
                        print('--', end=' ')
                print('')
            else:
                print('錯誤：未知的 block_type', block_type)
                exit(1)
        return

    def log(self, block):
        new_address = len(self.disk)
        self.disk.append(copy.deepcopy(block))
        return new_address

    def allocate_inode(self):
        if self.inode_policy == ALLOCATE_SEQUENTIAL:
            for i in range(len(self.inode_map)):
                if self.inode_map[i] == -1:
                    # 呃：先暫時佔個位置，之後再填入真正的磁碟位址
                    self.inode_map[i] = 1
                    return i
        elif self.inode_policy == ALLOCATE_RANDOM:
            # 用這種沒效率的方式確保還有空間
            # 用配置／釋放計數器來做會比較好，但現階段這樣就夠了
            space_exists = False
            imap_len = len(self.inode_map)
            for i in range(imap_len):
                if self.inode_map[i] == -1:
                    space_exists = True
                    break
            if not space_exists:
                return -1
            while True:
                index = int(random.random() * imap_len)
                if self.inode_map[index] == -1:
                    self.inode_map[index] = 1
                    return index
        # 找不到空閒的 inode
        return -1


    def free_inode(self, inum):
        assert(self.inode_map[inum] != -1)
        self.inode_map[inum] = -1
        return

    def remap(self, inode_number, inode_address):
        self.inode_map[inode_number] = inode_address
        return

    def dump_inode_map(self):
        for i in range(len(self.inode_map)):
            if self.inode_map[i] != -1:
                print('  ', i, '->', self.inode_map[i])
        print('')
        return

    def cr_sync(self):
        # 這是程式碼中唯一會做「覆寫」的地方
        self.disk[ADDR_CHECKPOINT_BLOCK] = copy.deepcopy({'block_type':BLOCK_TYPE_CHECKPOINT, 'entries': self.cr})
        return 0

    def get_inode_from_inumber(self, inode_number):
        imap_entry_index = int(inode_number / NUM_INODES_PER_IMAP_CHUNK)
        imap_entry_offset = inode_number % NUM_INODES_PER_IMAP_CHUNK

        if self.use_disk_cr:
            # 這是走磁碟的路徑
            checkpoint_block = self.disk[ADDR_CHECKPOINT_BLOCK]
            assert(checkpoint_block['block_type'] == BLOCK_TYPE_CHECKPOINT)

            imap_block_address = checkpoint_block['entries'][imap_entry_index]
            imap_block = self.disk[imap_block_address]
            assert(imap_block['block_type'] == BLOCK_TYPE_IMAP)

            inode_address = imap_block['entries'][imap_entry_offset]
        else:
            # 這是直接用記憶體內 inode_map 的路徑
            inode_address = self.inode_map[inode_number]

        assert(inode_address != -1)
        inode = self.disk[inode_address]
        assert(inode['block_type'] == BLOCK_TYPE_INODE)
        return inode

    def __lookup(self, parent_inode_number, name):
        parent_inode = self.get_inode_from_inumber(parent_inode_number)
        assert(parent_inode['type'] == INODE_DIRECTORY)
        for address in parent_inode['pointers']:
            if address == -1:
                continue
            directory_block = self.disk[address]
            assert(directory_block['block_type'] == BLOCK_TYPE_DATA_DIRECTORY)
            for entry_name, entry_inode_number in directory_block['entries']:
                if entry_name == name:
                    return (entry_inode_number, parent_inode)
        return (-1, parent_inode)

    def __walk_path(self, path):
        split_path = path.split('/')
        if split_path[0] != '':
            self.error_log('路徑格式錯誤：必須以 / 開頭')
            return -1, '', -1, ''
        inode_number = -1
        parent_inode_number = ROOT_INODE # 根目錄的 inode 編號是眾所皆知的
        for i in range(1, len(split_path) - 1):
            inode_number, inode = self.__lookup(parent_inode_number, split_path[i])
            if inode_number == -1:
                self.error_log('找不到目錄 %s' % split_path[i])
                return -1, '', -1, ''
            if inode['type'] != INODE_DIRECTORY:
                self.error_log('路徑中的元素 [%s] 不合法（不是目錄）' % split_path[i])
                return -1, '', -1, ''
            parent_inode_number = inode_number

        file_name = split_path[len(split_path) - 1]
        inode_number, parent_inode = self.__lookup(parent_inode_number, file_name)
        return inode_number, file_name, parent_inode_number, parent_inode

    def update_imap(self, inum_list):
        chunk_list = list()
        for inum in inum_list:
            cnum = self.inum_to_chunk(inum)
            if cnum not in chunk_list:
                chunk_list.append(cnum)
                self.log(self.make_imap_chunk(cnum))
                self.cr[cnum] = len(self.disk) - 1
        return

    def __read_dirblock(self, inode, index):
        return self.disk[inode['pointers'][index]]

    # 回傳 (inode_index, dirblock_index)
    def __find_matching_dir_slot(self, name, inode):
        for inode_index in range(inode['size']):
            directory_block = self.__read_dirblock(inode, inode_index)
            assert(directory_block['block_type'] == BLOCK_TYPE_DATA_DIRECTORY)

            for slot_index in range(len(directory_block['entries'])):
                entry_name, entry_inode_number = directory_block['entries'][slot_index]
                if entry_name == name:
                    return inode_index, slot_index
        return -1, -1

    def __add_dir_entry(self, parent_inode, file_name, inode_number):
        # 這會是用來存放新的 name->inum 對應關係的目錄區塊
        inode_index, dirblock_index = self.__find_matching_dir_slot('-', parent_inode)

        if inode_index != -1:
            # 現有區塊裡還有空間：做一份複本、更新它，再記錄下來
            index_to_update = inode_index
            parent_size = parent_inode['size']

            new_directory_block = copy.deepcopy(self.__read_dirblock(parent_inode, inode_index))
            new_directory_block['entries'][dirblock_index] = (file_name, inode_number)
        else:
            # 現有目錄區塊已無空間：如果 inode 還有空間可以指向新區塊，就配置一個新的
            if parent_inode['size'] != NUM_INODE_PTRS:
                index_to_update = parent_inode['size']
                parent_size = index_to_update + 1

                new_directory_block = self.make_empty_dirblock()
                new_directory_block['entries'][0] = (file_name, inode_number)
            else:
                return -1, -1, {}
        return index_to_update, parent_size, new_directory_block

    # 建立（檔案或目錄）
    def __file_create(self, path, is_file):
        inode_number, file_name, parent_inode_number, parent_inode = self.__walk_path(path)
        if inode_number != -1:
            # self.error_log('create failed: file %s already exists' % path)
            self.error_log('建立失敗：檔案已經存在')
            return -1

        if parent_inode_number == -1:
            self.error_log('建立失敗：walkpath 回傳錯誤 [%s]' % path)
            return -1

        # 最後，替新的檔案／目錄配置一個 inode 編號
        new_inode_number = self.allocate_inode()
        if new_inode_number == -1:
            self.error_log('建立失敗：已經沒有可用的 inode 了')
            return -1

        # 這會是用來存放新的 name->inum 對應關係的目錄區塊
        index_to_update, parent_size, new_directory_block = self.__add_dir_entry(parent_inode, file_name, new_inode_number)
        if index_to_update == -1:
            self.error_log('錯誤：目錄已滿（路徑 %s）' % path)
            self.free_inode(new_inode_number);
            return -1

        # 記錄目錄資料區塊（可能是舊區塊的新版本，也可能是全新的一個）
        new_directory_block_address = self.log(new_directory_block)

        # 現在必須做出目錄 inode 的新版本
        # 視需要更新 size、如果是目錄就增加 refs、並指向新的目錄區塊位址
        new_parent_inode = copy.deepcopy(parent_inode)
        new_parent_inode['size'] = parent_size
        if not is_file:
            new_parent_inode['refs'] += 1
        new_parent_inode['pointers'][index_to_update] = new_directory_block_address

        # 如果是目錄，必須建立一個空的目錄區塊
        if not is_file:
            self.log(self.make_new_dirblock(parent_inode_number, new_inode_number))
            new_dirblock_address = len(self.disk) - 1

        # 以及新的 inode 本身
        if is_file:
            # 預設建立一個空檔案
            new_inode = self.make_inode(itype=INODE_REGULAR, size=0, refs=1)
        else:
            # 建立目錄 inode，並指向它所擁有的那一個目錄區塊
            new_inode = self.make_inode(itype=INODE_DIRECTORY, size=1, refs=2)
            new_inode['pointers'][0] = new_dirblock_address

        #
        # 把更新後的父目錄 inode、檔案／目錄 inode 加入記錄（LOG）
        #
        new_parent_inode_address = self.log(new_parent_inode)
        new_inode_address = self.log(new_inode)

        # 為父目錄與新 inode 建立新的 imap 項目
        self.remap(parent_inode_number, new_parent_inode_address)
        self.remap(new_inode_number, new_inode_address)

        # 最後，建立新的一份 imap 區塊
        self.update_imap([parent_inode_number, new_inode_number])

        # 同步檢查點區域
        if not self.no_force_checkpoints:
            self.cr_sync()
        return 0

    # file_create()
    def file_create(self, path):
        self.error_clear()
        return self.__file_create(path, True)

    # dir_create()
    def dir_create(self, path):
        self.error_clear()
        return self.__file_create(path, False)

    # link()
    def file_link(self, srcpath, dstpath):
        self.error_clear()

        src_inode_number, src_file_name, src_parent_inode_number, src_parent_inode = self.__walk_path(srcpath)
        if src_inode_number == -1:
            self.error_log('連結失敗，找不到來源 [%s]' % srcpath)
            return -1

        src_inode = self.get_inode_from_inumber(src_inode_number)
        if src_inode['type'] != INODE_REGULAR:
            self.error_log('連結失敗：不能連結到非一般檔案 [%s]' % srcpath)
            return -1

        dst_inode_number, dst_file_name, dst_parent_inode_number, dst_parent_inode = self.__walk_path(dstpath)
        if dst_inode_number != -1:
            self.error_log('連結失敗，目的地 [%s] 已經存在' % dstpath)
            return -1

        # 這會是用來存放新的 name->inum 對應關係的目錄區塊
        dst_index_to_update, dst_parent_size, new_directory_block = self.__add_dir_entry(dst_parent_inode, dst_file_name, src_inode_number)
        if dst_index_to_update == -1:
            self.error_log('錯誤：目錄已滿 [路徑 %s]' % dstpath)
            return -1

        # 記錄目錄資料區塊（可能是舊區塊的新版本，也可能是全新的一個）
        new_directory_block_address = self.log(new_directory_block)

        # 現在必須做出目錄 inode 的新版本
        # 視需要更新 size、如果是目錄就增加 refs、並指向新的目錄區塊位址
        new_dst_parent_inode = copy.deepcopy(dst_parent_inode)
        new_dst_parent_inode['size'] = dst_parent_size
        new_dst_parent_inode['pointers'][dst_index_to_update] = new_directory_block_address

        # 把更新後的父目錄 inode 加入記錄（LOG）
        new_dst_parent_inode_address = self.log(new_dst_parent_inode)

        # inode 也必須改變，以反映新的 refs 計數
        new_src_inode = copy.deepcopy(src_inode)
        new_src_inode['refs'] += 1
        new_src_inode_address = self.log(new_src_inode)

        # 為父目錄與新 inode 建立新的 imap 項目
        self.remap(dst_parent_inode_number, new_dst_parent_inode_address)
        self.remap(src_inode_number, new_src_inode_address)

        # 最後，建立新的一份 imap 區塊
        self.update_imap([dst_parent_inode_number])

        # 同步檢查點區域
        if not self.no_force_checkpoints:
            self.cr_sync()
        return 0

    def file_write(self, path, offset, num_blks):
        self.error_clear()

        # 先隨便捏造出資料區塊的內容──最多到寫入要求的數量
        # 注意：實際可能不會全部寫完，因為 inode 空間可能不夠……
        contents = self.make_random_blocks(num_blks)

        inode_number, file_name, parent_inode_number, parent_inode = self.__walk_path(path)
        if inode_number == -1:
            self.error_log('寫入失敗：找不到檔案 [路徑 %s]' % path)
            return -1

        inode = self.get_inode_from_inumber(inode_number)
        if inode['type'] != INODE_REGULAR:
            self.error_log('寫入失敗：不能寫入非一般檔案 %s' % path)
            return -1

        if offset < 0 or offset >= NUM_INODE_PTRS:
            self.error_log('寫入失敗：不合法的 offset %d' % offset)
            return -1

        # 建立可能的寫入清單──最多到檔案的最大大小
        current_log_ptr = len(self.disk)
        current_offset = offset
        potential_writes = []
        while current_offset < NUM_INODE_PTRS and current_offset < offset + len(contents):
            potential_writes.append((current_offset, current_log_ptr))
            current_offset += 1
            current_log_ptr += 1

        # 寫入資料區塊
        for i in range(len(potential_writes)):
            self.log(self.make_data_block(contents[i]))

        # 寫入 inode 的新版本，並更新其大小
        new_inode = copy.deepcopy(inode)
        new_inode['size'] = max(current_offset, inode['size'])
        for new_offset, new_addr in potential_writes:
            new_inode['pointers'][new_offset] = new_addr
        new_inode_address = self.log(new_inode)

        # 寫入新的 imap 區塊
        self.remap(inode_number, new_inode_address)
        self.log(self.make_imap_chunk(self.inum_to_chunk(inode_number)))
        self.cr[self.inum_to_chunk(inode_number)] = len(self.disk) - 1

        # 寫入檢查點區域
        if not self.no_force_checkpoints:
            self.cr_sync()

        # 回傳實際寫入的大小（總共寫入的量，不一定等於要求的量，可能比要求的少）
        return current_offset - offset

    def file_delete(self, path):
        self.error_clear()

        inode_number, file_name, parent_inode_number, parent_inode = self.__walk_path(path)
        if inode_number == -1:
            self.error_log('刪除失敗：找不到檔案 [%s]' % path)
            return -1

        inode = self.get_inode_from_inumber(inode_number)
        if inode['type'] != INODE_REGULAR:
            self.error_log('刪除失敗：不能刪除非一般檔案 [%s]' % path)
            return -1

        # 必須檢查：這個檔案是不是剛好只剩下最後一個連結？
        if inode['refs'] == 1:
            self.free_inode(inode_number)

        # 接著，找出目錄資料區塊裡的項目，並把它清空
        inode_index, dirblock_index = self.__find_matching_dir_slot(file_name, parent_inode)
        assert(inode_index != -1)
        new_directory_block = copy.deepcopy(self.__read_dirblock(parent_inode, inode_index))
        new_directory_block['entries'][dirblock_index] = ('-', -1)

        # 這會導致目錄資料、目錄 inode（進而是 IMAP_CHUNK、CR_SYNC）都要寫入
        dir_addr = self.log(new_directory_block)

        new_parent_inode = copy.deepcopy(parent_inode)
        new_parent_inode['pointers'][inode_index] = dir_addr
        new_parent_inode_addr = self.log(new_parent_inode)
        self.remap(parent_inode_number, new_parent_inode_addr)

        # 如果這不是最後一個連結，就減少參照計數並輸出新版本
        if inode['refs'] > 1:
            new_inode = copy.deepcopy(inode)
            new_inode['refs'] -= 1
            new_inode_addr = self.log(new_inode)
            self.remap(inode_number, new_inode_addr)

        # 建立新的一份 imap 區塊
        self.update_imap([inode_number, parent_inode_number])

        # 如有需要就同步
        if not self.no_force_checkpoints:
            self.cr_sync()
        return 0

    def sync(self):
        self.error_clear()
        return self.cr_sync()

#
# 給主程式用的輔助函式
#
def pick_random(a_list):
    if len(a_list) == 0:
        return ''
    index = int(random.random() * len(a_list))
    return a_list[index]

def make_random_file_name(parent_dir):
    L1 = chr(ord('a') + int(random.random() * 26))
    L2 = chr(ord('a') + int(random.random() * 26))
    N1 = str(int(random.random() * 10))
    if parent_dir == '/':
        return '/' + L1 + L2 + N1
    return parent_dir + '/' + L1 + L2 + N1

#
# 格式必須是：cXX,wXX 等等
# 其中第一個字母是指令，XX 是百分比（0 到 100 之間）
#
def process_percentages(percentages):
    tmp = percentages.split(',')
    csum = 0
    for p in tmp:
        cmd = p[0]
        value = int(p[1:])
        if value < 0:
            print('百分比必須是零或正數')
            exit(1)
        csum += int(value)
    if csum != 100:
        print('百分比加起來不等於 100')
        exit(1)

    p_array = {}

    cmd_list = ['c', 'w', 'd', 'r', 'l', 's']

    for c in cmd_list:
        p_array[c] = (0, 0)

    csum = 0
    for p in tmp:
        cmd = p[0]
        if cmd not in cmd_list:
            print('不合法的指令', cmd)
            exit(1)
        value = int(p[1:])
        p_array[cmd] = (csum, csum + value)
        csum += value

    for i in p_array:
        p_array[i] = (p_array[i][0] / 100.0, p_array[i][1] / 100.0)

    return p_array

def make_command_list(num_commands, percent):
    command_list = ''
    existing_files = []
    existing_dirs = ['/']
    while num_commands > 0:
        chances = random.random()
        command = ''
        if chances >= percents['c'][0] and chances < percents['c'][1]:
            pdir = pick_random(existing_dirs)
            if pdir == '':
                continue
            nfile = make_random_file_name(pdir)
            command = 'c,%s' % nfile
            existing_files.append(nfile)
        elif chances >= percents['w'][0] and chances < percents['w'][1]:
            pfile = pick_random(existing_files)
            if pfile == '':
                continue
            woff = int(random.random() * 8)
            wlen = int(random.random() * 8)
            command = 'w,%s,%d,%d' % (pfile, woff, wlen)
        elif chances >= percents['d'][0] and chances < percents['d'][1]:
            pdir = pick_random(existing_dirs)
            if pdir == '':
                continue
            ndir = make_random_file_name(pdir)
            command = 'd,%s' % ndir
            existing_dirs.append(ndir)
        elif chances >= percents['r'][0] and chances < percents['r'][1]:
            if len(existing_files) == 0:
                continue
            index = int(random.random() * len(existing_files))
            command = 'r,%s' % existing_files[index]
            del existing_files[index]
        elif chances >= percents['l'][0] and chances < percents['l'][1]:
            if len(existing_files) == 0:
                continue
            index = int(random.random() * len(existing_files))
            pdir = pick_random(existing_dirs)
            if pdir == '':
                continue
            nfile = make_random_file_name(pdir)
            command = 'l,%s,%s' % (existing_files[index], nfile)
            existing_files.append(nfile)
        elif chances >= percents['s'][0] and chances < percents['s'][1]:
            command = 's'
        else:
            print('中止：百分比運算發生內部錯誤')
            exit(1)

        if command_list == '':
            command_list = command
        else:
            command_list += ':' + command

        num_commands -= 1
    return command_list

#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed', default=0, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-N', '--no_force', help='更新後不要強制寫入檢查點', default=False, action='store_true', dest='no_force_checkpoints')
parser.add_option('-F', '--no_final', help='不要顯示檔案系統的最終狀態', default=False, action='store_true', dest='no_final')
parser.add_option('-D', '--use_disk_cr', help='使用磁碟上（可能是舊版）的檢查點區域', default=False, action='store_true', dest='use_disk_cr')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true', default=False, dest='solve')
parser.add_option('-o', '--show_operations', help='在操作發生時把它印出來', action='store_true', default=False, dest='show_operations')
parser.add_option('-i', '--show_intermediate', help='在狀態改變時把它印出來', action='store_true', default=False, dest='show_intermediate')
parser.add_option('-e', '--show_return_codes', help='顯示錯誤／回傳碼', action='store_true', default=False, dest='show_return_codes')
parser.add_option('-v', '--show_live_paths', help='顯示存活的路徑', action='store_true', default=False, dest='show_live_paths')
parser.add_option('-n', '--num_commands', help='產生 N 個隨機指令', action='store', default=3, dest='num_commands')
parser.add_option('-p', '--percentages', help='各操作發生的機率百分比：createfile,writefile,createdir,rmfile,linkfile,sync（例如 c30,w30,d10,r20,l10,s0）', action='store', default='c30,w30,d10,r20,l10,s0', dest='percentages')
parser.add_option('-a', '--allocation_policy', help='inode 配置策略："r" 代表隨機（random），"s" 代表循序（sequential）', action='store', default='s', dest='inode_policy')
parser.add_option('-L', '--command_list', default = '', action='store', type='str', dest='command_list', help='指令清單，格式為："cmd1,arg1,...,argN:cmd2,arg1,...,argN:..."，其中 cmd 可以是：c:建立檔案、d:建立目錄、r:刪除、w:寫入、l:連結、s:同步；各指令格式為 c,filepath d,dirpath r,filepath w,filepath,offset,numblks l,srcpath,dstpath s')

(options, args) = parser.parse_args()

random.seed(options.seed)

command_list = options.command_list
num_commands = int(options.num_commands)
percents = process_percentages(options.percentages)

if options.inode_policy == 's':
    inode_policy = ALLOCATE_SEQUENTIAL
elif options.inode_policy == 'r':
    inode_policy = ALLOCATE_RANDOM
else:
    print('不合法的配置策略', options.inode_policy)
    exit(1)

# 大部分的工作都在這裡完成
L = LFS(use_disk_cr=options.use_disk_cr,
        no_force_checkpoints=options.no_force_checkpoints,
        inode_policy=inode_policy,
        solve=options.solve)

# 要顯示什麼
print_operation = options.show_operations
print_intermediate = options.show_intermediate

# 產生一些隨機指令
if command_list == '':
    if num_commands < 0:
        print('num_commands 必須大於零', num_commands)
        exit(1)
    command_list = make_command_list(num_commands, percents)


print('')
print('檔案系統的初始內容：')
L.dump(True)
L.dump_last = 4 # 有點醜……但為了讓中間過程的 dump 正確，需要這樣做
print('')

#
# 這個版本讓你可以控制每一個指令
#
files_that_exist = []
dirs_that_exist = []

if command_list != '':
    commands = command_list.split(':')
    for i in range(len(commands)):
        command_and_args = commands[i].split(',')
        if command_and_args[0] == 'c':
            assert(len(command_and_args) == 2)
            if print_operation:
                print('建立檔案', command_and_args[1], end=' ')
            rc = L.file_create(command_and_args[1])
            if rc == 0:
                files_that_exist.append(command_and_args[1])
        elif command_and_args[0] == 'd':
            assert(len(command_and_args) == 2)
            if print_operation:
                print('建立目錄', command_and_args[1], end=' ')
            rc = L.dir_create(command_and_args[1])
            if rc == 0:
                dirs_that_exist.append(command_and_args[1])
        elif command_and_args[0] == 'r':
            assert(len(command_and_args) == 2)
            if print_operation:
                print('刪除檔案', command_and_args[1], end=' ')
            rc = L.file_delete(command_and_args[1])
            if rc == 0:
                if command_and_args[1] in files_that_exist:
                    files_that_exist.remove(command_and_args[1])
                else:
                    print('警告：找不到檔案', command_and_args[1])
        elif command_and_args[0] == 'l':
            assert(len(command_and_args) == 3)
            if print_operation:
                print('連結檔案 ', command_and_args[1], command_and_args[2], end=' ')
            rc = L.file_link(command_and_args[1], command_and_args[2])
            if rc == 0:
                files_that_exist.append(command_and_args[2])
        elif command_and_args[0] == 'w':
            assert(len(command_and_args) == 4)
            if print_operation:
                print('寫入檔案  %s offset=%d size=%d' % (command_and_args[1], int(command_and_args[2]), int(command_and_args[3])), end=' ')
            rc = L.file_write(command_and_args[1], int(command_and_args[2]), int(command_and_args[3]))
        elif command_and_args[0] == 's':
            if print_operation:
                print('同步', end=' ')
            rc = L.sync()
        else:
            print('無法辨識的指令，略過 [%s]' % command_and_args[0])

        if not print_operation:
            print('指令？', end=' ')

        if print_intermediate:
            print('')
            print('')
            if command_and_args[0] == 's':
                L.dump_partial(False, True)
            else:
                L.dump_partial(False, False)
            print('')

        if options.show_return_codes:
            print('->', rc)
            L.error_dump()
        else:
            print('')

        #if not print_intermediate:
        #    print('\n記錄、檢查點區域有什麼變化？')
        #    print('')


if not options.no_final:
    print('')
    print('檔案系統的最終內容：')
    L.dump(False)
    print('')
    if options.show_live_paths:
        print('存活的目錄： ', dirs_that_exist)
        print('存活的檔案： ', files_that_exist)
        print('')
else:
    print('')
