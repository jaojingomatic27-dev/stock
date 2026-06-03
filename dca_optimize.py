# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load data from 2016
# ============================================================
def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[close.index >= "2016-01-01"]

spy = load_close(r"C:\AI\cc\stock\SPY_daily.csv", "SPY")
nvda = load_close(r"C:\AI\cc\stock\NVDA_daily.csv", "NVDA")

MIN_AMOUNT = 500.0
MID_AMOUNT = 1000.0
MAX_AMOUNT = 1500.0
AVG_AMOUNT = 1000.0  # For fair comparison, all strategies avg ~$1000/mo

print("=" * 80)
print(f"  Optimized DCA Strategies: ${MIN_AMOUNT:.0f} ~ ${MAX_AMOUNT:.0f}/month")
print(f"  Start: 2016-01 ~ 2026-06 (10.5 years)")
print(f"  SPY: ${spy.iloc[0]:.2f} -> ${spy.iloc[-1]:.2f}")
print(f"  NVDA: ${nvda.iloc[0]:.2f} -> ${nvda.iloc[-1]:.2f}")
print("=" * 80)

# ============================================================
# DCA Rule Functions - each returns (amount, reason) per month
# ============================================================

class DCARules:
    @staticmethod
    def fixed(price, prev_prices, position, history):
        """Baseline: always $1000"""
        return MID_AMOUNT

    @staticmethod
    def buy_dip_drawdown(price, prev_prices, position, history):
        """Invest more when price is far below 12-month high"""
        if len(prev_prices) < 252:
            return MID_AMOUNT
        high_12m = prev_prices[-252:].max()
        ratio = price / high_12m
        if ratio < 0.80:   return MAX_AMOUNT  # -20%+ from high: BUY BIG
        elif ratio < 0.90: return (MID_AMOUNT + MAX_AMOUNT) / 2  # -10~20%: $1250
        elif ratio > 0.97: return MIN_AMOUNT  # near high: buy less
        else:              return MID_AMOUNT

    @staticmethod
    def rsi_rule(price, prev_prices, position, history):
        """RSI(14): oversold=invest more, overbought=invest less"""
        if len(prev_prices) < 20:
            return MID_AMOUNT
        recent = prev_prices[-15:]  # last 15 days including today
        deltas = np.diff(recent)
        gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
        losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0
        rs = gains / losses if losses > 0 else 100
        rsi = 100 - (100 / (1 + rs))
        if rsi < 35:       return MAX_AMOUNT   # oversold
        elif rsi < 45:     return (MAX_AMOUNT + MID_AMOUNT) / 2  # $1250
        elif rsi > 70:     return MIN_AMOUNT   # overbought
        elif rsi > 60:     return (MIN_AMOUNT + MID_AMOUNT) / 2  # $750
        else:              return MID_AMOUNT

    @staticmethod
    def ma200_rule(price, prev_prices, position, history):
        """Price vs MA200: below=buy more (fear), far above=buy less (greed)"""
        if len(prev_prices) < 200:
            return MID_AMOUNT
        ma200 = prev_prices[-200:].mean()
        ratio = price / ma200
        if ratio < 0.85:   return MAX_AMOUNT    # deep fear
        elif ratio < 0.95: return (MAX_AMOUNT + MID_AMOUNT) / 2  # mild fear
        elif ratio < 1.00: return MID_AMOUNT
        elif ratio > 1.40: return MIN_AMOUNT    # extreme greed
        elif ratio > 1.20: return (MIN_AMOUNT + MID_AMOUNT) / 2  # greed
        else:              return MID_AMOUNT

    @staticmethod
    def volatility_rule(price, prev_prices, position, history):
        """Buy more when recent volatility is high (fear/V-shaped)"""
        if len(prev_prices) < 22:
            return MID_AMOUNT
        returns = prev_prices[-22:].pct_change().dropna() if hasattr(prev_prices[-22:], 'pct_change') else pd.Series(prev_prices[-22:]).pct_change().dropna()
        vol = returns.std()
        # Normalize: compare current vol to 1-year historical vol
        if len(prev_prices) >= 252:
            hist_ret = pd.Series(prev_prices[-252:]).pct_change().dropna()
            hist_vol = hist_ret.std()
            vol_ratio = vol / hist_vol if hist_vol > 0 else 1.0
        else:
            vol_ratio = 1.0
        if vol_ratio > 1.5:    return MAX_AMOUNT    # panic: buy big
        elif vol_ratio > 1.2:  return (MAX_AMOUNT + MID_AMOUNT) / 2
        elif vol_ratio < 0.6:  return MIN_AMOUNT    # calm: buy less
        else:                  return MID_AMOUNT

    @staticmethod
    def combo_rule(price, prev_prices, position, history):
        """Combine: drawdown + MA200. Majority vote decides tilt."""
        if len(prev_prices) < 252:
            return MID_AMOUNT
        # Drawdown signal
        dd_ratio = price / prev_prices[-252:].max()
        dd_score = 1 if dd_ratio < 0.80 else 0.5 if dd_ratio < 0.90 else 0 if dd_ratio > 0.97 else 0.5
        # MA200 signal
        ma200 = prev_prices[-200:].mean()
        ma_ratio = price / ma200
        ma_score = 1 if ma_ratio < 0.85 else 0.5 if ma_ratio < 0.95 else 0 if ma_ratio > 1.20 else 0.5
        # Average score
        avg_score = (dd_score + ma_score) / 2
        if avg_score > 0.7:   return MAX_AMOUNT
        elif avg_score > 0.5: return (MAX_AMOUNT + MID_AMOUNT) / 2
        elif avg_score < 0.2: return MIN_AMOUNT
        elif avg_score < 0.4: return (MIN_AMOUNT + MID_AMOUNT) / 2
        else:                return MID_AMOUNT

# ============================================================
# Run all strategies
# ============================================================
def run_dca_strategy(close_series, rule_func, rule_name):
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
    prev_prices = close_series[:first_dates[0]].tolist()

    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        prev_prices.append(price)
        amount = rule_func(price, np.array(prev_prices), total_shares, None)
        amount = np.clip(amount, MIN_AMOUNT, MAX_AMOUNT)
        shares_bought = amount / price
        total_shares += shares_bought
        total_invested += amount
        records.append({
            "date": dt, "price": price, "amount": amount,
            "shares_bought": shares_bought, "total_shares": total_shares,
            "invested": total_invested, "value": total_shares * price,
        })

    df_rec = pd.DataFrame(records).set_index("date")
    # Daily values
    daily = []
    for date in close_series.index:
        if date < df_rec.index[0]:
            continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        daily.append({"date": date, "value": last["total_shares"] * close_series.loc[date],
                       "invested": last["invested"]})
    daily_df = pd.DataFrame(daily).set_index("date")

    final_value = total_shares * close_series.iloc[-1]
    total_return = (final_value - total_invested) / total_invested * 100
    months = len(first_dates)
    years = months / 12.0
    ann_ret = ((final_value / total_invested) ** (1 / years) - 1) * 100 if years > 0 else 0

    return {
        "name": rule_name,
        "records": df_rec,
        "daily": daily_df,
        "total_invested": total_invested,
        "final_value": final_value,
        "total_return": total_return,
        "ann_ret": ann_ret,
        "total_shares": total_shares,
        "months": months,
        "avg_monthly": total_invested / months,
    }

# All rules
rules = [
    (DCARules.fixed, "1. Fixed $1000 (Baseline)"),
    (DCARules.buy_dip_drawdown, "2. Buy-the-Dip (12M High)"),
    (DCARules.rsi_rule, "3. RSI(14) Oversold/Bought"),
    (DCARules.ma200_rule, "4. MA200 Fear/Greed"),
    (DCARules.volatility_rule, "5. Volatility-Weighted"),
    (DCARules.combo_rule, "6. Combo (DD + MA200)"),
]

for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    print(f"\n{'='*80}")
    print(f"  {asset_name} - Enhanced DCA Strategy Comparison")
    print(f"{'='*80}")
    results = []
    for rule_fn, rule_name in rules:
        r = run_dca_strategy(series, rule_fn, rule_name)
        results.append(r)

    # Sort by final value
    results.sort(key=lambda x: x["final_value"], reverse=True)
    best = results[0]

    print(f"  {'Strategy':<32} {'Invested':>12} {'Final $':>14} {'Return':>10} {'Ann.Ret':>9} {'Avg/mo':>9}")
    print(f"  {'─'*88}")
    for r in results:
        marker = " <<<" if r == best else ""
        print(f"  {r['name']:<32} ${r['total_invested']:>11,.0f} ${r['final_value']:>13,.0f} "
              f"{r['total_return']:>9.1f}% {r['ann_ret']:>8.1f}% ${r['avg_monthly']:>8.0f}{marker}")

    # Compare with simple DCA at $1000
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    improvement = ((best["final_value"] / baseline["final_value"]) - 1) * 100
    print(f"\n  Best vs Baseline: +{improvement:.1f}% more final value")

    # Investment distribution for best strategy
    best_rec = best["records"]
    low_pct = (best_rec["amount"] == MIN_AMOUNT).sum() / len(best_rec) * 100
    mid_pct = (best_rec["amount"] == MID_AMOUNT).sum() / len(best_rec) * 100
    high_pct = (best_rec["amount"] == MAX_AMOUNT).sum() / len(best_rec) * 100
    other_pct = 100 - low_pct - mid_pct - high_pct
    print(f"  Invest distribution: ${MIN_AMOUNT:.0f}:{low_pct:.0f}%  ${MID_AMOUNT:.0f}:{mid_pct:.0f}%  "
          f"${MAX_AMOUNT:.0f}:{high_pct:.0f}%  other:{other_pct:.0f}%")

# ============================================================
# Charts
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(24, 14))

for col, (asset_name, series) in enumerate([("SPY", spy), ("NVDA", nvda)]):
    # Run all strategies
    asset_results = []
    for rule_fn, rule_name in rules:
        r = run_dca_strategy(series, rule_fn, rule_name)
        asset_results.append(r)
    asset_results.sort(key=lambda x: x["final_value"], reverse=True)

    # Panel: Equity curves for top 3 vs baseline (col 0 or 1)
    ax_equity = axes[0, col]
    colors_line = ["#2ca02c", "#ff7f0e", "#d62728", "black"]
    # Baseline (fixed)
    baseline = [r for r in asset_results if "Fixed" in r["name"]][0]
    # Top 3 non-baseline
    top3 = [r for r in asset_results if "Fixed" not in r["name"]][:3]
    to_plot = [baseline] + top3
    for i, r in enumerate(to_plot):
        c = colors_line[i] if r != baseline else "gray"
        lw = 2.0 if r == asset_results[0] else 1.2
        ls = "--" if r == baseline else "-"
        ax_equity.plot(r["daily"].index, r["daily"]["value"], color=c, linewidth=lw,
                       linestyle=ls, label=r["name"].split(". ")[1], alpha=0.9)
    ax_equity.set_title(f"{asset_name} - DCA Strategy Equity Curves", fontsize=12, fontweight="bold")
    ax_equity.set_ylabel("Portfolio Value ($)")
    ax_equity.legend(fontsize=7)
    ax_equity.grid(True, alpha=0.3)

    # Panel: Monthly investment amounts heat map/bars
    ax_amounts = axes[1, col]
    best_r = asset_results[0]
    best_rec = best_r["records"]
    # Quarterly for readability
    q_amounts = best_rec["amount"].resample("QE").mean()
    colors_amt = ["#d62728" if a >= MAX_AMOUNT * 0.9 else "#2ca02c" if a <= MIN_AMOUNT * 1.1 else "#ff7f0e"
                  for a in q_amounts]
    ax_amounts.bar(q_amounts.index, q_amounts, width=60, color=colors_amt, alpha=0.7)
    ax_amounts.axhline(y=MID_AMOUNT, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax_amounts.set_title(f"{asset_name} - Best Strategy: {best_r['name'].split('. ')[1]}", fontsize=11, fontweight="bold")
    ax_amounts.set_ylabel("Monthly Investment ($)")
    ax_amounts.set_ylim(0, MAX_AMOUNT * 1.3)
    ax_amounts.grid(True, alpha=0.3, axis="y")

# Panel 3 (col 2): SPY vs NVDA Best Strategy Comparison
ax_comp = axes[0, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    ar = []
    for rule_fn, rule_name in rules:
        ar.append(run_dca_strategy(series, rule_fn, rule_name))
    ar.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in ar if "Fixed" in r["name"]][0]
    best = ar[0]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    ax_comp.plot(best["daily"].index, best["daily"]["value"], color=color, linewidth=2, label=f"{asset_name} Best")
    ax_comp.plot(baseline["daily"].index, baseline["daily"]["value"], color=color, linewidth=1, linestyle="--", alpha=0.5, label=f"{asset_name} Fixed")
ax_comp.set_title("SPY vs NVDA: Best Strategy", fontsize=12, fontweight="bold")
ax_comp.set_ylabel("Portfolio Value ($)")
ax_comp.legend(fontsize=8)
ax_comp.grid(True, alpha=0.3)
ax_comp.set_yscale("log")

# Panel 4 (col 2): Bar chart - Final value comparison
ax_bar = axes[1, 2]
spy_ar = []
for rule_fn, rule_name in rules:
    spy_ar.append(run_dca_strategy(spy, rule_fn, rule_name))
nvda_ar = []
for rule_fn, rule_name in rules:
    nvda_ar.append(run_dca_strategy(nvda, rule_fn, rule_name))

spy_ar.sort(key=lambda x: x["final_value"], reverse=True)
nvda_ar.sort(key=lambda x: x["final_value"], reverse=True)

names_short = [r["name"].split(". ")[1] for r in spy_ar]
x = np.arange(len(names_short))
w = 0.35
spy_vals = [r["final_value"] for r in spy_ar]
nvda_vals = [r["final_value"] for r in nvda_ar]

bars1 = ax_bar.barh(x - w/2, [v/1000 for v in spy_vals], w, color="#1f77b4", alpha=0.7, label="SPY")
bars2 = ax_bar.barh(x + w/2, [v/1000 for v in nvda_vals], w, color="#76B900", alpha=0.7, label="NVDA")
for bar, val in zip(bars1, spy_vals):
    ax_bar.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2, f"${val/1000:.0f}K", va="center", fontsize=7)
for bar, val in zip(bars2, nvda_vals):
    ax_bar.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2, f"${val/1000:.0f}K", va="center", fontsize=7)
ax_bar.set_yticks(x)
ax_bar.set_yticklabels(names_short, fontsize=7)
ax_bar.set_title("All Strategies Final Value", fontsize=12, fontweight="bold")
ax_bar.set_xlabel("Final Value ($ Thousands)")
ax_bar.legend(fontsize=8)
ax_bar.grid(True, alpha=0.3, axis="x")
ax_bar.invert_yaxis()

plt.suptitle("Enhanced DCA Strategies: $500-$1500/month Rule Optimization (2016-2026)", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path = r"C:\AI\cc\stock\DCA_optimized.png"
plt.savefig(path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {path}")
plt.close()
