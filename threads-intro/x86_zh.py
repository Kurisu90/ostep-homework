#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import sys
import time
import random
from optparse import OptionParser

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

def time_clock():
    try:
        rc = time_clock()
    except:
        rc = time.process_time()
    return rc

#
# 輔助函式
#
def dospace(howmuch):
    for i in range(howmuch):
        print('%24s' % ' ', end=' ')

# 用來取代 assert 的輔助函式
def zassert(cond, str):
    if cond == False:
        print('中止(ABORT)::', str)
        exit(1)
    return

class cpu:
    #
    # 初始化：要用多少記憶體？
    #
    def __init__(self, memory, memtrace, regtrace, cctrace, compute, verbose):
        #
        # 常數
        #

        # 條件碼
        self.COND_GT        = 0
        self.COND_GTE       = 1
        self.COND_LT        = 2
        self.COND_LTE       = 3
        self.COND_EQ        = 4
        self.COND_NEQ       = 5

        # 系統中的暫存器
        self.REG_ZERO       = 0
        self.REG_AX         = 1
        self.REG_BX         = 2
        self.REG_CX         = 3
        self.REG_DX         = 4
        self.REG_SP         = 5
        self.REG_BP         = 6

        # 系統記憶體大小：以 KB 為單位
        self.max_memory     = memory * 1024

        # 要追蹤哪些記憶體位址與暫存器？
        self.memtrace       = memtrace
        self.regtrace       = regtrace
        self.cctrace        = cctrace
        self.compute        = compute
        self.verbose        = verbose

        self.PC             = 0
        self.registers      = {}
        self.conditions     = {}
        self.labels         = {}
        self.vars           = {}
        self.memory         = {}
        self.pmemory        = {}  # 用來存放記憶體內容（指令）的可印出版本

        self.condlist       = [self.COND_GTE, self.COND_GT, self.COND_LTE, self.COND_LT, self.COND_NEQ, self.COND_EQ]
        self.regnums        = [self.REG_ZERO, self.REG_AX,  self.REG_BX,   self.REG_CX,  self.REG_DX,   self.REG_SP,  self.REG_BP]

        self.regnames         = {}
        self.regnames['zero'] = self.REG_ZERO # 隱藏的、恆為 0 的暫存器
        self.regnames['ax']   = self.REG_AX
        self.regnames['bx']   = self.REG_BX
        self.regnames['cx']   = self.REG_CX
        self.regnames['dx']   = self.REG_DX
        self.regnames['sp']   = self.REG_SP
        self.regnames['bp']   = self.REG_BP

        tmplist = []
        for r in self.regtrace:
            zassert(r in self.regnames, '暫存器 %s 不存在，無法追蹤' % r)
            tmplist.append(self.regnames[r])
        self.regtrace = tmplist

        self.init_memory()
        self.init_registers()
        self.init_condition_codes()

    #
    # 開始執行機器之前
    #
    def init_condition_codes(self):
        for c in self.condlist:
            self.conditions[c] = False

    def init_memory(self):
        for i in range(self.max_memory):
            self.memory[i] = 0

    def init_registers(self):
        for i in self.regnums:
            self.registers[i] = 0

    def dump_memory(self):
        print('記憶體傾印')
        for i in range(self.max_memory):
            if i not in self.pmemory and i in self.memory and self.memory[i] != 0:
                print('  m[%d]' % i, self.memory[i])

    #
    # 提供關於硬體的資訊
    #
    def get_regnum(self, name):
        assert(name in self.regnames)
        return self.regnames[name]

    def get_regname(self, num):
        assert(num in self.regnums)
        for rname in self.regnames:
            if self.regnames[rname] == num:
                return rname
        return ''
    
    def get_regnums(self):
        return self.regnums

    def get_condlist(self):
        return self.condlist

    def get_reg(self, reg):
        assert(reg in self.regnums)
        return self.registers[reg]

    def get_cond(self, cond):
        assert(cond in self.condlist)
        return self.conditions[cond]

    def get_pc(self):
        return self.PC
        
    def set_reg(self, reg, value):
        assert(reg in self.regnums)
        self.registers[reg] = value

    def set_cond(self, cond, value):
        assert(cond in self.condlist)
        self.conditions[cond] = value

    def set_pc(self, pc):
        self.PC = pc
        
    #
    # 指令
    #
    def halt(self):
        return -1

    def iyield(self):
        return -2

    def nop(self):
        return 0

    def rdump(self):
        print('暫存器(REGISTERS)::', end=' ')
        print('ax:', self.registers[self.REG_AX], end=' ')
        print('bx:', self.registers[self.REG_BX], end=' ')
        print('cx:', self.registers[self.REG_CX], end=' ')
        print('dx:', self.registers[self.REG_DX], end=' ')

    def mdump(self, index):
        print('m[%d] ' % index, self.memory[index])

    def move_i_to_r(self, src, dst):
        self.registers[dst] = src
        return 0

    # 記憶體：數值、暫存器、暫存器
    def move_i_to_m(self, src, value, reg1, reg2):
        tmp = value + self.registers[reg1] + self.registers[reg2]
        self.memory[tmp] = src
        return 0

    def move_m_to_r(self, value, reg1, reg2, dst):
        tmp = value + self.registers[reg1] + self.registers[reg2]
        # print('執行 mov', '值:', value, '暫存器1:', self.get_regname(reg1), self.registers[reg1], '暫存器2:', self.get_regname(reg2), self.registers[reg2], '目的:', self.get_regname(dst), '暫存位址', tmp, '目的暫存器內容', self.registers[dst], '記憶體內容', self.memory[tmp])
        self.registers[dst] = self.memory[tmp]

    def move_r_to_m(self, src, value, reg1, reg2):
        tmp = value + self.registers[reg1] + self.registers[reg2]
        self.memory[tmp] = self.registers[src]
        return 0

    def move_r_to_r(self, src, dst):
        self.registers[dst] = self.registers[src]
        return 0

    def add_i_to_r(self, src, dst):
        self.registers[dst] += src
        return 0

    def add_r_to_r(self, src, dst):
        self.registers[dst] += self.registers[src]
        return 0

    def sub_i_to_r(self, src, dst):
        self.registers[dst] -= src
        return 0

    def sub_r_to_r(self, src, dst):
        self.registers[dst] -= self.registers[src]
        return 0


    #
    # 用來支援鎖（LOCKS）的指令
    #
    def atomic_exchange(self, src, value, reg1, reg2):
        tmp                 = value + self.registers[reg1] + self.registers[reg2]
        old                 = self.memory[tmp]
        self.memory[tmp]    = self.registers[src]
        self.registers[src] = old
        return 0

    def fetchadd(self, src, value, reg1, reg2):
        tmp                 = value + self.registers[reg1] + self.registers[reg2]
        old                 = self.memory[tmp]
        self.memory[tmp]    = self.memory[tmp] + self.registers[src] 
        self.registers[src] = old

    #
    # 用來測試條件（TEST）
    #
    def test_all(self, src, dst):
        self.init_condition_codes()
        if dst > src:
            self.conditions[self.COND_GT]  = True
        if dst >= src:
            self.conditions[self.COND_GTE] = True
        if dst < src:
            self.conditions[self.COND_LT]  = True
        if dst <= src:
            self.conditions[self.COND_LTE] = True
        if dst == src:
            self.conditions[self.COND_EQ]  = True
        if dst != src:
            self.conditions[self.COND_NEQ] = True
        return 0

    def test_i_r(self, src, dst):
        self.init_condition_codes()
        return self.test_all(src, self.registers[dst])

    def test_r_i(self, src, dst):
        self.init_condition_codes()
        return self.test_all(self.registers[src], dst)

    def test_r_r(self, src, dst):
        self.init_condition_codes()
        return self.test_all(self.registers[src], self.registers[dst])

    #
    # 跳躍指令
    #
    def jump(self, targ):
        self.PC = targ  
        return 0
    
    def jump_notequal(self, targ):
        if self.conditions[self.COND_NEQ] == True:
            self.PC = targ
        return 0

    def jump_equal(self, targ):
        if self.conditions[self.COND_EQ] == True:
            self.PC = targ
        return 0

    def jump_lessthan(self, targ):
        if self.conditions[self.COND_LT] == True:
            self.PC = targ
        return 0

    def jump_lessthanorequal(self, targ):
        if self.conditions[self.COND_LTE] == True:
            self.PC = targ
        return 0

    def jump_greaterthan(self, targ):
        if self.conditions[self.COND_GT] == True:
            self.PC = targ
        return 0

    def jump_greaterthanorequal(self, targ):
        if self.conditions[self.COND_GTE] == True:
            self.PC = targ
        return 0

    #
    # 呼叫（CALL）與返回（RETURN）
    #
    def call(self, targ):
        self.registers[self.REG_SP] -= 4
        self.memory[self.registers[self.REG_SP]] = self.PC 
        self.PC = targ

    def ret(self):
        self.PC = self.memory[self.registers[self.REG_SP]]
        self.registers[self.REG_SP] += 4

    #
    # 堆疊（STACK）與相關操作
    #
    def push_r(self, reg):
        self.registers[self.REG_SP] -= 4
        self.memory[self.registers[self.REG_SP]] = self.registers[reg]
        return 0

    def push_m(self, value, reg1, reg2):
        # print('push_m', value, reg1, reg2)
        self.registers[self.REG_SP] -= 4
        tmp = value + self.registers[reg1] + self.registers[reg2]
        # 把位址推入堆疊，而不是記憶體本身的值
        self.memory[self.registers[self.REG_SP]] = tmp
        return 0

    def pop(self):
        self.registers[self.REG_SP] += 4

    def pop_r(self, dst):
        self.registers[dst] = self.registers[self.REG_SP]
        self.registers[self.REG_SP] += 4

    #
    # getarg 用的輔助函式
    #
    def register_translate(self, r):
        if r in self.regnames:
            return self.regnames[r]
        zassert(False, '暫存器 %s 不是合法的暫存器' % r)
        return

    #
    # 用來解析 mov（相當簡陋）及其他指令的輔助函式
    # 傳回值：(數值, 類型)
    # 其中類型可以是 (TYPE_REGISTER, TYPE_IMMEDIATE, TYPE_MEMORY)
    #
    # 格式
    #    %ax           - 暫存器
    #    $10           - 立即值
    #    10            - 直接定址的記憶體
    #    10(%ax)       - 記憶體 + 一個暫存器間接定址
    #    10(%ax,%bx)   - 記憶體 + 兩個暫存器間接定址
    #    10(%ax,%bx,4) - XXX（尚未處理）
    #
    def getarg(self, arg):
        tmp1 = arg.replace(',', '')
        tmp  = tmp1.replace(' \t', '')

        if tmp[0] == '$':
            zassert(len(tmp) == 2, '正確格式應為 $數字（而非 %s）' % tmp)
            value = tmp.split('$')[1]
            zassert(value.isdigit(), '數值 [%s] 必須是數字' % value)
            return int(value), 'TYPE_IMMEDIATE'
        elif tmp[0] == '%':
            register = tmp.split('%')[1]
            return self.register_translate(register), 'TYPE_REGISTER'
        elif tmp[0] == '(':
            register = tmp.split('(')[1].split(')')[0].split('%')[1]
            return '%d,%d,%d' % (0, self.register_translate(register), self.register_translate('zero')), 'TYPE_MEMORY'
        elif tmp[0] == '.':
            targ = tmp
            return targ, 'TYPE_LABEL'
        elif tmp[0].isalpha() and not tmp[0].isdigit():
            zassert(tmp in self.vars, '變數 %s 未經宣告' % tmp)
            # print('%d,%d,%d' % (self.vars[tmp], self.register_translate('zero'), self.register_translate('zero')), 'TYPE_MEMORY')
            return '%d,%d,%d' % (self.vars[tmp], self.register_translate('zero'), self.register_translate('zero')), 'TYPE_MEMORY'
        elif tmp[0].isdigit() or tmp[0] == '-':
            # 最一般的情況：number(reg,reg) 或 number(reg)
            # 目前先忽略常見的 x86 number(reg,reg,constant) 形式
            neg = 1
            if tmp[0] == '-':
                tmp = tmp[1:]
                neg = -1
            s = tmp.split('(')
            if len(s) == 1:
                value = neg * int(tmp)
                # print('%d,%d,%d' % (int(value), self.register_translate('zero'), self.register_translate('zero')), 'TYPE_MEMORY')
                return '%d,%d,%d' % (int(value), self.register_translate('zero'), self.register_translate('zero')), 'TYPE_MEMORY'
            elif len(s) == 2:
                value = neg * int(s[0])
                t = s[1].split(')')[0].split(',')
                if len(t) == 1:
                    register = t[0].split('%')[1]
                    # print('%d,%d,%d' % (int(value), self.register_translate(register), self.register_translate('zero')), 'TYPE_MEMORY')
                    return '%d,%d,%d' % (int(value), self.register_translate(register), self.register_translate('zero')), 'TYPE_MEMORY'
                elif len(t) == 2:
                    register1 = t[0].split('%')[1]
                    register2 = t[1].split('%')[1]
                    # print('%d,%d,%d' % (int(value), self.register_translate(register1), self.register_translate(register2)), 'TYPE_MEMORY')
                    return '%d,%d,%d' % (int(value), self.register_translate(register1), self.register_translate(register2)), 'TYPE_MEMORY'
            else:
                print('mov: 不合法的引數 [%s]' % tmp)
                exit(1)
                return
        zassert(True, 'mov: 不合法的引數 [%s]' % arg)
        return

    #
    # 把程式載入記憶體
    # 讓它準備好可以執行
    #
    def load(self, infile, loadaddr):
        pc   = int(loadaddr)
        fd   = open(infile)

        bpc  = loadaddr
        data = 100

        for line in fd:
            cline = line.rstrip()
            # print('第一輪(PASS 1)', cline)

            # 移除註解符號之後的所有內容
            ctmp = cline.split('#')
            assert(len(ctmp) == 1 or len(ctmp) == 2)
            if len(ctmp) == 2:
                cline = ctmp[0]

            # 移除空白行，並依空白字元切割該行
            tmp = cline.split()
            if len(tmp) == 0:
                continue

            # 這一輪只處理標籤（label）與變數
            if tmp[0] == '.var':
                assert(len(tmp) == 2)
                assert(tmp[0] not in self.vars)
                self.vars[tmp[1]] = data
                data += 4
                zassert(data < bpc, '靜態資料的位址超出了程式碼載入位址')
                if self.verbose: print('指派變數(ASSIGN VAR)', tmp[0], "-->", tmp[1], self.vars[tmp[1]])
            elif tmp[0][0] == '.':
                assert(len(tmp) == 1)
                self.labels[tmp[0]] = int(pc)
                if self.verbose: print('指派標籤(ASSIGN LABEL)', tmp[0], "-->", pc)
            else:
                pc += 1
        fd.close()

        if self.verbose: print('')

        # 第二輪：處理剩下的所有內容
        pc = int(loadaddr)
        fd = open(infile)
        for line in fd:
            cline = line.rstrip()
            # print('第二輪(PASS 2)', cline)

            # 移除註解符號之後的所有內容
            ctmp = cline.split('#')
            assert(len(ctmp) == 1 or len(ctmp) == 2)
            if len(ctmp) == 2:
                cline = ctmp[0]

            # 移除空白行，並依空白字元切割該行
            tmp = cline.split()
            if len(tmp) == 0:
                continue

            # 跳過標籤：其他所有內容都必須是指令
            if cline[0] != '.':
                tmp              = cline.split(None, 1)
                opcode           = tmp[0]
                self.pmemory[pc] = cline.strip()

                # 主要的作業碼（OPCODE）處理迴圈
                if opcode == 'mov':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'mov: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    # print('MOV', src, stype, dst, dtype)
                    if stype == 'TYPE_MEMORY' and dtype == 'TYPE_MEMORY':
                        print('不合法的 mov：兩個引數都是記憶體')
                        exit(1)
                    elif stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_IMMEDIATE':
                        print('不合法的 mov：兩個引數都是立即值')
                        exit(1)
                    elif stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_REGISTER':
                        self.memory[pc]  = 'self.move_i_to_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_REGISTER':
                        self.memory[pc]  = 'self.move_i_to_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_MEMORY'    and dtype == 'TYPE_REGISTER':
                        tmp = src.split(',')
                        assert(len(tmp) == 3)
                        self.memory[pc] = 'self.move_m_to_r(%d, %d, %d, %d)' % (int(tmp[0]), int(tmp[1]), int(tmp[2]), dst)
                    elif stype == 'TYPE_REGISTER'  and dtype == 'TYPE_MEMORY':
                        tmp = dst.split(',')
                        assert(len(tmp) == 3)
                        self.memory[pc] = 'self.move_r_to_m(%d, %d, %d, %d)' % (src, int(tmp[0]), int(tmp[1]), int(tmp[2]))
                    elif stype == 'TYPE_REGISTER'  and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.move_r_to_r(%d, %d)' % (src, dst)
                    elif stype == 'TYPE_IMMEDIATE'  and dtype == 'TYPE_MEMORY':
                        tmp = dst.split(',')
                        assert(len(tmp) == 3)
                        self.memory[pc] = 'self.move_i_to_m(%d, %d, %d, %d)' % (src, int(tmp[0]), int(tmp[1]), int(tmp[2]))
                    else:
                        zassert(False, 'mov 指令格式錯誤')
                elif opcode == 'pop':
                    if len(tmp) == 1:
                        self.memory[pc] = 'self.pop()'
                    elif len(tmp) == 2:
                        arg = tmp[1].strip()
                        (dst, dtype) = self.getarg(arg)
                        zassert(dtype == 'TYPE_REGISTER', 'pop 只能彈出到暫存器')
                        self.memory[pc] = 'self.pop_r(%d)' % dst
                    else:
                        zassert(False, 'pop 指令只能有零個或一個引數')
                elif opcode == 'push':
                    (src, stype) = self.getarg(tmp[1].strip())
                    if stype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.push_r(%d)' % (int(src))
                    elif stype == 'TYPE_MEMORY':
                        tmp = src.split(',')
                        assert(len(tmp) == 3)
                        self.memory[pc] = 'self.push_m(%d,%d,%d)' % (int(tmp[0]), int(tmp[1]), int(tmp[2]))
                    else:
                        zassert(False, 'push 只能推入暫存器')
                elif opcode == 'call':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    if ttype == 'TYPE_LABEL':
                        self.memory[pc] = 'self.call(%d)' % (int(self.labels[targ]))
                    else:
                        zassert(False, 'call 只能呼叫標籤（label）')
                elif opcode == 'ret':
                    assert(len(tmp) == 1)
                    self.memory[pc] = 'self.ret()'
                elif opcode == 'add':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'add: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    if stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.add_i_to_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_REGISTER' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.add_r_to_r(%d, %d)' % (int(src), dst)
                    else:
                        zassert(False, 'add 指令使用方式錯誤')
                elif opcode == 'sub':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'sub: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    if stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.sub_i_to_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_REGISTER' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.sub_r_to_r(%d, %d)' % (int(src), dst)
                    else:
                        zassert(False, 'sub 指令使用方式錯誤')
                elif opcode == 'fetchadd':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'fetchadd: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    tmp = dst.split(',')
                    assert(len(tmp) == 3)
                    if stype == 'TYPE_REGISTER' and dtype == 'TYPE_MEMORY':
                        self.memory[pc] = 'self.fetchadd(%d, %d, %d, %d)' % (src, int(tmp[0]), int(tmp[1]), int(tmp[2]))
                    else:
                        zassert(False, 'fetchadd 指令的引數指定不當')
                elif opcode == 'xchg':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'xchg: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    tmp = dst.split(',')
                    assert(len(tmp) == 3)
                    if stype == 'TYPE_REGISTER' and dtype == 'TYPE_MEMORY':
                        self.memory[pc] = 'self.atomic_exchange(%d, %d, %d, %d)' % (src, int(tmp[0]), int(tmp[1]), int(tmp[2]))
                    else:
                        zassert(False, 'xchg（atomic exchange）指令的引數指定不當')
                elif opcode == 'test':
                    rtmp = tmp[1].split(',', 1)
                    zassert(len(tmp) == 2 and len(rtmp) == 2, 'test: 需要兩個以逗號分隔的引數 [%s]' % cline)
                    arg1 = rtmp[0].strip()
                    arg2 = rtmp[1].strip()
                    (src, stype) = self.getarg(arg1)
                    (dst, dtype) = self.getarg(arg2)
                    if stype == 'TYPE_IMMEDIATE' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.test_i_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_REGISTER' and dtype == 'TYPE_REGISTER':
                        self.memory[pc] = 'self.test_r_r(%d, %d)' % (int(src), dst)
                    elif stype == 'TYPE_REGISTER' and dtype == 'TYPE_IMMEDIATE':
                        self.memory[pc] = 'self.test_r_i(%d, %d)' % (int(src), dst)
                    else:
                        zassert(False, 'test 指令使用方式錯誤')
                elif opcode == 'j':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump(%d)' % int(self.labels[targ])
                elif opcode == 'jne':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_notequal(%d)' % int(self.labels[targ])
                elif opcode == 'je':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_equal(%d)' % self.labels[targ]
                elif opcode == 'jlt':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_lessthan(%d)' % int(self.labels[targ])
                elif opcode == 'jlte':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_lessthanorequal(%s)' % self.labels[targ]
                elif opcode == 'jgt':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_greaterthan(%d)' % int(self.labels[targ])
                elif opcode == 'jgte':
                    (targ, ttype) = self.getarg(tmp[1].strip())
                    zassert(ttype == 'TYPE_LABEL', '不合法的跳躍目標 [%s]' % tmp[1].strip())
                    self.memory[pc] = 'self.jump_greaterthanorequal(%s)' % self.labels[targ]
                elif opcode == 'nop':
                    self.memory[pc] = 'self.nop()'
                elif opcode == 'halt':
                    self.memory[pc] = 'self.halt()'
                elif opcode == 'yield':
                    self.memory[pc] = 'self.iyield()'
                elif opcode == 'rdump':
                    self.memory[pc] = 'self.rdump()'
                elif opcode == 'mdump':
                    self.memory[pc] = 'self.mdump(%s)' % tmp[1]
                else:
                    print('不合法的作業碼(opcode)： ', opcode)
                    exit(1)

                if self.verbose: print('pc:%d 載入中 %20s --> %s' % (pc, self.pmemory[pc], self.memory[pc]))

                # 載入器（loader）遞增 PC
                pc += 1
        # 結束：檔案逐行迴圈
        fd.close()
        if self.verbose: print('')
        return
    # 結束：load

    def print_headers(self, procs):
        # 印出一些表頭
        if len(self.memtrace) > 0:
            for m in self.memtrace:
                if m[0].isdigit():
                    print('%5d' % int(m), end=' ')
                else:
                    zassert(m in self.vars, '被追蹤的變數 %s 尚未宣告' % m)
                    print('%5s' % m, end=' ')
            print(' ', end=' ')
        if len(self.regtrace) > 0:
            for r in self.regtrace:
                print('%5s' % self.get_regname(r), end=' ')
            print(' ', end=' ')
        if cctrace == True:
            print('>= >  <= <  != ==', end=' ')

        # 以及每個執行緒各自的欄位
        for i in range(procs.getnum()):
            print('      執行緒 %d         ' % i, end=' ')
        print('')
        return

    def print_trace(self, newline):
        if len(self.memtrace) > 0:
            for m in self.memtrace:
                if self.compute:
                    if m[0].isdigit():
                        print('%5d' % self.memory[int(m)], end=' ')
                    else:
                        zassert(m in self.vars, '被追蹤的變數 %s 尚未宣告' % m)
                        print('%5d' % self.memory[self.vars[m]], end=' ')
                else:
                    print('%5s' % '?', end=' ')
            print(' ', end=' ')
        if len(self.regtrace) > 0:
            for r in self.regtrace:
                if self.compute:
                    print('%5d' % self.registers[r], end=' ')
                else:
                    print('%5s' % '?', end=' ')
            print(' ', end=' ')
        if cctrace == True:
            for c in self.condlist:
                if self.compute:
                    if self.conditions[c]:
                        print('1 ', end=' ')
                    else:
                        print('0 ', end=' ')
                else:
                    print('? ', end=' ')
        if (len(self.memtrace) > 0 or len(self.regtrace) > 0 or cctrace == True) and newline == True:
            print('')
        return

    def setint(self, intfreq, intrand):
        if intrand == False:
            return intfreq
        return int(random.random() * intfreq) + 1

    def run(self, procs, intfreq, intrand):
        # 硬體初始化：條件碼、中斷頻率等等
        interrupt = self.setint(intfreq, intrand)
        icount    = 0

        self.print_headers(procs)
        self.print_trace(True)

        while True:
            # 需要知道目前這個行程的執行緒 ID
            tid = procs.getcurr().gettid()

            # 擷取（FETCH）
            prevPC       = self.PC
            instruction  = self.memory[self.PC]
            self.PC     += 1

            # 解碼（DECODE）與執行（EXECUTE）
            # 關鍵：self.PC 可能在 eval 過程中被改變；因此必須在 eval 之前先遞增
            rc = eval(instruction)

            # 追蹤細節：一律在指令執行「之後」才印出
            self.print_trace(False)

            # 輸出：先依執行緒比例留白，接著印出 PC 與指令
            dospace(tid)
            print(prevPC, self.pmemory[prevPC])
            icount += 1

            # 發出了 halt 指令
            if rc == -1:
                procs.done()
                if procs.numdone() == procs.getnum():
                    return icount
                procs.next()
                procs.restore()

                self.print_trace(False)
                for i in range(procs.getnum()):
                    print('----- 結束並切換(Halt;Switch) ----- ', end=' ')
                print('')

            # 處理中斷
            interrupt -= 1
            if interrupt == 0 or rc == -2:
                interrupt = self.setint(intfreq, intrand)
                procs.save()
                procs.next()
                procs.restore()

                self.print_trace(False)
                for i in range(procs.getnum()):
                    print('------ 中斷(Interrupt) ------ ', end=' ')
                print('')
        # 結束：while 迴圈
        return

#
# 結束：cpu 類別
#


#
# 行程清單（PROCESS LIST）類別
#
class proclist:
    def __init__(self):
        self.plist  = []
        self.curr   = 0
        self.active = 0

    def done(self):
        self.plist[self.curr].setdone()
        self.active -= 1

    def numdone(self):
        return len(self.plist) - self.active

    def getnum(self):
        return len(self.plist)

    def add(self, p):
        self.active += 1
        self.plist.append(p)

    def getcurr(self):
        return self.plist[self.curr]

    def save(self):
        self.plist[self.curr].save()

    def restore(self):
        self.plist[self.curr].restore()

    def next(self):
        for i in range(self.curr+1, len(self.plist)):
            if self.plist[i].isdone() == False:
                self.curr = i
                return
        for i in range(0, self.curr+1):
            if self.plist[i].isdone() == False:
                self.curr = i
                return
            
#
# 行程（PROCESS）類別
#
class process:
    def __init__(self, cpu, tid, pc, stackbottom, reginit):
        self.cpu   = cpu  # 物件參照
        self.tid   = tid
        self.pc    = pc
        self.regs  = {}
        self.cc    = {}
        self.done  = False
        self.stack = stackbottom

        # 初始化暫存器：全部設為 0，或依指定特別設定某些值
        for r in self.cpu.get_regnums():
            self.regs[r] = 0
        if reginit != '':
            # 格式：ax=1,bx=2（可以只指定其中一部分暫存器）
            for r in reginit.split(':'):
                tmp = r.split('=')
                assert(len(tmp) == 2)
                self.regs[self.cpu.get_regnum(tmp[0])] = int(tmp[1])

        # 初始化條件碼（CC）
        for c in self.cpu.get_condlist():
            self.cc[c] = False

        # 堆疊
        self.regs[self.cpu.get_regnum('sp')] = stackbottom
        # print('暫存器', self.cpu.get_regnum('sp'), self.regs[self.cpu.get_regnum('sp')])

        return

    def gettid(self):
        return self.tid

    def save(self):
        self.pc = self.cpu.get_pc()
        for c in self.cpu.get_condlist():
            self.cc[c] = self.cpu.get_cond(c)
        for r in self.cpu.get_regnums():
            self.regs[r] = self.cpu.get_reg(r)

    def restore(self):
        self.cpu.set_pc(self.pc)
        for c in self.cpu.get_condlist():
            self.cpu.set_cond(c, self.cc[c])
        for r in self.cpu.get_regnums():
            self.cpu.set_reg(r, self.regs[r])

    def setdone(self):
        self.done = True

    def isdone(self):
        return self.done == True

#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',      default=0,          help='隨機種子',                          action='store',      type='int',    dest='seed')
parser.add_option('-t', '--threads',   default=2,          help='執行緒數量',                        action='store',      type='int',    dest='numthreads')
parser.add_option('-p', '--program',   default='',         help='原始程式（.s 檔）',                 action='store',      type='string', dest='progfile')
parser.add_option('-i', '--interrupt', default=50,         help='中斷頻率',                          action='store',      type='int',    dest='intfreq')
parser.add_option('-r', '--randints',  default=False,      help='中斷時機是否隨機決定',              action='store_true',                dest='intrand')
parser.add_option('-a', '--argv',      default='',
                  help='以逗號分隔的各執行緒引數（例如 ax=1,ax=2 會把執行緒 0 的 ax 暫存器設為 1，執行緒 1 的 ax 暫存器設為 2）；同一個執行緒若要設定多個暫存器，用冒號分隔（例如 ax=1:bx=2,cx=3 會設定執行緒 0 的 ax 與 bx，以及執行緒 1 的 cx）',
                  action='store',      type='string', dest='argv')
parser.add_option('-L', '--loadaddr',  default=1000,       help='程式碼載入的位址',                  action='store',      type='int',    dest='loadaddr')
parser.add_option('-m', '--memsize',   default=128,        help='位址空間大小（KB）',                action='store',      type='int',    dest='memsize')
parser.add_option('-M', '--memtrace',  default='',         help='以逗號分隔的待追蹤位址清單（例如 20000,20001）', action='store',
                  type='string', dest='memtrace')
parser.add_option('-R', '--regtrace',  default='',         help='以逗號分隔的待追蹤暫存器清單（例如 ax,bx,cx,dx）',  action='store',
                  type='string', dest='regtrace')
parser.add_option('-C', '--cctrace',   default=False,      help='是否要追蹤條件碼',                  action='store_true', dest='cctrace')
parser.add_option('-S', '--printstats',default=False,      help='印出一些額外的統計資訊',            action='store_true', dest='printstats')
parser.add_option('-v', '--verbose',   default=False,      help='印出一些額外的詳細資訊',            action='store_true', dest='verbose')
parser.add_option('-c', '--compute',   default=False,      help='幫我計算答案',                      action='store_true', dest='solve')
(options, args) = parser.parse_args()

print('參數 亂數種子(seed)',                  options.seed)
print('參數 執行緒數量(numthreads)',          options.numthreads)
print('參數 程式(program)',                   options.progfile)
print('參數 中斷頻率(interrupt frequency)',   options.intfreq)
print('參數 中斷是否隨機(interrupt randomness)', options.intrand)
print('參數 各執行緒引數(argv)',              options.argv)
print('參數 載入位址(load address)',          options.loadaddr)
print('參數 記憶體大小(memsize)',             options.memsize)
print('參數 追蹤位址(memtrace)',              options.memtrace)
print('參數 追蹤暫存器(regtrace)',            options.regtrace)
print('參數 追蹤條件碼(cctrace)',             options.cctrace)
print('參數 顯示統計資訊(printstats)',        options.printstats)
print('參數 詳細模式(verbose)',               options.verbose)
print('')

seed       = int(options.seed)
numthreads = int(options.numthreads)
intfreq    = int(options.intfreq)
zassert(intfreq > 0, '中斷頻率必須大於 0')
intrand    = int(options.intrand)
progfile   = options.progfile
zassert(progfile != '', '必須指定程式檔案')
argv       = options.argv.split(',')
zassert(len(argv) == numthreads or len(argv) == 1, 'argv：必須是每個執行緒各一組值，或所有執行緒共用一組值')

loadaddr   = options.loadaddr
memsize    = options.memsize
random_seed(seed)

memtrace   = []
if options.memtrace != '':
    for m in options.memtrace.split(','):
        memtrace.append(m)

regtrace   = []
if options.regtrace != '':
    for r in options.regtrace.split(','):
        regtrace.append(r)

cctrace    = options.cctrace

printstats = options.printstats
verbose    = options.verbose
        
#
# 主程式
#
debug = False
debug = False

cpu = cpu(memsize, memtrace, regtrace, cctrace, options.solve, verbose)

# 載入程式
cpu.load(progfile, loadaddr)

# 行程清單
procs = proclist()
pid   = 0
stack = memsize * 1000
for t in range(numthreads):
    if len(argv) > 1:
        arg = argv[pid]
    else:
        arg = argv[0]
    procs.add(process(cpu, pid, loadaddr, stack, arg))
    stack -= 1000
    pid += 1

# 讓第一個行程準備好！
procs.restore()

# 執行模擬
if printstats:
    t1 = time_clock()
ic = cpu.run(procs, intfreq, intrand)
if printstats:
    t2 = time_clock()

if printstats:
    print('')
    print('統計(STATS):: 指令數        %d' % ic)
    print('統計(STATS):: 模擬速度      %.2f 千指令/秒' % (float(ic) / float(t2 - t1) / 1000.0))

# 用於效能分析（profiling）
# import cProfile
# cProfile.run('run()')




