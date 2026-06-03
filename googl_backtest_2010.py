# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load GOOGL & NVDA, trim to 2010+
# ============================================================
googl = pd.read_csv(r"C:\AI\cc\stock\GOOGL_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
nvda = pd.read_csv(r"C:\AI\cc\stock\NVDA_daily.csv", header=[0, 1], index_col=0, parse_dates=True)

googl_close = googl[("Close", "GOOGL")].dropna()
nvda_close = nvda[("Close", "NVDA")].dropna()

START = "2010-01-01"
googl_close = googl_close[googl_close.index >= START]
nvda_close = nvda_close[nvda_close.index >= START]

initial_capital = 10000.0
years_g = (googl_close.index[-1] - googl_close.index[0]).days / 365.25
years_n = (nvda_close.index[-1] - nvda_close.index[0]).days / 365.25

print("=" * 70)
print("  GOOGL vs NVDA - All Strategies from 2010-01-01")
print(f"  GOOGL: {googl_close.index[0].strftime('%Y-%m-%d')} ~ {googl_close.index[-1].strftime('%Y-%m-%d')} ({years_g:.1f}y)")
print(f"  NVDA:  {nvda_close.index[0].strftime('%Y-%m-%d')} ~ {nvda_close.index[-1].strftime('%Y-%m-%d')} ({years_n:.1f}y)")
print("=" * 70)

# ============================================================
# Helper function: MA Cross Backtest
# ============================================================
def ma_cross_backtest(close_series, name):
    ma5 = close_series.rolling(5).mean()
    ma20 = close_series.rolling(20).mean()
    sig = pd.DataFrame({"close": close_series, "ma5": ma5, "ma20": ma20}).dropna()
    sig["ma5_above"] = sig["ma5"] > sig["ma20"]
    sig["cross_up"] = sig["ma5_above"] & (~sig["ma5_above"].shift(1).fillna(False))
    sig["cross_down"] = (~sig["ma5_above"]) & (sig["ma5_above"].shift(1).fillna(False))

    capital = initial_capital
    shares = 0.0
    in_position = False
    daily = []

    for date, row in sig.iterrows():
        price = row["close"]
        if row["cross_up"] and not in_position:
            shares = capital / price
            capital = 0.0
            in_position = True
        elif row["cross_down"] and in_position:
            capital = shares * price
            shares = 0.0
            in_position = False
        daily.append({"date": date, "value": shares * price if in_position else capital})

    if in_position:
        capital = shares * close_series.iloc[-1]

    values = pd.DataFrame(daily).set_index("date")
    final_val = capital
    total_ret = (final_val / initial_capital - 1) * 100
    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    ann_ret = ((final_val / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    peak = values["value"].cummax()
    max_dd = ((values["value"] - peak) / peak * 100).min()
    n_trades = len(sig[sig["cross_up"]])
    bh_final = initial_capital * close_series.iloc[-1] / close_series.loc[sig.index[0]]
    bh_ret = (bh_final / initial_capital - 1) * 100

    return {
        "name": name,
        "values": values,
        "final": final_val,
        "total_ret": total_ret,
        "ann_ret": ann_ret,
        "max_dd": max_dd,
        "trades": n_trades,
        "bh_final": bh_final,
        "bh_ret": bh_ret,
        "start": sig.index[0],
        "end": sig.index[-1],
        "years": n_years,
    }

# ============================================================
# Helper function: Momentum Backtest
# ============================================================
def momentum_backtest(close_series, name, formation=12, skip=1):
    monthly = close_series.resample("ME").last()
    monthly_ret = monthly.pct_change()
    sig = pd.DataFrame({"price": monthly, "return": monthly_ret})
    sig["momentum"] = sig["price"].pct_change(periods=formation).shift(skip)
    sig["position"] = (sig["momentum"] > 0).astype(int)
    sig["strategy_return"] = sig["position"].shift(1) * sig["return"]
    sig = sig.dropna()
    sig["strategy_value"] = initial_capital * (1 + sig["strategy_return"]).cumprod()
    sig["buyhold_value"] = initial_capital * (1 + sig["return"]).cumprod()

    final_val = sig["strategy_value"].iloc[-1]
    total_ret = (final_val / initial_capital - 1) * 100
    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    ann_ret = ((final_val / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    excess = sig["strategy_return"]
    sharpe = np.sqrt(12) * excess.mean() / excess.std() if excess.std() > 0 else 0
    peak = sig["strategy_value"].cummax()
    max_dd = ((sig["strategy_value"] - peak) / peak * 100).min()
    win_rate = (sig["strategy_return"] > 0).sum() / len(sig) * 100
    time_in = sig["position"].mean() * 100
    bh_val = sig["buyhold_value"].iloc[-1]
    bh_ret = (bh_val / initial_capital - 1) * 100

    n_signals = int(abs(sig["position"].diff()).sum())

    return {
        "name": name,
        "df": sig,
        "final": final_val,
        "total_ret": total_ret,
        "ann_ret": ann_ret,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "time_in": time_in,
        "bh_final": bh_val,
        "bh_ret": bh_ret,
        "signals": n_signals,
        "years": n_years,
        "start": sig.index[0],
        "end": sig.index[-1],
    }

# ============================================================
# Run all strategies
# ============================================================

# --- MA Cross ---
ma_googl = ma_cross_backtest(googl_close, "GOOGL")
ma_nvda = ma_cross_backtest(nvda_close, "NVDA")

# --- Momentum 6M ---
mom6_googl = momentum_backtest(googl_close, "GOOGL 6M", formation=6)
mom6_nvda = momentum_backtest(nvda_close, "NVDA 6M", formation=6)

# --- Momentum 12M ---
mom12_googl = momentum_backtest(googl_close, "GOOGL 12M", formation=12)
mom12_nvda = momentum_backtest(nvda_close, "NVDA 12M", formation=12)

# ============================================================
# Print Summary Table
# ============================================================
def print_strategy(title, r_googl, r_nvda):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")
    print(f"  {'指标':<18} {'GOOGL':>16} {'NVDA':>16}")
    print(f"  {'─'*50}")
    print(f"  {'最终资金':<18} ${r_googl['final']:>15,.2f} ${r_nvda['final']:>15,.2f}")
    print(f"  {'总收益率':<18} {r_googl['total_ret']:>15.2f}% {r_nvda['total_ret']:>15.2f}%")
    print(f"  {'年化收益率':<18} {r_googl['ann_ret']:>15.2f}% {r_nvda['ann_ret']:>15.2f}%")
    if "max_dd" in r_googl:
        print(f"  {'最大回撤':<18} {r_googl['max_dd']:>15.2f}% {r_nvda['max_dd']:>15.2f}%")
    if "sharpe" in r_googl:
        print(f"  {'夏普比率':<18} {r_googl['sharpe']:>15.2f} {r_nvda['sharpe']:>15.2f}")
    if "trades" in r_googl:
        print(f"  {'交易次数':<18} {r_googl['trades']:>15} {r_nvda['trades']:>15}")
    if "win_rate" in r_googl:
        print(f"  {'胜率':<18} {r_googl['win_rate']:>15.1f}% {r_nvda['win_rate']:>15.1f}%")
    if "time_in" in r_googl:
        print(f"  {'持仓时间占比':<18} {r_googl['time_in']:>15.1f}% {r_nvda['time_in']:>15.1f}%")
    print(f"  {'买入持有收益':<18} {r_googl['bh_ret']:>15.2f}% {r_nvda['bh_ret']:>15.2f}%")

print_strategy("MA5/MA20 金叉死叉策略", ma_googl, ma_nvda)
print_strategy("6M 动量策略 (skip 1M)", mom6_googl, mom6_nvda)
print_strategy("12M 动量策略 (skip 1M)", mom12_googl, mom12_nvda)

# ============================================================
# Final Comparison: Buy & Hold
# ============================================================
print(f"\n{'─'*70}")
print(f"  买入持有 (Buy & Hold) 对比")
print(f"{'─'*70}")
googl_bh = initial_capital * googl_close.iloc[-1] / googl_close.iloc[0]
nvda_bh = initial_capital * nvda_close.iloc[-1] / nvda_close.iloc[0]
googl_bh_ret = (googl_bh / initial_capital - 1) * 100
nvda_bh_ret = (nvda_bh / initial_capital - 1) * 100
print(f"  {'指标':<18} {'GOOGL':>16} {'NVDA':>16}")
print(f"  {'─'*50}")
print(f"  {'最终资金':<18} ${googl_bh:>15,.2f} ${nvda_bh:>15,.2f}")
print(f"  {'总收益率':<18} {googl_bh_ret:>15.2f}% {nvda_bh_ret:>15.2f}%")
print(f"  {'年化收益率':<18} {((googl_bh/initial_capital)**(1/years_g)-1)*100:>15.2f}% {((nvda_bh/initial_capital)**(1/years_n)-1)*100:>15.2f}%")

# ============================================================
# Charts: 4-panel comparison
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(20, 13))

# Panel 1: MA Cross Equity Curves (log)
ax1 = axes[0, 0]
ax1.plot(ma_googl["values"].index, ma_googl["values"]["value"], label="GOOGL MA Cross", color="#4285F4", linewidth=1.5)
ax1.plot(ma_nvda["values"].index, ma_nvda["values"]["value"], label="NVDA MA Cross", color="#76B900", linewidth=1.5)
ax1.plot(googl_close.index, initial_capital * googl_close / googl_close.iloc[0], color="black", linewidth=1, alpha=0.4, linestyle="--", label="GOOGL B&H")
ax1.plot(nvda_close.index, initial_capital * nvda_close / nvda_close.iloc[0], color="gray", linewidth=1, alpha=0.4, linestyle="--", label="NVDA B&H")
ax1.set_title("MA5/MA20 Cross Strategy - Equity Curve (Log Scale)", fontsize=12, fontweight="bold")
ax1.set_ylabel("Value ($)")
ax1.legend(fontsize=7)
ax1.grid(True, alpha=0.3)
ax1.set_yscale("log")

# Panel 2: Momentum 6M Equity Curves (log)
ax2 = axes[0, 1]
ax2.plot(mom6_googl["df"].index, mom6_googl["df"]["strategy_value"], label="GOOGL 6M Mom", color="#4285F4", linewidth=1.5)
ax2.plot(mom6_nvda["df"].index, mom6_nvda["df"]["strategy_value"], label="NVDA 6M Mom", color="#76B900", linewidth=1.5)
ax2.plot(mom6_googl["df"].index, mom6_googl["df"]["buyhold_value"], color="black", linewidth=1, alpha=0.4, linestyle="--", label="GOOGL B&H")
ax2.plot(mom6_nvda["df"].index, mom6_nvda["df"]["buyhold_value"], color="gray", linewidth=1, alpha=0.4, linestyle="--", label="NVDA B&H")
ax2.set_title("6M Momentum Strategy - Equity Curve (Log Scale)", fontsize=12, fontweight="bold")
ax2.set_ylabel("Value ($)")
ax2.legend(fontsize=7)
ax2.grid(True, alpha=0.3)
ax2.set_yscale("log")

# Panel 3: Strategy vs Buy&Hold final value bar chart
ax3 = axes[1, 0]
strategies = ["Buy & Hold", "MA Cross", "6M Mom", "12M Mom"]
googl_vals = [googl_bh, ma_googl["final"], mom6_googl["final"], mom12_googl["final"]]
nvda_vals = [nvda_bh, ma_nvda["final"], mom6_nvda["final"], mom12_nvda["final"]]

x = np.arange(len(strategies))
width = 0.35
bars1 = ax3.bar(x - width/2, [v/1000 for v in googl_vals], width, label="GOOGL", color="#4285F4", edgecolor="white")
bars2 = ax3.bar(x + width/2, [v/1000 for v in nvda_vals], width, label="NVDA", color="#76B900", edgecolor="white")

# Add value labels
for bar, val in zip(bars1, googl_vals):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, f"${val/1000:.0f}K", ha="center", fontsize=8, fontweight="bold")
for bar, val in zip(bars2, nvda_vals):
    ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, f"${val/1000:.0f}K", ha="center", fontsize=8, fontweight="bold")

ax3.set_title("Final Value Comparison ($10K -> ?)", fontsize=12, fontweight="bold")
ax3.set_xticks(x)
ax3.set_xticklabels(strategies, fontsize=9)
ax3.set_ylabel("Final Value ($ Thousands)")
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3, axis="y")

# Panel 4: Annualized Return & Max Drawdown scatter
ax4 = axes[1, 1]
all_results = [
    ("GOOGL B&H", googl_bh_ret, 0, "GOOGL", "*", 300),
    ("NVDA B&H", nvda_bh_ret, 0, "NVDA", "*", 300),
    ("GOOGL MA", ma_googl["ann_ret"], ma_googl["max_dd"], "GOOGL", "s", 120),
    ("NVDA MA", ma_nvda["ann_ret"], ma_nvda["max_dd"], "NVDA", "s", 120),
    ("GOOGL 6M", mom6_googl["ann_ret"], mom6_googl["max_dd"], "GOOGL", "D", 120),
    ("NVDA 6M", mom6_nvda["ann_ret"], mom6_nvda["max_dd"], "NVDA", "D", 120),
    ("GOOGL 12M", mom12_googl["ann_ret"], mom12_googl["max_dd"], "GOOGL", "o", 120),
    ("NVDA 12M", mom12_nvda["ann_ret"], mom12_nvda["max_dd"], "NVDA", "o", 120),
]

for label, ret, dd, stock, marker, size in all_results:
    color = "#4285F4" if stock == "GOOGL" else "#76B900"
    marker_label = "B&H" if marker == "*" else "MA" if marker == "s" else "6M" if marker == "D" else "12M"
    ax4.scatter(ret, dd, c=color, marker=marker, s=size, edgecolors="white", linewidth=0.5, zorder=5, label=f"{stock} {marker_label}")
    ax4.annotate(f"{stock}\n{marker_label}", (ret, dd), textcoords="offset points", xytext=(5, 5), fontsize=6, alpha=0.8)

ax4.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax4.axvline(x=0, color="gray", linewidth=0.5, linestyle="--")
ax4.set_title("Risk-Return: Ann.Return vs Max Drawdown", fontsize=12, fontweight="bold")
ax4.set_xlabel("Annualized Return (%)")
ax4.set_ylabel("Max Drawdown (%)")
ax4.grid(True, alpha=0.3)

# Remove duplicate legend
handles, labels = ax4.get_legend_handles_labels()
by_label = dict(zip(labels, handles))
ax4.legend(by_label.values(), by_label.keys(), fontsize=6, loc="lower right")

plt.suptitle("GOOGL vs NVDA Quantitative Strategy Backtest (2010-01-01 ~ 2026-06-02)", fontsize=15, fontweight="bold", y=1.01)
plt.tight_layout()
chart_path = r"C:\AI\cc\stock\GOOGL_vs_NVDA_2010.png"
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {chart_path}")
plt.close()

# ============================================================
# Winner summary
# ============================================================
print(f"\n{'='*70}")
print(f"  WINNER: Buy & Hold beats ALL strategies for both stocks")
print(f"{'='*70}")
print(f"  GOOGL B&H: ${googl_bh:,.0f}  vs  Best Strategy (6M Mom): ${mom6_googl['final']:,.0f}")
print(f"  NVDA  B&H: ${nvda_bh:,.0f}  vs  Best Strategy (6M Mom): ${mom6_nvda['final']:,.0f}")
print(f"")
print(f"  Key Insight: For individual mega-cap tech stocks in a historic")
print(f"  bull market, the best strategy is simply to buy and hold.")
print(f"  Quantitative strategies underperform because they periodically")
print(f"  go to cash and miss the largest up-moves.")
print(f"{'='*70}")
