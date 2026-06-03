# -*- coding: utf-8 -*-
"""
Warrant Backtest: Full 1-year strategy test on underlying stocks (NVDA, MU, ORCL),
with warrant leverage multipliers for scaling results to turbo call warrants.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# ============================================================
WARRANTS = [
    {"name": "W1: UBS OE Turbo Call NVDA 172.21",   "ticker": "NVDA", "strike": 172.21},
    {"name": "W2: HSBC OE-Turbo MU Call 538.82",    "ticker": "MU",   "strike": 538.82},
    {"name": "W3: Vontobel OE Turbo-OS MU",         "ticker": "MU",   "strike": 380.07},
    {"name": "W4: MS OE Turbo Long NVDA 176.67",    "ticker": "NVDA", "strike": 176.67},
    {"name": "W5: HSBC OE-Turbo ORCL Call 187.3",   "ticker": "ORCL", "strike": 187.30},
]

FINANCING_RATE = 0.045
BASE_INVEST = 10000

print("=" * 100)
print("  WARRANT BACKTEST: Full 1-Year Strategy Test (Underlying + Warrant Leverage)")
print("  Period: 2025-06-02 to 2026-06-03")
print("=" * 100)

# ============================================================
# Load Data
# ============================================================
print("\n--- Loading Data ---")
data = {}
for ticker in ["NVDA", "MU", "ORCL"]:
    path = rf"C:\AI\cc\stock\{ticker}_daily.csv"
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()
    data[ticker] = close
    print(f"  {ticker}: ${close.iloc[0]:.2f} -> ${close.iloc[-1]:.2f}  (min ${close.min():.2f}, max ${close.max():.2f}, {len(close)} days)")

# ============================================================
# Helper: compute metrics from daily returns
# ============================================================
def metrics_from_equity(equity, daily_rets, label, years):
    """Compute metrics from an equity curve Series."""
    valid = equity.dropna()
    final_val = float(valid.iloc[-1])
    total_ret = (final_val / BASE_INVEST - 1) * 100
    ann_ret = ((final_val / BASE_INVEST) ** (1 / max(years, 0.01)) - 1) * 100
    max_dd = float(((valid - valid.cummax()) / valid.cummax() * 100).min())
    rets = daily_rets.dropna()
    if len(rets) > 1 and rets.std() > 0:
        sharpe = float(np.sqrt(252) * rets.mean() / rets.std())
    else:
        sharpe = 0.0
    return {"name": label, "total_ret": total_ret, "ann_ret": ann_ret,
            "max_dd": max_dd, "sharpe": sharpe, "final_val": final_val}


# ============================================================
# Strategy 1: Buy & Hold
# ============================================================
def bh(close):
    rets = close.pct_change().fillna(0)
    equity = (1 + rets).cumprod() * BASE_INVEST
    years = len(close) / 252
    return metrics_from_equity(equity, rets, "Buy & Hold", years), equity, rets


# ============================================================
# Strategy 2: MA5/MA20 Cross
# ============================================================
def ma_cross(close):
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    signal = ((ma5 > ma20).astype(int)).shift(1).fillna(0)
    rets = close.pct_change().fillna(0)
    s_rets = rets * signal
    equity = (1 + s_rets).cumprod() * BASE_INVEST
    years = len(close) / 252

    # Trades
    trades = []
    in_t, entry = False, 0.0
    for i in range(1, len(signal)):
        if signal.iloc[i] == 1 and signal.iloc[i-1] == 0:
            in_t, entry = True, float(equity.iloc[i])
        elif signal.iloc[i] == 0 and signal.iloc[i-1] == 1:
            if in_t and entry > 0:
                trades.append(float(equity.iloc[i]) / entry - 1)
            in_t = False
    if in_t and entry > 0:
        trades.append(float(equity.iloc[-1]) / entry - 1)

    m = metrics_from_equity(equity, s_rets, "MA5/20 Cross", years)
    m["trades"] = len(trades)
    m["win_rate"] = sum(1 for t in trades if t > 0) / len(trades) * 100 if trades else 0
    return m, equity, s_rets


# ============================================================
# Strategy 3: Momentum (Jegadeesh-Titman)
# ============================================================
def momentum(close, formation_months):
    monthly = close.resample("ME").last()
    mom = monthly.pct_change(periods=formation_months).shift(1)
    mom_daily = mom.reindex(close.index).ffill()
    signal = (mom_daily > 0).astype(int).fillna(0)
    rets = close.pct_change().fillna(0)
    s_rets = rets * signal
    equity = (1 + s_rets).cumprod() * BASE_INVEST
    years = len(close) / 252
    m = metrics_from_equity(equity, s_rets, f"Momentum {formation_months}M", years)
    return m, equity, s_rets


# ============================================================
# Strategy 4: DCA Fixed $1000/month
# ============================================================
def dca_fixed(close, monthly=1000):
    shares, invested = 0.0, 0.0
    prev_ym = None
    vals, dts = [], []
    for dt, price in close.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            shares += monthly / price
            invested += monthly
            prev_ym = ym
        dts.append(dt)
        vals.append(shares * price)
    eq = pd.Series(vals, index=dts)
    years = len(close) / 252
    total_ret = (eq.iloc[-1] / invested - 1) * 100 if invested > 0 else 0
    ann_ret = ((eq.iloc[-1] / invested) ** (1 / years) - 1) * 100 if invested > 0 and years > 0 else 0
    monthly_rets = eq.resample("ME").last().pct_change().dropna()
    sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std()) if len(monthly_rets) > 1 and monthly_rets.std() > 0 else 0
    max_dd = float(((eq - eq.cummax()) / eq.cummax() * 100).min())
    return {"name": "DCA Fixed $1000/mo", "total_ret": total_ret, "ann_ret": ann_ret,
            "max_dd": max_dd, "sharpe": sharpe, "final_val": float(eq.iloc[-1]),
            "invested": invested}, eq, eq.pct_change().fillna(0)


# ============================================================
# Strategy 5: DCA Drawdown 3M
# ============================================================
def dca_drawdown(close, base=1000, min_a=500, max_a=1500):
    high_3m = close.rolling(63).max()
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    shares, invested, cash_reserve = 0.0, 0.0, 0.0
    vals, dts = [], []
    month_idx = 0
    for dt, price in close.items():
        # Check if this is a month-start investment day
        if month_idx < len(first_dates) and dt == first_dates[month_idx]:
            p = first_prices[month_idx]
            h3 = float(high_3m.loc[dt]) if dt in high_3m.index and not pd.isna(high_3m.loc[dt]) else None

            if h3 is None or pd.isna(h3):
                desired = base
            elif p < h3 * 0.90:
                desired = max_a
            elif p >= h3:
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

            shares += actual / price
            invested += actual
            month_idx += 1

        dts.append(dt)
        vals.append(shares * price)

    eq = pd.Series(vals, index=dts)
    years = len(close) / 252
    total_ret = (eq.iloc[-1] / invested - 1) * 100 if invested > 0 else 0
    ann_ret = ((eq.iloc[-1] / invested) ** (1 / years) - 1) * 100 if invested > 0 and years > 0 else 0
    monthly_rets = eq.resample("ME").last().pct_change().dropna()
    sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std()) if len(monthly_rets) > 1 and monthly_rets.std() > 0 else 0
    max_dd = float(((eq - eq.cummax()) / eq.cummax() * 100).min())
    return {"name": "DCA Drawdown 3M", "total_ret": total_ret, "ann_ret": ann_ret,
            "max_dd": max_dd, "sharpe": sharpe, "final_val": float(eq.iloc[-1]),
            "invested": invested}, eq, eq.pct_change().fillna(0)


# ============================================================
# Strategy 6: DCA Enhanced - RSI(14)
# ============================================================
def dca_rsi(close, base=1000, min_a=500, max_a=1500):
    # Compute RSI from scratch
    prices = close.values
    n = len(prices)
    rsi_vals = np.full(n, np.nan)
    for i in range(14, n):
        recent = prices[i-14:i+1]
        deltas = np.diff(recent)
        gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
        losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0.0001
        rsi_vals[i] = 100 - (100 / (1 + gains / losses))
    rsi_series = pd.Series(rsi_vals, index=close.index)

    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    shares, invested, cash_reserve = 0.0, 0.0, 0.0
    vals, dts = [], []
    month_idx = 0
    for dt, price in close.items():
        if month_idx < len(first_dates) and dt == first_dates[month_idx]:
            rsi = float(rsi_series.loc[dt]) if dt in rsi_series.index and not pd.isna(rsi_series.loc[dt]) else 50

            if pd.isna(rsi):
                desired = base
            elif rsi < 35:
                desired = max_a
            elif rsi > 70:
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

            shares += actual / price
            invested += actual
            month_idx += 1

        dts.append(dt)
        vals.append(shares * price)

    eq = pd.Series(vals, index=dts)
    years = len(close) / 252
    total_ret = (eq.iloc[-1] / invested - 1) * 100 if invested > 0 else 0
    ann_ret = ((eq.iloc[-1] / invested) ** (1 / years) - 1) * 100 if invested > 0 and years > 0 else 0
    monthly_rets = eq.resample("ME").last().pct_change().dropna()
    sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std()) if len(monthly_rets) > 1 and monthly_rets.std() > 0 else 0
    max_dd = float(((eq - eq.cummax()) / eq.cummax() * 100).min())
    return {"name": "DCA RSI(14)", "total_ret": total_ret, "ann_ret": ann_ret,
            "max_dd": max_dd, "sharpe": sharpe, "final_val": float(eq.iloc[-1]),
            "invested": invested}, eq, eq.pct_change().fillna(0)


# ============================================================
# Strategy 7: DCA Enhanced - MA200 Bear/Bull
# ============================================================
def dca_ma200(close, base=1000, min_a=500, max_a=1500):
    ma200 = close.rolling(200).mean()

    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt)
            first_prices.append(price)
            prev_ym = ym

    shares, invested, cash_reserve = 0.0, 0.0, 0.0
    vals, dts = [], []
    month_idx = 0
    for dt, price in close.items():
        if month_idx < len(first_dates) and dt == first_dates[month_idx]:
            ma = float(ma200.loc[dt]) if dt in ma200.index and not pd.isna(ma200.loc[dt]) else None

            if ma is None or pd.isna(ma):
                desired = base
            elif price < ma:
                desired = max_a  # Below MA200 -> bear, invest more
            elif price > ma * 1.35:
                desired = min_a  # Way above MA200 -> overbought, invest less
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

            shares += actual / price
            invested += actual
            month_idx += 1

        dts.append(dt)
        vals.append(shares * price)

    eq = pd.Series(vals, index=dts)
    years = len(close) / 252
    total_ret = (eq.iloc[-1] / invested - 1) * 100 if invested > 0 else 0
    ann_ret = ((eq.iloc[-1] / invested) ** (1 / years) - 1) * 100 if invested > 0 and years > 0 else 0
    monthly_rets = eq.resample("ME").last().pct_change().dropna()
    sharpe = float(np.sqrt(12) * monthly_rets.mean() / monthly_rets.std()) if len(monthly_rets) > 1 and monthly_rets.std() > 0 else 0
    max_dd = float(((eq - eq.cummax()) / eq.cummax() * 100).min())
    return {"name": "DCA MA200 Regime", "total_ret": total_ret, "ann_ret": ann_ret,
            "max_dd": max_dd, "sharpe": sharpe, "final_val": float(eq.iloc[-1]),
            "invested": invested}, eq, eq.pct_change().fillna(0)


# ============================================================
# MAIN: Run on each underlying
# ============================================================
all_stock_results = {}

for ticker in ["NVDA", "MU", "ORCL"]:
    close = data[ticker]
    print(f"\n{'=' * 100}")
    print(f"  {ticker}  |  ${close.iloc[0]:.2f} -> ${close.iloc[-1]:.2f}  |  1 Year")
    print(f"{'=' * 100}")

    strategies = {
        "Buy & Hold": bh,
        "MA5/20 Cross": ma_cross,
        "Momentum 3M": lambda c: momentum(c, 3),
        "Momentum 6M": lambda c: momentum(c, 6),
        "Momentum 12M": lambda c: momentum(c, 12),
        "DCA Fixed $1K": dca_fixed,
        "DCA Drawdown 3M": dca_drawdown,
        "DCA RSI(14)": dca_rsi,
        "DCA MA200": dca_ma200,
    }

    results = []
    for sname, sfunc in strategies.items():
        try:
            m, eq, rets = sfunc(close)
            results.append(m)
        except Exception as e:
            print(f"  {sname}: ERROR - {e}")

    # Print table
    print(f"\n  {'Strategy':<22} {'Final $':>10} {'Total%':>9} {'Ann%':>8} {'MaxDD%':>8} {'Sharpe':>7}")
    print(f"  {'-'*64}")
    for m in results:
        extra = ""
        if "trades" in m:
            extra = f"  ({m['trades']} trades, WR:{m['win_rate']:.0f}%)"
        print(f"  {m['name']:<22} ${m['final_val']:>9,.0f} {m['total_ret']:>8.1f}% {m['ann_ret']:>7.1f}% {m['max_dd']:>7.1f}% {m['sharpe']:>6.2f}{extra}")

    # Find best
    trading_results = [m for m in results if "Buy & Hold" not in m['name']]
    bh_r = [m for m in results if m['name'] == "Buy & Hold"][0]
    best = max(results, key=lambda x: x['final_val'])
    beats_bh = [m for m in trading_results if m['final_val'] > bh_r['final_val']]
    print(f"\n  >>> BEST: {best['name']} (${best['final_val']:,.0f})")
    if beats_bh:
        for m in beats_bh:
            print(f"  >>> BEATS B&H: {m['name']} by ${m['final_val'] - bh_r['final_val']:+,.0f} ({m['total_ret'] - bh_r['total_ret']:+.1f}%)")
    else:
        print(f"  >>> No strategy beats Buy & Hold for {ticker}")

    # DCA comparison
    dca_results = [m for m in results if "DCA" in m['name'] and "Fixed" not in m['name']]
    dca_fixed_r = [m for m in results if m['name'] == "DCA Fixed $1K"]
    if dca_fixed_r and dca_results:
        dca_f = dca_fixed_r[0]
        print(f"\n  DCA Rule vs Fixed $1000/mo (invested: ${dca_f.get('invested', 12000):,.0f}):")
        for m in dca_results:
            inv = m.get('invested', dca_f.get('invested', 12000))
            diff = m['final_val'] - dca_f['final_val']
            print(f"    {m['name']:<22}: ${m['final_val']:>9,.0f}  ({m['total_ret']:>+.1f}% vs Fixed, invested ${inv:,.0f})")

    all_stock_results[ticker] = results

# ============================================================
# Warrant Leverage Analysis
# ============================================================
print(f"\n\n{'=' * 100}")
print("  WARRANT LEVERAGE ANALYSIS")
print(f"  How to read: Warrant Return % = Stock Return % x Leverage")
print(f"  Leverage = Current_Price / (Current_Price - Adj_Strike)")
print(f"  Adj_Strike = Strike * (1 + {FINANCING_RATE*100:.1f}% financing / year)")
print(f"{'=' * 100}")

print(f"\n  {'Warrant':<46} {'Stock':>6} {'Strike':>8} {'Adj Str':>8} {'Intr Val':>9} {'Leverage':>8} {'ITM Days':>9} {'Status':>12}")
print(f"  {'-'*110}")

warrant_info = []
for w in WARRANTS:
    ticker = w["ticker"]
    strike = w["strike"]
    close = data[ticker]
    current_price = float(close.iloc[-1])

    # Find when warrant became ITM
    itm_start = None
    for dt, price in close.items():
        if price > strike:
            itm_start = dt
            break

    # Calculate adjusted strike
    if itm_start:
        days_since = (close.index[-1] - itm_start).days
        adj_strike = strike * (1 + FINANCING_RATE / 365) ** days_since
        intrinsic = current_price - adj_strike
        leverage = current_price / intrinsic if intrinsic > 0 else float('inf')
        itm_days = (close.index[-1] - itm_start).days
        status = "ITM" if intrinsic > 0 else "Knocked Out"
    else:
        adj_strike = strike
        intrinsic = 0
        leverage = float('inf')
        itm_days = 0
        status = "NEVER ITM"

    print(f"  {w['name']:<46} ${current_price:<5.0f} ${strike:<7.2f} ${adj_strike:<7.2f} ${intrinsic:<8.2f} {leverage:<6.1f}x {itm_days:<8}  {status}")

    # Calculate approximate warrant B&H return if held since first ITM day
    if itm_start:
        itm_slice = close[close.index >= itm_start]
        stock_ret_itm = (itm_slice.iloc[-1] / itm_slice.iloc[0] - 1) * 100

        # Calculate the REAL leverage effect over the ITM period
        # For each day: warrant_value = max(S - K_adj, 0), return = (S_t - K_t)/(S_{t-1} - K_{t-1}) - 1
        wp_vals = []
        dates_list = []
        K_t = strike
        for i, (dt, S) in enumerate(itm_slice.items()):
            if i == 0:
                K_t = strike
            else:
                days = (dt - itm_slice.index[i-1]).days
                K_t = K_t * (1 + FINANCING_RATE / 365 * days)
            wp_vals.append(max(S - K_t, 0.001))
            dates_list.append(dt)
        wp = pd.Series(wp_vals, index=dates_list)
        warrant_ret = (wp.iloc[-1] / wp.iloc[0] - 1) * 100

        # Calculate the effective average leverage over the period
        eff_leverage = warrant_ret / stock_ret_itm if abs(stock_ret_itm) > 0.01 else 0

        print(f"    ITM Period: {itm_start.strftime('%Y-%m-%d')} -> {close.index[-1].strftime('%Y-%m-%d')} ({itm_days}d)")
        print(f"    Stock B&H (ITM period): {stock_ret_itm:+.1f}%")
        print(f"    Warrant B&H (ITM period, modeled): {warrant_ret:+.1f}%")
        print(f"    Effective Avg Leverage: {eff_leverage:.1f}x")

        warrant_info.append({**w, "current_price": current_price, "adj_strike": adj_strike,
                             "leverage": leverage, "itm_days": itm_days, "eff_leverage": eff_leverage,
                             "stock_ret_itm": stock_ret_itm, "warrant_ret_itm": warrant_ret})

# ============================================================
# Full-Year Strategy Application to Warrants
# ============================================================
print(f"\n\n{'=' * 100}")
print("  STRATEGY PROJECTION ON WARRANTS (1-Year Underlying + Leverage)")
print("  Warning: Warrants were OTM for most of the year. Leverage amplifies BOTH gains & losses.")
print(f"{'=' * 100}")

for wi in warrant_info:
    ticker = wi["ticker"]
    stock_results = all_stock_results[ticker]
    print(f"\n  --- {wi['name']} ---")
    print(f"  Current Leverage: {wi['leverage']:.1f}x | ITM for {wi['itm_days']} days | Eff Leverage: {wi.get('eff_leverage', 0):.1f}x")

    # For each strategy, compute the warrant-equivalent return
    # Warrant strategy return = (1 + Stock_Strategy_Return)^Leverage - 1  (approximation)
    # More precisely: apply the same signals to warrant daily returns
    print(f"  {'Strategy':<22} {'Stock Ret':>9} {'Est Warrant Ret':>15} {'Note':>30}")
    print(f"  {'-'*76}")
    for sr in stock_results:
        stock_ret = sr['total_ret']
        # Approximate warrant return using levered stock return
        # W_ret = (1 + S_ret)^leverage - 1 (continuous compounding approximation)
        lev = wi['leverage']
        if stock_ret > -100:
            # Linear approximation for small returns, geometric for larger
            est_w_ret = ((1 + stock_ret/100) ** lev - 1) * 100
        else:
            est_w_ret = -100  # Total loss
        note = ""
        if sr['name'] == "Buy & Hold":
            note = f"Baseline for {ticker}"
        elif "DCA" in sr['name']:
            note = "Monthly investment"
        elif "Cross" in sr['name']:
            note = f"{sr.get('trades','?')} trades"
        print(f"  {sr['name']:<22} {stock_ret:>+8.1f}% {est_w_ret:>+14.1f}%   {note}")

print(f"\n{'=' * 100}")
print("  KEY TAKEAWAYS")
print(f"{'=' * 100}")
for wi in warrant_info:
    print(f"  {wi['name']}")
    print(f"    Leverage: {wi['leverage']:.1f}x -> 1% stock move = ~{wi['leverage']:.1f}% warrant move")
    if wi['itm_days'] < 60:
        print(f"    CAUTION: Only {wi['itm_days']} days ITM. Limited backtest data.")
    print()

print("\nDone.")
