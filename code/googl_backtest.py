# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# 1. Load GOOGL data
# ============================================================
df = pd.read_csv(r"C:\AI\cc\stock\data\GOOGL_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "GOOGL")].dropna()

initial_capital = 10000.0

print("=" * 70)
print("  GOOGL (Alphabet) Quantitative Backtests")
print(f"  Data: {close.index[0].strftime('%Y-%m-%d')} ~ {close.index[-1].strftime('%Y-%m-%d')}")
print(f"  Trading days: {len(close)}")
print("=" * 70)

# ============================================================
# STRATEGY 1: MA5 / MA20 Cross
# ============================================================
print("\n" + "=" * 70)
print("  STRATEGY 1: MA5 / MA20 Golden Cross / Death Cross")
print("=" * 70)

ma5 = close.rolling(5).mean()
ma20 = close.rolling(20).mean()

signal = pd.DataFrame({"close": close, "ma5": ma5, "ma20": ma20}).dropna()
signal["ma5_above"] = signal["ma5"] > signal["ma20"]
signal["cross_up"] = signal["ma5_above"] & (~signal["ma5_above"].shift(1).fillna(False))
signal["cross_down"] = (~signal["ma5_above"]) & (signal["ma5_above"].shift(1).fillna(False))

capital = initial_capital
shares = 0.0
in_position = False
trades_ma = []
daily_ma = []

for date, row in signal.iterrows():
    price = row["close"]
    if row["cross_up"] and not in_position:
        shares = capital / price
        capital = 0.0
        in_position = True
        trades_ma.append({"date": date, "action": "BUY", "price": price, "shares": shares})
    elif row["cross_down"] and in_position:
        capital = shares * price
        shares = 0.0
        in_position = False
        trades_ma.append({"date": date, "action": "SELL", "price": price, "capital": capital})
    daily_ma.append({"date": date, "value": shares * price if in_position else capital})

if in_position:
    final_p = close.iloc[-1]
    capital = shares * final_p
    trades_ma.append({"date": close.index[-1], "action": "SELL*", "price": final_p, "capital": capital})

trades_ma_df = pd.DataFrame(trades_ma)
values_ma = pd.DataFrame(daily_ma).set_index("date")
final_ma = capital
total_ret_ma = (final_ma / initial_capital - 1) * 100
years = (close.index[-1] - signal.index[0]).days / 365.25
ann_ret_ma = ((final_ma / initial_capital) ** (1 / years) - 1) * 100
peak_ma = values_ma["value"].cummax()
max_dd_ma = ((values_ma["value"] - peak_ma) / peak_ma * 100).min()

# Buy & hold
bh_shares = initial_capital / close.loc[signal.index[0]]
bh_final = bh_shares * close.iloc[-1]
bh_ret = (bh_final / initial_capital - 1) * 100

print(f"  回测区间: {signal.index[0].strftime('%Y-%m-%d')} ~ {close.index[-1].strftime('%Y-%m-%d')} ({years:.1f}年)")
print(f"  初始资金:     ${initial_capital:>12,.2f}")
print(f"  最终资金:     ${final_ma:>12,.2f}")
print(f"  总收益率:     {total_ret_ma:>+10.2f}%")
print(f"  年化收益率:   {ann_ret_ma:>+10.2f}%")
print(f"  最大回撤:     {max_dd_ma:>10.2f}%")
print(f"  交易次数:     {len(trades_ma_df) // 2} 次")
print(f"  买入持有收益: {bh_ret:>+10.2f}%")

print("\n  交易明细:")
for _, t in trades_ma_df.iterrows():
    if "BUY" in t["action"]:
        print(f"    {t['date'].strftime('%Y-%m-%d')}  [BUY ] @ ${t['price']:.2f}  |  {t['shares']:.2f} shares")
    else:
        print(f"    {t['date'].strftime('%Y-%m-%d')}  [SELL] @ ${t['price']:.2f}  |  capital ${t['capital']:,.2f}")

# ============================================================
# STRATEGY 2: Momentum (3M, 6M, 12M)
# ============================================================
print("\n\n" + "=" * 70)
print("  STRATEGY 2: Jegadeesh-Titman Momentum (skip 1 month)")
print("=" * 70)

def momentum_backtest(prices, formation_months=12, skip_months=1):
    monthly_prices = prices.resample("ME").last()
    monthly_ret = monthly_prices.pct_change()
    sig = pd.DataFrame({"price": monthly_prices, "return": monthly_ret})
    sig["momentum"] = sig["price"].pct_change(periods=formation_months).shift(skip_months)
    sig["position"] = (sig["momentum"] > 0).astype(int)
    sig["strategy_return"] = sig["position"].shift(1) * sig["return"]
    sig = sig.dropna()
    sig["strategy_value"] = initial_capital * (1 + sig["strategy_return"]).cumprod()
    sig["buyhold_value"] = initial_capital * (1 + sig["return"]).cumprod()
    return sig

periods = [
    (3, 1, "3M Momentum"),
    (6, 1, "6M Momentum"),
    (12, 1, "12M Momentum"),
]

mom_results = {}
for formation, skip, label in periods:
    sig = momentum_backtest(close, formation_months=formation, skip_months=skip)
    final_val = sig["strategy_value"].iloc[-1]
    bh_val = sig["buyhold_value"].iloc[-1]
    total_ret = (final_val / initial_capital - 1) * 100
    bh_ret_m = (bh_val / initial_capital - 1) * 100
    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    ann_ret = ((final_val / initial_capital) ** (1 / n_years) - 1) * 100
    excess = sig["strategy_return"]
    sharpe = np.sqrt(12) * excess.mean() / excess.std() if excess.std() > 0 else 0
    peak = sig["strategy_value"].cummax()
    max_dd = ((sig["strategy_value"] - peak) / peak * 100).min()
    win_rate = (sig["strategy_return"] > 0).sum() / len(sig) * 100
    time_in = sig["position"].mean() * 100

    mom_results[label] = sig

    print(f"\n  {label} (skip 1M):")
    print(f"    回测区间: {sig.index[0].strftime('%Y-%m')} ~ {sig.index[-1].strftime('%Y-%m')} ({n_years:.1f}年)")
    print(f"    最终资金:     ${final_val:>12,.2f}")
    print(f"    总收益率:     {total_ret:>+10.2f}%")
    print(f"    年化收益率:   {ann_ret:>+10.2f}%")
    print(f"    夏普比率:     {sharpe:>10.2f}")
    print(f"    最大回撤:     {max_dd:>10.2f}%")
    print(f"    胜率:         {win_rate:>10.1f}%")
    print(f"    持仓时间:     {time_in:>10.1f}%")
    print(f"    买入持有:     {bh_ret_m:>+10.2f}%")

# 12M signals detail
best_mom = mom_results["12M Momentum"]
best_mom["position_change"] = best_mom["position"].diff()
entries = best_mom[best_mom["position_change"] > 0]
exits = best_mom[best_mom["position_change"] < 0]

print(f"\n  12M Momentum signals ({len(entries)} long, {len(exits)} cash):")
all_signals = pd.concat([
    pd.DataFrame({"date": entries.index, "action": "LONG", "price": entries["price"]}),
    pd.DataFrame({"date": exits.index, "action": "CASH", "price": exits["price"]}),
]).sort_index()
for _, t in all_signals.iterrows():
    print(f"    {t['date'].strftime('%Y-%m-%d')}  [{t['action']:4s}] @ ${t['price']:.2f}")

# ============================================================
# 3. Charts
# ============================================================
fig, axes = plt.subplots(2, 3, figsize=(22, 12))

# --- Row 1: MA Cross ---
ax1 = axes[0, 0]
ax1.plot(values_ma.index, values_ma["value"], label="MA5/MA20 Strategy", color="blue", linewidth=1.2)
ax1.plot(close.index, initial_capital * close / close.loc[signal.index[0]], label="Buy & Hold", color="black", linewidth=1, alpha=0.6)
ax1.set_title("GOOGL - MA5/MA20 Cross Equity Curve", fontsize=11, fontweight="bold")
ax1.set_ylabel("Value ($)")
ax1.legend(fontsize=7)
ax1.grid(True, alpha=0.3)
ax1.set_yscale("log")

ax2 = axes[0, 1]
ax2.plot(close.index[-500:], close.iloc[-500:], color="black", linewidth=0.8, alpha=0.7, label="Close")
ax2.plot(ma5.index[-500:], ma5.iloc[-500:], color="blue", linewidth=1, label="MA5")
ax2.plot(ma20.index[-500:], ma20.iloc[-500:], color="red", linewidth=1, label="MA20")
ax2.set_title("GOOGL - MA5/MA20 (Last 500 days)", fontsize=11, fontweight="bold")
ax2.legend(fontsize=7)
ax2.grid(True, alpha=0.3)

ax3 = axes[0, 2]
dd_ma = (values_ma["value"] - values_ma["value"].cummax()) / values_ma["value"].cummax() * 100
ax3.fill_between(values_ma.index, 0, dd_ma, color="red", alpha=0.3)
ax3.set_title("MA5/MA20 Drawdown", fontsize=11, fontweight="bold")
ax3.set_ylabel("Drawdown (%)")
ax3.grid(True, alpha=0.3)

# --- Row 2: Momentum ---
ax4 = axes[1, 0]
for label, sig in mom_results.items():
    ax4.plot(sig.index, sig["strategy_value"], label=label, linewidth=1.5)
ax4.plot(best_mom.index, best_mom["buyhold_value"], label="Buy & Hold", color="black", linewidth=1.2, alpha=0.6)
ax4.set_title("GOOGL - Momentum Strategy Equity Curves", fontsize=11, fontweight="bold")
ax4.set_ylabel("Value ($)")
ax4.legend(fontsize=7)
ax4.grid(True, alpha=0.3)
ax4.set_yscale("log")

ax5 = axes[1, 1]
for label, sig in mom_results.items():
    peak = sig["strategy_value"].cummax()
    dd = (sig["strategy_value"] - peak) / peak * 100
    ax5.fill_between(sig.index, 0, dd, alpha=0.25, label=label)
ax5.set_title("Momentum Drawdown Comparison", fontsize=11, fontweight="bold")
ax5.set_ylabel("Drawdown (%)")
ax5.legend(fontsize=7)
ax5.grid(True, alpha=0.3)

ax6 = axes[1, 2]
for label, sig in mom_results.items():
    roll = sig["strategy_return"].rolling(36).mean() * 12 * 100
    ax6.plot(sig.index, roll, label=label, linewidth=1.5)
bh_roll = best_mom["return"].rolling(36).mean() * 12 * 100
ax6.plot(best_mom.index, bh_roll, label="Buy & Hold", color="black", linewidth=1, alpha=0.5)
ax6.axhline(y=0, color="gray", linewidth=0.5)
ax6.set_title("Rolling 3-Year Annualized Return", fontsize=11, fontweight="bold")
ax6.set_ylabel("Annualized Return (%)")
ax6.legend(fontsize=7)
ax6.grid(True, alpha=0.3)

plt.suptitle("GOOGL (Alphabet) Quantitative Strategy Backtests", fontsize=15, fontweight="bold", y=1.01)
plt.tight_layout()
chart_path = r"C:\AI\cc\stock\image\GOOGL_backtest_chart.png"
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
print(f"\n\nChart saved to: {chart_path}")
plt.close()

# ============================================================
# 4. Summary comparison
# ============================================================
print("\n\n" + "=" * 70)
print("  GOOGL vs NVDA: Strategy Summary")
print("=" * 70)

print(f"""
  {'Strategy':<25} {'GOOGL':>12} {'NVDA':>12}
  {'─'*50}
  MA5/MA20  年化收益率  {ann_ret_ma:>+10.2f}%  {'+26.75%':>12}
  MA5/MA20  最大回撤    {max_dd_ma:>+10.2f}%  {'-57.47%':>12}
  {'─'*50}
  12M 动量  夏普比率    {''.join([str(np.sqrt(12)*mom_results['12M Momentum']['strategy_return'].mean()/mom_results['12M Momentum']['strategy_return'].std())[:6]]):>12}  {'1.04':>12}
""")

# Save detailed CSVs
values_ma.to_csv(r"C:\AI\cc\stock\data\GOOGL_ma_cross.csv")
trades_ma_df.to_csv(r"C:\AI\cc\stock\data\GOOGL_ma_trades.csv")
best_mom.to_csv(r"C:\AI\cc\stock\data\GOOGL_momentum_12M.csv")
print("Detailed results saved: GOOGL_ma_cross.csv, GOOGL_ma_trades.csv, GOOGL_momentum_12M.csv")
