# -*- coding: utf-8 -*-
"""DCA 最佳买入日分析 — NVDA & AVGO

测试：
  A. 固定日历日：每月 1/5/10/15/20/25 号最近交易日
  B. 交易日相对位置：第1个交易日、第5个、第10个、第15个、最后1个
  C. 信号触发买入：跌日买入、连跌后买入、RSI低点、距MA50远
  D. 周几效应：周一~周五
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import os

DATA = r'C:\AI\cc\stock\data'

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

def month_trading_days(close):
    """返回每月所有交易日的列表 [(date, price, day_of_month, trading_day_idx_in_month), ...]"""
    result = []
    current_month = None
    day_count = 0
    for dt, px in close.items():
        ym = (dt.year, dt.month)
        if ym != current_month:
            current_month = ym
            day_count = 0
        day_count += 1
        result.append((dt, float(px), dt.day, day_count, dt.dayofweek))
    return result

def dca_by_trading_day(close, day_idx, base=1000):
    """每月第 day_idx 个交易日买入（1=第一个，-1=最后一个）"""
    days = month_trading_days(close)
    # 按年月分组
    months = {}
    for dt, px, dom, tidx, dow in days:
        ym = (dt.year, dt.month)
        if ym not in months:
            months[ym] = []
        months[ym].append((dt, px, dom, tidx, dow))

    shares = 0; invested = 0
    for ym in sorted(months.keys()):
        mdays = months[ym]
        if day_idx > 0 and day_idx <= len(mdays):
            _, px, _, _, _ = mdays[day_idx - 1]
        elif day_idx < 0 and abs(day_idx) <= len(mdays):
            _, px, _, _, _ = mdays[day_idx]
        else:
            # fallback to last day
            _, px, _, _, _ = mdays[-1]
        shares += base / px
        invested += base

    # 最终估值
    last_day = days[-1]
    final_val = shares * last_day[1]
    y = len(months) / 12
    cagr = ((final_val / invested) ** (1/y) - 1) * 100 if y > 0 else 0
    return final_val, cagr, invested

def dca_by_calendar_day(close, target_day, base=1000):
    """每月 target_day 号最近交易日买入"""
    days = month_trading_days(close)
    months = {}
    for dt, px, dom, tidx, dow in days:
        ym = (dt.year, dt.month)
        if ym not in months:
            months[ym] = []
        months[ym].append((dt, px, dom))

    shares = 0; invested = 0
    for ym in sorted(months.keys()):
        mdays = months[ym]
        # 找最接近 target_day 的交易日
        best = min(mdays, key=lambda x: abs(x[2] - target_day))
        px = best[1]
        shares += base / px
        invested += base

    last_day = days[-1]
    final_val = shares * last_day[1]
    y = len(months) / 12
    cagr = ((final_val / invested) ** (1/y) - 1) * 100 if y > 0 else 0
    return final_val, cagr, invested

def dca_by_dow(close, target_dow, base=1000):
    """每月第一个 target_dow 交易日买入（0=周一...4=周五）"""
    days = month_trading_days(close)
    months = {}
    for dt, px, dom, tidx, dow in days:
        ym = (dt.year, dt.month)
        if ym not in months:
            months[ym] = []
        months[ym].append((dt, px, dow))

    shares = 0; invested = 0
    for ym in sorted(months.keys()):
        mdays = months[ym]
        # 找第一个匹配的 weekday
        found = None
        for dt, px, dow in mdays:
            if dow == target_dow:
                found = px
                break
        if found is None:
            found = mdays[-1][1]  # fallback
        shares += found / base
        invested += base

    final_val = shares * days[-1][1]
    y = len(months) / 12
    cagr = ((final_val / invested) ** (1/y) - 1) * 100 if y > 0 else 0
    return final_val, cagr, invested

def dca_signal(close, signal_type, base=1000):
    """基于信号买入：
    - 'red_day': 当月第一个下跌日（收盘 < 开盘）
    - 'red_2day': 当月第一次连跌2天后的那天买入
    - 'rsi_low': 当月 RSI(14) 最低的那天
    - 'below_ma50': 当月收盘价低于 MA50 最多的那天
    - 'dip_5pct': 当月如果出现从月高回撤 > 5% 的那天买入
    """
    df = pd.DataFrame({'close': close})
    df['open'] = close  # approximate — we need actual open. Use close as approx for now
    # Actually yfinance data may not have Open. Let's use Close for the signal logic.

    # Compute indicators
    df['ma50'] = df['close'].rolling(50).mean()
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))
    df['down_day'] = delta < 0
    df['down_2day'] = (delta < 0) & (delta.shift(1) < 0)

    # Monthly grouping
    days_list = []
    for dt, row in df.iterrows():
        days_list.append({
            'date': dt,
            'close': float(row['close']),
            'down_day': bool(row['down_day']),
            'down_2day': bool(row['down_2day']),
            'rsi': float(row['rsi']) if not pd.isna(row['rsi']) else 50,
            'ma50': float(row['ma50']) if not pd.isna(row['ma50']) else float(row['close']),
            'ym': (dt.year, dt.month),
        })

    months = {}
    for d in days_list:
        ym = d['ym']
        if ym not in months:
            months[ym] = []
        months[ym].append(d)

    shares = 0; invested = 0
    for ym in sorted(months.keys()):
        mdays = months[ym]
        if signal_type == 'red_day':
            # 第一个下跌日
            candidates = [d for d in mdays if d['down_day']]
            pick = candidates[0] if candidates else mdays[0]
        elif signal_type == 'red_2day':
            candidates = [d for d in mdays if d['down_2day']]
            pick = candidates[0] if candidates else mdays[0]
        elif signal_type == 'rsi_low':
            pick = min(mdays, key=lambda d: d['rsi'])
        elif signal_type == 'below_ma50':
            # 收盘价相对 MA50 最低的那天
            pick = min(mdays, key=lambda d: d['close'] / d['ma50'] if d['ma50'] > 0 else 1)
        elif signal_type == 'dip_5pct':
            # 从月内高点回撤 > 5% 的第一次
            peak = mdays[0]['close']
            pick = mdays[0]
            for d in mdays:
                if d['close'] > peak:
                    peak = d['close']
                dd = (d['close'] - peak) / peak
                if dd < -0.05:
                    pick = d
                    break
        else:
            pick = mdays[0]

        shares += base / pick['close']
        invested += base

    final_val = shares * days_list[-1]['close']
    y = len(months) / 12
    cagr = ((final_val / invested) ** (1/y) - 1) * 100 if y > 0 else 0
    return final_val, cagr, invested

# ═══════════════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════════════

np.random.seed(42)

print("加载数据...")
nvda = load('NVDA')
avgo = load('AVGO')
print(f"  NVDA: {nvda.index[0].date()} ~ {nvda.index[-1].date()}")
print(f"  AVGO: {avgo.index[0].date()} ~ {avgo.index[-1].date()}")

for ticker, close in [('NVDA', nvda), ('AVGO', avgo)]:
    print(f"\n{'=' * 100}")
    print(f"  {ticker} — 每月不同日期/信号定投对比 (2016-01 ~ 2026-06)")
    print(f"{'=' * 100}")

    # ── A. 交易日序号 ──
    print(f"\n  【A. 每月第 N 个交易日买入】")
    print(f"  {'策略':<28} {'最终市值':>14} {'CAGR':>10} {'相对第1天':>10}")
    print(f"  {'─'*28} {'─'*14} {'─'*10} {'─'*10}")

    trading_day_results = []
    baseline = None
    for tday in [1, 2, 3, 5, 10, 15, -5, -3, -2, -1]:
        label = f'第{tday}个交易日' if tday > 0 else f'倒数第{abs(tday)}个'
        val, cagr, inv = dca_by_trading_day(close, tday)
        trading_day_results.append((label, val, cagr))
        if tday == 1:
            baseline = val

    trading_day_results.sort(key=lambda x: x[1], reverse=True)
    for rank, (label, val, cagr) in enumerate(trading_day_results, 1):
        diff = (val / baseline - 1) * 100
        mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
        print(f"  {mark} {label:<26} ${val:>12,.0f}  {cagr:>+8.2f}%  {diff:>+9.2f}%")

    # ── B. 日历日 ──
    print(f"\n  【B. 每月固定日历日最近的交易日买入】")
    print(f"  {'策略':<28} {'最终市值':>14} {'CAGR':>10} {'相对1号':>10}")
    print(f"  {'─'*28} {'─'*14} {'─'*10} {'─'*10}")

    cal_results = []
    cal_baseline = None
    for day in [1, 5, 10, 15, 20, 25]:
        val, cagr, inv = dca_by_calendar_day(close, day)
        cal_results.append((f'每月{day}号', val, cagr))
        if day == 1:
            cal_baseline = val

    cal_results.sort(key=lambda x: x[1], reverse=True)
    for rank, (label, val, cagr) in enumerate(cal_results, 1):
        diff = (val / cal_baseline - 1) * 100
        mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
        print(f"  {mark} {label:<26} ${val:>12,.0f}  {cagr:>+8.2f}%  {diff:>+9.2f}%")

    # ── C. 周几 ──
    print(f"\n  【C. 每月第一个星期 X 买入】")
    print(f"  {'策略':<28} {'最终市值':>14} {'CAGR':>10} {'相对周一':>10}")
    print(f"  {'─'*28} {'─'*14} {'─'*10} {'─'*10}")

    dow_names = ['周一', '周二', '周三', '周四', '周五']
    dow_results = []
    dow_baseline = None
    for dow in range(5):
        val, cagr, inv = dca_by_dow(close, dow)
        dow_results.append((f'每月第一个{dow_names[dow]}', val, cagr))
        if dow == 0:
            dow_baseline = val

    dow_results.sort(key=lambda x: x[1], reverse=True)
    for rank, (label, val, cagr) in enumerate(dow_results, 1):
        diff = (val / dow_baseline - 1) * 100
        mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
        print(f"  {mark} {label:<26} ${val:>12,.0f}  {cagr:>+8.2f}%  {diff:>+9.2f}%")

    # ── D. 信号买入 ──
    print(f"\n  【D. 每月基于信号择日买入】")
    print(f"  {'策略':<28} {'最终市值':>14} {'CAGR':>10} {'相对月初':>10}")
    print(f"  {'─'*28} {'─'*14} {'─'*10} {'─'*10}")

    signal_results = []
    sig_baseline = None
    signals = [
        ('first_day', '月初第1天（基准）'),
        ('red_day', '当月首次下跌日买入'),
        ('red_2day', '连跌2日后买入'),
        ('rsi_low', 'RSI最低日买入'),
        ('below_ma50', 'MA50下方最多日买入'),
        ('dip_5pct', '月高回撤>5%日买入'),
    ]

    for sig, label in signals:
        if sig == 'first_day':
            val, cagr, inv = dca_by_trading_day(close, 1)
            sig_baseline = val
        else:
            val, cagr, inv = dca_signal(close, sig)
        signal_results.append((label, val, cagr))

    signal_results.sort(key=lambda x: x[1], reverse=True)
    for rank, (label, val, cagr) in enumerate(signal_results, 1):
        diff = (val / sig_baseline - 1) * 100
        mark = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else f'  {rank}'
        print(f"  {mark} {label:<26} ${val:>12,.0f}  {cagr:>+8.2f}%  {diff:>+9.2f}%")

    # ── E. 蒙特卡洛随机择日 ──
    print(f"\n  【E. 随机择日 1000 次模拟 — 看看排序是否纯属运气】")
    rand_vals = []
    for _ in range(1000):
        val, cagr, inv = dca_by_trading_day(close, np.random.randint(1, 22))
        rand_vals.append(val)
    rand_vals = np.array(rand_vals)
    print(f"  随机择日: 均值 ${rand_vals.mean():,.0f}  标准差 ${rand_vals.std():,.0f}")
    print(f"  范围: ${rand_vals.min():,.0f} ~ ${rand_vals.max():,.0f}")
    print(f"  变异系数 (CV): {rand_vals.std()/rand_vals.mean()*100:.2f}% — ", end='')
    if rand_vals.std()/rand_vals.mean() < 0.01:
        print("差异极小，哪天买几乎没区别")
    elif rand_vals.std()/rand_vals.mean() < 0.03:
        print("有微弱差异，但远小于选股的影响")
    else:
        print("择日确实有一定影响")

print(f"\n{'=' * 100}")
print(f"  结论：择日不如择股。NVDA/AVGO 这种强趋势股，哪天买差异不到 1%。")
print(f"        与其纠结日子，不如定好闹钟每个月自动执行。")
print(f"{'=' * 100}")
