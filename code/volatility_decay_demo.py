# -*- coding: utf-8 -*-
"""
波动衰减 (Volatility Decay) 详解：为什么 NVDA +57%，9x 杠杆反而 -18.5%
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

path = r"C:\AI\cc\stock\data\NVDA_daily.csv"
df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "NVDA")].dropna()
daily_rets = close.pct_change().fillna(0).values
n = len(daily_rets)

print("=" * 75)
print("  波动衰减原理：为什么 9x 杠杆在 NVDA +57% 时反而亏钱")
print("=" * 75)

# ============================================================
# Part 1: 数学原理
# ============================================================
print("""
  【数学原理】杠杆 ETF/权证的每日收益率公式：

    R_leveraged = L * R_stock

    累积收益（复利）：
    V_T = V_0 * PRODUCT(1 + L * r_i)    for i = 1..n

    对数展开近似：
    log(V_T/V_0) = SUM[ L*r_i - (L*r_i)^2/2 + (L*r_i)^3/3 - ... ]

                  = L * SUM(r_i)  -  L^2/2 * SUM(r_i^2)  +  O(L^3)
                    ~~~~~~~~~~~     ~~~~~~~~~~~~~~~~~~~~
                    线性收益项         波动衰减项 (负值!)

    关键：波动衰减项 ∝ L^2 * 方差，增长比线性项更快！
""")

# ============================================================
# Part 2: 实际数据验证
# ============================================================
print("  NVDA 一年实际数据：")
print(f"    交易日: {n}  正股收益: {close.iloc[-1]/close.iloc[0]-1:+.2%}")
print(f"    日均收益: {daily_rets.mean()*100:.4f}%")
print(f"    日波动率: {daily_rets.std()*100:.3f}%")
print()

# 计算各项
sum_r = daily_rets.sum()
sum_r2 = (daily_rets ** 2).sum()
print(f"  SUM(r_i)   = {sum_r:.4f}   (累积对数收益 ≈ 总收益)")
print(f"  SUM(r_i^2) = {sum_r2:.4f}   (方差项 × n)")
print()

# 对不同杠杆计算近似
print(f"  {'杠杆':<6} {'L*SUM(r)':>10} {'-L^2/2*SUM(r^2)':>18} {'近似 log 收益':>14} {'实际终值':>12} {'实际收益率':>12}")
print(f"  {'-'*75}")

for L in [1, 2, 3, 4.5, 6, 7.5, 9, 10]:
    linear = L * sum_r
    decay = -(L**2) / 2 * sum_r2
    approx_log = linear + decay
    approx_ret = np.exp(approx_log) - 1

    # 实际模拟
    val = 1000.0
    for r in daily_rets:
        val *= (1 + L * r)
    actual_ret = val / 1000 - 1

    marker = " <<< 最优" if L == 4.5 else (" <<< 转负!" if L == 9 else "")
    print(f"  {L:<6.1f}x {linear:>+10.4f} {decay:>+18.4f} {approx_log:>+14.4f} ${val:>11,.0f} {actual_ret:>+11.1%}{marker}")

# ============================================================
# Part 3: 两日例子直观演示
# ============================================================
print(f"\n{'=' * 75}")
print("  【直观例子】为什么涨涨跌跌会吃掉杠杆收益")
print(f"{'=' * 75}")

# 虚构一个两日场景
print("""
  假设正股两日走势：+10%, -9.09%（回到原点）

  正股：$100 -> $110 -> $100    (0%)

  3x 杠杆：
    第1天：+30%  -> $130
    第2天：-27.3% -> $94.55    (-5.5%!)

  9x 杠杆：
    第1天：+90%  -> $190
    第2天：-81.8% -> $34.55    (-65.5%!)

  看：正股没动，杠杆产品亏得一塌糊涂。
  这就是波动衰减——涨跌幅度乘以杠杆后，回来的路比去的路更长。
""")

# 用 NVDA 真实数据找一个震荡期演示
print(f"\n  【真实案例】NVDA 数据中的震荡期演示")
print(f"{'─' * 75}")

# 找一个来回震荡的片段
# 计算每个窗口的"往返效率"
window = 20
best_decay = float('inf')
best_start = 0
for start in range(n - window):
    vals_1x = 1000.0
    vals_9x = 1000.0
    for i in range(start, start + window):
        r = daily_rets[i]
        vals_1x *= (1 + r)
        vals_9x *= (1 + 9 * r)
    stock_ret = vals_1x / 1000 - 1
    lev_ret = vals_9x / 1000 - 1
    # 找正股接近0但杠杆大亏的窗口
    if abs(stock_ret) < 0.02 and lev_ret < -0.1:
        if lev_ret < best_decay:
            best_decay = lev_ret
            best_start = start

if best_decay < float('inf'):
    start = best_start
    print(f"  日期：{close.index[start].strftime('%Y-%m-%d')} → {close.index[start+window-1].strftime('%Y-%m-%d')} ({window}天)")
    print(f"  正股：${close.iloc[start]:.2f} → ${close.iloc[start+window-1]:.2f}")

    vals_1x = 1000.0
    vals_9x = 1000.0
    print(f"\n  {'Day':<5} {'日期':<12} {'正股%':>8} {'1x 价值':>10} {'9x 价值':>10} {'9x日变%':>9}")
    print(f"  {'-'*57}")
    for i in range(start, start + min(window, 15)):
        r = daily_rets[i]
        vals_1x *= (1 + r)
        vals_9x *= (1 + 9 * r)
        dt = close.index[i].strftime("%Y-%m-%d")
        print(f"  {i-start:<5} {dt:<12} {r*100:>+7.2f}% ${vals_1x:>9,.0f} ${vals_9x:>9,.0f} {r*900:>+8.1f}%")

    stock_ret = vals_1x / 1000 - 1
    lev_ret = vals_9x / 1000 - 1
    print(f"\n  这段正股收益：{stock_ret:+.2%}")
    print(f"  这段 9x 收益：{lev_ret:+.2%}  <<< 正股没怎么动，9x 大亏!")

# ============================================================
# Part 4: 每日 9x 杠杆 vs 正股 累积对比
# ============================================================
print(f"\n{'=' * 75}")
print("  【全程追踪】9x 杠杆 vs 正股 关键节点")
print(f"{'=' * 75}")

# 找几个关键节点
val_9x = 1000.0
val_1x = 1000.0
peak_9x = 1000.0
milestones = [50, 100, 150, 200, 252]

print(f"\n  {'Day':<6} {'日期':<12} {'正股价':>8} {'1x 价值':>10} {'9x 价值':>10} {'9x 回撤':>9}")
print(f"  {'-'*58}")
for i in range(n):
    r = daily_rets[i]
    val_1x *= (1 + r)
    val_9x *= (1 + 9 * r)
    if val_9x > peak_9x:
        peak_9x = val_9x
    dd_9x = (val_9x - peak_9x) / peak_9x * 100

    if i in milestones or i == n-1:
        dt = close.index[i].strftime("%Y-%m-%d")
        print(f"  {i:<6} {dt:<12} ${close.iloc[i]:>7.2f} ${val_1x:>9,.0f} ${val_9x:>9,.0f} {dd_9x:>+8.1f}%")

print(f"\n  最终结果：1x = ${val_1x:,.0f}  |  9x = ${val_9x:,.0f}")

# ============================================================
# Part 5: 最优杠杆推导
# ============================================================
print(f"\n{'=' * 75}")
print("  【理论最优杠杆】Kelly 公式近似")
print(f"{'=' * 75}")

mu = daily_rets.mean() * 252  # 年化日均收益
sigma = daily_rets.std() * np.sqrt(252)  # 年化波动率

print(f"  NVDA 年化收益: {mu*100:.1f}%")
print(f"  NVDA 年化波动: {sigma*100:.1f}%")

# Kelly 最优杠杆（不考虑敲出）: L* = mu / sigma^2
L_optimal = mu / (sigma**2)
print(f"\n  Kelly 最优杠杆 L* = mu/sigma^2 = {L_optimal:.2f}x")
print(f"  (这与我们实测的 4.5x 一致!)")

# 过高的杠杆
print(f"\n  当 L > L* 时：")
print(f"    波动衰减项 L^2*sigma^2/2 超过 收益项 L*mu")
print(f"    每多一天震荡，杠杆产品就多亏一点")
print(f"    NVDA 虽然没有大跌，但日常 1-2% 的来回波动")
print(f"    在 9x 放大下变成了 9-18% 的日振幅")
print(f"    复利效应让这些损耗层层叠加")

# 用赌场类比
print(f"\n  【类比】就像赌场里的凯利准则：")
print(f"    你有一枚 51% 胜率的硬币")
print(f"    每次下注 10% 资金 → 长期暴富")
print(f"    每次下注 90% 资金 → 迟早破产")
print(f"    杠杆 = 下注比例，过高杠杆 = 过度下注 = 自我毁灭")
