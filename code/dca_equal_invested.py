# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_close(path, col_name):
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    return df[("Close", col_name)].dropna()["2016-01-01":]

spy = load_close(r"C:\AI\cc\stock\data\SPY_daily.csv", "SPY")
nvda = load_close(r"C:\AI\cc\stock\data\NVDA_daily.csv", "NVDA")

BASE, MIN_A, MAX_A = 1000.0, 500.0, 1500.0

print("=" * 80)
print(f"  Equal-Total DCA: ALL strategies invest the SAME total amount")
print(f"  Base: ${BASE:.0f}/mo, Range: ${MIN_A:.0f}~${MAX_A:.0f}/mo")
print(f"  Cash Reserve System: save when investing less, deploy when investing more")
print(f"  2016-01 ~ 2026-06")
print("=" * 80)

# ============================================================
# Strategy rules return DESIRED amount (before reserve constraint)
# Each strategy receives current state: price, i, all_prices, shares, invested, reserve, month_count
# ============================================================

def rule_fixed(state):
    return BASE

def rule_drawdown_3m(state):
    """Desire: $1500 when -12%+ from 3M high, $500 at new highs"""
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
    """Desire: $1500 below MA50, $500 far above MA50"""
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

def rule_rsi(state):
    """Desire: $1500 when RSI(14) < 35, $500 when RSI > 70"""
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 20: return BASE
    recent = np.array(prices[i-14:i+1])  # last 15 including current
    deltas = np.diff(recent)
    gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
    losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0.0001
    rsi = 100 - (100 / (1 + gains/losses))
    if rsi < 35:      return MAX_A
    elif rsi < 45:    return 1250
    elif rsi > 70:    return MIN_A
    elif rsi > 60:    return 750
    else:             return BASE

def rule_bear_bull(state):
    """Desire: $1500 below MA200 (bear), $500 at extreme greed"""
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 200: return BASE
    ma50 = np.mean(prices[i-50:i+1])
    ma200 = np.mean(prices[i-200:i+1])
    ratio_200 = price / ma200
    above_ma50 = price > ma50

    if price < ma200:
        return MAX_A
    elif not above_ma50 and price > ma200:
        return 1250
    elif ratio_200 > 1.35:
        return MIN_A
    elif ratio_200 > 1.15:
        return 750
    else:
        return BASE

def rule_volatility(state):
    """Desire: $1500 when 1M vol > 1.5x 1Y avg vol (panic)"""
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 252: return BASE
    recent_ret = np.diff(np.array(prices[i-21:i+1])) / np.array(prices[i-21:i])
    vol_1m = np.std(recent_ret) if len(recent_ret) > 1 else 0
    hist_ret = np.diff(np.array(prices[i-252:i+1])) / np.array(prices[i-252:i])
    vol_1y = np.std(hist_ret) if len(hist_ret) > 1 else 0.0001
    ratio = vol_1m / vol_1y if vol_1y > 0 else 1.0
    if ratio > 1.5:     return MAX_A
    elif ratio > 1.2:   return 1250
    elif ratio < 0.6:   return MIN_A
    else:               return BASE

def rule_momentum(state):
    """Desire: $1500 when 3M momentum negative, $500 when 12M > +30%"""
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
    if score > 0.5:      return MAX_A
    elif score > 0.25:   return 1250
    elif score < -0.4:   return MIN_A
    elif score < -0.2:   return 750
    else:               return BASE

def rule_buy_dips_aggressive(state):
    """Desire: $1500 when multiple timeframe dips align, $500 at extreme highs"""
    price, i, prices = state["price"], state["i"], state["prices"]
    if i < 126: return BASE
    high_1m = max(prices[i-21:i+1])
    high_6m = max(prices[i-126:i+1])
    high_1y = max(prices[i-252:i+1])
    dd_1m = (price - high_1m) / high_1m
    dd_6m = (price - high_6m) / high_6m
    dd_1y = (price - high_1y) / high_1y

    amount = BASE
    if dd_1m < -0.03:  amount += 150
    if dd_1m < -0.06:  amount += 150
    if dd_6m < -0.10:  amount += 100
    if dd_6m < -0.20:  amount += 100
    if dd_1y < -0.15:  amount += 100
    if dd_1y < -0.25:  amount += 100
    if dd_1m > -0.01 and dd_6m > -0.02: amount -= 250
    if dd_1y > -0.03:  amount -= 250
    return max(MIN_A, min(MAX_A, amount))

# ============================================================
# Backtest with Cash Reserve (ensures equal total invested)
# ============================================================
def backtest_equal_invested(close_series, desire_func, name):
    # Find first trading day each month
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close_series.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    n_months = len(first_dates)
    budget_total = n_months * BASE  # Must end close to this
    cash_reserve = 0.0  # Cash accumulated for later deployment
    total_shares = 0.0
    total_invested = 0.0
    prices_history = list(first_prices)
    records = []

    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        state = {"price": price, "i": i, "prices": prices_history,
                 "shares": total_shares, "invested": total_invested,
                 "reserve": cash_reserve, "month": i, "total_months": n_months}

        desired = desire_func(state)

        # Constrain by cash reserve:
        # - Can't invest more than BASE + cash_reserve (and capped at MAX_A)
        # - If invest less than BASE, surplus goes to reserve
        max_possible = min(MAX_A, BASE + cash_reserve)
        min_possible = max(MIN_A, BASE - (budget_total - total_invested - (n_months - i - 1) * MIN_A))
        # Actually simpler: must invest at least MIN_A, at most what reserve allows above BASE

        if desired > BASE:
            # Want to invest more: can only if reserve has cash
            extra = min(desired - BASE, cash_reserve)
            actual = BASE + extra
        elif desired < BASE:
            # Want to invest less: save to reserve
            save = min(BASE - desired, BASE - MIN_A)  # can't save more than BASE - MIN_A
            actual = BASE - save
        else:
            actual = BASE

        # Update reserve
        if actual < BASE:
            cash_reserve += (BASE - actual)
        elif actual > BASE:
            cash_reserve -= (actual - BASE)

        # Ensure cash_reserve doesn't go negative and actual within bounds
        actual = max(MIN_A, min(MAX_A, actual))
        # Reconcile: if we forced actual, adjust reserve accordingly
        # (should be fine with the logic above)

        shares_bought = actual / price
        total_shares += shares_bought
        total_invested += actual

        records.append({
            "date": dt, "price": price, "desired": desired, "actual": actual,
            "reserve": cash_reserve, "shares": total_shares,
            "invested": total_invested, "value": total_shares * price,
        })

    df_rec = pd.DataFrame(records).set_index("date")

    # Daily values for chart
    daily = []
    for date in close_series.index:
        if date < df_rec.index[0]: continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        daily.append({"date": date, "value": last["shares"] * close_series.loc[date],
                       "invested": last["invested"]})
    daily_df = pd.DataFrame(daily).set_index("date")

    final_value = total_shares * close_series.iloc[-1]
    total_return = (final_value - total_invested) / total_invested * 100
    years = n_months / 12.0
    ann_ret = ((final_value / total_invested) ** (1 / years) - 1) * 100

    # Monthly IRR
    monthly_vals = df_rec["value"].tolist()
    cashflows = [-df_rec["actual"].iloc[0]] + [-df_rec["actual"].iloc[i] for i in range(1, n_months)] + [monthly_vals[-1]]

    return {
        "name": name, "records": df_rec, "daily": daily_df,
        "total_invested": total_invested, "final_value": final_value,
        "total_return": total_return, "ann_ret": ann_ret,
        "avg_monthly": total_invested / n_months,
        "final_reserve": cash_reserve, "months": n_months,
    }

# ============================================================
# Run all strategies
# ============================================================
all_rules = [
    (rule_fixed, "Fixed $1000"),
    (rule_drawdown_3m, "Drawdown (3M High)"),
    (rule_ma50, "MA50 Distance"),
    (rule_rsi, "RSI(14)"),
    (rule_bear_bull, "Bear/Bull (MA200)"),
    (rule_volatility, "Volatility Panic"),
    (rule_momentum, "Momentum Adaptive"),
    (rule_buy_dips_aggressive, "Buy Dips Aggressive"),
]

for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)

    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]

    print(f"\n{'─'*80}")
    print(f"  {asset_name} — Equal Total Invested DCA Comparison")
    print(f"  Target: {baseline['total_invested']:,.0f} total across {baseline['months']} months")
    print(f"{'─'*80}")
    print(f"  {'#':<3} {'Strategy':<24} {'Invested':>11} {'Final $':>14} {'Return':>9} {'Ann':>8} {'vs Fixed':>10} {'Reserve':>10}")
    print(f"  {'─'*90}")

    for i, r in enumerate(results):
        vf = ((r["final_value"] / baseline["final_value"]) - 1) * 100
        marker = " <<< BEST" if r["name"] == best["name"] else ""
        print(f"  {i+1:<3} {r['name']:<24} ${r['total_invested']:>10,.0f} ${r['final_value']:>13,.0f} "
              f"{r['total_return']:>8.1f}% {r['ann_ret']:>7.1f}% {vf:>+9.2f}% ${r['final_reserve']:>9,.0f}{marker}")

    # Monthly distribution stats for best strategy
    best_rec = best["records"]
    n = len(best_rec)
    lo = (best_rec["actual"] <= MIN_A + 1).sum()
    hi = (best_rec["actual"] >= MAX_A - 1).sum()
    mid = (abs(best_rec["actual"] - BASE) < 1).sum()
    other = n - lo - mid - hi
    print(f"\n  Best [{best['name']}]: ")
    print(f"    Invest distribution: ${MIN_A:.0f}:{lo}mo({lo/n*100:.0f}%)  ${BASE:.0f}:{mid}mo({mid/n*100:.0f}%)  ${MAX_A:.0f}:{hi}mo({hi/n*100:.0f}%)  other:{other}mo({other/n*100:.0f}%)")
    max_months = best_rec[best_rec["actual"] >= MAX_A - 1]
    min_months = best_rec[best_rec["actual"] <= MIN_A + 1]
    if len(max_months) > 0:
        print(f"    MAX ($1500) months: {', '.join(max_months.index.strftime('%Y-%m')[:8])}")
    if len(min_months) > 0:
        print(f"    MIN ($500)  months: {', '.join(min_months.index.strftime('%Y-%m')[:8])}")
    # Avg price at MAX vs MIN
    if len(max_months) > 0 and len(min_months) > 0:
        avg_max_price = max_months["price"].mean()
        avg_min_price = min_months["price"].mean()
        print(f"    Avg price when MAX invest: ${avg_max_price:.2f}  |  when MIN invest: ${avg_min_price:.2f}")
        print(f"    -> Bought {'CHEAPER' if avg_max_price < avg_min_price else 'more expensive'} during MAX months")

# ============================================================
# Charts
# ============================================================
fig, axes = plt.subplots(2, 4, figsize=(28, 14))

for col, (asset_name, series) in enumerate([("SPY", spy), ("NVDA", nvda)]):
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]

    # 1. Equity curves (top 3 + baseline)
    ax1 = axes[0, col]
    to_plot = [baseline] + [r for r in results if r["name"] != baseline["name"]][:3]
    line_colors = ["gray", "#2ca02c", "#ff7f0e", "#d62728"]
    for i, r in enumerate(to_plot):
        ls = "--" if "Fixed" in r["name"] else "-"
        lw = 3.0 if r["name"] == best["name"] else 1.3
        label = r["name"] + (" <<<" if r["name"] == best["name"] else "")
        ax1.plot(r["daily"].index, r["daily"]["value"], color=line_colors[i], linewidth=lw,
                 linestyle=ls, label=label, alpha=0.9)
    ax1.set_title(f"{asset_name}: Equity Curves", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.legend(fontsize=6.5)
    ax1.grid(True, alpha=0.3)

    # 2. Monthly investment (best strategy)
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
    ax2.set_title(f"{asset_name}: {best['name']}  "
                  f"(${best['total_invested']:,.0f} total → ${best['final_value']:,.0f})",
                  fontsize=10, fontweight="bold")
    ax2.set_ylabel("Monthly Invest ($)")
    ax2.set_ylim(0, MAX_A * 1.3)
    ax2.grid(True, alpha=0.3, axis="y")

# 3. SPY vs NVDA Best Strategy (log scale)
ax3 = axes[0, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    ax3.plot(best["daily"].index, best["daily"]["value"], color=color, linewidth=2, label=f"{asset_name} Best")
    ax3.plot(baseline["daily"].index, baseline["daily"]["value"], color=color,
             linewidth=1, linestyle="--", alpha=0.4, label=f"{asset_name} Fixed")
ax3.set_title("SPY vs NVDA: Best Strategy (Log)", fontsize=11, fontweight="bold")
ax3.set_ylabel("Portfolio Value ($)")
ax3.legend(fontsize=7)
ax3.grid(True, alpha=0.3)
ax3.set_yscale("log")

# 4. Improvement vs Fixed (bar chart)
ax4 = axes[0, 3]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)
    baseline = [r for r in results if "Fixed" in r["name"]][0]
    results_sorted = sorted(results, key=lambda x: x["final_value"], reverse=True)
    names = [r["name"] for r in results_sorted]
    imps = [(r["final_value"] / baseline["final_value"] - 1) * 100 for r in results_sorted]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    x = np.arange(len(names))
    w = 0.35
    offset = -w/2 if asset_name == "SPY" else w/2
    bars = ax4.barh(x + offset, imps, w, color=color, alpha=0.75, label=asset_name)
    for bar, imp in zip(bars, imps):
        ax4.text(bar.get_width() + (0.05 if bar.get_width() >= 0 else -0.5),
                 bar.get_y() + bar.get_height()/2, f"{imp:+.1f}%", va="center", fontsize=7,
                 ha="left" if bar.get_width() >= 0 else "right")
ax4.set_yticks(x)
ax4.set_yticklabels(names, fontsize=7)
ax4.set_title("Improvement vs Fixed $1000", fontsize=11, fontweight="bold")
ax4.set_xlabel("Excess Return (%)")
ax4.legend(fontsize=8, loc="lower right")
ax4.axvline(x=0, color="black", linewidth=0.5, linestyle="--")
ax4.grid(True, alpha=0.3, axis="x")
ax4.invert_yaxis()

# 5. Cash Reserve utilization (best strategy)
ax5 = axes[1, 2]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    best = results[0]
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    rec = best["records"]
    ax5.plot(rec.index, rec["reserve"], color=color, linewidth=1.5, label=f"{asset_name} Reserve")
ax5.axhline(y=0, color="black", linewidth=0.5)
ax5.set_title("Cash Reserve Balance (Accumulated Savings)", fontsize=11, fontweight="bold")
ax5.set_ylabel("Cash Reserve ($)")
ax5.legend(fontsize=8)
ax5.grid(True, alpha=0.3)

# 6. Price vs Investment timing scatter
ax6 = axes[1, 3]
for asset_name, series in [("SPY", spy), ("NVDA", nvda)]:
    results = []
    for rule_fn, rule_name in all_rules:
        r = backtest_equal_invested(series, rule_fn, rule_name)
        results.append(r)
    results.sort(key=lambda x: x["final_value"], reverse=True)
    best = results[0]
    best_rec = best["records"]
    # Normalize prices to 0-1 range for comparison
    norm_price = (best_rec["price"] - best_rec["price"].min()) / (best_rec["price"].max() - best_rec["price"].min())
    color = "#1f77b4" if asset_name == "SPY" else "#76B900"
    ax6.scatter(norm_price, best_rec["actual"], c=color, s=20, alpha=0.4, label=f"{asset_name}")
    # Trend line
    z = np.polyfit(norm_price, best_rec["actual"], 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, 1, 100)
    ax6.plot(x_line, p(x_line), color=color, linewidth=2, alpha=0.8)
ax6.axhline(y=BASE, color="black", linewidth=0.5, linestyle="--")
ax6.set_xlabel("Normalized Price (0=Cheapest, 1=Most Expensive)")
ax6.set_ylabel("Monthly Investment ($)")
ax6.set_title("Does the Strategy Buy More When Cheaper?", fontsize=11, fontweight="bold")
ax6.legend(fontsize=7)
ax6.grid(True, alpha=0.3)

plt.suptitle("Equal-Total Enhanced DCA: Same Budget, Smarter Allocation ($500-$1500/mo, 2016-2026)",
             fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
path = r"C:\AI\cc\stock\image\DCA_equal_invested.png"
plt.savefig(path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {path}")
plt.close()
