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

def print_hex(v):
    if v < 16:
        return '0x0%x' % v
    else:
        return '0x%x' % v

def print_bin(word):
    v = bin(word)
    o = '0b'
    o += ('0' * (10 - len(str(v))))
    o += str(v)[2:]
    return o


parser = OptionParser()
parser.add_option('-s', '--seed', default='0', help='隨機種子', action='store', type='int', dest='seed')
parser.add_option('-d', '--data_size', default='4', help='資料字組中的位元組數量', action='store', type='int', dest='data_size')
parser.add_option('-D', '--data', default='', help='以逗號分隔的資料內容', action='store', type='string', dest='data')
parser.add_option('-c', '--compute', help='幫我計算答案', action='store_true', default=False, dest='solve')
(options, args) = parser.parse_args()

print('')
print('選項 seed（隨機種子）', options.seed)
print('選項 data_size（資料位元組數量）', options.data_size)
print('選項 data（資料內容）', options.data)
print('')

random_seed(options.seed)

values = []
if options.data != '':
    tmp = options.data.split(',')
    for t in tmp:
        values.append(int(t))
else:
    for t in range(int(options.data_size)):
        values.append(int(random.random() * 256))


add = 0
xor = 0
fletcher_a, fletcher_b = 0, 0

for value in values:
    add = (add + value) % 256
    xor = xor ^ value
    fletcher_a = (fletcher_a + value) % 255
    fletcher_b = (fletcher_b + fletcher_a) % 255

print('十進位：  ', end=' ')
for word in values:
    print('%10s' % str(word), end=' ')
print('')

print('十六進位：', end=' ')
for word in values:
    print('     ', print_hex(word), end=' ')
print('')

print('二進位：  ', end=' ')
for word in values:
    print(print_bin(word), end=' ')
print('')

print('')
if options.solve:
    print('加總：         ', '%3d      ' % add, '(%s)' % print_bin(add))
    print('互斥或：       ', '%3d      ' % xor, '(%s)' % print_bin(xor))
    print('Fletcher(a,b)：', '%3d,%3d  ' % (fletcher_a, fletcher_b), '(%s,%s)' % (print_bin(fletcher_a), print_bin(fletcher_b)))
else:
    print('加總：    ?')
    print('互斥或：  ?')
    print('Fletcher：?')
print('')


