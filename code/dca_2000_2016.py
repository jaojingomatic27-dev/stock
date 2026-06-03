# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# Load data: 2000-01-01 to 2016-01-01
# ============================================================
def load_close(path, col_name, start="2000-01-01", end="2016-01-01"):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[start:end]

spy = load_close(r"C:\AI\cc\stock\data\SPY_daily.csv", "SPY")
nvda = load_close(r"C:\AI\cc\stock\data\NVDA_daily.csv", "NVDA")

# Check data availability
print("=" * 80)
print(f"  Data Availability Check")
print(f"  SPY:  {spy.index[0].strftime('%Y-%m-%d')} ~ {spy.index[-1].strftime('%Y-%m-%d')}  ({len(spy)} days)")
print(f"  NVDA: {nvda.index[0].strftime('%Y-%m-%d')} ~ {nvda.index[-1].strftime('%Y-%m-%d')}  ({len(nvda)} days)")
print("=" * 80)

BASE, MIN_A, MAX_A = 1000.0, 500.0, 1500.0

# ============================================================
# Strategy rules (same as v2)
# ============================================================
def rule_fixed(state): return BASE

def rule_drawdown_3m(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 63: return BASE
    high_3m = max(prices[i-63:i+1])
    dd = (price - high_3m) / high_3m
    if dd < -0.10:   return MAX_A
    elif dd < -0.05: return 1250
    elif dd < -0.02: return 1100
    elif dd > -0.01: return MIN_A
    else:            return BASE

def rule_ma50(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 60: return BASE
    ma50 = np.mean(prices[i-50:i+1])
    ratio = price / ma50
    if ratio < 0.92:   return MAX_A
    elif ratio < 0.96: return 1250
    elif ratio < 0.99: return 1100
    elif ratio > 1.08: return MIN_A
    elif ratio > 1.04: return 750
    else:              return BASE

def rule_bear_bull(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 200: return BASE
    ma200 = np.mean(prices[i-200:i+1])
    ratio_200 = price / ma200
    above_ma50 = price > np.mean(prices[i-50:i+1])
    if price < ma200:        return MAX_A
    elif not above_ma50:    return 1250
    elif ratio_200 > 1.35:  return MIN_A
    elif ratio_200 > 1.15:  return 750
    else:                   return BASE

def rule_rsi(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 20: return BASE
    recent = np.array(prices[i-14:i+1])
    deltas = np.diff(recent)
    gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
    losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0.0001
    rsi = 100 - (100 / (1 + gains/losses))
    if rsi < 35:     return MAX_A
    elif rsi < 45:   return 1250
    elif rsi > 70:   return MIN_A
    elif rsi > 60:   return 750
    else:            return BASE

def rule_volatility(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 252: return BASE
    r1 = np.diff(np.array(prices[i-21:i+1])) / np.array(prices[i-21:i])
    vol_1m = np.std(r1) if len(r1) > 1 else 0
    r2 = np.diff(np.array(prices[i-252:i+1])) / np.array(prices[i-252:i])
    vol_1y = np.std(r2) if len(r2) > 1 else 0.0001
    ratio = vol_1m / vol_1y if vol_1y > 0 else 1.0
    if ratio > 1.5:    return MAX_A
    elif ratio > 1.2:  return 1250
    elif ratio < 0.6:  return MIN_A
    else:              return BASE

def rule_momentum(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 63: return BASE
    mom_3m = price / prices[i-63] - 1
    mom_12m = price / prices[i-252] - 1 if i >= 252 else mom_3m
    score = 0.0
    if mom_3m < -0.08:  score += 0.4
    elif mom_3m < 0:    score += 0.2
    elif mom_3m > 0.15: score -= 0.3
    if mom_12m < -0.10: score += 0.4
    elif mom_12m < 0:   score += 0.15
    elif mom_12m > 0.35: score -= 0.3
    if score > 0.5:     return MAX_A
    elif score > 0.25:  return 1250
    elif score < -0.4:  return MIN_A
    elif score < -0.2:  return 750
    else:               return BASE

def rule_buy_dips(state):
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 126: return BASE
    high_1m = max(prices[i-21:i+1])
    high_6m = max(prices[i-126:i+1])
    high_1y = max(prices[i-252:i+1])
    dd_1m = (price - high_1m) / high_1m
    dd_6m = (price - high_6m) / high_6m
    dd_1y = (price - high_1y) / high_1y
    amount = BASE
    if dd_1m < -0.03: amount += 150
    if dd_1m < -0.06: amount += 150
    if dd_6m < -0.10: amount += 100
    if dd_6m < -0.20: amount += 100
    if dd_1y < -0.15: amount += 100
    if dd_1y < -0.25: amount += 100
    if dd_1m > -0.01 and dd_6m > -0.02: amount -= 250
    if dd_1y > -0.03: amount -= 250
    return max(MIN_A, min(MAX_A, amount))

# ============================================================
# Backtest with cash reserve
# ============================================================
def backtest_equal(close_series, desire_func):
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close_series.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    n = len(first_dates)
    cash = 0.0; shares = 0.0; invested = 0.0
    prices_hist = list(first_prices)
    records = []

    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        state = {"price": price, "i": i, "prices": prices_hist,
                 "shares": shares, "invested": invested,
                 "reserve": cash, "month": i, "total_months": n}
        desired = desire_func(state)
        if desired > BASE:
            extra = min(desired - BASE, cash)
            actual = BASE + extra
        elif desired < BASE:
            save = min(BASE - desired, BASE - MIN_A)
            actual = BASE - save
        else:
            actual = BASE
        actual = max(MIN_A, min(MAX_A, actual))

        if actual < BASE:   cash += (BASE - actual)
        elif actual > BASE: cash -= (actual - BASE)

        shares += actual / price
        invested += actual
        records.append({"date": dt, "price": price, "desired": desired, "actual": actual,
                        "reserve": cash, "shares": shares, "invested": invested,
                        "value": shares * price})

    df_rec = pd.DataFrame(records).set_index("date")
    daily = []
    for date in close_series.index:
        if date < df_rec.index[0]: continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        daily.append({"date": date, "value": last["shares"] * close_series.loc[date],
                       "invested": last["invested"]})
    daily_df = pd.DataFrame(daily).set_index("date")

    final_value = shares * close_series.iloc[-1]
    total_return = (final_value - invested) / invested * 100
    years = n / 12.0
    ann_ret = ((final_value / invested) ** (1 / years) - 1) * 100
    return {
        "total_invested": invested, "final_value": final_value,
        "total_return": total_return, "ann_ret": ann_ret,
        "avg_monthly": invested / n, "final_reserve": cash, "months": n,
        "records": df_rec, "daily": daily_df,
    }

# ============================================================
# Run
# ============================================================
all_rules = [
    (rule_fixed, "Fixed $1000"),
    (rule_drawdown_3m, "Drawdown (3M High)"),
    (rule_ma50, "MA50 Distance"),
    (rule_rsi, "RSI(14)"),
    (rule_bear_bull, "Bear/Bull (MA200)"),
    (rule_volatility, "Volatility Panic"),
    (rule_momentum, "Momentum Adaptive"),
    (rule_buy_dips, "Buy Dips Aggressive"),
]

period_label = "2000-2016 (Bear Market Era)"

for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    # Check if we have enough data
    if len(series) < 252:  # less than 1 year
        print(f"\n{asset_name}: INSUFFICIENT DATA ({len(series)} days) - skipping")
        continue

    price_start = series.iloc[0]
    price_end = series.iloc[-1]
    bh_ret = (price_end / price_start - 1) * 100
    years = (series.index[-1] - series.index[0]).days / 365.25

    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal(series, rule_fn)
        r["name"] = rule_name
        results.append(r)

    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]

    print(f"\n{'─'*80}")
    print(f"  {asset_name} — {period_label}")
    print(f"  Price: ${price_start:.2f} -> ${price_end:.2f} ({bh_ret:+.1f}%, {years:.1f}y)")
    print(f"  Target total: ${baseline['total_invested']:,.0f} over {baseline['months']} months")
    print(f"{'─'*80}")
    print(f"  {'#':<3} {'Strategy':<24} {'Invested':>11} {'Final $':>14} {'Return':>9} {'Ann':>8} {'vs Fixed':>10} {'Reserve':>10}")
    print(f"  {'─'*90}")

    for i, r in enumerate(results):
        vf = ((r["final_value"] / baseline["final_value"]) - 1) * 100
        marker = " <<< BEST" if r["name"] == best["name"] else ""
        print(f"  {i+1:<3} {r['name']:<24} ${r['total_invested']:>10,.0f} ${r['final_value']:>13,.0f} "
              f"{r['total_return']:>8.1f}% {r['ann_ret']:>7.1f}% {vf:>+9.2f}% ${r['final_reserve']:>9,.0f}{marker}")

    # Best strategy analysis
    best_rec = best["records"]
    lo = (best_rec["actual"] <= MIN_A + 1).sum()
    hi = (best_rec["actual"] >= MAX_A - 1).sum()
    mid = (abs(best_rec["actual"] - BASE) < 1).sum()
    print(f"\n  Best [{best['name']}]: ${MIN_A:.0f}:{lo}mo  ${BASE:.0f}:{mid}mo  ${MAX_A:.0f}:{hi}mo  "
          f"Cash unused: ${best['final_reserve']:,.0f}")

    max_m = best_rec[best_rec["actual"] >= MAX_A - 1]
    min_m = best_rec[best_rec["actual"] <= MIN_A + 1]
    if len(max_m) > 0:
        print(f"    MAX ($1500) in: {', '.join(max_m.index.strftime('%Y-%m')[:6])}")
    if len(min_m) > 0:
        print(f"    MIN ($500)  in: {', '.join(min_m.index.strftime('%Y-%m')[:6])}")

# ============================================================
# Combined chart
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(24, 13))

for col, (asset_name, series) in enumerate([("SPY", spy), ("NVDA", nvda)]):
    if len(series) < 252:
        continue
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal(series, rule_fn)
        r["name"] = rule_name
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]

    # Panel: Equity curves
    ax1 = axes[0, col]
    top_plot = [baseline] + [r for r in results if r["name"] != baseline["name"]][:3]
    colors = ["gray", "#2ca02c", "#ff7f0e", "#d62728"]
    for i, r in enumerate(top_plot):
        ls = "--" if "Fixed" in r["name"] else "-"
        lw = 3 if r["name"] == best["name"] else 1.2
        lbl = r["name"] + (" <<<" if r["name"] == best["name"] else "")
        ax1.plot(r["daily"].index, r["daily"]["value"], color=colors[i], linewidth=lw,
                 linestyle=ls, label=lbl, alpha=0.9)
    ax1.set_title(f"{asset_name} ({period_label})", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Value ($)")
    ax1.legend(fontsize=6.5)
    ax1.grid(True, alpha=0.3)

    # Panel: Monthly investment pattern
    ax2 = axes[1, col]
    rec = best["records"]
    q_amts = rec["actual"].resample("QE").mean()
    colors_amt = []
    for a in q_amts:
        if a >= MAX_A * 0.9: colors_amt.append("#d62728")
        elif a <= MIN_A * 1.1: colors_amt.append("#2ca02c")
        elif a > BASE * 1.05: colors_amt.append("#ff7f0e")
        elif a < BASE * 0.95: colors_amt.append("#1f77b4")
        else: colors_amt.append("gray")
    ax2.bar(q_amts.index, q_amts, width=60, color=colors_amt, alpha=0.75)
    ax2.axhline(y=BASE, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_title(f"{asset_name} Best: {best['name']}", fontsize=10, fontweight="bold")
    ax2.set_ylabel("Monthly Invest ($)")
    ax2.set_ylim(0, MAX_A * 1.3)
    ax2.grid(True, alpha=0.3, axis="y")

# Panel: SPY vs NVDA best (log)
ax3 = axes[0, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    if len(series) < 252: continue
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal(series, rule_fn)
        r["name"] = rule_name
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    bl = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]
    c = "#1f77b4" if asset_name == "SPY" else "#76B900"
    ax3.plot(best["daily"].index, best["daily"]["value"], color=c, lw=2, label=f"{asset_name} Best")
    ax3.plot(bl["daily"].index, bl["daily"]["value"], color=c, lw=0.8, ls="--", alpha=0.4, label=f"{asset_name} Fixed")
ax3.set_title("SPY vs NVDA Best Strategy (Log)", fontsize=11, fontweight="bold")
ax3.set_ylabel("Value ($)")
ax3.legend(fontsize=7)
ax3.grid(True, alpha=0.3)
ax3.set_yscale("log")

# Panel: Improvement over baseline
ax4 = axes[1, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    if len(series) < 252: continue
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal(series, rule_fn)
        r["name"] = rule_name
        results.append(r)
    bl = [r for r in results if "Fixed" in r["name"]][0]
    results_sorted = sorted(results, key=lambda x: x["final_value"], reverse=True)
    names = [r["name"] for r in results_sorted]
    imps = [(r["final_value"] / bl["final_value"] - 1) * 100 for r in results_sorted]
    w = 0.35
    offset = -w/2 if asset_name == "SPY" else w/2
    c = "#1f77b4" if asset_name == "SPY" else "#76B900"
    x = np.arange(len(names))
    bars = ax4.barh(x + offset, imps, w, color=c, alpha=0.7, label=asset_name)
    for bar, imp in zip(bars, imps):
        ax4.text(bar.get_width() + (0.1 if bar.get_width() >= 0 else -0.5),
                 bar.get_y() + bar.get_height()/2, f"{imp:+.1f}%", va="center", fontsize=7)
ax4.set_yticks(x)
ax4.set_yticklabels(names, fontsize=7)
ax4.set_title("Improvement vs Fixed $1000", fontsize=11, fontweight="bold")
ax4.set_xlabel("Excess Return (%)")
ax4.legend(fontsize=8)
ax4.axvline(x=0, color="black", linewidth=0.5, linestyle="--")
ax4.grid(True, alpha=0.3, axis="x")
ax4.invert_yaxis()

plt.suptitle(f"Equal-Total DCA Strategy Comparison: {period_label}", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path = r"C:\AI\cc\stock\image\DCA_2000_2016.png"
plt.savefig(path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {path}")
plt.close()

# ============================================================
# Summary comparison table
# ============================================================
print(f"\n{'='*80}")
print(f"  CROSS-ERA COMPARISON: 2000-2016 vs 2016-2026")
print(f"{'='*80}")
print(f"  {'Strategy':<24} {'SPY 00-16':>12} {'SPY 16-26':>12} {'NVDA 00-16':>12} {'NVDA 16-26':>12}")
print(f"  {'─'*72}")
print(f"  {'Market Type':<24} {'BEAR-heavy':>12} {'BULL-only':>12} {'BEAR-heavy':>12} {'BULL-only':>12}")
print(f"  {'─'*72}")
for name in ["Fixed $1000", "Drawdown (3M High)", "Bear/Bull (MA200)", "RSI(14)", "MA50 Distance",
             "Momentum Adaptive", "Buy Dips Aggressive", "Volatility Panic"]:
    row = f"  {name:<24}"
    for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
        if len(series) < 252:
            row += f" {'N/A':>12}"
        else:
            results = []
            for rule_fn, rule_name in all_rules:
                r = backtest_equal(series, rule_fn)
                r["name"] = rule_name
                results.append(r)
            bl = [r for r in results if "Fixed" in r["name"]][0]
            r_match = [r for r in results if r["name"] == name]
            if r_match:
                vf = (r_match[0]["final_value"] / bl["final_value"] - 1) * 100
                row += f" {vf:>+11.1f}%"
            else:
                row += f" {'—':>12}"
    print(row)
