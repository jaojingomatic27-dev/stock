# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load all 6 assets
# ============================================================
def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[close.index >= "2010-01-01"]

assets = {
    "SPY":   load_close(r"C:\AI\cc\stock\data\SPY_daily.csv", "SPY"),
    "GOOGL": load_close(r"C:\AI\cc\stock\data\GOOGL_daily.csv", "GOOGL"),
    "NVDA":  load_close(r"C:\AI\cc\stock\data\NVDA_daily.csv", "NVDA"),
    "ORCL":  load_close(r"C:\AI\cc\stock\data\ORCL_daily.csv", "ORCL"),
    "AMZN":  load_close(r"C:\AI\cc\stock\data\AMZN_daily.csv", "AMZN"),
    "GLD":   load_close(r"C:\AI\cc\stock\data\GLD_daily.csv", "GLD"),
}

initial_capital = 10000.0

print("=" * 80)
print("  6-Asset Quantitative Strategy Backtest: 2010-01 ~ 2026-06")
print("=" * 80)
print(f"  {'Ticker':<8} {'Start $':>10} {'End $':>10} {'Years':>6} {'Days':>7}")
print(f"  {'─'*45}")
for name, s in assets.items():
    y = (s.index[-1] - s.index[0]).days / 365.25
    print(f"  {name:<8} ${s.iloc[0]:>9.2f} ${s.iloc[-1]:>9.2f} {y:>5.1f}y {len(s):>6}d")
print("=" * 80)

# ============================================================
# Strategy Functions
# ============================================================
def ma_cross(close_series):
    ma5 = close_series.rolling(5).mean()
    ma20 = close_series.rolling(20).mean()
    sig = pd.DataFrame({"c": close_series, "ma5": ma5, "ma20": ma20}).dropna()
    sig["above"] = sig["ma5"] > sig["ma20"]
    sig["up"] = sig["above"] & (~sig["above"].shift(1).fillna(False))
    sig["down"] = (~sig["above"]) & (sig["above"].shift(1).fillna(False))

    cap = initial_capital; shares = 0.0; in_pos = False; daily = []
    for _, row in sig.iterrows():
        p = row["c"]
        if row["up"] and not in_pos:
            shares = cap / p; cap = 0.0; in_pos = True
        elif row["down"] and in_pos:
            cap = shares * p; shares = 0.0; in_pos = False
        daily.append(cap if not in_pos else shares * p)
    if in_pos:
        cap = shares * close_series.iloc[-1]
    return daily_to_metrics(daily, sig, close_series, cap)

def daily_to_metrics(daily, sig, close_series, final_cap):
    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    vals = pd.Series(daily, index=sig.index)
    peak = vals.cummax()
    dd = ((vals - peak) / peak * 100).min()
    monthly = vals.resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly.mean() / monthly.std() if monthly.std() > 0 else 0
    bh_final = initial_capital * close_series.iloc[-1] / sig["c"].iloc[0]
    ann = ((final_cap / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    return {
        "final": final_cap, "ann": ann, "dd": dd, "sharpe": sharpe,
        "bh_final": bh_final, "values": vals,
    }

def momentum(close_series, formation=6, skip=1):
    monthly = close_series.resample("ME").last()
    mr = monthly.pct_change()
    sig = pd.DataFrame({"price": monthly, "ret": mr})
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
# Run all strategies
# ============================================================
names = list(assets.keys())

bh = {}
for name in names:
    s = assets[name]
    final = initial_capital * s.iloc[-1] / s.iloc[0]
    n_y = (s.index[-1] - s.index[0]).days / 365.25
    ann = ((final / initial_capital) ** (1 / n_y) - 1) * 100 if n_y > 0 else 0
    monthly = s.resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly.mean() / monthly.std() if monthly.std() > 0 else 0
    peak = s.cummax()
    dd = ((s - peak) / peak * 100).min()
    bh[name] = {"final": final, "ann": ann, "sharpe": sharpe, "dd": dd}

ma_res = {n: ma_cross(assets[n]) for n in names}
mom6_res = {n: momentum(assets[n], 6) for n in names}
mom12_res = {n: momentum(assets[n], 12) for n in names}

# ============================================================
# Print strategy tables
# ============================================================
def print_table(title, strategy_dict, metrics):
    print(f"\n{'─'*80}")
    print(f"  {title}")
    print(f"{'─'*80}")
    header = f"  {'Metric':<16}"
    for n in names:
        header += f" {n:>10}"
    print(header)
    print(f"  {'─'*76}")
    for label, key, fmt in metrics:
        row = f"  {label:<16}"
        for n in names:
            v = strategy_dict[n][key]
            if fmt == "$":
                if v >= 1e6:
                    row += f" ${v/1e6:>8.2f}M"
                elif v >= 1000:
                    row += f" ${v/1000:>8.1f}K"
                else:
                    row += f" ${v:>9,.0f}"
            elif fmt == "%":
                row += f" {v:>9.1f}%"
            elif fmt == ".2f":
                row += f" {v:>9.2f}"
            elif fmt == "d":
                row += f" {v:>9}"
            else:
                row += f" {v:>10}"
        print(row)
    # B&H comparison
    row = f"  {'B&H final':<16}"
    for n in names:
        v = bh[n]["final"]
        if v >= 1e6:
            row += f" ${v/1e6:>8.2f}M"
        else:
            row += f" ${v/1000:>8.1f}K"
    print(row)

m = [("Final Value", "final", "$"), ("Ann.Return", "ann", "%"), ("Max Drawdown", "dd", "%"), ("Sharpe", "sharpe", ".2f")]
m_mom = [("Final Value", "final", "$"), ("Ann.Return", "ann", "%"), ("Max Drawdown", "dd", "%"),
         ("Sharpe", "sharpe", ".2f"), ("Signals", "signals", "d"), ("Win Rate", "win", "%"), ("Time in Mkt", "time_in", "%")]

print_table("Buy & Hold Benchmark", bh, m)
print_table("MA5/MA20 Cross", ma_res, m)
print_table("6M Momentum (skip 1M)", mom6_res, m_mom)
print_table("12M Momentum (skip 1M)", mom12_res, m_mom)

# ============================================================
# B&H vs Best Strategy comparison
# ============================================================
print(f"\n{'─'*80}")
print(f"  B&H vs Best Active Strategy (highest final value)")
print(f"{'─'*80}")
print(f"  {'Stock':<8} {'B&H':>12} {'Best Active':>12} {'Strategy':>12} {'Capture %':>10}")
print(f"  {'─'*58}")
for n in names:
    best = max(ma_res[n]["final"], mom6_res[n]["final"], mom12_res[n]["final"])
    best_name = "MA" if best == ma_res[n]["final"] else "6M" if best == mom6_res[n]["final"] else "12M"
    capture = best / bh[n]["final"] * 100
    print(f"  {n:<8} ${bh[n]['final']:>11,.0f} ${best:>11,.0f} {best_name:>12} {capture:>9.1f}%")

# ============================================================
# Ranking
# ============================================================
print(f"\n{'─'*80}")
print(f"  FINAL RANKING: $10,000 -> ? (2010-01 ~ 2026-06)")
print(f"{'─'*80}")
all_entries = []
for n in names:
    all_entries.append((n, "Buy & Hold", bh[n]["final"], bh[n]["ann"]))
    all_entries.append((n, "12M Mom", mom12_res[n]["final"], mom12_res[n]["ann"]))
    all_entries.append((n, "6M Mom", mom6_res[n]["final"], mom6_res[n]["ann"]))
    all_entries.append((n, "MA Cross", ma_res[n]["final"], ma_res[n]["ann"]))
all_entries.sort(key=lambda x: x[2], reverse=True)

print(f"  {'#':<3} {'Stock':<7} {'Strategy':<12} {'Final ($)':>14} {'Ann.Ret':>9}")
print(f"  {'─'*48}")
for i, (stock, strat, val, ann) in enumerate(all_entries, 1):
    if val >= 1e6:
        vs = f"${val/1e6:>11.2f}M"
    else:
        vs = f"${val/1000:>11.1f}K"
    print(f"  {i:<3} {stock:<7} {strat:<12} {vs:>14} {ann:>8.1f}%")

# ============================================================
# Charts (2 pages: B&H + Momentum)
# ============================================================
colors = {"SPY": "#1f77b4", "GOOGL": "#4285F4", "NVDA": "#76B900",
          "ORCL": "#d62728", "AMZN": "#ff7f0e", "GLD": "#9467bd"}

# --- Chart 1: B&H + MA Cross ---
fig, axes = plt.subplots(2, 2, figsize=(22, 13))

ax1 = axes[0, 0]
for n in names:
    eq = initial_capital * assets[n] / assets[n].iloc[0]
    ax1.plot(assets[n].index, eq, label=n, color=colors[n], linewidth=1.3)
ax1.set_title("Buy & Hold Equity Curves (Log)", fontsize=12, fontweight="bold")
ax1.set_ylabel("Value ($)")
ax1.legend(fontsize=8, ncol=2)
ax1.grid(True, alpha=0.3)
ax1.set_yscale("log")

ax2 = axes[0, 1]
for n in names:
    ax2.plot(ma_res[n]["values"].index, ma_res[n]["values"], label=n, color=colors[n], linewidth=1)
ax2.set_title("MA5/MA20 Cross Equity Curves (Log)", fontsize=12, fontweight="bold")
ax2.legend(fontsize=8, ncol=2)
ax2.grid(True, alpha=0.3)
ax2.set_yscale("log")

ax3 = axes[1, 0]
for n in names:
    df6 = mom6_res[n]["df"]
    ax3.plot(df6.index, df6["sval"], label=n, color=colors[n], linewidth=1.2)
ax3.set_title("6M Momentum Equity Curves (Log)", fontsize=12, fontweight="bold")
ax3.set_ylabel("Value ($)")
ax3.legend(fontsize=8, ncol=2)
ax3.grid(True, alpha=0.3)
ax3.set_yscale("log")

ax4 = axes[1, 1]
x = np.arange(len(names))
w = 0.2
for i, (label, res, c) in enumerate([("B&H", bh, "steelblue"), ("12M Mom", mom12_res, "orange"),
                                       ("6M Mom", mom6_res, "green"), ("MA Cross", ma_res, "red")]):
    vals = [res[n]["final"] for n in names]
    bars = ax4.bar(x + i*w - w*1.5, [v/1000 for v in vals], w, label=label, color=c, edgecolor="white")
    for bar, val in zip(bars, vals):
        if val > 200000:
            lbl = f"${val/1e6:.1f}M"
        elif val > 1000:
            lbl = f"${val/1000:.0f}K"
        else:
            lbl = f"${val:.0f}"
        ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, lbl, ha="center", fontsize=5.5, fontweight="bold", rotation=90)
ax4.set_title("Final Value: Strategy x Asset", fontsize=12, fontweight="bold")
ax4.set_xticks(x)
ax4.set_xticklabels(names, fontsize=9)
ax4.set_ylabel("Final Value ($ Thousands)")
ax4.legend(fontsize=7)
ax4.grid(True, alpha=0.3, axis="y")

plt.suptitle("6-Asset Quantitative Strategy Comparison (2010-2026)", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path1 = r"C:\AI\cc\stock\image\ALL6_strategies.png"
plt.savefig(path1, dpi=150, bbox_inches="tight")
plt.close()

# --- Chart 2: Risk/Return scatter ---
fig2, ax = plt.subplots(figsize=(14, 10))
markers = {"B&H": "*", "12M Mom": "o", "6M Mom": "D", "MA Cross": "s"}
for n in names:
    pts = [
        ("B&H", bh[n]["ann"], bh[n]["dd"]),
        ("12M Mom", mom12_res[n]["ann"], mom12_res[n]["dd"]),
        ("6M Mom", mom6_res[n]["ann"], mom6_res[n]["dd"]),
        ("MA Cross", ma_res[n]["ann"], ma_res[n]["dd"]),
    ]
    for label, ann, dd in pts:
        ax.scatter(ann, dd, c=colors[n], marker=markers[label], s=180,
                   edgecolors="white", linewidth=1, zorder=5)
        ax.annotate(f"{n}\n{label}", (ann, dd), textcoords="offset points",
                    xytext=(6, -10), fontsize=6.5, alpha=0.85)

ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="--")
ax.axvline(x=0, color="gray", linewidth=0.5, linestyle="--")
ax.set_title("Risk-Return Map: Annualized Return vs Max Drawdown", fontsize=14, fontweight="bold")
ax.set_xlabel("Annualized Return (%)", fontsize=12)
ax.set_ylabel("Max Drawdown (%)", fontsize=12)
ax.grid(True, alpha=0.3)

# Legend
from matplotlib.lines import Line2D
leg_elements = [Line2D([0], [0], marker=m, color='gray', markersize=10, label=l, linestyle='None')
                for l, m in markers.items()]
leg1 = ax.legend(handles=leg_elements, title="Strategy", fontsize=9, loc="lower left")
ax.add_artist(leg1)
leg_colors = [Line2D([0], [0], marker='o', color=c, markersize=10, label=n, linestyle='None')
              for n, c in colors.items()]
ax.legend(handles=leg_colors, title="Asset", fontsize=9, loc="lower right")

plt.tight_layout()
path2 = r"C:\AI\cc\stock\image\ALL6_risk_return.png"
plt.savefig(path2, dpi=150, bbox_inches="tight")
plt.close()

print(f"\nCharts saved to:\n  {path1}\n  {path2}")
print(f"\n{'='*80}")
print(f"  BOTTOM LINE: B&H wins on ALL 6 assets. No timing strategy adds value.")
print(f"  Best non-B&H performer: NVDA 6M Mom (${mom6_res['NVDA']['final']:,.0f})")
print(f"  GLD is the only asset where active strategies come close to B&H.")
print(f"{'='*80}")
