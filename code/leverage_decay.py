# -*- coding: utf-8 -*-
"""分析 6 只 Turbo 权证的杠杆衰减曲线"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

strikes = {'NVDA': 176.54, 'MSFT': 340.72, 'ORCL': 187.35, 'PLTR': 97.62, 'SMCI': 30.00, 'TSLA': 281.36}
currents = {'NVDA': 214.75, 'MSFT': 427.34, 'ORCL': 230.33, 'PLTR': 142.20, 'SMCI': 47.42, 'TSLA': 423.70}

print()
print('杠杆衰减曲线（从当前股价到涨100%）：')
print('=' * 80)
print(f"{'':>8}", end='')
for pct in [0, 20, 40, 60, 80, 100]:
    print(f"{'涨'+str(pct)+'%':>10}", end='')
print(f"{'  KO安全边际':>14}")
print('-' * 80)

for t in ['NVDA', 'MSFT', 'ORCL', 'PLTR', 'SMCI', 'TSLA']:
    s = strikes[t]
    c = currents[t]
    print(f'{t:>8}', end='')
    for pct in [0, 20, 40, 60, 80, 100]:
        px = c * (1 + pct/100)
        lev = px / (px - s) if px > s else float('inf')
        print(f'{lev:>8.1f}x ', end='')
    margin = (c - s) / c * 100
    print(f'{margin:>12.1f}%')

print()
print('结论：')
print('  1. 当前杠杆 2.7x-5.6x。涨 50% 后全部跌破 3x，涨 100% 后降到 1.3-2.3x。')
print('  2. 低杠杆下 40% 回撤阈值几乎不会触发，轮动策略形同虚设。')
print('  3. 建议：杠杆 < 3x 时换到新 Turbo（strike≈股价×0.80），大约每 6-12 个月操作一次。')
print('  4. 换仓也有代价：bid-ask spread + 新高 KO 风险，需权衡。')
