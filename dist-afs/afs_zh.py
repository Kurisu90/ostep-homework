#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import random
from optparse import OptionParser
import string

# 讓 Python2 與 Python3 的隨機數行為一致
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

def tprint(str):
    print(str)

def dprint(str):
    return

def dospace(howmuch):
    for i in range(howmuch + 1):
        print('%28s' % ' ', end='')

# 給定一個 list，從中隨機挑一個元素並回傳
def pickrand(tlist):
    n = int(random.random() * len(tlist))
    p = tlist[n]
    return p

# 給定一個數字，判斷其第 n 個位元是否為 1
def isset(num, index):
    mask = 1 << index
    return (num & mask) > 0

# 用來取代 assert，比較好用
def zassert(cond, str):
    if cond == False:
        print('中止::', str)
        exit(1)

#
# 模擬中會用到哪些檔案
#
# 這裡並不是要代表任何真實存在的東西，
# 只是為了方便產生隨機的執行記錄而已……
#
# 為了方便起見，檔案的名稱就叫 'a'、'b' 等等
# 或許可以加上數字讓檔案數量超過 26 個，
# 但沒有人在乎這件事
#

class files:
    def __init__(self, numfiles):
        self.numfiles = numfiles
        self.value    = 0
        self.filelist = list(string.ascii_lowercase)[0:numfiles]

    def getfiles(self):
        return self.filelist

    def getvalue(self):
        rc = self.value
        self.value += 1
        return rc

#
# 模擬 AFS 伺服器的行為
#
# 唯二真正的互動只有 get/put
# get() 會讓伺服器記錄哪個檔案被哪個用戶端快取；
# put() 則可能會觸發回呼（callback），使用戶端的快取失效
#
class server:
    def __init__(self, files, solve, detail):
        self.files  = files
        self.solve  = solve
        self.detail = detail

        flist = self.files.getfiles()
        self.contents = {}
        for f in flist:
            v = self.files.getvalue()
            self.contents[f] = v
        self.getcnt, self.putcnt = 0, 0

    def stats(self):
        print('伺服器   -- 取得次數:%d 寫回次數:%d' % (self.getcnt, self.putcnt))

    def filestats(self, printcontents):
        for fname in self.contents:
            if printcontents:
                print('檔案:%s 內容:%d' % (fname, self.contents[fname]))
            else:
                print('檔案:%s 內容:?' % fname)


    def setclients(self, clients):
        # 需要用戶端清單
        self.clients = clients

        # 每個用戶端各自的回呼清單
        self.cache = {}
        for c in self.clients:
            self.cache[c.getname()] = []

    def get(self, client, fname):
        zassert(fname in self.contents, 'server:get() -- 找不到檔案:%s（伺服器上沒有此檔案）' % fname)
        self.getcnt += 1
        if self.solve and isset(self.detail, 0):
            print('取得檔案:%s c:%s [%d]' % (fname, client, self.contents[fname]))
        if fname not in self.cache[client]:
            self.cache[client].append(fname)
            # dprint('  -> 用戶端 %s 的清單' % client, ' 是 ', self.cache[client])
        return self.contents[fname]

    def put(self, client, fname, value):
        zassert(fname in self.contents, 'server:put() -- 找不到檔案:%s（伺服器上沒有此檔案）' % fname)
        self.putcnt += 1
        self.contents[fname] = value
        if self.solve and isset(self.detail, 0):
            print('寫回檔案:%s c:%s [%s]' % (fname, client, self.contents[fname]))
        # 掃描其他用戶端，看是否要送出回呼
        for c in self.clients:
            cname = c.getname()
            if fname in self.cache[cname] and cname != client:
                if self.solve and isset(self.detail, 1):
                    print('回呼: c:%s 檔案:%s' % (cname, fname))
                c.invalidate(fname)
                # XXX - 這裡其實不太對……
                # self.cache[cname].remove(fname)

#
# 每個用戶端的檔案描述符
#
# 如果模擬允許同時開啟一個以上的檔案，這個類別
# 才比較有用；目前雖然某種程度上支援，但沒有真正
# 被用到
#
class filedesc:
    def __init__(self, max=1024):
        self.max = max
        self.fd  = {}
        for i in range(self.max):
            self.fd[i] = ''

    def alloc(self, fname, sfd=-1):
        if sfd != -1:
            zassert(self.fd[sfd] == '', 'filedesc:alloc() -- fd:%d 已被使用，無法配置' % sfd)
            self.fd[sfd] = fname
            return sfd
        else:
            for i in range(self.max):
                if self.fd[i] == '':
                    self.fd[i] = fname
                    return i
            return -1

    def lookup(self, sfd):
        zassert(i >= 0 and i < self.max, 'filedesc:lookup() -- 檔案描述符超出有效範圍（%d 不在 0 到 %d 之間）' % (sfd, self.max))
        zassert(self.fd[sfd] != '',      'filedesc:lookup() -- fd:%d 尚未使用，無法查詢' % sfd)
        return self.fd[sfd]

    def free(self, i):
        zassert(i >= 0 and i < self.max, 'filedesc:free() -- 檔案描述符超出有效範圍（%d 不在 0 到 %d 之間）' % (sfd, self.max))
        zassert(self.fd[sfd] != '',      'filedesc:free() -- fd:%d 尚未使用，無法釋放' % sfd)
        self.fd[i] = ''

#
# 用戶端的快取
#
# 只是單純模擬哪些檔案被快取住了。
# 當一個檔案被開啟時，它的內容會從伺服器取得
# 並放進快取。此時，快取內容會是 VALID（有效），
# DIRTY（是否被寫過），且 REFERENCE COUNT（參考計數）
# 會被設為 1。如果同一個檔案被多次開啟，
# REFERENCE COUNT 會相應更新。VALID 會在快取被回呼
# 弄失效時變成 0；不過，如果這個用戶端已經開啟了
# 這個檔案，即使快取失效了，內容仍然可能會被繼續使用。
# 注意，回呼並不會阻止用戶端覆寫一個已經開啟的檔案。
#
class cache:
    def __init__(self, name, num, solve, detail):
        self.name       = name
        self.num        = num
        self.solve      = solve
        self.detail     = detail

        self.cache      = {}

        self.hitcnt     = 0
        self.misscnt    = 0
        self.invalidcnt = 0

    def stats(self):
        print('   快取 -- 命中次數:%d 未命中次數:%d 失效次數:%d' % (self.hitcnt, self.misscnt, self.invalidcnt))

    def put(self, fname, data, dirty, refcnt):
        self.cache[fname] = dict(data=data, dirty=dirty, refcnt=refcnt, valid=True)

    def update(self, fname, data):
        self.cache[fname] = dict(data=data, dirty=True, refcnt=self.cache[fname]['refcnt'], valid=self.cache[fname]['valid'])

    def invalidate(self, fname):
        dospace(self.num)
        print('使檔案失效:%s' % fname, '快取:', self.cache)
        # zassert(fname in self.cache, 'cache:invalidate() -- 無法讓不在快取中的檔案失效 (%s)' % fname)
        if fname not in self.cache:
            return
        self.invalidcnt += 1
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=self.cache[fname]['dirty'],
                                 refcnt=self.cache[fname]['refcnt'], valid=False)
        if self.solve and isset(self.detail, 1):
            dospace(self.num)
            if isset(self.detail,3):
                print('%2s 使 %s 失效' % (self.name, fname))
            else:
                print('使 %s 失效' % (fname))
            self.printstate(self.num)

    def checkvalid(self, fname):
        zassert(fname in self.cache, 'cache:checkvalid() -- 無法對不在快取中的檔案執行 checkvalid (%s)' % fname)
        if self.cache[fname]['valid'] == False and self.cache[fname]['refcnt'] == 0:
            del self.cache[fname]

    def printstate(self, fname):
        for fname in self.cache:
            data   = self.cache[fname]['data']
            dirty  = self.cache[fname]['dirty']
            refcnt = self.cache[fname]['refcnt']
            valid  = self.cache[fname]['valid']
            if valid == True:
                validPrint = 1
            else:
                validPrint = 0
            if dirty == True:
                dirtyPrint = 1
            else:
                dirtyPrint = 0

            if self.solve and isset(self.detail, 2):
                dospace(self.num)
                if isset(self.detail, 3):
                    print('%s [%s:%2d (v=%d,d=%d,r=%d)]' % (self.name, fname, data, validPrint, dirtyPrint, refcnt))
                else:
                    print('[%s:%2d (v=%d,d=%d,r=%d)]' % (fname, data, validPrint, dirtyPrint, refcnt))

    def checkget(self, fname):
        if fname in self.cache:
            self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=self.cache[fname]['dirty'],
                                     refcnt=self.cache[fname]['refcnt'], valid=self.cache[fname]['valid'])
            self.hitcnt += 1
            return (True, self.cache[fname])
        self.misscnt += 1
        return (False, -1)

    def get(self, fname):
        assert(fname in self.cache)
        return (True, self.cache[fname])

    def incref(self, fname):
        assert(fname in self.cache)
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=self.cache[fname]['dirty'],
                                 refcnt=self.cache[fname]['refcnt'] + 1, valid=self.cache[fname]['valid'])

    def decref(self, fname):
        assert(fname in self.cache)
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=self.cache[fname]['dirty'],
                                 refcnt=self.cache[fname]['refcnt'] - 1, valid=self.cache[fname]['valid'])

    def setdirty(self, fname, dirty):
        assert(fname in self.cache)
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=dirty,
                                 refcnt=self.cache[fname]['refcnt'], valid=self.cache[fname]['valid'])

    def setclean(self, fname):
        assert(fname in self.cache)
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=False,
                                 refcnt=self.cache[fname]['refcnt'], valid=self.cache[fname]['valid'])

    def isdirty(self, fname):
        assert(fname in self.cache)
        return (self.cache[fname]['dirty'] == True)

    def setvalid(self, fname):
        assert(fname in self.cache)
        self.cache[fname] = dict(data=self.cache[fname]['data'], dirty=self.cache[fname]['dirty'],
                                 refcnt=self.cache[fname]['refcnt'], valid=True)


# 動作代碼
MICRO_OPEN      = 1
MICRO_READ      = 2
MICRO_WRITE     = 3
MICRO_CLOSE     = 4

def op2name(op):
    if op == MICRO_OPEN:
        return 'MICRO_OPEN'
    elif op == MICRO_READ:
        return 'MICRO_READ'
    elif op == MICRO_WRITE:
        return 'MICRO_WRITE'
    elif op == MICRO_CLOSE:
        return 'MICRO_CLOSE'
    else:
        abort('錯誤：不明的操作代碼 -> ' + op)

#
# 用戶端類別
#
# 模擬系統中每個用戶端的行為。
#
#
#
class client:
    def __init__(self, name, cid, server, files, bias, numsteps, actions, solve, detail):
        self.name    = name      # 用戶端的易讀名稱
        self.cid     = cid       # 用戶端 ID
        self.server  = server    # 伺服器物件
        self.files   = files     # 檔案物件
        self.bias    = bias      # 偏向讀取還是寫入
        self.actions = actions   # 是否有精確指定的排程？
        self.solve   = solve     # 是否顯示答案？
        self.detail  = detail    # 要顯示多少細節的答案

        # 快取
        self.cache   = cache(self.name, self.cid, self.solve, self.detail)

        # 檔案描述符
        self.fd      = filedesc()

        # 統計數據
        self.readcnt  = 0
        self.writecnt = 0

        # 初始化動作
        self.done    = False     # 追蹤狀態
        self.acnt    = 0         # 執行時用來記錄目前位置
        self.acts    = []        # 用來記錄操作碼

        if self.actions == '':
            # 若沒有指定精確動作，就自己隨機產生一份
            for i in range(numsteps):
                fname = pickrand(self.files.getfiles())
                r = random.random()
                fd = self.fd.alloc(fname)
                zassert(fd >= 0, 'client:init() -- 檔案描述符用完了，抱歉！')
                if r < self.bias[0]:
                    # FILE_READ
                    self.acts.append((MICRO_OPEN,  fname, fd))
                    self.acts.append((MICRO_READ,  fd))
                    self.acts.append((MICRO_CLOSE, fd))
                else:
                    # FILE_WRITE
                    self.acts.append((MICRO_OPEN,  fname, fd))
                    self.acts.append((MICRO_WRITE, fd))
                    self.acts.append((MICRO_CLOSE, fd))
        else:
            # 這種情況下，要把動作字串解析出來並實際執行
            # 格式應該長得像這樣："oa1:r1:c1"（開啟 'a' 並以檔案描述符 1 讀取，
            # 從 fd:1 讀取，再關閉 fd:1）
            # 沒錯，對於 read/write/close 來說，檔案描述符跟檔名是重複的資訊
            for a in self.actions.split(':'):
                act = a[0]
                if act == 'o':
                    zassert(len(a) == 3, 'client:init() -- open 動作格式錯誤 (%s)，應該要長得像 oa1 這樣' % a)
                    fname, fd = a[1], int(a[2])
                    self.fd.alloc(fname, fd)
                    assert(fd >= 0)
                    self.acts.append((MICRO_OPEN,  fname, fd))
                elif act == 'r':
                    zassert(len(a) == 2, 'client:init() -- read 動作格式錯誤 (%s)，應該要長得像 r1 這樣' % a)
                    fd = int(a[1])
                    self.acts.append((MICRO_READ,  fd))
                elif act == 'w':
                    zassert(len(a) == 2, 'client:init() -- write 動作格式錯誤 (%s)，應該要長得像 w1 這樣' % a)
                    fd = int(a[1])
                    self.acts.append((MICRO_WRITE, fd))
                elif act == 'c':
                    zassert(len(a) == 2, 'client:init() -- close 動作格式錯誤 (%s)，應該要長得像 c1 這樣' % a)
                    fd = int(a[1])
                    self.acts.append((MICRO_CLOSE, fd))
                else:
                    print('無法識別的指令: %s（來自 %s）' % (act, a))
                    exit(1)
        print(self.acts)
        return

    def getname(self):
        return self.name

    def stats(self):
        print('%s       -- 讀取次數:%d 寫入次數:%d' % (self.name, self.readcnt, self.writecnt))
        self.cache.stats()

    def getfile(self, fname):
        (in_cache, item) = self.cache.checkget(fname)
        if in_cache == True and item['valid'] == 1:
            dprint('  -> 用戶端 %s：已有本機端副本 %s' % (self.name, fname))
            # self.cache.setdirty(fname, dirty)
        else:
            data = self.server.get(self.name, fname)
            self.cache.put(fname, data, False, 0)
        self.cache.incref(fname)
        return

    def putfile(self, fname, value):
        self.server.put(self.name, fname, value)
        self.cache.setclean(fname)
        self.cache.setvalid(fname)
        return

    def invalidate(self, fname):
        self.cache.invalidate(fname)
        return

    def step(self, space):
        if self.done == True:
            return -1
        if self.acnt == len(self.acts):
            self.done = True
            return 0

        # 現在來判斷該做什麼，並且執行它
        # action, fname, fd = self.acts[self.acnt]
        action = self.acts[self.acnt][0]

        # print ''
        # print '*************************'
        # print '%s 動作 -> %s' % (self.name, op2name(action))
        # print '*************************'

        # 首先，先印出對應的縮排（見下方）
        dospace(space)

        if isset(self.detail, 3) == True:
            print(self.name, end=' ')

        # 現在處理這個動作
        if action == MICRO_OPEN:
            fname, fd = self.acts[self.acnt][1], self.acts[self.acnt][2]
            tprint('開啟:%s [fd:%d]' % (fname, fd))
            # self.getfile(fname, dirty=False)
            self.getfile(fname)
        elif action == MICRO_READ:
            fd    = self.acts[self.acnt][1]
            fname = self.fd.lookup(fd)
            self.readcnt += 1
            in_cache, contents = self.cache.get(fname)
            assert(in_cache == True)
            if self.solve:
                tprint('讀取:%d -> %d' % (fd, contents['data']))
            else:
                tprint('讀取:%d -> 數值?' % (fd))
        elif action == MICRO_WRITE:
            fd    = self.acts[self.acnt][1]
            fname = self.fd.lookup(fd)
            self.writecnt += 1
            in_cache, contents = self.cache.get(fname)
            assert(in_cache == True)
            v = self.files.getvalue()
            self.cache.update(fname, v)
            if self.solve:
                tprint('寫入:%d %d -> %d' % (fd, contents['data'], v))
            else:
                tprint('寫入:%d 數值? -> %d' % (fd, v))
        elif action == MICRO_CLOSE:
            fd    = self.acts[self.acnt][1]
            fname = self.fd.lookup(fd)
            in_cache, contents = self.cache.get(fname)
            assert(in_cache == True)
            tprint('關閉:%d' % (fd))
            if self.cache.isdirty(fname):
                self.putfile(fname, contents['data'])
            self.cache.decref(fname)
            self.cache.checkvalid(fname)

        # 方便觀察目前狀態
        self.cache.printstate(self.name)

        if self.solve and self.detail > 0:
            print('')

        # 回傳「還有事情要做」
        self.acnt += 1
        return 1


#
# 主程式
#
parser = OptionParser()
parser.add_option('-s', '--seed',      default=0,      help='隨機種子',           action='store', type='int', dest='seed')
parser.add_option('-C', '--clients',   default=2,      help='用戶端數量',         action='store', type='int', dest='numclients')
parser.add_option('-n', '--numsteps',  default=2,      help='每個用戶端要執行的操作數量',   action='store', type='int', dest='numsteps')
parser.add_option('-f', '--numfiles',  default=1,      help='伺服器上的檔案數量', action='store', type='int', dest='numfiles')
parser.add_option('-r', '--readratio', default=0.5,    help='讀取與寫入的比例',     action='store', type='float', dest='readratio')
parser.add_option('-A', '--actions',   default='',     help='精確指定每個用戶端的動作，例如 oa1:r1:c1,oa1:w1:c1 表示有兩個用戶端；兩者都開啟檔案 a，用戶端 0 讀取它，用戶端 1 寫入它，然後兩者都將它關閉', action='store', type='string', dest='actions')
parser.add_option('-S', '--schedule',  default='',     help='要執行的確切排程；01 表示在用戶端 0 與 1 之間輪流（round robin）執行。若不指定則採隨機排程', action='store', type='string', dest='schedule')
parser.add_option('-p', '--printstats', default=False, help='印出額外的統計資訊',      action='store_true', dest='printstats')
parser.add_option('-c', '--compute',    default=False, help='幫我計算答案', action='store_true', dest='solve')
parser.add_option('-d', '--detail',     default=0,     help='產生答案時的詳細程度（1:伺服器動作,2:失效事件,4:用戶端快取,8:額外標籤）；可用 OR 運算疊加多種', action='store', type='int', dest='detail')
(options, args) = parser.parse_args()

print('參數 種子',       options.seed)
print('參數 用戶端數量', options.numclients)
print('參數 步驟數',     options.numsteps)
print('參數 檔案數量',   options.numfiles)
print('參數 讀取比例',   options.readratio)
print('參數 動作',       options.actions)
print('參數 排程',       options.schedule)
print('參數 詳細程度',   options.detail)
print('')

seed       = int(options.seed)
numclients = int(options.numclients)
numsteps   = int(options.numsteps)
numfiles   = int(options.numfiles)
readratio  = float(options.readratio)
actions    = options.actions
schedule   = options.schedule
printstats = options.printstats
solve      = options.solve
detail     = options.detail

# 若指定了精確的排程，特定動作清單中的檔案都會以單一字母表示
# 但我們目前先忽略這件事……

zassert(numfiles > 0 and numfiles <= 26, 'main: 最多只能模擬 26 個檔案，抱歉')
zassert(readratio >= 0.0 and readratio <= 1.0, 'main: 讀取比例必須介於 0 到 1 之間（含頭尾）')

# 開始執行
random_seed(seed)

# 一開始伺服器上有哪些檔案
f = files(numfiles)

# 建立伺服器
s = server(f, solve, detail)

clients = []

if actions != '':
    # 若指定了精確動作，先在這裡把一些東西算出來
    # 例如 oa1:ra1:ca1,oa1:ra1:ca1 就是用戶端 0 的動作清單，接著是用戶端 1 的，以此類推
    cactions = actions.split(',')
    if numclients != len(cactions):
        numclients = len(cactions)
    i = 0
    for clist in cactions:
        clients.append(client('c%d' % i, i, s, f, [], len(clist), clist, solve, detail))
        i += 1
else:
    # 否則就隨機建立用戶端
    for i in range(numclients):
        clients.append(client('c%d' % i, i, s, f, [readratio, 1.0], numsteps, '', solve, detail))

# 讓伺服器知道有哪些用戶端
s.setclients(clients)

# 印出用戶端的表頭
print('%12s' % '伺服器', '%12s' % ' ', end=' ')
for c in clients:
    print('%13s' % c.getname(), '%13s' % ' ', end=' ')
print('')

# 主迴圈
#
# 隨著時間推進，隨機挑一個用戶端
# 讓它做一件事，並顯示發生了什麼
# 接著換下一個，依此類推

s.filestats(True)

# 給精確排程使用
schedcurr = 0

# 檢查排程是否合法（必須包含所有用戶端）
if schedule != '':
    for i in range(len(clients)):
        cnt = 0
        for j in range(len(schedule)):
            curr = schedule[j]
            if int(curr) == i:
                cnt += 1
        zassert(cnt != 0, 'main: 用戶端 %d 不在排程:%s 中，這樣模擬永遠不會結束' % (i, schedule))

# 執行排程（隨機或使用者指定皆可）
numrunning = len(clients)
while numrunning > 0:
    if schedule == '':
        c = pickrand(clients)
    else:
        idx = int(schedule[schedcurr])
        # print '排程除錯訊息:: schedule:', schedule, 'schedcurr', schedcurr, 'index', idx
        c = clients[idx]
        schedcurr += 1
        if schedcurr == len(schedule):
            schedcurr = 0
    rc = c.step(clients.index(c))
    if rc == 0:
        numrunning -= 1


s.filestats(solve)

if printstats:
    s.stats()
    for c in clients:
        c.stats()

