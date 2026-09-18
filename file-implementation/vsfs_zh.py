#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
import random
from optparse import OptionParser

# 讓 Python2 與 Python3 的行為一致 -- 有夠蠢的作法
def random_seed(seed):
    try:
        random.seed(seed, version=1)
    except:
        random.seed(seed)
    return

DEBUG = False

def dprint(str):
    if DEBUG:
        print(str)

printOps      = True
printState    = True
printFinal    = True

class bitmap:
    def __init__(self, size):
        self.size = size
        self.bmap = []
        for num in range(size):
            self.bmap.append(0)
        self.numAllocated = 0

    def alloc(self):
        for num in range(len(self.bmap)):
            if self.bmap[num] == 0:
                self.bmap[num] = 1
                self.numAllocated += 1
                return num
        return -1

    def free(self, num):
        assert(self.bmap[num] == 1)
        self.numAllocated -= 1
        self.bmap[num] = 0

    def markAllocated(self, num):
        assert(self.bmap[num] == 0)
        self.numAllocated += 1
        self.bmap[num] = 1

    def numFree(self):
        return self.size - self.numAllocated

    def dump(self):
        s = ''
        for i in range(len(self.bmap)):
            s += str(self.bmap[i])
        return s

class block:
    def __init__(self, ftype):
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype = ftype
        # 以下這幾個欄位只有目錄會用到，理論上該獨立出子類別，但將就一下
        self.dirUsed = 0
        self.maxUsed = 32
        self.dirList = []
        self.data    = ''

    def dump(self):
        if self.ftype == 'free':
            return '[]'
        elif self.ftype == 'd':
            rc = ''
            for d in self.dirList:
                # d 的格式為 ('name', inum)，也就是 (名稱, inode 編號)
                short = '(%s,%s)' % (d[0], d[1])
                if rc == '':
                    rc = short
                else:
                    rc += ' ' + short
            return '['+rc+']'
            # return '%s' % self.dirList
        else:
            return '[%s]' % self.data

    def setType(self, ftype):
        assert(self.ftype == 'free')
        self.ftype = ftype

    def addData(self, data):
        assert(self.ftype == 'f')
        self.data = data

    def getNumEntries(self):
        assert(self.ftype == 'd')
        return self.dirUsed

    def getFreeEntries(self):
        assert(self.ftype == 'd')
        return self.maxUsed - self.dirUsed

    def getEntry(self, num):
        assert(self.ftype == 'd')
        assert(num < self.dirUsed)
        return self.dirList[num]

    def addDirEntry(self, name, inum):
        assert(self.ftype == 'd')
        self.dirList.append((name, inum))
        self.dirUsed += 1
        assert(self.dirUsed <= self.maxUsed)

    def delDirEntry(self, name):
        assert(self.ftype == 'd')
        tname = name.split('/')
        dname = tname[len(tname) - 1]
        for i in range(len(self.dirList)):
            if self.dirList[i][0] == dname:
                self.dirList.pop(i)
                self.dirUsed -= 1
                return
        assert(1 == 0)

    def dirEntryExists(self, name):
        assert(self.ftype == 'd')
        for d in self.dirList:
            if name == d[0]:
                return True
        return False

    def free(self):
        assert(self.ftype != 'free')
        if self.ftype == 'd':
            # 檢查是否只剩下 . 和 .. 這兩筆項目
            assert(self.dirUsed == 2)
            self.dirUsed = 0
        self.data  = ''
        self.ftype = 'free'

class inode:
    def __init__(self, ftype='free', addr=-1, refCnt=1):
        self.setAll(ftype, addr, refCnt)

    def setAll(self, ftype, addr, refCnt):
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype  = ftype
        self.addr   = addr
        self.refCnt = refCnt

    def incRefCnt(self):
        self.refCnt += 1

    def decRefCnt(self):
        self.refCnt -= 1

    def getRefCnt(self):
        return self.refCnt

    def setType(self, ftype):
        assert(ftype == 'd' or ftype == 'f' or ftype == 'free')
        self.ftype = ftype

    def setAddr(self, block):
        self.addr = block

    def getSize(self):
        if self.addr == -1:
            return 0
        else:
            return 1

    def getAddr(self):
        return self.addr

    def getType(self):
        return self.ftype

    def free(self):
        self.ftype = 'free'
        self.addr  = -1


class fs:
    def __init__(self, numInodes, numData):
        self.numInodes = numInodes
        self.numData   = numData

        self.ibitmap = bitmap(self.numInodes)
        self.inodes  = []
        for i in range(self.numInodes):
            self.inodes.append(inode())

        self.dbitmap = bitmap(self.numData)
        self.data    = []
        for i in range(self.numData):
            self.data.append(block('free'))

        # 根目錄的 inode
        self.ROOT = 0

        # 建立根目錄
        self.ibitmap.markAllocated(self.ROOT)
        self.inodes[self.ROOT].setAll('d', 0, 2)
        self.dbitmap.markAllocated(self.ROOT)
        self.data[0].setType('d')
        self.data[0].addDirEntry('.',  self.ROOT)
        self.data[0].addDirEntry('..', self.ROOT)

        # 以下這些只是用來產生假的工作負載（workload）
        self.files      = []
        self.dirs       = ['/']
        self.nameToInum = {'/':self.ROOT}

    def dump(self):
        print('inode 點陣圖 ', self.ibitmap.dump())
        print('inode 內容   ', end='')
        for i in range(0,self.numInodes):
            ftype = self.inodes[i].getType()
            if ftype == 'free':
                print('[]', end='')
            else:
                print('[%s a:%s r:%d]' % (ftype, self.inodes[i].getAddr(), self.inodes[i].getRefCnt()), end='')
        print('')
        print('資料點陣圖   ', self.dbitmap.dump())
        print('資料區塊     ', end='')
        for i in range(self.numData):
            print(self.data[i].dump(), end='')
        print('')

    def makeName(self):
        p = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'j', 'k', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z']
        return p[int(random.random() * len(p))]
        p = ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 's', 't', 'v', 'w', 'x', 'y', 'z']
        f = p[int(random.random() * len(p))]
        p = ['a', 'e', 'i', 'o', 'u']
        s = p[int(random.random() * len(p))]
        p = ['b', 'c', 'd', 'f', 'g', 'j', 'k', 'l', 'm', 'n', 'p', 's', 't', 'v', 'w', 'x', 'y', 'z']
        l = p[int(random.random() * len(p))]
        return '%c%c%c' % (f, s, l)

    def inodeAlloc(self):
        return self.ibitmap.alloc()

    def inodeFree(self, inum):
        self.ibitmap.free(inum)
        self.inodes[inum].free()

    def dataAlloc(self):
        return self.dbitmap.alloc()

    def dataFree(self, bnum):
        self.dbitmap.free(bnum)
        self.data[bnum].free()

    def getParent(self, name):
        tmp = name.split('/')
        if len(tmp) == 2:
            return '/'
        pname = ''
        for i in range(1, len(tmp)-1):
            pname = pname + '/' + tmp[i]
        return pname

    def deleteFile(self, tfile):
        if printOps:
            print('unlink("%s");' % tfile)

        inum = self.nameToInum[tfile]
        ftype = self.inodes[inum].getType()

        if self.inodes[inum].getRefCnt() == 1:
            # 先釋放資料區塊
            dblock = self.inodes[inum].getAddr()
            if dblock != -1:
                self.dataFree(dblock)
            # 然後釋放 inode
            self.inodeFree(inum)
        else:
            self.inodes[inum].decRefCnt()

        # 從父目錄中移除
        parent = self.getParent(tfile)
        # print('--> 從父目錄刪除', parent)
        pinum = self.nameToInum[parent]
        # print('--> 從父目錄刪除的 inode 編號', pinum)
        pblock = self.inodes[pinum].getAddr()
        # 修正過的 bug：如有需要，遞減父目錄 inode 的參照計數（感謝 Srinivasan Thirunarayanan 提出）
        if ftype == 'd':
            self.inodes[pinum].decRefCnt()
        # print('--> 從父目錄刪除的資料區塊位址', pblock)
        self.data[pblock].delDirEntry(tfile)

        # 最後，從檔案清單中移除
        self.files.remove(tfile)
        return 0

    def createLink(self, target, newfile, parent):
        # 找出父目錄的資訊
        parentInum = self.nameToInum[parent]

        # 父目錄裡還有空間嗎？
        pblock = self.inodes[parentInum].getAddr()
        if self.data[pblock].getFreeEntries() <= 0:
            dprint('*** createLink 失敗：父目錄已無空間 ***')
            return -1

        # print('%s 是否已存在於目錄 %d 中' % (newfile, pblock))
        if self.data[pblock].dirEntryExists(newfile):
            dprint('*** createLink 失敗：名稱重複 ***')
            return -1

        # 接著找出目標檔案的 inode 編號
        tinum = self.nameToInum[target]
        self.inodes[tinum].incRefCnt()

        # 不要增加父目錄的參照計數──只有目錄才需要這麼做
        # self.inodes[parentInum].incRefCnt()

        # 接著加入目錄項目
        tmp = newfile.split('/')
        ename = tmp[len(tmp)-1]
        self.data[pblock].addDirEntry(ename, tinum)
        return tinum

    def createFile(self, parent, newfile, ftype):
        # 找出父目錄的資訊
        parentInum = self.nameToInum[parent]

        # 父目錄裡還有空間嗎？
        pblock = self.inodes[parentInum].getAddr()
        if self.data[pblock].getFreeEntries() <= 0:
            dprint('*** createFile 失敗：父目錄已無空間 ***')
            return -1

        # 必須確保檔名是唯一的
        block = self.inodes[parentInum].getAddr()
        # print('%s 是否已存在於目錄 %d 中' % (newfile, block))
        if self.data[block].dirEntryExists(newfile):
            dprint('*** createFile 失敗：名稱重複 ***')
            return -1

        # 找出空閒的 inode
        inum = self.inodeAlloc()
        if inum == -1:
            dprint('*** createFile 失敗：inode 已用完 ***')
            return -1

        # 如果是目錄，必須配置一個目錄用的資料區塊，存放基本的 (., ..) 項目
        fblock = -1
        if ftype == 'd':
            refCnt = 2
            fblock = self.dataAlloc()
            if fblock == -1:
                dprint('*** createFile 失敗：資料區塊已用完 ***')
                self.inodeFree(inum)
                return -1
            else:
                self.data[fblock].setType('d')
                self.data[fblock].addDirEntry('.',  inum)
                self.data[fblock].addDirEntry('..', parentInum)
        else:
            refCnt = 1

        # 現在可以正式初始化這個 inode 了
        self.inodes[inum].setAll(ftype, fblock, refCnt)

        # 如果這是目錄，增加父目錄的參照計數
        if ftype == 'd':
            self.inodes[parentInum].incRefCnt()

        # 並加入父目錄的目錄項目
        self.data[pblock].addDirEntry(newfile, inum)
        return inum

    def writeFile(self, tfile, data):
        inum = self.nameToInum[tfile]
        curSize = self.inodes[inum].getSize()
        dprint('writeFile：inum:%d cursize:%d refcnt:%d' % (inum, curSize, self.inodes[inum].getRefCnt()))
        if curSize == 1:
            dprint('*** writeFile 失敗：檔案已滿 ***')
            return -1
        fblock = self.dataAlloc()
        if fblock == -1:
            dprint('*** writeFile 失敗：資料區塊已用完 ***')
            return -1
        else:
            self.data[fblock].setType('f')
            self.data[fblock].addData(data)
        self.inodes[inum].setAddr(fblock)
        if printOps:
            print('fd=open("%s", O_WRONLY|O_APPEND); write(fd, buf, BLOCKSIZE); close(fd);' % tfile)
        return 0

    def doDelete(self):
        dprint('doDelete')
        if len(self.files) == 0:
            return -1
        dfile = self.files[int(random.random() * len(self.files))]
        dprint('嘗試 delete(%s)' % dfile)
        return self.deleteFile(dfile)

    def doLink(self):
        dprint('doLink')
        if len(self.files) == 0:
            return -1
        parent = self.dirs[int(random.random() * len(self.dirs))]
        nfile = self.makeName()

        # 隨機挑選目標檔案
        target = self.files[int(random.random() * len(self.files))]
        # 必須是檔案，不能是目錄（在這裡這個條件一定成立）

        # 組出 newfile 的完整路徑名稱
        if parent == '/':
            fullName = parent + nfile
        else:
            fullName = parent + '/' + nfile

        dprint('嘗試 createLink(%s %s %s)' % (target, nfile, parent))
        inum = self.createLink(target, nfile, parent)
        if inum >= 0:
            self.files.append(fullName)
            self.nameToInum[fullName] = inum
            if printOps:
                print('link("%s", "%s");' % (target, fullName))
            return 0
        return -1

    def doCreate(self, ftype):
        dprint('doCreate')
        parent = self.dirs[int(random.random() * len(self.dirs))]
        nfile = self.makeName()
        if ftype == 'd':
            tlist = self.dirs
        else:
            tlist = self.files

        if parent == '/':
            fullName = parent + nfile
        else:
            fullName = parent + '/' + nfile

        dprint('嘗試 createFile(%s %s %s)' % (parent, nfile, ftype))
        inum = self.createFile(parent, nfile, ftype)
        if inum >= 0:
            tlist.append(fullName)
            self.nameToInum[fullName] = inum
            if parent == '/':
                parent = ''
            if ftype == 'd':
                if printOps:
                    print('mkdir("%s/%s");' % (parent, nfile))
            else:
                if printOps:
                    print('creat("%s/%s");' % (parent, nfile))
            return 0
        return -1

    def doAppend(self):
        dprint('doAppend')
        if len(self.files) == 0:
            return -1
        afile = self.files[int(random.random() * len(self.files))]
        dprint('嘗試 writeFile(%s)' % afile)
        data = chr(ord('a') + int(random.random() * 26))
        rc = self.writeFile(afile, data)
        return rc

    def run(self, numRequests):
        self.percentMkdir  = 0.40
        self.percentWrite  = 0.40
        self.percentDelete = 0.20
        self.numRequests   = 20

        print('初始狀態')
        print('')
        self.dump()
        print('')

        for i in range(numRequests):
            if printOps == False:
                print('發生了哪個操作？')
            rc = -1
            while rc == -1:
                r = random.random()
                if r < 0.3:
                    rc = self.doAppend()
                    dprint('doAppend rc:%d' % rc)
                elif r < 0.5:
                    rc = self.doDelete()
                    dprint('doDelete rc:%d' % rc)
                elif r < 0.7:
                    rc = self.doLink()
                    dprint('doLink rc:%d' % rc)
                else:
                    if random.random() < 0.75:
                        rc = self.doCreate('f')
                        dprint('doCreate(f) rc:%d' % rc)
                    else:
                        rc = self.doCreate('d')
                        dprint('doCreate(d) rc:%d' % rc)
                if self.ibitmap.numFree() == 0:
                    print('檔案系統的 inode 已經用完；請透過命令列旗標增加數量後重新執行？')
                    exit(1)
                if self.dbitmap.numFree() == 0:
                    print('檔案系統的資料區塊已經用完；請透過命令列旗標增加數量後重新執行？')
                    exit(1)
            if printState == True:
                print('')
                self.dump()
                print('')
            else:
                print('')
                print('  檔案系統目前狀態為何（inode 點陣圖、inode 內容、資料點陣圖、資料區塊）？')
                print('')

        if printFinal:
            print('')
            print('檔案與目錄摘要：')
            print('')
            print('  檔案：      ', self.files)
            print('  目錄：', self.dirs)
            print('')

#
# 主程式
#
parser = OptionParser()

parser.add_option('-s', '--seed',        default=0,     help='隨機種子',                          action='store', type='int', dest='seed')
parser.add_option('-i', '--numInodes',   default=8,     help='檔案系統中的 inode 數量',           action='store', type='int', dest='numInodes')
parser.add_option('-d', '--numData',     default=8,     help='檔案系統中的資料區塊數量',          action='store', type='int', dest='numData')
parser.add_option('-n', '--numRequests', default=10,    help='要模擬的請求數量',                  action='store', type='int', dest='numRequests')
parser.add_option('-r', '--reverse',     default=False, help='不列印狀態，改成列印操作內容',      action='store_true',        dest='reverse')
parser.add_option('-p', '--printFinal',  default=False, help='列印最終的檔案／目錄清單',          action='store_true',        dest='printFinal')
parser.add_option('-c', '--compute',     default=False, help='幫我計算答案',                      action='store_true',        dest='solve')

(options, args) = parser.parse_args()

print('參數 seed（隨機種子）',            options.seed)
print('參數 numInodes（inode 數量）',      options.numInodes)
print('參數 numData（資料區塊數量）',      options.numData)
print('參數 numRequests（模擬請求數量）',  options.numRequests)
print('參數 reverse（反向模式）',          options.reverse)
print('參數 printFinal（列印最終清單）',   options.printFinal)
print('')

random_seed(options.seed)

if options.reverse:
    printState = False
    printOps   = True
else:
    printState = True
    printOps   = False

if options.solve:
    printOps   = True
    printState = True

printFinal = options.printFinal

#
# 必須對檔案系統產生「合法」的隨機請求！
#

f = fs(options.numInodes, options.numData)

#
# 操作種類：mkdir rmdir : create delete : append write
#

f.run(options.numRequests)

