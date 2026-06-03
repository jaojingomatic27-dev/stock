# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load data
# ============================================================
def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[close.index >= "2010-01-01"]

spy = load_close(r"C:\AI\cc\stock\SPY_daily.csv", "SPY")
nvda = load_close(r"C:\AI\cc\stock\NVDA_daily.csv", "NVDA")

monthly_amount = 500.0

# ============================================================
# DCA: invest $500 on the 1st trading day of each month
# ============================================================
def dca_sim(close_series, amount=500.0):
    # Find first trading day of each month by scanning
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close_series.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    total_invested = 0.0
    total_shares = 0.0
    records = []

    for dt, price in zip(first_dates, first_prices):
        shares_bought = amount / price
        total_shares += shares_bought
        total_invested += amount
        records.append({
            "date": dt,
            "price": price,
            "shares_bought": shares_bought,
            "total_shares": total_shares,
            "invested": total_invested,
            "value": total_shares * price,
        })

    df_rec = pd.DataFrame(records).set_index("date")

    # Daily values for chart
    daily_vals = []
    for date in close_series.index:
        if date < df_rec.index[0]:
            continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        sh = last["total_shares"]
        inv = last["invested"]
        daily_vals.append({"date": date, "value": sh * close_series.loc[date], "invested": inv})
    daily_df = pd.DataFrame(daily_vals).set_index("date")

    final_value = total_shares * close_series.iloc[-1]
    total_return = (final_value - total_invested) / total_invested * 100
    months = len(first_dates)
    years = months / 12.0
    ann_ret = ((final_value / total_invested) ** (1 / years) - 1) * 100 if years > 0 else 0
    avg_cost = total_invested / total_shares if total_shares > 0 else 0

    return {
        "records": df_rec,
        "daily": daily_df,
        "total_invested": total_invested,
        "final_value": final_value,
        "total_return": total_return,
        "ann_ret": ann_ret,
        "total_shares": total_shares,
        "months": months,
        "years": years,
        "avg_cost": avg_cost,
        "last_price": close_series.iloc[-1],
    }

spy_r = dca_sim(spy, monthly_amount)
nvda_r = dca_sim(nvda, monthly_amount)

# ============================================================
# Print Results
# ============================================================
print("=" * 65)
print(f"  Monthly DCA: ${monthly_amount:.0f}/month  (2010-01 ~ 2026-06)")
print("=" * 65)

for name, r in [("SPY", spy_r), ("NVDA", nvda_r)]:
    profit = r["final_value"] - r["total_invested"]
    cost_gain = (r["last_price"] / r["avg_cost"] - 1) * 100
    print(f"\n{'─'*50}")
    print(f"  {name} - Dollar Cost Averaging")
    print(f"{'─'*50}")
    print(f"  定投月数:       {r['months']} 个月 ({r['years']:.1f} 年)")
    print(f"  总投入资金:     ${r['total_invested']:>12,.0f}")
    print(f"  最终市值:       ${r['final_value']:>12,.0f}")
    print(f"  总盈利:         ${profit:>12,.0f}")
    print(f"  总收益率:       {r['total_return']:>+11.1f}%")
    print(f"  年化收益率:     {r['ann_ret']:>+11.1f}%")
    print(f"  累计持股:       {r['total_shares']:>10.1f} 股")
    print(f"  最新股价:       ${r['last_price']:>11.2f}")
    print(f"  平均成本:       ${r['avg_cost']:>11.2f}")
    print(f"  成本之上涨幅:   {cost_gain:>+11.1f}%")

# ============================================================
# Comparison
# ============================================================
print(f"\n{'='*65}")
print(f"  SPY vs NVDA DCA - Head to Head")
print(f"{'='*65}")
print(f"  {'':<20} {'SPY':>18} {'NVDA':>18}")
print(f"  {'─'*56}")
labels = [
    ("总投入", "total_invested", "$"),
    ("最终市值", "final_value", "$"),
    ("总盈利", "profit", "$"),
    ("总收益率", "total_return", "%"),
    ("年化收益率", "ann_ret", "%"),
    ("平均成本", "avg_cost", "$p"),
    ("持股数", "total_shares", "d"),
]
for label, key, fmt in labels:
    if key == "profit":
        sv = spy_r["final_value"] - spy_r["total_invested"]
        nv = nvda_r["final_value"] - nvda_r["total_invested"]
    else:
        sv = spy_r[key]
        nv = nvda_r[key]
    if fmt == "$":
        print(f"  {label:<20} ${sv:>17,.0f} ${nv:>17,.0f}")
    elif fmt == "%":
        print(f"  {label:<20} {sv:>17.1f}% {nv:>17.1f}%")
    elif fmt == "$p":
        print(f"  {label:<20} ${sv:>17.2f} ${nv:>17.2f}")
    elif fmt == "d":
        print(f"  {label:<20} {sv:>17.1f} {nv:>17.1f}")

# ============================================================
# Lump sum comparison
# ============================================================
print(f"\n{'='*65}")
print(f"  Lump Sum vs DCA: invest ${spy_r['total_invested']:,.0f} once in Jan 2010")
print(f"{'='*65}")

for name, series in [("SPY", spy), ("NVDA", nvda)]:
    r = spy_r if name == "SPY" else nvda_r
    lump = r["total_invested"]
    shares = lump / series.iloc[0]
    lump_final = shares * series.iloc[-1]
    lump_ret = (lump_final / lump - 1) * 100
    y = (series.index[-1] - series.index[0]).days / 365.25
    lump_ann = ((lump_final / lump) ** (1 / y) - 1) * 100
    dca_final = r["final_value"]
    dca_ret = r["total_return"]
    print(f"  {name}:")
    print(f"    一次性投入  ${lump:,.0f} -> ${lump_final:,.0f}  ({lump_ret:+.1f}%, 年化 {lump_ann:+.1f}%)")
    print(f"    每月定投    ${lump:,.0f} -> ${dca_final:,.0f}  ({dca_ret:+.1f}%, 年化 {r['ann_ret']:+.1f}%)")
    ratio = dca_final / lump_final * 100
    print(f"    DCA 捕获率: {ratio:.1f}%")

# ============================================================
# Charts
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(22, 13))

# Panel 1: SPY DCA
ax1 = axes[0, 0]
d_s = spy_r["daily"]
ax1.fill_between(d_s.index, 0, d_s["value"], alpha=0.3, color="#1f77b4")
ax1.plot(d_s.index, d_s["value"], color="#1f77b4", linewidth=1.2, label="SPY Market Value")
ax1.plot(d_s.index, d_s["invested"], color="black", linewidth=1.5, linestyle="--", label="Total Invested")
ax1.set_title(f"SPY DCA: ${monthly_amount:.0f}/month", fontsize=12, fontweight="bold")
ax1.set_ylabel("Value ($)")
ax1.legend(fontsize=8)
ax1.grid(True, alpha=0.3)

# Panel 2: NVDA DCA
ax2 = axes[0, 1]
d_n = nvda_r["daily"]
ax2.fill_between(d_n.index, 0, d_n["value"], alpha=0.3, color="#76B900")
ax2.plot(d_n.index, d_n["value"], color="#76B900", linewidth=1.2, label="NVDA Market Value")
ax2.plot(d_n.index, d_n["invested"], color="black", linewidth=1.5, linestyle="--", label="Total Invested")
ax2.set_title(f"NVDA DCA: ${monthly_amount:.0f}/month", fontsize=12, fontweight="bold")
ax2.set_ylabel("Value ($)")
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

# Panel 3: SPY vs NVDA DCA (log)
ax3 = axes[0, 2]
ax3.plot(d_s.index, d_s["value"], color="#1f77b4", linewidth=1.5, label="SPY DCA")
ax3.plot(d_n.index, d_n["value"], color="#76B900", linewidth=1.5, label="NVDA DCA")
ax3.plot(d_s.index, d_s["invested"], color="black", linewidth=1, linestyle="--", alpha=0.5, label="Total Invested")
ax3.set_title("SPY vs NVDA DCA (Log Scale)", fontsize=12, fontweight="bold")
ax3.set_ylabel("Value ($)")
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3)
ax3.set_yscale("log")

# Panel 4: Annual contributions and growth
ax4 = axes[1, 0]
spy_rec = spy_r["records"]
nvda_rec = nvda_r["records"]
# Annual snapshots
spy_ann = spy_rec["value"].resample("YE").last()
nvda_ann = nvda_rec["value"].resample("YE").last()
inv_ann = spy_rec["invested"].resample("YE").last()
years_list = [d.year for d in spy_ann.index]

x = np.arange(len(years_list))
w = 0.3
ax4.bar(x - w, spy_ann / 1000, w, color="#1f77b4", alpha=0.7, label="SPY DCA")
ax4.bar(x, nvda_ann / 1000, w, color="#76B900", alpha=0.7, label="NVDA DCA")
ax4.bar(x + w, inv_ann / 1000, w, color="gray", alpha=0.4, label="Total Invested")
ax4.set_title("Year-End Portfolio Value ($K)", fontsize=12, fontweight="bold")
ax4.set_xticks(x[::2])
ax4.set_xticklabels([str(y) for y in years_list[::2]], fontsize=8)
ax4.legend(fontsize=7)
ax4.grid(True, alpha=0.3, axis="y")

# Panel 5: Bar chart - DCA vs Lump Sum
ax5 = axes[1, 1]
invested = spy_r["total_invested"]
spy_lump = invested / spy.iloc[0] * spy.iloc[-1]
nvda_lump = invested / nvda.iloc[0] * nvda.iloc[-1]
cats = ["SPY\nDCA", "SPY\nLump", "NVDA\nDCA", "NVDA\nLump"]
vals = [spy_r["final_value"], spy_lump, nvda_r["final_value"], nvda_lump]
colors_bar = ["#1f77b4", "#1f77b4", "#76B900", "#76B900"]
alphas = [0.7, 0.35, 0.7, 0.35]
bars = ax5.bar(cats, [v/1000 for v in vals], color=colors_bar, edgecolor="white")
for bar, alpha_val in zip(bars, alphas):
    bar.set_alpha(alpha_val)
for bar, val in zip(bars, vals):
    if val >= 1e6:
        lbl = f"${val/1e6:.1f}M"
    else:
        lbl = f"${val/1000:.0f}K"
    ax5.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, lbl, ha="center", fontsize=9, fontweight="bold")
ax5.axhline(y=invested/1000, color="red", linewidth=1, linestyle="--", alpha=0.6)
ax5.text(3.5, invested/1000 + 5, f"Invested\n${invested:,.0f}", fontsize=7, color="red")
ax5.set_title(f"Final Value: DCA vs Lump Sum", fontsize=11, fontweight="bold")
ax5.grid(True, alpha=0.3, axis="y")

# Panel 6: Sharpe-like efficiency
ax6 = axes[1, 2]
# Monthly returns
spy_mr = spy_rec["value"].pct_change().dropna() * 100
nvda_mr = nvda_rec["value"].pct_change().dropna() * 100
bp = ax6.boxplot([spy_mr, nvda_mr], labels=["SPY DCA", "NVDA DCA"], patch_artist=True)
bp["boxes"][0].set_facecolor("#1f77b4")
bp["boxes"][1].set_facecolor("#76B900")
ax6.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax6.set_title("Monthly Portfolio Return Distribution", fontsize=12, fontweight="bold")
ax6.set_ylabel("Monthly Return (%)")
ax6.grid(True, alpha=0.3, axis="y")

plt.suptitle(f"Dollar Cost Averaging: ${monthly_amount:.0f}/month SPY vs NVDA (2010-2026)", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path = r"C:\AI\cc\stock\DCA_SPY_vs_NVDA.png"
plt.savefig(path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {path}")
plt.close()
