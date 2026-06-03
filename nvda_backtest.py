# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ============================================================
# Read data
# ============================================================
df = pd.read_csv(r"C:\AI\cc\stock\NVDA_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "NVDA")].dropna()

# ============================================================
# Calculate MAs
# ============================================================
ma5 = close.rolling(window=5).mean()
ma20 = close.rolling(window=20).mean()

# ============================================================
# Generate signals
# ============================================================
signal = pd.DataFrame({"close": close, "ma5": ma5, "ma20": ma20}).dropna()

signal["ma5_above_ma20"] = signal["ma5"] > signal["ma20"]
signal["cross_up"] = signal["ma5_above_ma20"] & (~signal["ma5_above_ma20"].shift(1).fillna(False))
signal["cross_down"] = (~signal["ma5_above_ma20"]) & (signal["ma5_above_ma20"].shift(1).fillna(False))

# ============================================================
# Backtest
# ============================================================
initial_capital = 10000.0
capital = initial_capital
shares = 0.0
in_position = False

trades = []
daily_values = []

for date, row in signal.iterrows():
    price = row["close"]

    # Buy signal
    if row["cross_up"] and not in_position:
        shares = capital / price
        capital = 0.0
        in_position = True
        trades.append({"date": date, "action": "BUY", "price": price, "shares": shares})

    # Sell signal
    elif row["cross_down"] and in_position:
        capital = shares * price
        shares = 0.0
        in_position = False
        trades.append({"date": date, "action": "SELL", "price": price, "capital": capital})

    # Daily portfolio value
    if in_position:
        daily_values.append({"date": date, "value": shares * price})
    else:
        daily_values.append({"date": date, "value": capital})

# Liquidate at end if still holding
if in_position:
    final_price = close.iloc[-1]
    capital = shares * final_price
    trades.append({"date": close.index[-1], "action": "SELL (final)", "price": final_price, "capital": capital})

trades_df = pd.DataFrame(trades)
values_df = pd.DataFrame(daily_values).set_index("date")

# ============================================================
# Performance metrics
# ============================================================
final_value = capital
total_return = (final_value - initial_capital) / initial_capital * 100

start_date = signal.index[0]
end_date = signal.index[-1]
years = (end_date - start_date).days / 365.25
annualized_return = ((final_value / initial_capital) ** (1 / years) - 1) * 100

# Max drawdown
values_df["peak"] = values_df["value"].cummax()
values_df["drawdown"] = (values_df["value"] - values_df["peak"]) / values_df["peak"] * 100
max_drawdown = values_df["drawdown"].min()

# Buy & hold comparison
buy_hold_shares = initial_capital / close.loc[signal.index[0]]
buy_hold_final = buy_hold_shares * close.iloc[-1]
buy_hold_return = (buy_hold_final - initial_capital) / initial_capital * 100

# ============================================================
# Output
# ============================================================
print("=" * 65)
print("  NVDA MA5/MA20 Cross Strategy Backtest")
print("=" * 65)
print(f"  Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}  ({years:.1f} years)")
print(f"  Initial Capital: ${initial_capital:,.2f}")
print(f"  Final Value:     ${final_value:,.2f}")
print(f"  Total Return:    {total_return:+.2f}%")
print(f"  Annualized Ret:  {annualized_return:+.2f}%")
print(f"  Max Drawdown:    {max_drawdown:.2f}%")
print(f"  Trade Pairs:     {len(trades_df) // 2}")
print("-" * 65)
print(f"  Buy & Hold:      {buy_hold_return:+.2f}%  (comparison)")
print("=" * 65)

# Trade details
print("\nTrade Details:")
print("-" * 85)
for _, t in trades_df.iterrows():
    if "BUY" in t["action"]:
        print(f"  {t['date'].strftime('%Y-%m-%d')}  [BUY ]  @ ${t['price']:>10.2f}  |  {t['shares']:.2f} shares")
    else:
        print(f"  {t['date'].strftime('%Y-%m-%d')}  [SELL]  @ ${t['price']:>10.2f}  |  capital ${t['capital']:,.2f}")
print("-" * 85)

# Save
values_df.to_csv(r"C:\AI\cc\stock\NVDA_equity.csv")
trades_df.to_csv(r"C:\AI\cc\stock\NVDA_trades.csv")
print("\nEquity curve saved to: NVDA_equity.csv")
print("Trade log saved to: NVDA_trades.csv")
