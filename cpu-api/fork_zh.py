#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# 從像這樣的一連串事件
# a forks b
# a forks c
# a forks d
# b forks e
# b forks f
# d forks g

# 轉換成一棵行程樹（process tree）
#a --- b --- e
#   |     |
#   |     |- f
#   |- c
#   |
#   |- d --- g


from __future__ import print_function
import random
import string
from optparse import OptionParser

#
# 讓 Python2 與 Python3 的隨機數行為一致
#
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

#
# Forker 這個類別負責做所有的事情
#
class Forker:
    def __init__(self, fork_percentage, actions, action_list, show_tree, just_final,
                 leaf_only, local_reparent, print_style, solve):
        self.fork_percentage = fork_percentage
        self.max_actions = actions
        self.action_list = action_list
        self.show_tree = show_tree
        self.just_final = just_final
        self.leaf_only = leaf_only
        self.local_reparent = local_reparent
        self.print_style = print_style
        self.solve = solve

        # 根行程（root process）永遠是這個
        self.root_name = 'a'

        # 行程清單：目前所有存活行程的名稱
        self.process_list = [self.root_name]

        # 記錄每個行程的子行程
        self.children = {}
        self.children[self.root_name] = []

        # 也記錄每個行程的父行程
        self.parents = {}

        # 這是用來產生好看的行程名稱……
        self.name_length = 1
        self.base_names = string.ascii_lowercase + string.ascii_uppercase
        self.curr_names = self.base_names
        self.curr_index = 1

        return

    def grow_names(self):
        new_names = []
        for b1 in self.curr_names:
            for b2 in self.base_names:
                new_names.append(b1 + b2)
        self.curr_names = new_names
        self.curr_index = 0
        return

    def get_name(self):
        if self.curr_index == len(self.curr_names):
            self.grow_names()

        name = self.curr_names[self.curr_index]
        self.curr_index += 1
        return name

    def walk(self, p, level, pmask, is_last):
        print('                               ', end='')
        if self.print_style == 'basic':
            for i in range(level):
                print('   ', end='')
            print('%2s' % p)
            for child in self.children[p]:
                self.walk(child, level + 1, {}, False)
            return
        elif self.print_style == 'line1':
            chars = ('|', '-', '+', '|')
        elif self.print_style == 'line2':
            chars = ('|', '_', '|', '|')
        elif self.print_style == 'fancy':
            # 這些字元借用自 'treelib'，一個好玩的樹狀列印套件
            # https://github.com/caesar0301/treelib
            # chars = ('│', '─', '├', '└')
            chars = (u'│', u'─', u'├', u'└')
        else:
            print('不合法的印列風格 %s' % self.print_style)
            exit(1)

        # 印出節點之前先印一些東西
        if level > 0:
            # 主要的印列邏輯
            for i in range(level-1):
                if pmask[i]:
                    # '|  '
                    print('%s   ' % chars[0], end='')
                else:
                    print('    ', end='')
            if pmask[level-1]:
                # '|__'
                if is_last:
                    print('%s%s%s ' % (chars[3], chars[1], chars[1]), end='')
                else:
                    print('%s%s%s ' % (chars[2], chars[1], chars[1]), end='')
            else:
                # '___'
                print(' %s%s%s ' % (chars[1], chars[1], chars[1]), end='')

        # 印出節點本身
        print('%s' % p)

        # 復原父層的垂直線
        if is_last:
            pmask[level-1] = False

        # 遞迴處理子行程
        pmask[level] = True
        for child in self.children[p][:-1]:
            self.walk(child, level + 1, pmask, False)
        for child in self.children[p][-1:]:
            self.walk(child, level + 1, pmask, True)
        return

    def print_tree(self):
        return self.walk(self.root_name, 0, {}, False)

    def do_fork(self, p, c):
        self.process_list.append(c)
        self.children[c] = []
        self.children[p].append(c)
        self.parents[c] = p
        return '%s fork 出 %s' % (p, c)

    def collect_children(self, p):
        if self.children[p] == []:
            return [p]
        else:
            L = [p]
            for c in self.children[p]:
                L += self.collect_children(c)
            return L

    def do_exit(self, p):
        # 把這個行程從行程清單中移除
        if p == self.root_name:
            print('根行程（root process）：無法結束執行')
            exit(1)
        exit_parent = self.parents[p]
        self.process_list.remove(p)

        # 對每個孤兒行程，把它的父行程設為結束的行程原本的父行程，或設為 root
        if self.local_reparent:
            for orphan in self.children[p]:
                self.parents[orphan] = exit_parent
                self.children[exit_parent].append(orphan)
        else:
            # 應該把「所有」子孫行程都改設為 ROOT 的子行程
            descendents = self.collect_children(p)
            descendents.remove(p)
            for d in descendents:
                self.children[d] = []
                self.parents[d] = self.root_name
                self.children[self.root_name].append(d)

        # 從父行程的子行程清單中移除這一筆
        self.children[exit_parent].remove(p)
        self.children[p] = -1 # 之後不應該再被用到
        self.parents[p] = -1  # 之後不應該再被用到

        # 從 children 中移除這個行程的紀錄
        return '%s 結束執行' % p

    def bad_action(self, action):
        print('不合法的動作（%s），格式必須是 X+Y 或 X-，其中 X 和 Y 是行程名稱' % action)
        exit(1)
        return

    def check_legal(self, action):
        if '+' in action:
            tmp = action.split('+')
            if len(tmp) != 2:
                self.bad_action(action)
            return [tmp[0], tmp[1]]
        elif '-' in action:
            tmp = action.split('-')
            if len(tmp) != 2:
                self.bad_action(action)
            return [tmp[0]]
        else:
            self.bad_action(action)
        return

    def run(self):
        print('                           行程樹（Process Tree）：')
        self.print_tree()
        print('')

        if self.action_list != '':
            # 使用指定的動作清單
            action_list = self.action_list.split(',')
        else:
            action_list = []
            actions = 0
            temp_process_list = [self.root_name]
            level_list = {}
            level_list[self.root_name] = 1

            # 這段寫得有點醜，重複做了不少事
            while actions < self.max_actions:
                if random.random() < self.fork_percentage:
                    # FORK：隨機選一個父行程，幫它加一個子行程
                    fork_choice = random_choice(temp_process_list)
                    new_child = self.get_name()
                    action_list.append('%s+%s' % (fork_choice, new_child))
                    temp_process_list.append(new_child)
                else:
                    # EXIT：隨機選一個子行程，把它移除
                    #        例外：不能殺掉 root 行程，抱歉
                    exit_choice = random_choice(temp_process_list)
                    if exit_choice == self.root_name:
                        continue
                    temp_process_list.remove(exit_choice)
                    action_list.append('%s-' % exit_choice)
                actions += 1

        for a in action_list:
            tmp = self.check_legal(a)
            if len(tmp) == 2:
                fork_choice, new_child = tmp[0], tmp[1]
                if fork_choice not in self.process_list:
                    self.bad_action(a)
                action = self.do_fork(fork_choice, new_child)
            else:
                exit_choice = tmp[0]
                if exit_choice not in self.process_list:
                    self.bad_action(a)
                if self.leaf_only and len(self.children[exit_choice]) > 0:
                    action = '%s 結束執行失敗（仍有子行程）' % exit_choice
                else:
                    action = self.do_exit(exit_choice)

            # 如果執行到這裡，代表我們真的做了一個動作……
            if self.show_tree:
                # 顯示行程樹（讓你猜動作）
                if self.solve:
                    print('動作：', action)
                else:
                    print('動作？')
                # print('行程樹：')
                if not self.just_final:
                    self.print_tree()
            else:
                # 顯示動作（讓你猜行程樹）
                print('動作：', action)
                if not self.just_final:
                    if self.solve:
                        # print('行程樹：')
                        self.print_tree()
                    else:
                        print('行程樹？')

        if self.just_final:
            if self.show_tree:
                print('\n                        最終行程樹：')
                self.print_tree()
                print('')
            else:
                if self.solve:
                    print('\n                        最終行程樹：')
                    self.print_tree()
                    print('')
                else:
                    print('\n                        最終行程樹？\n')

        return


#
# 主程式
#

parser = OptionParser()
parser.add_option('-s', '--seed', default=-1, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-f', '--forks', default=0.7, help='動作中屬於 fork（而非 exit）的比例', action='store', type='float', dest='fork_percentage')
parser.add_option('-A', '--action_list', default='', help='指定動作清單，而非隨機產生（格式：a+b,b+c,b- 代表 a fork 出 b、b fork 出 c、b 結束執行）', action='store', type='string', dest='action_list')
parser.add_option('-a', '--actions', default=5, help='要執行的 fork/exit 動作數量', action='store', type='int', dest='actions')
parser.add_option('-t', '--show_tree', help='顯示行程樹（而非動作）', action='store_true', default=False, dest='show_tree')
parser.add_option('-P', '--print_style', help='行程樹的印列風格（basic、line1、line2、fancy）', action='store', type='string', default='fancy', dest='print_style')
parser.add_option('-F', '--final_only', help='只顯示最終狀態', action='store_true', default=False, dest='just_final')
parser.add_option('-L', '--leaf_only', help='只有葉節點行程可以結束執行', action='store_true', default=False, dest='leaf_only')
parser.add_option('-R', '--local_reparent', help='改設為本地父行程（local parent）的子行程', action='store_true', default=False, dest='local_reparent')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true', default=False, dest='solve')

(options, args) = parser.parse_args()

if options.seed != -1:
    random_seed(options.seed)

if options.fork_percentage <= 0.001:
    print('fork_percentage 必須大於 0.001')
    exit(1)

print('')
print('參數 seed', options.seed)
print('參數 fork_percentage', options.fork_percentage)
print('參數 actions', options.actions)
print('參數 action_list', options.action_list)
print('參數 show_tree', options.show_tree)
print('參數 just_final', options.just_final)
print('參數 leaf_only', options.leaf_only)
print('參數 local_reparent', options.local_reparent)
print('參數 print_style', options.print_style)
print('參數 solve', options.solve)
print('')

f = Forker(options.fork_percentage, options.actions, options.action_list, options.show_tree, options.just_final, options.leaf_only, options.local_reparent, options.print_style, options.solve)
f.run()

