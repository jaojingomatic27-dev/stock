# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close[close.index >= "2016-01-01"]

spy = load_close(r"C:\AI\cc\stock\data\SPY_daily.csv", "SPY")
nvda = load_close(r"C:\AI\cc\stock\data\NVDA_daily.csv", "NVDA")

MIN_A, MID_A, MAX_A = 500.0, 1000.0, 1500.0
SHOW_TOP = 5  # how many strategies to show in detail

print("=" * 80)
print(f"  Optimized DCA v2: ${MIN_A:.0f}~${MAX_A:.0f}/month (2016-01 ~ 2026-06)")
print("=" * 80)

# ============================================================
# Strategy rules - return $amount for this month
# ============================================================
class Rules:
    @staticmethod
    def fixed(price, i, all_prices, shares, invested):
        return MID_A

    @staticmethod
    def drawdown_3m(price, i, all_prices, shares, invested):
        """Buy more based on drawdown from 3-month (63-day) high"""
        if i < 63: return MID_A
        high = max(all_prices[i-63:i])
        dd = (price - high) / high  # negative = drawdown
        if dd < -0.12:    return MAX_A      # -12%+ drawdown
        elif dd < -0.06:  return 1250        # -6%~-12%
        elif dd < -0.03:  return 1100
        elif dd > 0.02:   return MIN_A      # at/near new high
        else:             return MID_A

    @staticmethod
    def ma50_distance(price, i, all_prices, shares, invested):
        """Price relative to MA50"""
        if i < 60: return MID_A
        ma50 = np.mean(all_prices[i-50:i+1])
        ratio = price / ma50
        if ratio < 0.90:   return MAX_A
        elif ratio < 0.95: return 1250
        elif ratio < 0.98: return 1100
        elif ratio > 1.10: return MIN_A
        elif ratio > 1.05: return 750
        else:              return MID_A

    @staticmethod
    def value_averaging(price, i, all_prices, shares, invested):
        """Value Averaging: target portfolio grows 0.6%/month"""
        if i < 1: return MID_A * 1.5  # Start with $1500
        target_growth = 1.006  # 0.6% per month
        month_num = i + 1
        # Target value: if we invest $1000/month compounding at 0.6%
        target = MID_A * ((1 + target_growth) ** month_num - 1) / target_growth * target_growth
        current = shares * price
        needed = target - current
        # Buy enough to reach target, but capped
        amount = max(MIN_A, min(MAX_A, needed))
        return amount

    @staticmethod
    def buy_dips_aggressive(price, i, all_prices, shares, invested):
        """Each 5% dip from recent high adds $250 to investment"""
        if i < 21: return MID_A
        high_1m = max(all_prices[i-21:i+1])
        high_3m = max(all_prices[i-min(63,i):i+1])
        high_6m = max(all_prices[i-min(126,i):i+1])
        dd_1m = (price - high_1m) / high_1m
        dd_3m = (price - high_3m) / high_3m
        dd_6m = (price - high_6m) / high_6m

        amount = MID_A
        # Each 2.5% drawdown from 1M adds $125
        if dd_1m < -0.025: amount += 125
        if dd_1m < -0.05:  amount += 125
        if dd_1m < -0.075: amount += 125
        if dd_1m < -0.10:  amount += 125
        # Drawdown from 6M high adds more
        if dd_6m < -0.10:  amount += 250
        if dd_6m < -0.20:  amount += 250
        # Near highs: reduce
        if dd_1m > -0.01 and dd_3m > -0.02: amount -= 250
        if dd_6m > -0.02: amount -= 250
        return max(MIN_A, min(MAX_A, amount))

    @staticmethod
    def momentum_adaptive(price, i, all_prices, shares, invested):
        """Based on 3M and 12M momentum: buy more when momentum is weak/negative"""
        if i < 63: return MID_A
        mom_3m = price / all_prices[i-63] - 1
        mom_12m = price / all_prices[i-min(252,i)] - 1 if i >= 252 else mom_3m

        # Weak momentum = buy more (mean reversion bet)
        # Strong momentum = buy less (don't chase)
        amount = MID_A
        if mom_3m < -0.10:   amount += 250
        if mom_3m < -0.05:   amount += 125
        if mom_12m < -0.10:  amount += 250
        if mom_12m < -0.05:  amount += 125
        if mom_3m > 0.10:    amount -= 250
        if mom_3m > 0.20:    amount -= 250
        if mom_12m > 0.30:   amount -= 250
        return max(MIN_A, min(MAX_A, amount))

    @staticmethod
    def bear_bull_regime(price, i, all_prices, shares, invested):
        """MA50 vs MA200 regime + drawdown combo"""
        if i < 200: return MID_A
        ma50 = np.mean(all_prices[i-50:i+1])
        ma200 = np.mean(all_prices[i-200:i+1])
        above_ma200 = price > ma200
        above_ma50 = price > ma50
        high_3m = max(all_prices[i-63:i])
        dd = (price - high_3m) / high_3m

        if not above_ma200:
            # Bear market: aggressive buying
            amount = MAX_A
        elif not above_ma50 and above_ma200:
            # Correction in bull: buy more
            amount = 1250 if dd < -0.05 else 1000
        elif above_ma50 and dd < -0.03:
            # Mild dip: slight increase
            amount = 1100
        elif above_ma50 and dd > 0:
            # At highs: reduce
            amount = MIN_A if dd > 0.05 else 750
        else:
            amount = MID_A
        return amount

# ============================================================
# Run backtest for one strategy
# ============================================================
def backtest(close_series, rule_func):
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close_series.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    all_prices = list(first_prices)  # will grow
    total_shares = 0.0
    total_invested = 0.0
    records = []

    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        amount = rule_func(price, i, all_prices, total_shares, total_invested)
        amount = np.clip(amount, MIN_A, MAX_A)
        shares_bought = amount / price
        total_shares += shares_bought
        total_invested += amount
        all_prices[i] = price  # already in list
        records.append({"date": dt, "amount": amount, "price": price,
                        "shares": total_shares, "invested": total_invested,
                        "value": total_shares * price})

    df_rec = pd.DataFrame(records).set_index("date")
    daily_vals = []
    for date in close_series.index:
        if date < df_rec.index[0]: continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        daily_vals.append({"date": date, "value": last["shares"] * close_series.loc[date],
                           "invested": last["invested"]})
    daily_df = pd.DataFrame(daily_vals).set_index("date")

    final_value = total_shares * close_series.iloc[-1]
    total_return = (final_value - total_invested) / total_invested * 100
    years = len(first_dates) / 12.0
    ann_ret = ((final_value / total_invested) ** (1 / years) - 1) * 100 if years > 0 else 0

    return {
        "records": df_rec, "daily": daily_df,
        "total_invested": total_invested, "final_value": final_value,
        "total_return": total_return, "ann_ret": ann_ret,
        "avg_monthly": total_invested / len(first_dates),
        "shares": total_shares, "years": years,
    }

# ============================================================
# Run all strategies
# ============================================================
all_rules = [
    (Rules.fixed, "Fixed $1000"),
    (Rules.drawdown_3m, "Drawdown (3M High)"),
    (Rules.ma50_distance, "MA50 Distance"),
    (Rules.value_averaging, "Value Averaging"),
    (Rules.buy_dips_aggressive, "Buy Dips Aggressive"),
    (Rules.momentum_adaptive, "Momentum Adaptive"),
    (Rules.bear_bull_regime, "Bear/Bull Regime"),
]

for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    # Collect all results
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest(series, rule_fn)
        r["name"] = rule_name
        results.append(r)

    # Sort
    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]

    print(f"\n{'─'*80}")
    print(f"  {asset_name} - Enhanced DCA Results (2016-01 ~ 2026-06)")
    print(f"{'─'*80}")
    print(f"  {'#':<3} {'Strategy':<24} {'Invested':>10} {'Avg/mo':>8} {'Final $':>14} {'Return':>9} {'Ann':>8} {'vs Fixed':>10}")
    print(f"  {'─'*85}")

    for i, r in enumerate(results):
        vf = ((r["final_value"] / baseline["final_value"]) - 1) * 100
        # Only show top strategies in detail
        marker = " <<<" if r["name"] == best["name"] else ""
        print(f"  {i+1:<3} {r['name']:<24} ${r['total_invested']:>9,.0f} ${r['avg_monthly']:>7,.0f} "
              f"${r['final_value']:>13,.0f} {r['total_return']:>8.1f}% {r['ann_ret']:>7.1f}% {vf:>+9.1f}%{marker}")

    # Best strategy monthly distribution
    best_rec = best["records"]
    n = len(best_rec)
    lo = (best_rec["amount"] <= MIN_A + 1).sum()
    hi = (best_rec["amount"] >= MAX_A - 1).sum()
    mid = (abs(best_rec["amount"] - MID_A) < 1).sum()
    other = n - lo - mid - hi
    print(f"\n  Best [{best['name']}]: ${MIN_A:.0f}:{lo}({lo/n*100:.0f}%)  "
          f"${MID_A:.0f}:{mid}({mid/n*100:.0f}%)  ${MAX_A:.0f}:{hi}({hi/n*100:.0f}%)  "
          f"other:{other}({other/n*100:.0f}%)")

    # Show best buy points
    best_buys = best_rec[best_rec["amount"] >= MAX_A - 1]["price"]
    best_sells = best_rec[best_rec["amount"] <= MIN_A + 1]["price"]
    print(f"  MAX invest months: {len(best_buys)}  ({', '.join(best_buys.index.strftime('%Y-%m')[:5])}...)")
    print(f"  MIN invest months: {len(best_sells)}  ({', '.join(best_sells.index.strftime('%Y-%m')[:5])}...)")

# ============================================================
# Special: test with much wider range - prove the concept
# ============================================================
print(f"\n{'='*80}")
print(f"  EXTREME TEST: If you could perfectly time dips vs peaks")
print(f"  $1500 at EVERY -5%+ monthly drop, $500 at EVERY +5%+ monthly gain")
print(f"{'='*80}")

def perfect_clairvoyance(price, i, all_prices, shares, invested):
    """Can only know this month's return (no future knowledge)"""
    if i < 1: return MID_A
    monthly_ret = price / all_prices[i-1] - 1
    if monthly_ret < -0.05:  return MAX_A
    elif monthly_ret < -0.02: return 1250
    elif monthly_ret > 0.05:  return MIN_A
    elif monthly_ret > 0.02: return 750
    else: return MID_A

for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    r_perfect = backtest(series, perfect_clairvoyance)
    r_fixed = backtest(series, Rules.fixed)
    improvement = (r_perfect["final_value"] / r_fixed["final_value"] - 1) * 100
    print(f"  {asset_name}: Perfect timing = ${r_perfect['final_value']:,.0f} vs Fixed = ${r_fixed['final_value']:,.0f} (+{improvement:.1f}%)")
    print(f"    Avg/mo: ${r_perfect['avg_monthly']:.0f}, Return: {r_perfect['total_return']:.1f}%, Ann: {r_perfect['ann_ret']:.1f}%")

# ============================================================
# Charts
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(24, 14))

for col, (asset_name, series) in enumerate([("SPY", spy), ("NVDA", nvda)]):
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest(series, rule_fn)
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
        marker = " <<< BEST" if r["name"] == best["name"] else ""
        ls = "--" if "Fixed" in r["name"] else "-"
        ax1.plot(r["daily"].index, r["daily"]["value"], color=colors[i], linewidth=2.5 if r["name"] == best["name"] else 1.2,
                 linestyle=ls, label=r["name"] + marker, alpha=0.9)
    ax1.set_title(f"{asset_name} - DCA Equity Curves", fontsize=12, fontweight="bold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(fontsize=7)
    ax1.grid(True, alpha=0.3)

    # Panel: Monthly investment distribution
    ax2 = axes[1, col]
    best_rec = best["records"]
    # Color bars by amount
    amounts = best_rec["amount"]
    q_amts = amounts.resample("QE").mean()
    colors_amt = []
    for a in q_amts:
        if a >= MAX_A * 0.9: colors_amt.append("#d62728")
        elif a <= MIN_A * 1.1: colors_amt.append("#2ca02c")
        else: colors_amt.append("#ff7f0e")
    ax2.bar(q_amts.index, q_amts, width=60, color=colors_amt, alpha=0.7)
    ax2.axhline(y=MID_A, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax2.set_title(f"{asset_name} - Best: {best['name']} (${best['avg_monthly']:.0f}/mo avg)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Monthly Investment ($)")
    ax2.set_ylim(0, MAX_A * 1.3)
    ax2.grid(True, alpha=0.3, axis="y")

# Panel (0,2): SPY vs NVDA log-scale comparison
ax3 = axes[0, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest(series, rule_fn)
        r["name"] = rule_name
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    ax3.plot(best["daily"].index, best["daily"]["value"], color=color, linewidth=2, label=f"{asset_name} Best")
    ax3.plot(baseline["daily"].index, baseline["daily"]["value"], color=color, linewidth=0.8,
             linestyle="--", alpha=0.4, label=f"{asset_name} Fixed")
ax3.set_title("SPY vs NVDA: Best vs Fixed DCA (Log)", fontsize=12, fontweight="bold")
ax3.set_ylabel("Portfolio Value ($)")
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.3)
ax3.set_yscale("log")

# Panel (1,2): Improvement over baseline
ax4 = axes[1, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest(series, rule_fn)
        r["name"] = rule_name
        results.append(r)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    results_sorted = sorted(results, key=lambda x: x["final_value"], reverse=True)
    names = [r["name"] for r in results_sorted]
    imps = [(r["final_value"] / baseline["final_value"] - 1) * 100 for r in results_sorted]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    x = np.arange(len(names))
    w = 0.35
    offset = -w/2 if asset_name == "SPY" else w/2
    bars = ax4.barh(x + offset, imps, w, color=color, alpha=0.7, label=asset_name)
    for bar, imp in zip(bars, imps):
        ax4.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                 f"{imp:+.1f}%", va="center", fontsize=7)

ax4.set_yticks(x)
ax4.set_yticklabels(names, fontsize=7)
ax4.set_title("Improvement vs Fixed $1000 DCA", fontsize=12, fontweight="bold")
ax4.set_xlabel("Excess Return (%)")
ax4.legend(fontsize=8)
ax4.axvline(x=0, color="black", linewidth=0.5, linestyle="--")
ax4.grid(True, alpha=0.3, axis="x")
ax4.invert_yaxis()

plt.suptitle("Enhanced DCA Strategies: $500-$1500/month Optimization (2016-2026)", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path = r"C:\AI\cc\stock\image\DCA_optimized_v2.png"
plt.savefig(path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {path}")
plt.close()
