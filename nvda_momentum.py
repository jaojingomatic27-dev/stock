# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# 1. Load data
# ============================================================
df = pd.read_csv(r"C:\AI\cc\stock\NVDA_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "NVDA")].dropna()

# Resample to monthly for momentum strategy
monthly = close.resample("ME").last()
monthly_returns = monthly.pct_change()

print("=" * 70)
print("  NVDA Momentum Strategy Backtest")
print(f"  Data: {monthly.index[0].strftime('%Y-%m')} ~ {monthly.index[-1].strftime('%Y-%m')}")
print(f"  Monthly bars: {len(monthly)}")
print("=" * 70)

# ============================================================
# 2. Momentum strategy function
# ============================================================
# Classic Jegadeesh-Titman momentum:
#   Formation period: look back N months
#   Skip period: skip 1 month (to avoid short-term reversal)
#   Signal: if past-N-month return (excluding last month) > 0 -> long, else cash

def momentum_backtest(prices, formation_months=12, skip_months=1):
    """
    Momentum strategy on a single asset.
    - Each month, calculate return from (t - formation - skip) to (t - skip)
    - If return > 0, go long for the next month; otherwise cash.
    """
    monthly_prices = prices.resample("ME").last()
    monthly_ret = monthly_prices.pct_change()

    signals = pd.DataFrame({
        "price": monthly_prices,
        "return": monthly_ret,
    })

    # Momentum signal: cumulative return from t-formation-skip to t-skip
    signals["momentum"] = signals["price"].pct_change(periods=formation_months).shift(skip_months)

    # Generate position: 1 = long, 0 = cash
    # Also try: long only when momentum > risk-free threshold
    signals["position"] = (signals["momentum"] > 0).astype(int)

    # Strategy returns: position * next month return
    signals["strategy_return"] = signals["position"].shift(1) * signals["return"]

    # Drop NaN rows
    signals = signals.dropna()

    # Portfolio value
    initial_capital = 10000.0
    signals["strategy_value"] = initial_capital * (1 + signals["strategy_return"]).cumprod()
    signals["buyhold_value"] = initial_capital * (1 + signals["return"]).cumprod()

    return signals

# ============================================================
# 3. Test multiple formation periods
# ============================================================
periods = [
    (3, 1, "3M Momentum (skip 1M)"),
    (6, 1, "6M Momentum (skip 1M)"),
    (12, 1, "12M Momentum (skip 1M)"),
]

results = {}
for formation, skip, label in periods:
    sig = momentum_backtest(close, formation_months=formation, skip_months=skip)

    final_val = sig["strategy_value"].iloc[-1]
    bh_val = sig["buyhold_value"].iloc[-1]
    total_ret = (final_val / 10000 - 1) * 100
    bh_ret = (bh_val / 10000 - 1) * 100

    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    ann_ret = ((final_val / 10000) ** (1 / n_years) - 1) * 100

    # Sharpe ratio (monthly)
    excess = sig["strategy_return"] - 0.0  # assume risk-free = 0 for simplicity
    sharpe = np.sqrt(12) * excess.mean() / excess.std() if excess.std() > 0 else 0

    # Max drawdown
    peak = sig["strategy_value"].cummax()
    dd = (sig["strategy_value"] - peak) / peak * 100
    max_dd = dd.min()

    # Win rate
    win_rate = (sig["strategy_return"] > 0).sum() / (sig["strategy_return"] != 0).sum() * 100

    # Time in market
    time_in_market = sig["position"].mean() * 100

    results[label] = sig

    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    print(f"  最终资金:       ${final_val:>12,.2f}")
    print(f"  总收益率:       {total_ret:>+10.2f}%")
    print(f"  年化收益率:     {ann_ret:>+10.2f}%")
    print(f"  夏普比率:       {sharpe:>10.2f}")
    print(f"  最大回撤:       {max_dd:>10.2f}%")
    print(f"  胜率:           {win_rate:>10.1f}%")
    print(f"  持仓时间占比:   {time_in_market:>10.1f}%")
    print(f"  买入持有收益:   {bh_ret:>+10.2f}%")

# ============================================================
# 4. Comparison chart
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(18, 12))

# Plot 1: Equity curves
ax1 = axes[0, 0]
for label, sig in results.items():
    ax1.plot(sig.index, sig["strategy_value"], label=label, linewidth=1.5)
ax1.plot(sig.index, sig["buyhold_value"], label="Buy & Hold", color="black", linewidth=1.5, alpha=0.7)
ax1.set_title("NVDA Momentum Strategy - Equity Curves", fontsize=13, fontweight="bold")
ax1.set_ylabel("Portfolio Value ($)")
ax1.legend(fontsize=8)
ax1.grid(True, alpha=0.3)
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

# Make log scale for better comparison
ax1.set_yscale("log")

# Plot 2: Drawdown
ax2 = axes[0, 1]
for label, sig in results.items():
    peak = sig["strategy_value"].cummax()
    dd = (sig["strategy_value"] - peak) / peak * 100
    ax2.fill_between(sig.index, 0, dd, alpha=0.3, label=label)
ax2.set_title("Drawdown Comparison", fontsize=13, fontweight="bold")
ax2.set_ylabel("Drawdown (%)")
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax2.xaxis.set_major_locator(mdates.YearLocator(2))

# Plot 3: 12M Momentum signal vs price
ax3 = axes[1, 0]
best_sig = results["12M Momentum (skip 1M)"]
ax3_twin = ax3.twinx()
ax3.plot(best_sig.index, best_sig["price"], color="black", linewidth=1, alpha=0.7)
ax3.set_ylabel("NVDA Price ($)", color="black")
colors = ["green" if v > 0 else "red" for v in best_sig["momentum"]]
ax3_twin.bar(best_sig.index, best_sig["momentum"] * 100, width=20, color=colors, alpha=0.4)
ax3_twin.axhline(y=0, color="gray", linewidth=0.5)
ax3_twin.set_ylabel("12M Momentum (%)", color="gray")
ax3.set_title("12M Momentum Signal vs Price", fontsize=13, fontweight="bold")
ax3.grid(True, alpha=0.3)
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.xaxis.set_major_locator(mdates.YearLocator(2))

# Plot 4: Rolling 3-year returns
ax4 = axes[1, 1]
for label, sig in results.items():
    roll_3y = sig["strategy_return"].rolling(36).mean() * 12 * 100
    ax4.plot(sig.index, roll_3y, label=label, linewidth=1.5)
bh_roll = best_sig["return"].rolling(36).mean() * 12 * 100
ax4.plot(best_sig.index, bh_roll, label="Buy & Hold", color="black", linewidth=1.5, alpha=0.5)
ax4.axhline(y=0, color="gray", linewidth=0.5)
ax4.set_title("Rolling 3-Year Annualized Return", fontsize=13, fontweight="bold")
ax4.set_ylabel("Annualized Return (%)")
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)
ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax4.xaxis.set_major_locator(mdates.YearLocator(2))

plt.suptitle("NVDA Momentum Strategy Backtest (Jegadeesh-Titman Method)", fontsize=16, fontweight="bold", y=1.01)
plt.tight_layout()
output_path = r"C:\AI\cc\stock\NVDA_momentum_chart.png"
plt.savefig(output_path, dpi=150, bbox_inches="tight")
print(f"\nChart saved to: {output_path}")
plt.close()

# ============================================================
# 5. Trade log for best strategy (12M)
# ============================================================
print(f"\n{'=' * 70}")
print("  Best Strategy: 12M Momentum - Monthly Signals")
print(f"{'=' * 70}")

best = results["12M Momentum (skip 1M)"]
best["position_change"] = best["position"].diff()

entries = best[best["position_change"] > 0]
exits = best[best["position_change"] < 0]

all_trades = pd.concat([
    pd.DataFrame({"date": entries.index, "action": "LONG", "price": entries["price"], "momentum_pct": entries["momentum"] * 100}),
    pd.DataFrame({"date": exits.index, "action": "CASH", "price": exits["price"], "momentum_pct": exits["momentum"] * 100}),
]).sort_index()

print(f"  Total signals: {len(all_trades)}")
print(f"  Long entries:  {len(entries)}")
print(f"  Cash exits:    {len(exits)}")
print(f"\n  Recent signals (last 24 months):")
print(f"  {'Date':<12} {'Action':<6} {'Price':>10} {'Momentum%':>10}")
print(f"  {'-'*42}")
for _, t in all_trades.tail(24).iterrows():
    print(f"  {t['date'].strftime('%Y-%m-%d'):<12} {t['action']:<6} ${t['price']:>9.2f} {t['momentum_pct']:>9.1f}%")

# Save
best.to_csv(r"C:\AI\cc\stock\NVDA_momentum_12M.csv")
print(f"\nDetailed data saved to: NVDA_momentum_12M.csv")
