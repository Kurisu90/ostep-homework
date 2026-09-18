#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import print_function
import random
import re
import string
import os
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
# 這些是給 .c 檔案用的樣板程式碼，「可讀版」與「可執行版」都會用到
# （NOTE：以下透過 fd.write() 產生的是「C 原始碼」本身的內容，因此
#  仍然保持英文，這是要交給 gcc 編譯執行的程式，不屬於本工具的
#  介面文字，故不翻譯，以維持產生出來的 C 程式碼與範例一致）
#
class Boilerplate:
    def __init__(self, fd):
        self.fd = fd
        return

    def init(self):
        self.fd.write('#include <assert.h>\n')
        self.fd.write('#include <stdio.h>\n')
        self.fd.write('#include <stdlib.h>\n')
        self.fd.write('#include <string.h>\n')
        self.fd.write('#include <sys/time.h>\n')
        self.fd.write('#include <sys/wait.h>\n')
        self.fd.write('#include <unistd.h>\n')
        self.fd.write('\n')
        self.fd.write('void wait_or_die() {\n')
        self.fd.write('    int rc = wait(NULL);\n')
        self.fd.write('    assert(rc > 0);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('int fork_or_die() {\n')
        self.fd.write('    int rc = fork();\n')
        self.fd.write('    assert(rc >= 0);\n')
        self.fd.write('    return rc;\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        return

    def init_runnable(self):
        self.init()
        self.fd.write('#define Time_GetSeconds() ({ struct timeval t; int rc = gettimeofday(&t, NULL); assert(rc == 0); (double) t.tv_sec + (double) t.tv_usec/1e6; })\n')
        self.fd.write('\n')
        self.fd.write('double t_start;\n')
        self.fd.write('\n')
        self.fd.write('struct pid_map {\n')
        self.fd.write('    int pid;\n')
        self.fd.write('    char name[10];\n')
        self.fd.write('    struct pid_map *next;\n')
        self.fd.write('};\n')
        self.fd.write('\n')
        self.fd.write('struct pid_map *head = NULL;\n')
        self.fd.write('\n')
        self.fd.write('void Space(char c) {\n')
        self.fd.write('    int i;\n')
        self.fd.write('    for (i = 0; i < 5 * (c - \'a\'); i++) {\n')
        self.fd.write('        printf(\" \"); \n')
        self.fd.write('    }\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('char *Lookup(int pid) {\n')
        self.fd.write('    struct pid_map *curr = head;\n')
        self.fd.write('    while (curr) {\n')
        self.fd.write('        if (curr->pid == pid) \n')
        self.fd.write('	           return(curr->name);\n')
        self.fd.write('	       curr = curr->next;\n')
        self.fd.write('    }\n')
        self.fd.write('    return NULL;\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void Record(int pid, char *m) {\n')
        self.fd.write('    struct pid_map *n = malloc(sizeof(struct pid_map));\n')
        self.fd.write('    assert(n);\n')
        self.fd.write('    n->pid = pid;\n')
        self.fd.write('    strcpy(n->name, m);\n')
        self.fd.write('    n->next = head;\n')
        self.fd.write('    head = n;\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void Wait(char *m) {\n')
        self.fd.write('    int rc = wait(NULL);\n')
        self.fd.write('    assert(rc > 0);\n')
        self.fd.write('    double t = Time_GetSeconds() - t_start;\n')
        self.fd.write('    printf(\"%3d \", (int)t);\n')
        self.fd.write('    Space(m[0]);\n')
        self.fd.write('    char *n = Lookup(rc);\n')
        self.fd.write('    assert(n != NULL);\n')
        self.fd.write('    printf(\"%s<-%s\\n\", m, n);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void Sleep(int s, char *m) {\n')
        self.fd.write('    sleep(s);\n')
        self.fd.write('    double t = Time_GetSeconds() - t_start;\n')
        self.fd.write('    printf(\"%3d %s\\n\", (int)t, m);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void Fork(char *p, char *c) {\n')
        self.fd.write('    double t = Time_GetSeconds() - t_start;\n')
        self.fd.write('    printf(\"%3d \", (int)t);\n')
        self.fd.write('    Space(p[0]);\n')
        self.fd.write('    printf(\"%s->%s\\n\", p, c);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void __Begin(char *m) {\n')
        self.fd.write('    double t = Time_GetSeconds() - t_start;\n')
        self.fd.write('    printf(\"%3d \", (int)t);\n')
        self.fd.write('    Space(m[0]);\n')
        self.fd.write('    printf(\"%s+\\n\", m);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('void __End(char *m) {\n')
        self.fd.write('    double t = Time_GetSeconds() - t_start;\n')
        self.fd.write('    printf(\"%3d \", (int)t);\n')
        self.fd.write('    Space(m[0]);\n')
        self.fd.write('    printf(\"%s-\\n\", m);\n')
        self.fd.write('}\n')
        self.fd.write('\n')
        self.fd.write('#define Begin(m) { __Begin(m); }\n')
        self.fd.write('#define End(m)   { __End(m); exit(0); }\n')
        self.fd.write('\n')
        return

    def fini(self):
        self.fd.write('    return 0;\n')
        self.fd.write('}\n\n')
        return

    def main(self):
        self.fd.write('int main(int argc, char *argv[]) {\n')
        return

    def main_runnable(self):
        self.main()
        self.fd.write('    int rc;\n')
        self.fd.write('    t_start = Time_GetSeconds();\n')
        return

    def __fini__(self):
        close(self.fd)
        return


class CodeGeneratorReadable:
    def __init__(self, out_file_base, actions):
        self.out_file = out_file_base + '.c'
        self.actions = actions

        self.tab_level = 1
        self.fd = open(self.out_file, 'w')
        self.boiler = Boilerplate(self.fd)
        return

    def __fini__(self):
        self.fd.close()
        return

    def tab(self):
        for i in range(self.tab_level):
            self.fd.write('    ')
        return

    def add_thread(self, thread_id):
        self.tab()
        self.fd.write('// process %s\n' % thread_id)
        return

    def add_fork(self):
        self.tab()
        self.fd.write('if (fork_or_die() == 0) {\n')
        self.tab_level += 1
        return

    def add_sleep(self, sleep_time):
        self.tab()
        self.fd.write('sleep(%s);\n' % sleep_time)
        return

    def add_exit(self):
        self.tab()
        self.fd.write('exit(0);\n')
        self.tab_level -= 1
        self.tab()
        self.fd.write('}\n')
        return

    def add_wait(self):
        self.tab()
        self.fd.write('wait_or_die();\n')
        return

    def generate(self):
        self.boiler.init()
        self.boiler.main()
        self.add_thread('a')
        for a in actions:
            tmp = a.split(' ')
            if tmp[0] == 'fork':
                # fork thread_id sleep_time
                assert(len(tmp) == 3)
                self.add_fork()
                self.add_sleep(tmp[2])
                self.add_thread(tmp[1])
            elif tmp[0] == 'exit':
                assert(len(tmp) == 1)
                self.add_exit()
            elif tmp[0] == 'wait':
                assert(len(tmp) == 1)
                self.add_wait()
            else:
                print('不合法的指令')
                exit(1)
                return
        self.boiler.fini()
        self.__fini__()
        return

class CodeGeneratorRunnable:
    def __init__(self, out_file_base, actions):
        self.out_file = out_file_base + '.c'
        self.actions = actions

        self.tab_level = 1
        self.fd = open(self.out_file, 'w')
        self.boiler = Boilerplate(self.fd)

        self.parent_list = []
        self.waiting_for = {}

        self.used_times = {}
        return

    def __fini__(self):
        self.fd.close()
        return

    def tab(self):
        for i in range(self.tab_level):
            self.fd.write('    ')
        return

    def add_thread(self, thread_id):
        self.tab()
        self.waiting_for[thread_id] = []
        self.fd.write('Begin(\"%s\");\n' % thread_id)
        self.curr_thread = thread_id
        return

    def add_fork(self, child_thread, sleep_time):
        self.parent_list.append(self.curr_thread)
        self.waiting_for[self.curr_thread].append(child_thread)
        # print('add fork for %s' % self.curr_thread, self.waiting_for[self.curr_thread])
        self.tab()
        self.fd.write('Fork(\"%s\", \"%s\");\n' % (self.curr_thread, child_thread))
        self.tab()
        self.fd.write('if ((rc = fork_or_die()) == 0) {\n')
        self.tab_level += 1
        return

    def add_sleep(self, sleep_time):
        self.tab()
        self.fd.write('sleep(%s);\n' % sleep_time)
        return

    def add_exit(self):
        # 必須先完成所有該做的 wait（！）
        if len(self.waiting_for[self.curr_thread]) > 0:
            print('錯誤：執行緒必須先完成所有必要的 wait，才能結束執行')
            print('  執行緒 %s 還有尚未處理的子執行緒：' % self.curr_thread, self.waiting_for[self.curr_thread])
            exit(1)
        self.tab()
        self.fd.write('End(\"%s\");\n' % self.curr_thread)
        self.tab_level -= 1
        self.tab()
        self.fd.write('}\n')
        self.tab()
        self.fd.write('Record(rc, \"%s\");\n' % self.curr_thread)
        self.curr_thread = self.parent_list.pop()
        return

    def add_wait(self):
        self.tab()
        # 要怎麼知道該等誰？
        waiting_for = self.waiting_for[self.curr_thread].pop(0)
        # print('%s waited for %s' % (self.curr_thread, waiting_for[1]))
        self.fd.write('Wait(\"%s\");\n' % self.curr_thread);
        return

    def generate(self):
        self.boiler.init_runnable()
        self.boiler.main_runnable()
        self.add_thread('a')
        for a in actions:
            tmp = a.split(' ')
            if tmp[0] == 'fork':
                # fork thread_id sleep_time
                assert(len(tmp) == 3)
                self.add_fork(tmp[1], tmp[2])
                self.add_sleep(tmp[2])
                self.add_thread(tmp[1])
            elif tmp[0] == 'exit':
                assert(len(tmp) == 1)
                self.add_exit()
            elif tmp[0] == 'wait':
                assert(len(tmp) == 1)
                self.add_wait()
            else:
                print('不合法的指令')
                exit(1)
                return
        self.boiler.fini()
        self.__fini__()
        return

#
# 產生給 C 程式碼產生器使用的輸入資料
#
class ProgramGenerator:
    def __init__(self, num_actions, max_sleep_time):
        self.num_actions = num_actions
        self.max_sleep_time = max_sleep_time

        self.names = string.ascii_lowercase + string.ascii_uppercase
        self.name_index = 1

        self.used_times = {}
        self.used_times[0] = True

        return

    def get_next_name(self):
        if self.name_index == len(self.names):
            print('program generator：名稱用完了（行程數量太多）')
            exit(1)
        n = self.names[self.name_index]
        self.name_index += 1
        return n

    def get_sleep_time(self):
        return random_randint(1, self.max_sleep_time)

    def add_fork_begin(self):
        name = self.get_next_name()
        sleep_time = self.get_sleep_time()
        self.actions.append('fork %s %d' % (name, sleep_time))
        self.need_wait[self.fork_level] += 1
        self.fork_level += 1
        self.need_wait[self.fork_level] = 0
        return

    def add_fork_end(self):
        self.actions.append('exit')
        self.fork_level -= 1
        return

    def add_wait(self):
        self.actions.append('wait')
        self.need_wait[self.fork_level] -= 1
        return

    def clean_up(self):
        n = self.need_wait[self.fork_level]
        for i in range(n):
            self.actions.append('wait')
        if self.fork_level > 0:
            self.actions.append('exit')
        return n + 1

    def generate(self, fork_chance, wait_chance, exit_chance):
        self.actions = []
        self.fork_level = 0
        self.need_wait = {}
        self.need_wait[self.fork_level] = 0

        total_chance = fork_chance + wait_chance + exit_chance
        if total_chance != 100:
            print('fork/wait/exit 的機率總和必須是 100，但目前總和是', total_chance)
            exit(1)

        self.fork_chance = float(fork_chance) / 100.0
        self.wait_chance = float(fork_chance + wait_chance) / 100.0
        # 剩下的就是 'exit_chance'

        n = 0
        while n < self.num_actions:
            r = random.random()
            if r < self.fork_chance:
                # print('fork')
                self.add_fork_begin()
                n += 1
            elif r < self.wait_chance:
                # print('wait?')
                if self.need_wait[self.fork_level] > 0:
                    # print('wait')
                    self.add_wait()
                    n += 1
            else:
                # print('exit')
                if self.fork_level > 0:
                    # 必須先完成現在所需的所有 wait
                    # self.add_fork_end()
                    n += self.clean_up()
                    self.fork_level -= 1
            # diagnostics
            # print('level', self.fork_level, 'actions', self.actions, 'nw', self.need_wait[self.fork_level])

        # 收尾：
        while self.fork_level >= 0:
            self.clean_up()
            self.fork_level -= 1

        return self.actions

#
# 把使用者輸入的內容解析成 C 程式碼產生器能理解的格式
#
class Parser:
    def __init__(self, program):
        self.program = program
        self.orig_program = program

    def abort_if(self, condition, message):
        if condition:
            print('不合法的程式：[%s]' % self.orig_program)
            print(message)
            exit(1)
        return

    def parse(self):
        # 移除逗號前後的空白
        program = self.program
        p = re.compile(r'\s*,\s*', re.VERBOSE)
        m = p.search(program)
        while m:
            program = program.replace(m.group(), ',', 1)
            m = p.search(program, m.end())

        # 在大括號前後加上空白
        program = program.replace('{', ' { ')
        program = program.replace('}', ' } ')

        # 接著找出所有指令
        # 直接用空白切開字串，解析起來很容易
        tokens = program.split()
        action_list = []  # 把產生器能理解的動作加到這裡
        curr = 0          # 目前處理到 token 清單的哪個位置
        brace_count = 0   # 確保大括號數量成對
        wait_count = {}   # 針對每一層 fork 巢狀層級，記錄是否加上了足夠的 wait
        fork_level = 0    # 記錄目前 fork 的巢狀層級
        wait_count[fork_level] = 0
        while curr < len(tokens):
            if tokens[curr] == '':
                curr += 1
                continue
            elif tokens[curr] == 'fork':
                wait_count[fork_level] += 1
                fork_level += 1
                wait_count[fork_level] = 0
                self.abort_if(len(tokens) < curr + 2, '格式錯誤的程式：fork 之後需要接「行程名稱,睡眠時間」，再接一個 {描述該子行程行為的內容}')
                args = tokens[curr + 1]
                args_split = args.split(',')
                self.abort_if(len(args_split) != 2, 'fork 的參數不足（需要行程名稱與睡眠時間）')
                lbrace = tokens[curr + 2]
                self.abort_if(lbrace != '{', 'fork 後面必須接著 {}')
                action_list.append('fork %s %s' % (args_split[0], args_split[1]))
                # 跳過參數與左括號
                curr += 2
                brace_count += 1
            elif tokens[curr] == '}':
                self.abort_if(fork_level == 0, '多出來的右括號')
                action_list.append("exit")
                self.abort_if(wait_count[fork_level] != 0, 'wait 的數量與 fork 的數量不相符')
                brace_count -= 1
                fork_level -= 1
            elif tokens[curr] == 'wait':
                wait_count[fork_level] -= 1
                action_list.append("wait")
            else:
                self.abort_if(True, '無法辨識的 token %s' % tokens[curr])
            # 持續處理直到所有 token 都處理完
            curr += 1

        # 最後再做一些檢查
        self.abort_if(wait_count[0] != 0, 'wait 的數量與 fork 的數量不相符')
        self.abort_if(brace_count != 0, '大括號數量不成對')

        return action_list

#
# 主程式
#

parser = OptionParser()
parser.add_option('-s', '--seed', default=-1, help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-r', '--readable', default='read', help='要讀取（顯示）的檔案名稱（例如 "read"，會產生 read.c）', action='store', type='string', dest='readable')
parser.add_option('-R', '--runnable', default='run', help='要編譯執行的檔案名稱（例如 "run"，會產生 run.c）', action='store', type='string', dest='runnable')
parser.add_option('-n', '--num_actions', default=10, help='動作數量', action='store', type='int', dest='num_actions')
parser.add_option('-f', '--fork_chance', default=30, help='程式呼叫 fork 的機率', action='store', type='int', dest='fork_chance')
parser.add_option('-w', '--wait_chance', default=40, help='程式呼叫 wait 的機率', action='store', type='int', dest='wait_chance')
parser.add_option('-e', '--exit_chance', default=30, help='程式呼叫 exit 的機率', action='store', type='int', dest='exit_chance')
parser.add_option('-S', '--sleep_time', default=10, help='一個行程的最長睡眠時間', action='store', type='int', dest='max_sleep_time')
parser.add_option('-A', '--action_list', default='none', help='指定動作清單，而非隨機產生（簡單範例："fork b,10 {} wait" 代表執行一個行程（稱為 a），它先 fork 出行程 b，b 執行 10 秒，接著 a 等待 b 結束；詳見 README）', action='store', type='string', dest='action_list')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true', default=False, dest='solve')

(options, args) = parser.parse_args()

if options.seed != -1:
    random_seed(options.seed)

if options.max_sleep_time < 1:
    print('最長睡眠時間必須 >= 1')
    exit(1)

if options.fork_chance < 1 or options.fork_chance > 99:
    print('fork 的機率必須介於 1 到 99 之間')
    exit(1)

if options.wait_chance < 1 or options.wait_chance > 99:
    print('wait 的機率必須介於 1 到 99 之間')
    exit(1)

if options.exit_chance < 1 or options.exit_chance > 99:
    print('exit 的機率必須介於 1 到 99 之間')
    exit(1)

if options.action_list == 'none':
    pg = ProgramGenerator(options.num_actions, options.max_sleep_time)
    actions = pg.generate(options.fork_chance, options.wait_chance, options.exit_chance)
else:
    action_list = options.action_list
    p = Parser(action_list)
    actions = p.parse()

# print(actions)

cg_read = CodeGeneratorReadable(options.readable, actions)
cg_read.generate()

cg_run = CodeGeneratorRunnable(options.runnable, actions)
cg_run.generate()

# 接下來，要嘛列出程式碼，要嘛直接執行它
if options.solve:
    os.system('gcc -o %s %s.c -Wall' % (options.runnable, options.runnable))
    os.system('./%s' % options.runnable)
else:
    # print('cat %s.c' % options.readable)
    stream = os.popen('cat %s.c' % options.readable)
    output = stream.read()
    print(output)
    # rc = os.system('cat %s.c' % options.readable)
    # print(rc)



