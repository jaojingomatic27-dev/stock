# -*- coding: utf-8 -*-
"""
Warrant Backtest: Test MA Cross, Momentum, DCA strategies on 5 Turbo Call Warrants.
Models Open-End Turbo Call warrant prices from underlying stock data.
Starts from LAST time underlying crossed above strike (current continuous ITM period).
Warrant % return = Leverage * Stock % return (ratio cancels out).
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# ============================================================
# Warrant Definitions
# ============================================================
WARRANTS = [
    {"name": "W1: UBS OE Turbo Call NVDA 172.21",   "ticker": "NVDA", "strike": 172.21},
    {"name": "W2: HSBC OE-Turbo MU Call 538.82",    "ticker": "MU",   "strike": 538.82},
    {"name": "W3: Vontobel OE Turbo-OS MU",         "ticker": "MU",   "strike": 380.07},
    {"name": "W4: MS OE Turbo Long NVDA 176.67",    "ticker": "NVDA", "strike": 176.67},
    {"name": "W5: HSBC OE-Turbo ORCL Call 187.3",   "ticker": "ORCL", "strike": 187.30},
]

FINANCING_RATE = 0.045  # 4.5% annual financing cost
BASE_INVEST = 10000

print("=" * 90)
print("WARRANT BACKTEST: 1-Year Strategy Test on 5 Turbo Call Warrants")
print("=" * 90)
print()

# ============================================================
# Load Data
# ============================================================
print("Loading underlying stock data...")
data = {}
for ticker in ["NVDA", "MU", "ORCL"]:
    path = rf"C:\AI\cc\stock\{ticker}_daily.csv"
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()
    data[ticker] = close
    print(f"  {ticker}: {len(close)} days, ${close.iloc[0]:.2f} -> ${close.iloc[-1]:.2f}")


# ============================================================
# Warrant Price Model
# ============================================================
def model_warrant_prices(underlying, initial_strike, financing_rate=FINANCING_RATE):
    """
    Model daily warrant intrinsic value with financing cost adjustment.
    Uses the LAST continuous ITM period (most recent crossing above strike).
    If underlying drops to/below strike -> knock-out, warrant = 0 permanently.
    Returns: (warrant_prices, strikes_adj, knocked_out, ko_date, start_idx)
    """
    prices = underlying.values
    dates = underlying.index
    n = len(prices)

    # Find the LAST crossing above strike (start of current continuous ITM period)
    start_idx = None
    for i in range(n - 1, -1, -1):
        if prices[i] <= initial_strike:
            # Found the last dip below strike
            if i < n - 1:
                start_idx = i + 1
            break
    if start_idx is None:
        start_idx = 0  # Always above strike

    # If start_idx is 0 and price is below strike, never ITM
    if prices[start_idx] <= initial_strike:
        # Check if there's ANY ITM period later
        found = False
        for i in range(start_idx, n):
            if prices[i] > initial_strike:
                start_idx = i
                found = True
                break
        if not found:
            return None, None, True, dates[0], 0

    warrant_vals = np.full(n, np.nan)
    strikes_arr = np.full(n, np.nan)
    knocked_out = False
    ko_date = None

    for i in range(start_idx, n):
        if i == start_idx:
            strikes_arr[i] = initial_strike
        else:
            days_elapsed = (dates[i] - dates[i-1]).days
            strikes_arr[i] = strikes_arr[i-1] * (1 + financing_rate / 365 * max(days_elapsed, 0))

        intrinsic = prices[i] - strikes_arr[i]
        if intrinsic <= 0 and i > start_idx:
            # Knock-out
            warrant_vals[i] = 0.0
            knocked_out = True
            ko_date = dates[i]
            for j in range(i + 1, n):
                warrant_vals[j] = 0.0
            break
        else:
            warrant_vals[i] = max(intrinsic, 0.001)  # Small floor to avoid /0

    return (pd.Series(warrant_vals, index=dates),
            pd.Series(strikes_arr, index=dates),
            knocked_out, ko_date, start_idx)


# ============================================================
# Utility: compute metrics
# ============================================================
def compute_metrics(equity_series, daily_rets, years):
    valid = equity_series.dropna()
    final = float(valid.iloc[-1])
    total_ret = (final / BASE_INVEST - 1) * 100
    ann_ret = ((final / BASE_INVEST) ** (1 / max(years, 0.01)) - 1) * 100
    max_dd = ((valid - valid.cummax()) / valid.cummax() * 100).min()
    rets_clean = daily_rets.dropna()
    if len(rets_clean) > 1 and rets_clean.std() > 0:
        sharpe = float(np.sqrt(252) * rets_clean.mean() / rets_clean.std())
    else:
        sharpe = 0.0
    return {"total_ret": total_ret, "ann_ret": ann_ret, "max_dd": max_dd,
            "sharpe": sharpe, "final_value": final}


def get_active_data(underlying, wp, start_idx):
    """Get clean overlapping data from start_idx onwards."""
    wp_clean = wp.dropna()
    common_idx = underlying.index.intersection(wp_clean.index)
    return underlying.loc[common_idx], wp_clean.loc[common_idx]


# ============================================================
# Strategy 1: MA5/MA20 Cross
# ============================================================
def backtest_ma_cross(underlying, wp, start_idx):
    und, wpr = get_active_data(underlying, wp, start_idx)
    if len(und) < 20:
        return None

    ma5 = und.rolling(5).mean()
    ma20 = und.rolling(20).mean()
    signal = (ma5 > ma20).astype(int)
    signal = signal.shift(1).fillna(0)

    daily_ret = wpr.pct_change().fillna(0)
    strategy_ret = daily_ret * signal

    equity = (1 + strategy_ret).cumprod() * BASE_INVEST
    years = len(und) / 252

    metrics = compute_metrics(equity, strategy_ret, years)

    # Count trades
    trades = []
    in_trade = False
    entry_val = 0.0
    for i in range(1, len(signal)):
        if signal.iloc[i] == 1 and signal.iloc[i-1] == 0:
            in_trade = True
            entry_val = float(equity.iloc[i])
        elif signal.iloc[i] == 0 and signal.iloc[i-1] == 1:
            if in_trade and entry_val > 0:
                trades.append(float(equity.iloc[i]) / entry_val - 1)
            in_trade = False
    if in_trade and entry_val > 0:
        trades.append(float(equity.iloc[-1]) / entry_val - 1)
    win_rate = sum(1 for t in trades if t > 0) / len(trades) * 100 if trades else 0

    metrics["strategy"] = "MA5/20 Cross"
    metrics["win_rate"] = win_rate
    metrics["n_trades"] = len(trades)
    metrics["equity"] = equity
    return metrics


# ============================================================
# Strategy 2: Momentum
# ============================================================
def backtest_momentum(underlying, wp, start_idx, formation_months):
    und, wpr = get_active_data(underlying, wp, start_idx)
    min_need = formation_months * 21 + 21
    if len(und) < min_need:
        return None

    monthly = und.resample("ME").last()
    mom_ret = monthly.pct_change(periods=formation_months).shift(1)
    mom_daily = mom_ret.reindex(und.index).ffill()

    signal = (mom_daily > 0).astype(int).fillna(0)

    daily_ret = wpr.pct_change().fillna(0)
    strategy_ret = daily_ret * signal

    equity = (1 + strategy_ret).cumprod() * BASE_INVEST
    years = len(und) / 252

    metrics = compute_metrics(equity, strategy_ret, years)
    metrics["strategy"] = f"Momentum {formation_months}M"
    metrics["win_rate"] = 0
    metrics["n_trades"] = 0
    metrics["equity"] = equity
    return metrics


# ============================================================
# Strategy 3: Buy & Hold
# ============================================================
def backtest_buy_hold(underlying, wp, start_idx):
    und, wpr = get_active_data(underlying, wp, start_idx)
    daily_ret = wpr.pct_change().fillna(0)
    equity = (1 + daily_ret).cumprod() * BASE_INVEST
    years = len(wpr) / 252

    metrics = compute_metrics(equity, daily_ret, years)
    metrics["strategy"] = "Buy & Hold"
    metrics["win_rate"] = 0
    metrics["n_trades"] = 0
    metrics["equity"] = equity
    return metrics


# ============================================================
# Strategy 4: DCA Fixed
# ============================================================
def backtest_dca_fixed(underlying, wp, start_idx, monthly_amount=1000):
    und, wpr = get_active_data(underlying, wp, start_idx)
    shares = 0.0
    invested = 0.0
    prev_ym = None
    values = []
    dates_list = []

    for dt, price in wpr.items():
        if price <= 0 or pd.isna(price):
            continue
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            shares += monthly_amount / price
            invested += monthly_amount
            prev_ym = ym
        dates_list.append(dt)
        values.append(shares * price)

    if len(values) == 0:
        return None

    values_series = pd.Series(values, index=dates_list)
    years = len(wpr) / 252

    total_ret = (values_series.iloc[-1] / invested - 1) * 100 if invested > 0 else 0
    ann_ret = ((values_series.iloc[-1] / invested) ** (1 / max(years, 0.01)) - 1) * 100 if invested > 0 else 0
    monthly_rets = values_series.resample("ME").last().pct_change().dropna()
    if len(monthly_rets) > 1 and monthly_rets.std() > 0:
        sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std())
    else:
        sharpe = 0.0
    max_dd = ((values_series - values_series.cummax()) / values_series.cummax() * 100).min()

    return {
        "strategy": "DCA Fixed $1000/mo",
        "total_ret": total_ret, "ann_ret": ann_ret, "max_dd": max_dd,
        "sharpe": sharpe, "win_rate": 0, "n_trades": 0,
        "final_value": float(values_series.iloc[-1]), "equity": values_series,
        "total_invested": invested
    }


# ============================================================
# Strategy 5: DCA Enhanced - Drawdown 3M
# ============================================================
def backtest_dca_drawdown(underlying, wp, start_idx, base=1000, min_a=500, max_a=1500):
    und, wpr = get_active_data(underlying, wp, start_idx)
    if len(und) < 63:
        return None

    high_3m = und.rolling(63).max()

    # Find first-of-month dates
    first_dates = []
    first_prices = []
    prev_ym = None
    for dt, price in und.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    shares = 0.0
    invested = 0.0
    cash_reserve = 0.0

    for j, dt in enumerate(first_dates):
        if dt not in wpr.index:
            continue
        w_price = float(wpr.loc[dt])
        if w_price <= 0 or pd.isna(w_price):
            continue

        price = first_prices[j]
        # Find the 3M high at this date
        if dt in high_3m.index:
            h3 = float(high_3m.loc[dt])
        else:
            h3 = float(high_3m.reindex([dt], method='ffill').iloc[0])

        if pd.isna(h3):
            desired = base
        elif price < h3 * 0.90:
            desired = max_a
        elif price >= h3:
            desired = min_a
        else:
            desired = base

        if desired > base:
            extra = min(desired - base, cash_reserve)
            actual = base + extra
        elif desired < base:
            save = min(base - desired, base - min_a)
            actual = base - save
        else:
            actual = base

        if actual < base:
            cash_reserve += (base - actual)
        elif actual > base:
            cash_reserve -= (actual - base)

        shares += actual / w_price
        invested += actual

    if invested == 0:
        return None

    # Daily equity curve
    equity = pd.Series(index=wpr.index, dtype=float)
    for dt in wpr.index:
        wp_val = float(wpr.loc[dt])
        equity[dt] = shares * wp_val if wp_val > 0 else 0.0

    years = len(wpr) / 252
    total_ret = (equity.iloc[-1] / invested - 1) * 100
    ann_ret = ((equity.iloc[-1] / invested) ** (1 / max(years, 0.01)) - 1) * 100
    monthly_rets = equity.resample("ME").last().pct_change().dropna()
    if len(monthly_rets) > 1 and monthly_rets.std() > 0:
        sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std())
    else:
        sharpe = 0.0
    max_dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()

    return {
        "strategy": "DCA Drawdown 3M",
        "total_ret": total_ret, "ann_ret": ann_ret, "max_dd": max_dd,
        "sharpe": sharpe, "win_rate": 0, "n_trades": 0,
        "final_value": float(equity.iloc[-1]), "equity": equity,
        "total_invested": invested
    }


# ============================================================
# Also: Underlying Stock Buy & Hold (for reference)
# ============================================================
def backtest_stock_bh(underlying, wp, start_idx):
    """Buy & Hold the underlying stock (not the warrant) for comparison."""
    und, wpr = get_active_data(underlying, wp, start_idx)
    daily_ret = und.pct_change().fillna(0)
    equity = (1 + daily_ret).cumprod() * BASE_INVEST
    years = len(und) / 252
    metrics = compute_metrics(equity, daily_ret, years)
    metrics["strategy"] = "Stock B&H (ref)"
    metrics["win_rate"] = 0
    metrics["n_trades"] = 0
    metrics["equity"] = equity
    return metrics


# ============================================================
# MAIN
# ============================================================
all_results = []

for w in WARRANTS:
    name = w["name"]
    ticker = w["ticker"]
    strike = w["strike"]
    underlying = data[ticker]

    print(f"\n{'=' * 90}")
    print(f"  {name}")
    print(f"  Underlying: {ticker} | Strike: ${strike:.2f} | Financing: {FINANCING_RATE*100:.1f}%/yr")
    print(f"{'=' * 90}")

    wp, strikes_adj, knocked_out, ko_date, start_idx = model_warrant_prices(underlying, strike)

    if wp is None:
        print(f"  *** NEVER ITM: {ticker} never crossed above ${strike:.2f} ***")
        continue

    active_wp = wp.dropna()
    first_dt = active_wp.index[0]
    last_dt = active_wp.index[-1]
    n_days = len(active_wp)
    active_years = n_days / 252

    if knocked_out:
        print(f"  ITM: {first_dt.strftime('%Y-%m-%d')} to {ko_date.strftime('%Y-%m-%d')} | KNOCK-OUT! | {n_days} days")
    else:
        print(f"  ITM: {first_dt.strftime('%Y-%m-%d')} to {last_dt.strftime('%Y-%m-%d')} | {n_days} days ({active_years:.2f} yrs)")

    current_S = underlying.loc[last_dt]
    current_K = float(strikes_adj.dropna().iloc[-1])
    leverage = current_S / (current_S - current_K) if current_S > current_K else float('inf')
    print(f"  Last Price: ${current_S:.2f} | Adj Strike: ${current_K:.2f} | Leverage: {leverage:.1f}x")

    if n_days < 20:
        print(f"  *** Too few active days ({n_days}) for meaningful backtest ***")
        continue

    # Run strategies
    results = []

    # Stock B&H reference
    r = backtest_stock_bh(underlying, wp, start_idx)
    if r:
        results.append(r)

    # Warrant B&H
    r = backtest_buy_hold(underlying, wp, start_idx)
    if r:
        results.append(r)

    # MA Cross
    r = backtest_ma_cross(underlying, wp, start_idx)
    if r:
        results.append(r)

    # Momentum
    for mom in [3, 6, 12]:
        r = backtest_momentum(underlying, wp, start_idx, mom)
        if r:
            results.append(r)

    # DCA Fixed
    r = backtest_dca_fixed(underlying, wp, start_idx)
    if r:
        results.append(r)

    # DCA Drawdown 3M
    r = backtest_dca_drawdown(underlying, wp, start_idx)
    if r:
        results.append(r)

    if len(results) < 2:
        print(f"  *** Not enough strategies succeeded ***")
        continue

    # Print table
    print(f"\n  {'Strategy':<24} {'Final $':>10} {'Total%':>9} {'Ann%':>8} {'MaxDD%':>8} {'Sharpe':>7}")
    print(f"  {'-'*66}")
    for r in results:
        extra = ""
        if r['strategy'] == "MA5/20 Cross" and 'n_trades' in r:
            extra = f"  ({r['n_trades']} trades, WR:{r['win_rate']:.0f}%)"
        print(f"  {r['strategy']:<24} ${r['final_value']:>9,.0f} {r['total_ret']:>8.1f}% {r['ann_ret']:>7.1f}% {r['max_dd']:>7.1f}% {r['sharpe']:>6.2f}{extra}")

    # Best among warrant strategies (exclude stock B&H ref)
    warrant_results = [r for r in results if "Stock B&H" not in r['strategy']]
    if warrant_results:
        best = max(warrant_results, key=lambda x: x['final_value'])
        bh_w = warrant_results[0]
        print(f"\n  >>> BEST: {best['strategy']} (${best['final_value']:,.0f}) vs Warrant B&H (${bh_w['final_value']:,.0f})")
        # Leverage check
        if "Stock B&H" in [r['strategy'] for r in results]:
            stock_bh = [r for r in results if r['strategy'] == "Stock B&H (ref)"][0]
            print(f"  >>> Leverage check: Warrant B&H = {bh_w['total_ret']:.1f}% vs Stock B&H = {stock_bh['total_ret']:.1f}% (ratio = {bh_w['total_ret']/max(stock_bh['total_ret'],0.01):.1f}x)")

    all_results.append({"warrant": name, "ticker": ticker, "strike": strike,
                         "leverage": leverage, "ko": knocked_out,
                         "n_days": n_days, "results": results})


# ============================================================
# Cross-Warrant Summary
# ============================================================
if all_results:
    print(f"\n\n{'=' * 90}")
    print("  CROSS-WARRANT RANKING (by Warrant Buy & Hold final value)")
    print(f"{'=' * 90}")

    sorted_w = sorted(all_results, key=lambda x: x['results'][1]['final_value'], reverse=True)
    print(f"  {'Rank':<5} {'Warrant':<46} {'Warr B&H':>10} {'Stock B&H':>10} {'Lev':>6} {'Days':>6}")
    print(f"  {'-'*83}")
    for rank, wr in enumerate(sorted_w, 1):
        bh_w = wr['results'][1]  # Warrant B&H
        bh_s = wr['results'][0]  # Stock B&H
        ko_flag = " [KO!]" if wr['ko'] else ""
        print(f"  {rank:<5} {wr['warrant']:<46} ${bh_w['final_value']:>9,.0f} ${bh_s['final_value']:>9,.0f} {wr['leverage']:>4.1f}x{ko_flag} {wr['n_days']:>5}")

    print(f"\n\n{'=' * 90}")
    print("  STRATEGY VS WARRANT BUY & HOLD: Excess Return (% points)")
    print(f"{'=' * 90}")
    print(f"  {'Warrant':<46} {'MA Cross':>9} {'Mom 3M':>9} {'Mom 6M':>9} {'Mom 12M':>8} {'DCA Fix':>9} {'DCA DD3M':>9}")
    print(f"  {'-'*101}")
    for wr in all_results:
        warrant_results = [r for r in wr['results'] if "Stock B&H" not in r['strategy']]
        if len(warrant_results) < 2:
            continue
        bh_ret = warrant_results[0]['total_ret']
        diffs = []
        for r in warrant_results[1:]:
            diffs.append(f"{r['total_ret'] - bh_ret:>+8.1f}%")
        # Pad if some strategies didn't run
        while len(diffs) < 6:
            diffs.append(f"{'N/A':>9}")
        name_short = wr['warrant'][:45]
        print(f"  {name_short:<46} {diffs[0]:>9} {diffs[1]:>9} {diffs[2]:>9} {diffs[3]:>9} {diffs[4]:>9} {diffs[5]:>9}")

print("\nDone.")
