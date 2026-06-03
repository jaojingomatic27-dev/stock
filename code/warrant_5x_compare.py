# -*- coding: utf-8 -*-
"""
一年前各投$1000：NVDA/MU 正股 vs 5倍杠杆权证
模拟5x每日重置杠杆权证，检查敲出风险
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

INVEST = 1000
LEVERAGE = 5.0

print("=" * 80)
print("  正股 vs 5x杠杆权证：$1,000 各投NVDA和MU，持有一年")
print(f"  期间：2025-06-02 → 2026-06-03")
print("=" * 80)

for ticker in ["NVDA", "MU"]:
    path = rf"C:\AI\cc\stock\{ticker}_daily.csv"
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()

    start_price = float(close.iloc[0])
    end_price = float(close.iloc[-1])
    min_price = float(close.min())
    max_price = float(close.max())

    print(f"\n{'─' * 80}")
    print(f"  {ticker}")
    print(f"{'─' * 80}")
    print(f"  股价：${start_price:.2f} → ${end_price:.2f}")
    print(f"  区间最低：${min_price:.2f}  最高：${max_price:.2f}")

    # ============================================================
    # 正股 Buy & Hold
    # ============================================================
    stock_shares = INVEST / start_price
    stock_final = stock_shares * end_price
    stock_ret = (stock_final / INVEST - 1) * 100

    print(f"\n  >>> 正股 Buy & Hold <<<")
    print(f"  买入 ${INVEST} → {stock_shares:.4f} 股")
    print(f"  最终价值：${stock_final:,.2f}")
    print(f"  收益率：{stock_ret:+.1f}%")

    # ============================================================
    # 5x 杠杆权证（每日重置）
    # ============================================================
    daily_ret = close.pct_change().fillna(0).values
    n = len(daily_ret)

    # 5x杠杆权证：每日收益 = 5 × 正股日收益
    warrant_vals = np.zeros(n)
    warrant_vals[0] = INVEST

    knocked_out = False
    ko_day = None
    ko_price = None
    max_warrant_val = INVEST

    for i in range(1, n):
        # 5x杠杆日收益
        w_daily_ret = LEVERAGE * daily_ret[i]
        warrant_vals[i] = warrant_vals[i-1] * (1 + w_daily_ret)

        # 追踪最高值
        if warrant_vals[i] > max_warrant_val:
            max_warrant_val = warrant_vals[i]

        # 敲出检查：权证价值跌破初始值的5%（即亏损95%以上）
        if not knocked_out and warrant_vals[i] < INVEST * 0.05:
            knocked_out = True
            ko_day = i
            ko_price = float(close.iloc[i])
            warrant_vals[i] = 0.0
            # 后面全是0
            for j in range(i+1, n):
                warrant_vals[j] = 0.0
            break

    warrant_final = warrant_vals[-1]
    warrant_ret = (warrant_final / INVEST - 1) * 100
    warrant_dd = (warrant_vals[:ko_day+1] if knocked_out else warrant_vals).min() / max_warrant_val * 100 - 100 if max_warrant_val > 0 else -100

    print(f"\n  >>> 5x 杠杆权证（每日重置） <<<")
    if knocked_out:
        ko_dt = close.index[ko_day].strftime("%Y-%m-%d")
        print(f"  *** 敲出!!! ***")
        print(f"  敲出日期：{ko_dt}  (第{ko_day}个交易日)")
        print(f"  敲出时正股价：${ko_price:.2f}")
        # 计算敲出当天的跌幅
        ko_daily_drop = daily_ret[ko_day] * 100
        print(f"  敲出日正股跌幅：{ko_daily_drop:.1f}% → 权证跌幅：{ko_daily_drop * LEVERAGE:.1f}%")
        print(f"  最终价值：$0.00")
        print(f"  收益率：-100.0%  (全部亏损)")
    else:
        print(f"  未敲出 ✓")
        print(f"  最终价值：${warrant_final:,.2f}")
        print(f"  收益率：{warrant_ret:+.1f}%")
        print(f"  最大回撤：{warrant_dd:.1f}%")

    # ============================================================
    # 逐日细节：最大单日波动
    # ============================================================
    max_up_day = daily_ret.max() * 100
    max_down_day = daily_ret.min() * 100

    print(f"\n  >>> 风险指标 <<<")
    print(f"  正股最大单日涨幅：{max_up_day:+.1f}% → 权证当日：{max_up_day * LEVERAGE:+.1f}%")
    print(f"  正股最大单日跌幅：{max_down_day:.1f}% → 权证当日：{max_down_day * LEVERAGE:.1f}%")

    # 理论敲出阈值：单日跌 -20% 会敲出（5x = -100%）
    # 但累积亏损到 -95% 也会敲出
    worst_streak_days = 0
    worst_streak_cum = 0.0
    cum = 0.0
    for r in daily_ret:
        if r < 0:
            cum += r
            worst_streak_days += 1
        else:
            if cum < worst_streak_cum:
                worst_streak_cum = cum
            cum = 0.0
    if cum < worst_streak_cum:
        worst_streak_cum = cum

    # 计算5x杠杆下最大连续回撤
    w_cum = 1.0
    w_peak = 1.0
    w_max_dd_pct = 0.0
    w_max_dd_dt = None
    for i in range(1, n):
        w_cum *= (1 + LEVERAGE * daily_ret[i])
        if w_cum > w_peak:
            w_peak = w_cum
        dd = (w_cum - w_peak) / w_peak * 100
        if dd < w_max_dd_pct:
            w_max_dd_pct = dd
            w_max_dd_dt = close.index[i]

    if not knocked_out:
        print(f"  权证最大回撤：{w_max_dd_pct:.1f}% (日期：{w_max_dd_dt.strftime('%Y-%m-%d') if w_max_dd_dt else 'N/A'})")

    # ============================================================
    # 对比总结
    # ============================================================
    print(f"\n  >>> 对比 <<<")
    print(f"  {'':<20} {'投入':>10} {'最终价值':>12} {'收益率':>10}")
    print(f"  {'正股 B&H':<20} ${INVEST:>9,.0f} ${stock_final:>11,.2f} {stock_ret:>+9.1f}%")
    if knocked_out:
        print(f"  {'5x 杠杆权证':<20} ${INVEST:>9,.0f} ${0:>11,.2f} {-100:>+9.1f}%  *** 敲出 ***")
    else:
        print(f"  {'5x 杠杆权证':<20} ${INVEST:>9,.0f} ${warrant_final:>11,.2f} {warrant_ret:>+9.1f}%")
        multiple = warrant_final / stock_final
        print(f"  {'权证/正股倍数':<20} {'':>10} {'':>12} {multiple:>9.1f}x")

print(f"\n{'=' * 80}")
print("  总结")
print(f"{'=' * 80}")
print("""
  杠杆权证的关键风险：
  1. 单日暴跌：正股跌-20% → 5x权证跌-100%，直接归零
  2. 连续阴跌：不需要单日跌20%，连续几天各跌5%也能把权证跌残
  3. 波动率衰减（volatility decay）：杠杆ETF/权证在震荡市中会持续损耗
  4. 即使正股最终上涨，权证也可能在途中因波动而价值大减

  杠杆权证只适合：
  - 强烈看涨且确信无大幅回调
  - 能承受100%亏损
  - 短期持有，不宜长持（波动衰减随时间累积）
""")
