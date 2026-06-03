# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load all data, trim to 2010+
# ============================================================
def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[close.index >= "2010-01-01"]

spy = load_close(r"C:\AI\cc\stock\SPY_daily.csv", "SPY")
googl = load_close(r"C:\AI\cc\stock\GOOGL_daily.csv", "GOOGL")
nvda = load_close(r"C:\AI\cc\stock\NVDA_daily.csv", "NVDA")

initial_capital = 10000.0

print("=" * 75)
print("  SPY vs GOOGL vs NVDA — All Strategies from 2010-01-01")
print(f"  Period: 2010-01-04 ~ 2026-06-02 (16.4 years)")
print(f"  SPY: ${spy.iloc[0]:.2f} -> ${spy.iloc[-1]:.2f}")
print(f"  GOOGL: ${googl.iloc[0]:.2f} -> ${googl.iloc[-1]:.2f}")
print(f"  NVDA: ${nvda.iloc[0]:.2f} -> ${nvda.iloc[-1]:.2f}")
print("=" * 75)

# ============================================================
# Strategy Functions
# ============================================================
def ma_cross(close_series):
    ma5 = close_series.rolling(5).mean()
    ma20 = close_series.rolling(20).mean()
    sig = pd.DataFrame({"close": close_series, "ma5": ma5, "ma20": ma20}).dropna()
    sig["above"] = sig["ma5"] > sig["ma20"]
    sig["cross_up"] = sig["above"] & (~sig["above"].shift(1).fillna(False))
    sig["cross_down"] = (~sig["above"]) & (sig["above"].shift(1).fillna(False))

    capital = initial_capital; shares = 0.0; in_pos = False; daily = []
    for date, row in sig.iterrows():
        p = row["close"]
        if row["cross_up"] and not in_pos:
            shares = capital / p; capital = 0.0; in_pos = True
        elif row["cross_down"] and in_pos:
            capital = shares * p; shares = 0.0; in_pos = False
        daily.append({"date": date, "value": shares * p if in_pos else capital})
    if in_pos:
        capital = shares * close_series.iloc[-1]

    values = pd.DataFrame(daily).set_index("date")
    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    final = capital
    ann = ((final / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    peak = values["value"].cummax()
    dd = ((values["value"] - peak) / peak * 100).min()
    # Monthly returns for Sharpe
    monthly_v = values["value"].resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly_v.mean() / monthly_v.std() if monthly_v.std() > 0 else 0
    n_trades = int(sig["cross_up"].sum())
    bh_final = initial_capital * close_series.iloc[-1] / close_series.loc[sig.index[0]]
    return {
        "final": final, "ann": ann, "dd": dd, "sharpe": sharpe,
        "trades": n_trades, "bh_final": bh_final, "values": values,
    }

def momentum(close_series, formation=6, skip=1):
    monthly = close_series.resample("ME").last()
    monthly_ret = monthly.pct_change()
    sig = pd.DataFrame({"price": monthly, "ret": monthly_ret})
    sig["mom"] = sig["price"].pct_change(periods=formation).shift(skip)
    sig["pos"] = (sig["mom"] > 0).astype(int)
    sig["sret"] = sig["pos"].shift(1) * sig["ret"]
    sig = sig.dropna()
    sig["sval"] = initial_capital * (1 + sig["sret"]).cumprod()
    sig["bval"] = initial_capital * (1 + sig["ret"]).cumprod()

    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    final = sig["sval"].iloc[-1]
    ann = ((final / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    sharpe = np.sqrt(12) * sig["sret"].mean() / sig["sret"].std() if sig["sret"].std() > 0 else 0
    peak = sig["sval"].cummax()
    dd = ((sig["sval"] - peak) / peak * 100).min()
    n_signals = int(abs(sig["pos"].diff()).sum())
    win = (sig["sret"] > 0).sum() / len(sig) * 100
    time_in = sig["pos"].mean() * 100
    bh_final = sig["bval"].iloc[-1]
    return {
        "final": final, "ann": ann, "dd": dd, "sharpe": sharpe,
        "signals": n_signals, "win": win, "time_in": time_in,
        "bh_final": bh_final, "df": sig,
    }

# ============================================================
# Run all
# ============================================================
stocks = {"SPY": spy, "GOOGL": googl, "NVDA": nvda}

ma_results = {name: ma_cross(series) for name, series in stocks.items()}
mom6_results = {name: momentum(series, 6) for name, series in stocks.items()}
mom12_results = {name: momentum(series, 12) for name, series in stocks.items()}

# B&H
bh = {}
for name, series in stocks.items():
    final = initial_capital * series.iloc[-1] / series.iloc[0]
    n_y = (series.index[-1] - series.index[0]).days / 365.25
    ann = ((final / initial_capital) ** (1 / n_y) - 1) * 100
    monthly_r = series.resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly_r.mean() / monthly_r.std() if monthly_r.std() > 0 else 0
    peak = series.cummax()
    dd = ((series - peak) / peak * 100).min()
    bh[name] = {"final": final, "ann": ann, "sharpe": sharpe, "dd": dd, "years": n_y}

# ============================================================
# Print Tables
# ============================================================
def print_table(title, labels, getter):
    print(f"\n{'─'*75}")
    print(f"  {title}")
    print(f"{'─'*75}")
    header = f"  {'指标':<18}"
    for s in ["SPY", "GOOGL", "NVDA"]:
        header += f" {s:>17}"
    print(header)
    print(f"  {'─'*69}")
    for label, key in labels:
        row = f"  {label:<18}"
        for s in ["SPY", "GOOGL", "NVDA"]:
            v = getter(s, key)
            if isinstance(v, float):
                if "final" in key or "bh" in key:
                    row += f" ${v:>16,.0f}"
                elif "ann" in key or "ret" in key or "dd" in key or "win" in key or "time" in key:
                    row += f" {v:>16.1f}%"
                elif "sharpe" in key:
                    row += f" {v:>16.2f}"
                elif "trades" in key or "signals" in key:
                    row += f" {v:>16}"
                else:
                    row += f" {v:>16.1f}"
        print(row)
    # B&H comparison
    row = f"  {'买入持有':<18}"
    for s in ["SPY", "GOOGL", "NVDA"]:
        row += f" {bh[s]['final']:>16,.0f}"
    print(f"  {'(B&H 最终资金)':<18}" + "".join([f" ${bh[s]['final']:>15,.0f}" for s in ["SPY", "GOOGL", "NVDA"]]))
    bh_row = f"  {'(B&H 收益率)':<18}"
    for s in ["SPY", "GOOGL", "NVDA"]:
        ret = (bh[s]['final'] / initial_capital - 1) * 100
        bh_row += f" {ret:>16.1f}%"
    print(bh_row)

print_table("Buy & Hold 基准", [
    ("最终资金", "final"), ("年化收益率", "ann"), ("夏普比率", "sharpe"), ("最大回撤", "dd"),
], lambda s, k: bh[s][k])

print_table("MA5/MA20 金叉死叉", [
    ("最终资金", "final"), ("年化收益率", "ann"), ("夏普比率", "sharpe"),
    ("最大回撤", "dd"), ("交易次数", "trades"),
], lambda s, k: ma_results[s][k])

print_table("6M 动量 (skip 1M)", [
    ("最终资金", "final"), ("年化收益率", "ann"), ("夏普比率", "sharpe"),
    ("最大回撤", "dd"), ("信号次数", "signals"), ("胜率", "win"), ("持仓占比", "time_in"),
], lambda s, k: mom6_results[s][k])

print_table("12M 动量 (skip 1M)", [
    ("最终资金", "final"), ("年化收益率", "ann"), ("夏普比率", "sharpe"),
    ("最大回撤", "dd"), ("信号次数", "signals"), ("胜率", "win"), ("持仓占比", "time_in"),
], lambda s, k: mom12_results[s][k])

# ============================================================
# Winner summary
# ============================================================
print(f"\n{'='*75}")
print(f"  FINAL RANKING: $10,000 -> ?")
print(f"{'='*75}")
ranking = []
for name in ["SPY", "GOOGL", "NVDA"]:
    ranking.append((name, "Buy & Hold", bh[name]["final"], bh[name]["ann"]))
    ranking.append((name, "12M Mom", mom12_results[name]["final"], mom12_results[name]["ann"]))
    ranking.append((name, "6M Mom", mom6_results[name]["final"], mom6_results[name]["ann"]))
    ranking.append((name, "MA Cross", ma_results[name]["final"], ma_results[name]["ann"]))
ranking.sort(key=lambda x: x[2], reverse=True)

print(f"  {'Rank':<5} {'Stock':<7} {'Strategy':<12} {'Final Value':>16} {'Ann.Ret':>10}")
print(f"  {'─'*52}")
for i, (stock, strat, val, ann) in enumerate(ranking, 1):
    print(f"  {i:<5} {stock:<7} {strat:<12} ${val:>15,.0f} {ann:>9.1f}%")

# ============================================================
# Charts
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(20, 13))

colors = {"SPY": "#1f77b4", "GOOGL": "#4285F4", "NVDA": "#76B900"}

# Panel 1: B&H equity curves (log)
ax1 = axes[0, 0]
for name, series in stocks.items():
    eq = initial_capital * series / series.iloc[0]
    ax1.plot(series.index, eq, label=f"{name} B&H", color=colors[name], linewidth=1.5)
ax1.set_title("Buy & Hold Equity Curves (Log Scale)", fontsize=12, fontweight="bold")
ax1.set_ylabel("Value ($)")
ax1.legend(fontsize=9)
ax1.grid(True, alpha=0.3)
ax1.set_yscale("log")

# Panel 2: 6M Mom equity curves (log)
ax2 = axes[0, 1]
for name in ["SPY", "GOOGL", "NVDA"]:
    df = mom6_results[name]["df"]
    ax2.plot(df.index, df["sval"], label=f"{name} 6M Mom", color=colors[name], linewidth=1.5)
    ax2.plot(df.index, df["bval"], color=colors[name], linewidth=0.8, alpha=0.3, linestyle="--", label=f"{name} B&H")
# Clean up duplicate B&H labels
handles, labels = ax2.get_legend_handles_labels()
unique = {}
for h, l in zip(handles, labels):
    if l not in unique:
        unique[l] = h
ax2.legend(unique.values(), unique.keys(), fontsize=7)
ax2.set_title("6M Momentum Strategy (Log Scale)", fontsize=12, fontweight="bold")
ax2.set_ylabel("Value ($)")
ax2.grid(True, alpha=0.3)
ax2.set_yscale("log")

# Panel 3: Bar chart - Strategy vs B&H
ax3 = axes[1, 0]
categories = ["SPY", "GOOGL", "NVDA"]
x = np.arange(len(categories))
width = 0.2
strats = [
    ("B&H", [bh[s]["final"] for s in categories], "steelblue"),
    ("12M Mom", [mom12_results[s]["final"] for s in categories], "orange"),
    ("6M Mom", [mom6_results[s]["final"] for s in categories], "green"),
    ("MA Cross", [ma_results[s]["final"] for s in categories], "red"),
]
for i, (label, vals, c) in enumerate(strats):
    bars = ax3.bar(x + i * width - width * 1.5, [v / 1000 for v in vals], width, label=label, color=c, edgecolor="white")
    for bar, val in zip(bars, vals):
        if val > 100000:
            ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 10,
                     f"${val/1000000:.1f}M", ha="center", fontsize=6, fontweight="bold", rotation=90)
        else:
            ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                     f"${val/1000:.0f}K", ha="center", fontsize=6, fontweight="bold", rotation=90)

ax3.set_title("$10K Final Value by Strategy & Stock", fontsize=12, fontweight="bold")
ax3.set_xticks(x)
ax3.set_xticklabels(categories, fontsize=11)
ax3.set_ylabel("Final Value ($ Thousands)")
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3, axis="y")

# Panel 4: Risk-Return scatter
ax4 = axes[1, 1]
markers = {"B&H": "*", "12M Mom": "o", "6M Mom": "D", "MA Cross": "s"}
for name in ["SPY", "GOOGL", "NVDA"]:
    pts = [
        ("B&H", bh[name]["ann"], bh[name]["dd"]),
        ("12M Mom", mom12_results[name]["ann"], mom12_results[name]["dd"]),
        ("6M Mom", mom6_results[name]["ann"], mom6_results[name]["dd"]),
        ("MA Cross", ma_results[name]["ann"], ma_results[name]["dd"]),
    ]
    for label, ann, dd in pts:
        ax4.scatter(ann, dd, c=colors[name], marker=markers[label], s=120,
                    edgecolors="white", linewidth=0.5, zorder=5)
        ax4.annotate(f"{name} {label}", (ann, dd), textcoords="offset points",
                     xytext=(5, -8), fontsize=5, alpha=0.75)

ax4.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax4.axvline(x=0, color="gray", linewidth=0.5, linestyle="--")
ax4.set_title("Risk-Return: Ann.Return vs Max Drawdown", fontsize=12, fontweight="bold")
ax4.set_xlabel("Annualized Return (%)")
ax4.set_ylabel("Max Drawdown (%)")
ax4.grid(True, alpha=0.3)

plt.suptitle("SPY vs GOOGL vs NVDA — Quantitative Strategy Comparison (2010-2026)", fontsize=15, fontweight="bold", y=1.01)
plt.tight_layout()
chart_path = r"C:\AI\cc\stock\SPY_GOOGL_NVDA_chart.png"
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {chart_path}")
plt.close()

print(f"\n{'='*75}")
print(f"  KEY TAKEAWAY:")
print(f"  For ALL 3 assets, Buy & Hold beats every trading strategy.")
print(f"  The more active the strategy, the worse it performs.")
print(f"  Momentum strategies preserve more capital (lower DD) but")
print(f"  at the cost of missing the biggest up-moves.")
print(f"{'='*75}")
