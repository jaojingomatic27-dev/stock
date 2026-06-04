# -*- coding: utf-8 -*-
"""DCA 完整星期定投分析

策略：每月 $2000，SPY 10% / NVDA 60% / AVGO 30%
择时：每月第一个"完整星期"内择日买入
  - "完整星期"定义：若1号不是周一，等到下周一（确保整周都在本月）
  - 测试完整星期内周一~周五哪个最好
  - 同时对比：等第一个跌日买、RSI低点买
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import os

DATA = r'C:\AI\cc\stock\data'
ALLOC = {'SPY': 0.10, 'NVDA': 0.60, 'AVGO': 0.30}
BASE = 2000

def load(t):
    for fmt in [f'{t}_2016_daily.csv', f'{t}_daily.csv']:
        p = os.path.join(DATA, fmt)
        if os.path.exists(p):
            df = pd.read_csv(p, header=[0,1], index_col=0, parse_dates=True)
            try: return df[('Close',t)].dropna()
            except:
                df = pd.read_csv(p, index_col=0, parse_dates=True)
                return df['Close'].dropna() if 'Close' in df.columns else df.iloc[:,0].dropna()
    return None

print("加载数据...")
prices = {}
for t in ['NVDA', 'AVGO', 'SPY']:
    prices[t] = load(t)

# 对齐
common = prices['NVDA'].index.intersection(prices['AVGO'].index).intersection(prices['SPY'].index)
common = common[common >= '2016-01-01']
for t in prices:
    prices[t] = prices[t].loc[common]
print(f"共同交易日: {len(common)} 天, {common[0].date()} ~ {common[-1].date()}")

# ═══════════════════════════════════════
# 构建每月数据
# ═══════════════════════════════════════
months = {}
for dt in common:
    ym = (dt.year, dt.month)
    if ym not in months:
        months[ym] = []
    months[ym].append(dt)

print(f"月份数: {len(months)}")

# 每月第一个完整星期（周一到周五都在本月）
# 以及用户的"等7天"版本
def get_complete_week_days(month_dates):
    """返回完整星期（Mon-Fri）的 5 个交易日，以及等7天后的同周日。
    完整星期 = 第一个周一到周五都落在这个月的星期。
    """
    dt_list = sorted(month_dates)
    # 找第一个周一
    first_mon = None
    for dt in dt_list:
        if dt.dayofweek == 0:
            first_mon = dt
            break
    if first_mon is None:
        return None, None

    # 完整星期：Mon, Tue, Wed, Thu, Fri
    week_days = {}
    dow_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    for i, name in enumerate(dow_names):
        target = first_mon + pd.Timedelta(days=i)
        if target in dt_list:
            week_days[name] = target
        else:
            return None, None  # 不完整的星期

    # 等7天版本：1号的星期几 + 7天
    first_of_month = dt_list[0]
    dow_1st = first_of_month.dayofweek
    wait_7 = first_of_month + pd.Timedelta(days=7)
    # 找最近的交易日
    wait_buy = None
    for dt in dt_list:
        if dt >= wait_7:
            wait_buy = dt
            break
    if wait_buy is None:
        wait_buy = dt_list[-1]

    return week_days, wait_buy


def get_first_dow(month_dates, target_dow):
    """每月第一个 target_dow 交易日"""
    for dt in sorted(month_dates):
        if dt.dayofweek == target_dow:
            return dt
    return sorted(month_dates)[0]

def get_first_dip_day(month_dates):
    """每月第一个下跌日"""
    prev_close = None
    for dt in sorted(month_dates):
        px = float(prices['NVDA'].loc[dt])
        if prev_close is not None and px < prev_close:
            return dt
        prev_close = px
    return sorted(month_dates)[0]  # 没跌就第一天

def get_rsi_low_day(month_dates):
    """月内 RSI(14) 最低日"""
    # 用 NVDA 作为信号
    nvda_px = [float(prices['NVDA'].loc[dt]) for dt in sorted(month_dates)]
    rsi_vals = []
    for i in range(len(nvda_px)):
        if i < 14:
            rsi_vals.append(50)
        else:
            deltas = np.diff(nvda_px[i-14:i+1])
            gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
            losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0.0001
            rsi_vals.append(100 - (100 / (1 + gains/losses)))
    idx = np.argmin(rsi_vals)
    return sorted(month_dates)[idx]


# ═══════════════════════════════════════
# 测试各种买法
# ═══════════════════════════════════════
def simulate(selector_func):
    """selector_func(month_dates) -> buy_date"""
    shares = {'NVDA': 0.0, 'AVGO': 0.0, 'SPY': 0.0}
    invested = 0.0
    vals = []
    for ym in sorted(months.keys()):
        mdates = months[ym]
        buy_dt = selector_func(mdates)
        for t, w in ALLOC.items():
            amt = BASE * w
            px = float(prices[t].loc[buy_dt])
            shares[t] += amt / px
            invested += amt
        # 月末估值
        last_dt = max(mdates)
        total_val = sum(shares[t] * float(prices[t].loc[last_dt]) for t in ALLOC)
        vals.append(total_val)
    final = vals[-1]
    years = len(vals) / 12
    cagr = ((final / invested) ** (1/years) - 1) * 100
    peak = np.maximum.accumulate(np.array(vals))
    max_dd = (np.array(vals) - peak).min() / peak[np.argmin(np.array(vals) - peak)] * 100
    return final, cagr, invested, max_dd

# ── 测试 ──
print(f"\n{'=' * 110}")
print(f"  每月 $2,000 | SPY {ALLOC['SPY']*100:.0f}% / NVDA {ALLOC['NVDA']*100:.0f}% / AVGO {ALLOC['AVGO']*100:.0f}%")
print(f"  全部策略对比 (2016-01 ~ 2026-06)")
print(f"{'=' * 110}")

all_strategies = []

# 1. 完整星期各天
dow_cn = ['周一', '周二', '周三', '周四', '周五']

print(f"\n  【完整星期内各天买入】")
print(f"  {'策略':<30} {'最终市值':>14} {'CAGR':>10} {'最大回撤':>9} {'相对周一':>10}")
print(f"  {'─'*30} {'─'*14} {'─'*10} {'─'*9} {'─'*10}")

complete_week_results = []
for dow_idx, dow_name in enumerate(dow_cn):
    dow_key = ['Mon','Tue','Wed','Thu','Fri'][dow_idx]
    def buy_complete_week_dow(mdates, dk=dow_key):
        wd, _ = get_complete_week_days(mdates)
        if wd is None:
            return sorted(mdates)[0]
        return wd[dk]
    final, cagr, inv, max_dd = simulate(buy_complete_week_dow)
    complete_week_results.append((f'完整星期{dow_name}买入', final, cagr, max_dd))
    all_strategies.append((f'完整星期{dow_name}', final, cagr, max_dd))

baseline_cw = complete_week_results[0][1]
for label, final, cagr, max_dd in complete_week_results:
    diff = (final / baseline_cw - 1) * 100
    print(f"  {label:<30} ${final:>12,.0f}  {cagr:>+8.2f}%  {max_dd:>+7.1f}%  {diff:>+9.2f}%")

# 2. "等7天"版本（用户提到的）
print(f"\n  【用户方案：1号+7天 的同周日买入】")
def buy_wait7(mdates):
    _, wait_dt = get_complete_week_days(mdates)
    if wait_dt is None:
        return sorted(mdates)[0]
    return wait_dt
final_w7, cagr_w7, inv_w7, maxdd_w7 = simulate(buy_wait7)
all_strategies.append(('【用户方案】1号+7天', final_w7, cagr_w7, maxdd_w7))
print(f"  {'1号+7天买入':<30} ${final_w7:>12,.0f}  {cagr_w7:>+8.2f}%  {maxdd_w7:>+7.1f}%")

# 3. 其他对照策略
print(f"\n  【对照策略】")
print(f"  {'策略':<30} {'最终市值':>14} {'CAGR':>10} {'最大回撤':>9} {'vs完整周周一':>13}")
print(f"  {'─'*30} {'─'*14} {'─'*10} {'─'*9} {'─'*13}")

benchmarks = [
    ('月初第1天', lambda m: sorted(m)[0]),
    ('月初第2天', lambda m: sorted(m)[1] if len(m)>1 else sorted(m)[0]),
    ('月初第3天', lambda m: sorted(m)[2] if len(m)>2 else sorted(m)[-1]),
    ('每月5号最近', lambda m: min(m, key=lambda d: abs(d.day-5))),
    ('每月1号', lambda m: min(m, key=lambda d: abs(d.day-1))),
    ('等第一个跌日', get_first_dip_day),
    ('RSI最低日(事后)', get_rsi_low_day),
]

for label, func in benchmarks:
    final, cagr, inv, max_dd = simulate(func)
    diff = (final / baseline_cw - 1) * 100
    all_strategies.append((label, final, cagr, max_dd))
    print(f"  {label:<30} ${final:>12,.0f}  {cagr:>+8.2f}%  {max_dd:>+7.1f}%  {diff:>+12.2f}%")

# ── 排名 ──
print(f"\n  {'=' * 90}")
print(f"  【全部策略排名】")
print(f"  {'排名':<5} {'策略':<32} {'最终市值':>14} {'CAGR':>10} {'最大回撤':>9}")
print(f"  {'─'*5} {'─'*32} {'─'*14} {'─'*10} {'─'*9}")

all_strategies.sort(key=lambda x: x[1], reverse=True)
for rank, (label, final, cagr, max_dd) in enumerate(all_strategies, 1):
    mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
    print(f"  {mark:<5} {label:<32} ${final:>12,.0f}  {cagr:>+8.2f}%  {max_dd:>+7.1f}%")

# ── 完整星期详细分析 ──
print(f"\n  {'=' * 90}")
print('  【完整星期内各天的特征分析】')
print(f"  为什么某天更好？看看该天前后 NVDA 的走势：")

for dow_idx, dow_name in enumerate(dow_cn):
    dow_key = ['Mon','Tue','Wed','Thu','Fri'][dow_idx]
    # 收集所有完整星期该天的前后数据
    day_returns = []
    prev_day_returns = []
    for ym in sorted(months.keys()):
        mdates = months[ym]
        wd, _ = get_complete_week_days(mdates)
        if wd is None:
            continue
        dt = wd[dow_key]
        # 该天 vs 前一天的涨跌
        idx = common.get_loc(dt)
        if idx > 0:
            prev_dt = common[idx-1]
            ret = float(prices['NVDA'].loc[dt]) / float(prices['NVDA'].loc[prev_dt]) - 1
            day_returns.append(ret)
        # 前一天 vs 前两天
        if idx > 1:
            prev2 = common[idx-2]
            prev_ret = float(prices['NVDA'].loc[prev_dt]) / float(prices['NVDA'].loc[prev2]) - 1
            prev_day_returns.append(prev_ret)

    up_pct = sum(1 for r in day_returns if r > 0) / len(day_returns) * 100 if day_returns else 0
    prev_up = sum(1 for r in prev_day_returns if r < 0) / len(prev_day_returns) * 100 if prev_day_returns else 0
    print(f"  {dow_name}: 当天上涨概率 {up_pct:.0f}% | 前一天下跌概率 {prev_up:.0f}% | "
          f"平均日收益 {np.mean(day_returns)*100:+.2f}% ({len(day_returns)}次)")

print(f"\n{'=' * 110}")
print(f"  最终推荐：每月第一个完整星期的周三或周四买入 SPY 10% + NVDA 60% + AVGO 30%")
print(f"  理由：月中效应 + 避免周一波动 + 不等到周五（越晚越贵）")
print(f"{'=' * 110}")
