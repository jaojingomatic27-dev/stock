# -*- coding: utf-8 -*-
"""NVDA + AVGO + SPY 定投组合优化 — 找到收益/风险最优的持仓比例

测试所有整数比例组合（步长 5%），找到不同风险偏好下的最优配置。
每月固定 $1000，按比例分配到三只标的。
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import os, itertools

DATA = r'C:\AI\cc\stock\data'

def load(t):
    for fmt in [f'{t}_2016_daily.csv', f'{t}_daily.csv']:
        p = os.path.join(DATA, fmt)
        if os.path.exists(p):
            df = pd.read_csv(p, header=[0,1], index_col=0, parse_dates=True)
            try:
                return df[('Close',t)].dropna()
            except:
                df = pd.read_csv(p, index_col=0, parse_dates=True)
                return df['Close'].dropna() if 'Close' in df.columns else df.iloc[:,0].dropna()
    return None


def dca_monthly(close, start='2016-01-01', base=1000):
    """返回每月市值序列。"""
    close = close[close.index >= start]
    firsts = []; prev = None
    for dt, px in close.items():
        ym = (dt.year, dt.month)
        if ym != prev:
            firsts.append((dt, float(px)))
            prev = ym

    shares = 0; invested = 0; vals = []; dates = []
    for dt, px in firsts:
        shares += base / px
        invested += base
        vals.append(shares * px)
        dates.append(dt)
    return np.array(vals), dates, invested


def metrics(vals, invested):
    """从市值序列计算指标。"""
    y = len(vals) / 12
    cagr = ((vals[-1]/invested)**(1/y)-1)*100 if y > 0 else 0
    peak = np.maximum.accumulate(vals)
    dd = (vals - peak) / peak * 100
    max_dd = dd.min()
    # Annual returns for min-year calculation
    annual = []
    for i in range(12, len(vals), 12):
        yr_ret = (vals[i] - vals[i-12]) / vals[i-12] * 100
        annual.append(yr_ret)
    worst_year = min(annual) if annual else 0
    mr = (vals[1:]-vals[:-1])/vals[:-1]
    sharpe = np.sqrt(12)*mr.mean()/mr.std() if mr.std()>0 else 0
    # 月度胜率
    monthly = (vals[1:]-vals[:-1])/vals[:-1]
    win_months = (monthly > 0).sum() / len(monthly) * 100
    return {'cagr': cagr, 'max_dd': max_dd, 'sharpe': sharpe,
            'worst_year': worst_year, 'final': vals[-1], 'invested': invested,
            'win_months': win_months, 'years': y}


# 加载数据
print("加载数据...")
data = {}
for t in ['NVDA', 'AVGO', 'SPY']:
    c = load(t)
    data[t] = c
    print(f"  {t}: {c.index[0].date()} ~ {c.index[-1].date()} ({len(c)}d)")

# 对齐日期：找到三者的共同交易日
common_idx = data['NVDA'].index.intersection(data['AVGO'].index).intersection(data['SPY'].index)
common_idx = common_idx[common_idx >= '2016-01-01']
print(f"\n共同交易日: {len(common_idx)} 天，{common_idx[0].date()} ~ {common_idx[-1].date()}")

prices = {
    'NVDA': data['NVDA'].loc[common_idx],
    'AVGO': data['AVGO'].loc[common_idx],
    'SPY': data['SPY'].loc[common_idx],
}

# 找每月第一个共同交易日
firsts = []; prev = None
for dt in common_idx:
    ym = (dt.year, dt.month)
    if ym != prev:
        firsts.append(dt)
        prev = ym

print(f"共同定投月: {len(firsts)} 期")

# 测试所有比例（步长 5%）
STEP = 5
weights_list = []
for w_nvda in range(0, 101, STEP):
    for w_avgo in range(0, 101 - w_nvda, STEP):
        w_spy = 100 - w_nvda - w_avgo
        weights_list.append((w_nvda, w_avgo, w_spy))

print(f"\n测试 {len(weights_list)} 种比例组合...")

results = []
for w_nvda, w_avgo, w_spy in weights_list:
    nvda_vals, _, _ = dca_monthly(prices['NVDA'])
    avgo_vals, _, _ = dca_monthly(prices['AVGO'])
    spy_vals, _, _ = dca_monthly(prices['SPY'])

    # 按比例合成
    total_invested = 0
    combined_vals = np.zeros(len(firsts))
    shares = {'NVDA': 0, 'AVGO': 0, 'SPY': 0}

    for i, dt in enumerate(firsts):
        monthly = 1000
        # NVDA
        nvda_amt = monthly * w_nvda / 100
        shares['NVDA'] += nvda_amt / prices['NVDA'].loc[dt]
        # AVGO
        avgo_amt = monthly * w_avgo / 100
        shares['AVGO'] += avgo_amt / prices['AVGO'].loc[dt]
        # SPY
        spy_amt = monthly * w_spy / 100
        shares['SPY'] += spy_amt / prices['SPY'].loc[dt]

        total_invested += monthly
        combined_vals[i] = (shares['NVDA'] * prices['NVDA'].loc[dt] +
                            shares['AVGO'] * prices['AVGO'].loc[dt] +
                            shares['SPY'] * prices['SPY'].loc[dt])

    m = metrics(combined_vals, total_invested)
    m['w_nvda'] = w_nvda
    m['w_avgo'] = w_avgo
    m['w_spy'] = w_spy
    m['label'] = f'{w_nvda:02d}/{w_avgo:02d}/{w_spy:02d}'
    results.append(m)

# ═══════════════════════════════════════════════════════
# 输出：不同目标的最优配置
# ═══════════════════════════════════════════════════════

print(f"\n{'=' * 110}")
print(f"  NVDA + AVGO + SPY 定投组合优化 — 每月 $1000 | {firsts[0].date()} ~ {firsts[-1].date()} ({len(firsts)}期)")
print(f"{'=' * 110}")

# ── 1. 最大 Sharpe（风险调整最优）──
print(f"\n  【一、最大 Sharpe 比率 — 每单位风险赚最多钱】")
sorted_sharpe = sorted(results, key=lambda r: r['sharpe'], reverse=True)
print(f"  {'排名':<5} {'NVDA%':<8} {'AVGO%':<8} {'SPY%':<8} {'终值':>12} {'CAGR':>8} {'最大回撤':>8} {'Sharpe':>7} {'最差年':>8} {'月胜率':>7}")
print(f"  {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*12} {'─'*8} {'─'*8} {'─'*7} {'─'*8} {'─'*7}")
for rank, r in enumerate(sorted_sharpe[:10], 1):
    mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
    print(f"  {mark:<5} {r['w_nvda']:>5}%   {r['w_avgo']:>5}%   {r['w_spy']:>5}%   "
          f"${r['final']:>10,.0f}  {r['cagr']:>+6.1f}%  {r['max_dd']:>+6.1f}%  "
          f"{r['sharpe']:>6.2f}  {r['worst_year']:>+6.1f}%  {r['win_months']:>5.1f}%")

# ── 2. 最低回撤但年化 > 15% ──
print(f"\n  【二、安全优先 — 最大回撤最低 且 CAGR > 15%】")
safe = [r for r in results if r['cagr'] > 15]
safe.sort(key=lambda r: -r['max_dd'])  # smallest DD = closest to 0
print(f"  {'排名':<5} {'NVDA%':<8} {'AVGO%':<8} {'SPY%':<8} {'终值':>12} {'CAGR':>8} {'最大回撤':>8} {'Sharpe':>7} {'最差年':>8}")
print(f"  {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*12} {'─'*8} {'─'*8} {'─'*7} {'─'*8}")
for rank, r in enumerate(safe[:10], 1):
    mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
    print(f"  {mark:<5} {r['w_nvda']:>5}%   {r['w_avgo']:>5}%   {r['w_spy']:>5}%   "
          f"${r['final']:>10,.0f}  {r['cagr']:>+6.1f}%  {r['max_dd']:>+6.1f}%  "
          f"{r['sharpe']:>6.2f}  {r['worst_year']:>+6.1f}%")

# ── 3. 不同风险偏好推荐 ──
print(f"\n  【三、按风险偏好推荐】")
print()

preferences = [
    ('极度保守', lambda r: r['max_dd'] > -22),
    ('保守', lambda r: r['max_dd'] > -28),
    ('均衡', lambda r: r['max_dd'] > -35),
    ('进取', lambda r: r['max_dd'] > -45),
    ('激进', lambda r: r['cagr'] > 0),  # all
]

for name, filt in preferences:
    candidates = [r for r in results if filt(r)]
    if not candidates:
        continue
    # Pick best by Sharpe within the DD constraint
    best = max(candidates, key=lambda r: r['sharpe'])
    print(f"  {'─'*80}")
    print(f"  【{name}型】最大回撤 ≤ {abs(best['max_dd']):.0f}%")
    print(f"    配置:  NVDA {best['w_nvda']}%  +  AVGO {best['w_avgo']}%  +  SPY {best['w_spy']}%")
    print(f"    月供:  NVDA ${best['w_nvda']*10}  +  AVGO ${best['w_avgo']*10}  +  SPY ${best['w_spy']*10}")
    print(f"    结果:  终值 ${best['final']:,.0f}  |  CAGR {best['cagr']:+.1f}%  |  最差年 {best['worst_year']:+.1f}%  |  Sharpe {best['sharpe']:.2f}")
    print()

# ── 4. 极端配置对比 ──
print(f"  {'─'*80}")
print(f"  【四、极端配置对照表】")
print(f"  {'策略':<25} {'NVDA:AVGO:SPY':>16} {'终值':>12} {'CAGR':>8} {'最大回撤':>8} {'最差年':>8} {'Sharpe':>7}")
print(f"  {'─'*25} {'─'*16} {'─'*12} {'─'*8} {'─'*8} {'─'*8} {'─'*7}")

extremes = [
    ('100% SPY', {'w_nvda': 0, 'w_avgo': 0, 'w_spy': 100}),
    ('100% AVGO', {'w_nvda': 0, 'w_avgo': 100, 'w_spy': 0}),
    ('100% NVDA', {'w_nvda': 100, 'w_avgo': 0, 'w_spy': 0}),
    ('各 1/3 (~)', {'w_nvda': 35, 'w_avgo': 35, 'w_spy': 30}),
    ('AVGO 50 + SPY 50', {'w_nvda': 0, 'w_avgo': 50, 'w_spy': 50}),
    ('Sharpe 最优', None),  # use sorted_sharpe[0]
    ('安全型最优', None),   # use safe[0]
]

# Find the actual results for the fixed configs
for i, (name, config) in enumerate(extremes):
    if config is None:
        if 'Sharpe' in name:
            r = sorted_sharpe[0]
        else:
            r = safe[0]
    else:
        r = next(x for x in results if x['w_nvda'] == config['w_nvda']
                 and x['w_avgo'] == config['w_avgo'] and x['w_spy'] == config['w_spy'])
    print(f"  {name:<25} {r['label']:>16} "
          f"${r['final']:>10,.0f}  {r['cagr']:>+6.1f}%  {r['max_dd']:>+6.1f}%  "
          f"{r['worst_year']:>+6.1f}%  {r['sharpe']:>6.2f}")

# ── 5. 效率前沿简表（性价比排名）──
print(f"\n  {'─'*80}")
print('  【五、"性价比"排名 — CAGR/|MaxDD| 比值最高的前 10】')
print(f"  {'排名':<5} {'NVDA%':<8} {'AVGO%':<8} {'SPY%':<8} {'终值':>12} {'CAGR':>8} {'MaxDD':>8} {'性价比':>8} {'Sharpe':>7}")
print(f"  {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*12} {'─'*8} {'─'*8} {'─'*8} {'─'*7}")

for r in results:
    r['efficiency'] = r['cagr'] / abs(r['max_dd']) if r['max_dd'] != 0 else 0

results.sort(key=lambda r: r['efficiency'], reverse=True)
for rank, r in enumerate(results[:10], 1):
    mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
    print(f"  {mark:<5} {r['w_nvda']:>5}%   {r['w_avgo']:>5}%   {r['w_spy']:>5}%   "
          f"${r['final']:>10,.0f}  {r['cagr']:>+6.1f}%  {r['max_dd']:>+6.1f}%  "
          f"{r['efficiency']:>7.3f}  {r['sharpe']:>6.2f}")

print(f"\n{'=' * 110}")
print(f"  结论: 没有万能比例。你的风险承受力决定最优配置。")
print(f"        如果你能忍受 -35% 回撤 → 多配 NVDA")
print(f"        如果你想睡得着觉     → 多配 AVGO + SPY")
print(f"{'=' * 110}")
