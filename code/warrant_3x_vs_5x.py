# -*- coding: utf-8 -*-
"""
3x vs 5x 杠杆权证对比
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

INVEST = 1000

def simulate_leveraged(close, leverage, knock_threshold=0.05):
    daily_ret = close.pct_change().fillna(0).values
    n = len(daily_ret)
    vals = np.zeros(n)
    vals[0] = INVEST
    max_v = INVEST
    knocked_out = False
    ko_day = None
    ko_price = None

    for i in range(1, n):
        vals[i] = vals[i-1] * (1 + leverage * daily_ret[i])
        if vals[i] > max_v:
            max_v = vals[i]
        if not knocked_out and vals[i] < INVEST * knock_threshold:
            knocked_out = True
            ko_day = i
            ko_price = float(close.iloc[i])
            for j in range(i, n):
                vals[j] = 0.0
            break

    w_peak = 1.0
    w_cum = 1.0
    max_dd = 0.0
    max_dd_dt = None
    for i in range(1, n if not knocked_out else ko_day + 1):
        w_cum *= (1 + leverage * daily_ret[i])
        if w_cum > w_peak:
            w_peak = w_cum
        dd = (w_cum - w_peak) / w_peak * 100
        if dd < max_dd:
            max_dd = dd
            max_dd_dt = close.index[i]

    return {
        "final_val": vals[-1],
        "ret_pct": (vals[-1] / INVEST - 1) * 100,
        "ko": knocked_out,
        "ko_day": ko_day,
        "ko_date": close.index[ko_day] if ko_day else None,
        "ko_price": ko_price,
        "max_dd": max_dd,
        "max_dd_dt": max_dd_dt,
        "daily_rets": daily_ret,
    }

print("=" * 85)
print("  正股 vs 3x vs 5x 杠杆权证：各投 $1,000，持有一年")
print("  2025-06-02 → 2026-06-03")
print("=" * 85)

for ticker in ["NVDA", "MU"]:
    path = rf"C:\AI\cc\stock\{ticker}_daily.csv"
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()

    start_p = float(close.iloc[0])
    end_p = float(close.iloc[-1])
    min_p = float(close.min())
    max_p = float(close.max())

    # Stock
    shares = INVEST / start_p
    stock_final = shares * end_p
    stock_ret = (stock_final / INVEST - 1) * 100

    # 3x and 5x
    r3 = simulate_leveraged(close, 3.0)
    r5 = simulate_leveraged(close, 5.0)

    print(f"\n{'─' * 85}")
    print(f"  {ticker}: ${start_p:.2f} → ${end_p:.2f}  (最低 ${min_p:.2f}, 最高 ${max_p:.2f})")
    print(f"{'─' * 85}")

    # Header
    print(f"  {'':<18} {'投入':>8} {'最终价值':>14} {'收益率':>12} {'最大回撤':>10} {'敲出':>6}")
    print(f"  {'-' * 70}")

    # Stock row
    print(f"  {'正股 B&H':<18} ${INVEST:>7,.0f} ${stock_final:>13,.2f} {stock_ret:>+11.1f}% {'N/A':>10} {'否':>6}")

    # 3x row
    ko3_str = "<<敲出!!>>" if r3["ko"] else "否"
    dd3_str = f"{r3['max_dd']:.1f}%" if not r3["ko"] else "N/A"
    if r3["ko"]:
        ko_dt = r3["ko_date"].strftime("%Y-%m-%d")
        print(f"  {'3x 杠杆权证':<18} ${INVEST:>7,.0f} ${0:>13,.2f} {-100:>+11.1f}% {dd3_str:>10} {ko3_str:>6}  ({ko_dt})")
    else:
        mult3 = r3["final_val"] / stock_final
        print(f"  {'3x 杠杆权证':<18} ${INVEST:>7,.0f} ${r3['final_val']:>13,.2f} {r3['ret_pct']:>+11.1f}% {dd3_str:>10} {ko3_str:>6}  ({mult3:.1f}x vs 正股)")

    # 5x row
    ko5_str = "<<敲出!!>>" if r5["ko"] else "否"
    dd5_str = f"{r5['max_dd']:.1f}%" if not r5["ko"] else "N/A"
    if r5["ko"]:
        ko_dt = r5["ko_date"].strftime("%Y-%m-%d")
        print(f"  {'5x 杠杆权证':<18} ${INVEST:>7,.0f} ${0:>13,.2f} {-100:>+11.1f}% {dd5_str:>10} {ko5_str:>6}  ({ko_dt})")
    else:
        mult5 = r5["final_val"] / stock_final
        print(f"  {'5x 杠杆权证':<18} ${INVEST:>7,.0f} ${r5['final_val']:>13,.2f} {r5['ret_pct']:>+11.1f}% {dd5_str:>10} {ko5_str:>6}  ({mult5:.1f}x vs 正股)")

    # Risk metrics
    max_up = float(close.pct_change().max() * 100)
    max_dn = float(close.pct_change().min() * 100)
    print(f"\n  >>> 风险指标 <<<")
    print(f"  正股最大单日涨: {max_up:+.1f}% | 3x权证当日: {max_up*3:+.1f}% | 5x权证当日: {max_up*5:+.1f}%")
    print(f"  正股最大单日跌: {max_dn:+.1f}% | 3x权证当日: {max_dn*3:+.1f}% | 5x权证当日: {max_dn*5:+.1f}%")
    print(f"  敲出阈值: 亏损-95%")

print(f"\n{'=' * 85}")
print("  结论")
print(f"{'=' * 85}")
print("""
  3x vs 5x 关键差异：
  ┌──────────┬────────────────────┬────────────────────┐
  │          │ 3x 杠杆            │ 5x 杠杆            │
  ├──────────┼────────────────────┼────────────────────┤
  │ 敲出风险 │ 低（需正股跌~32%） │ 中（需正股跌~19%） │
  │ 波动衰减 │ 较小               │ 较大               │
  │ 趋势收益 │ 3倍复利            │ 5倍复利            │
  │ 回撤幅度 │ 可控               │ 可能触及-90%+      │
  │ 适合场景 │ 中等信心+趋势      │ 高信心+强趋势      │
  └──────────┴────────────────────┴────────────────────┘
""")
