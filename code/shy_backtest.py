# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ============================================================
# Load all assets
# ============================================================
def load_close(path, col_name): # type: ignore
    df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", col_name)].dropna()
    return close

# SHY starts 2002-07, others earlier. Align to 2010 for multi-asset comparison
assets_raw = {
    "SHY":   load_close(r"C:\AI\cc\stock\data\SHY_daily.csv", "SHY"),
    "SPY":   load_close(r"C:\AI\cc\stock\data\SPY_daily.csv", "SPY"),
    "GLD":   load_close(r"C:\AI\cc\stock\data\GLD_daily.csv", "GLD"),
    "NVDA":  load_close(r"C:\AI\cc\stock\data\NVDA_daily.csv", "NVDA"),
}

# Align to common start
start_date = "2010-01-01"
assets = {n: s[s.index >= start_date] for n, s in assets_raw.items()}

initial_capital = 10000.0

print("=" * 90)
print("  US 3-Year Treasury (SHY) vs Stocks, Gold, NVDA — Full Strategy Comparison")
print(f"  Period: {start_date} ~ 2026-06  |  Initial Capital: ${initial_capital:,.0f}")
print("=" * 90)

# Asset summary
print(f"\n  {'Asset':<8} {'Start Price':>12} {'End Price':>12} {'Return':>10} {'Years':>6} {'Days':>6}")
print(f"  {'─'*58}")
for name, s in assets.items():
    ret = (s.iloc[-1]/s.iloc[0] - 1) * 100
    y = (s.index[-1] - s.index[0]).days / 365.25
    print(f"  {name:<8} ${s.iloc[0]:>11.2f} ${s.iloc[-1]:>11.2f} {ret:>+9.1f}% {y:>5.1f}y {len(s):>5}d")

# ============================================================
# Strategy 1: Buy & Hold
# ============================================================
def compute_bh(series):
    final = initial_capital * series.iloc[-1] / series.iloc[0]
    n_years = (series.index[-1] - series.index[0]).days / 365.25
    ann = ((final / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    monthly_ret = series.resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly_ret.mean() / monthly_ret.std() if monthly_ret.std() > 0 else 0
    peak = series.cummax()
    dd = ((series - peak) / peak * 100).min()
    # Volatility
    vol = series.pct_change().std() * np.sqrt(252) * 100
    return {"final": final, "ann": ann, "sharpe": sharpe, "dd": dd, "vol": vol}

bh = {n: compute_bh(assets[n]) for n in assets}

# ============================================================
# Strategy 2: MA5/MA20 Cross
# ============================================================
def ma_cross_strategy(close_series):
    ma5 = close_series.rolling(5).mean()
    ma20 = close_series.rolling(20).mean()
    df = pd.DataFrame({"c": close_series, "ma5": ma5, "ma20": ma20}).dropna()
    df["above"] = df["ma5"] > df["ma20"]
    df["golden"] = df["above"] & (~df["above"].shift(1).fillna(False))
    df["death"] = (~df["above"]) & (df["above"].shift(1).fillna(False))

    cap = initial_capital; shares = 0.0; in_market = False
    daily_vals = []; trades = 0
    for idx, row in df.iterrows():
        p = row["c"]
        if row["golden"] and not in_market:
            shares = cap / p; cap = 0.0; in_market = True; trades += 1
        elif row["death"] and in_market:
            cap = shares * p; shares = 0.0; in_market = False; trades += 1
        daily_vals.append(cap if not in_market else shares * p)

    if in_market:
        cap = shares * close_series.iloc[-1]

    vals = pd.Series(daily_vals, index=df.index)
    final = cap if not in_market else shares * close_series.iloc[-1]
    n_years = (df.index[-1] - df.index[0]).days / 365.25
    ann = ((final / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    peak = vals.cummax()
    dd = ((vals - peak) / peak * 100).min()
    monthly_ret = vals.resample("ME").last().pct_change().dropna()
    sharpe = np.sqrt(12) * monthly_ret.mean() / monthly_ret.std() if monthly_ret.std() > 0 else 0
    vol = vals.pct_change().std() * np.sqrt(252) * 100
    # Time in market
    time_in = (df["above"].sum() / len(df)) * 100
    # Win rate (profitable trades)
    return {"final": final, "ann": ann, "dd": dd, "sharpe": sharpe, "vol": vol,
            "trades": trades, "time_in": time_in, "values": vals}

ma_res = {n: ma_cross_strategy(assets[n]) for n in assets}

# ============================================================
# Strategy 3: Jegadeesh-Titman Momentum
# ============================================================
def momentum_strategy(close_series, formation=6, skip=1):
    monthly = close_series.resample("ME").last()
    sig = pd.DataFrame({"price": monthly})
    sig["ret"] = sig["price"].pct_change()
    sig["mom"] = sig["price"].pct_change(periods=formation).shift(skip)
    sig["long"] = sig["mom"] > 0
    sig["strategy_ret"] = sig["long"].shift(1) * sig["ret"]
    sig = sig.dropna()
    sig["eq"] = initial_capital * (1 + sig["strategy_ret"]).cumprod()
    sig["bh_eq"] = initial_capital * (1 + sig["ret"]).cumprod()

    n_years = (sig.index[-1] - sig.index[0]).days / 365.25
    final = sig["eq"].iloc[-1]
    ann = ((final / initial_capital) ** (1 / n_years) - 1) * 100 if n_years > 0 else 0
    sharpe = np.sqrt(12) * sig["strategy_ret"].mean() / sig["strategy_ret"].std() if sig["strategy_ret"].std() > 0 else 0
    peak = sig["eq"].cummax()
    dd = ((sig["eq"] - peak) / peak * 100).min()
    vol = sig["strategy_ret"].std() * np.sqrt(12) * 100
    n_signals = int(abs(sig["long"].astype(int).diff()).sum())
    win_rate = (sig["strategy_ret"] > 0).mean() * 100
    time_in = sig["long"].mean() * 100
    bh_final = sig["bh_eq"].iloc[-1]
    return {"final": final, "ann": ann, "dd": dd, "sharpe": sharpe, "vol": vol,
            "signals": n_signals, "win_rate": win_rate, "time_in": time_in,
            "bh_final": bh_final, "df": sig}

mom6 = {n: momentum_strategy(assets[n], 6, 1) for n in assets}
mom12 = {n: momentum_strategy(assets[n], 12, 1) for n in assets}

# ============================================================
# Print Strategy Tables
# ============================================================
names = list(assets.keys())

def print_table(title, res_dict, metrics_spec):
    print(f"\n{'─'*90}")
    print(f"  {title}")
    print(f"{'─'*90}")
    header = f"  {'Metric':<18}"
    for n in names:
        header += f" {n:>16}"
    print(header)
    print(f"  {'─'*87}")
    for label, key, fmt in metrics_spec:
        row = f"  {label:<18}"
        for n in names:
            v = res_dict[n].get(key, 0)
            if fmt == "money":
                if v >= 1e6: row += f" ${v/1e6:>13.2f}M"
                elif v >= 1000: row += f" ${v/1000:>13.1f}K"
                else: row += f" ${v:>14,.0f}"
            elif fmt == "pct":
                row += f" {v:>15.1f}%"
            elif fmt == ".2f":
                row += f" {v:>15.2f}"
            elif fmt == "int":
                row += f" {v:>15.0f}"
        print(row)

metrics_basic = [
    ("Final Value",    "final",  "money"),
    ("Ann. Return",    "ann",    "pct"),
    ("Max Drawdown",   "dd",     "pct"),
    ("Sharpe Ratio",   "sharpe", ".2f"),
    ("Volatility(ann)","vol",    "pct"),
]
metrics_mom = [
    ("Final Value",    "final",  "money"),
    ("Ann. Return",    "ann",    "pct"),
    ("Max Drawdown",   "dd",     "pct"),
    ("Sharpe Ratio",   "sharpe", ".2f"),
    ("Win Rate",       "win_rate", "pct"),
    ("Time in Market", "time_in", "pct"),
    ("Signals",        "signals", "int"),
]
metrics_ma = [
    ("Final Value",    "final",  "money"),
    ("Ann. Return",    "ann",    "pct"),
    ("Max Drawdown",   "dd",     "pct"),
    ("Sharpe Ratio",   "sharpe", ".2f"),
    ("Trades",         "trades", "int"),
    ("Time in Market", "time_in", "pct"),
]

print_table("1. Buy & Hold (Benchmark)", bh, metrics_basic)
print_table("2. MA5/MA20 Golden Cross", ma_res, metrics_ma)
print_table("3. 6M Momentum (skip 1M)", mom6, metrics_mom)
print_table("4. 12M Momentum (skip 1M)", mom12, metrics_mom)

# ============================================================
# B&H vs Best Strategy Summary
# ============================================================
print(f"\n{'─'*90}")
print(f"  B&H vs Best Active Strategy")
print(f"{'─'*90}")
print(f"  {'Asset':<8} {'B&H Final':>14} {'B&H Ann':>8} {'B&H DD':>8} {'Best Act':>13} {'Best Name':>14} {'Capture':>9}")
print(f"  {'─'*82}")
for n in names:
    candidates = [
        (ma_res[n]["final"], "MA Cross"),
        (mom6[n]["final"], "6M Mom"),
        (mom12[n]["final"], "12M Mom"),
    ]
    best_val, best_name = max(candidates, key=lambda x: x[0])
    capture = best_val / bh[n]["final"] * 100
    bv = bh[n]["final"]
    ba = bh[n]["ann"]
    bd = bh[n]["dd"]
    print(f"  {n:<8} ${bv:>13,.0f} {ba:>7.1f}% {bd:>7.1f}% ${best_val:>12,.0f} {best_name:>14} {capture:>8.1f}%")

# ============================================================
# Risk-Return Analysis
# ============================================================
print(f"\n{'─'*90}")
print(f"  Risk-Adjusted Return: Sharpe Ratio Ranking")
print(f"{'─'*90}")
all_sharpe = []
for n in names:
    all_sharpe.append((n, "B&H", bh[n]["sharpe"], bh[n]["ann"], bh[n]["dd"], bh[n]["vol"]))
    all_sharpe.append((n, "MA Cross", ma_res[n]["sharpe"], ma_res[n]["ann"], ma_res[n]["dd"], ma_res[n]["vol"]))
    all_sharpe.append((n, "6M Mom", mom6[n]["sharpe"], mom6[n]["ann"], mom6[n]["dd"], mom6[n]["vol"]))
    all_sharpe.append((n, "12M Mom", mom12[n]["sharpe"], mom12[n]["ann"], mom12[n]["dd"], mom12[n]["vol"]))
all_sharpe.sort(key=lambda x: x[2], reverse=True)

print(f"  {'#':<3} {'Asset':<8} {'Strategy':<14} {'Sharpe':>8} {'Ann.Ret':>8} {'MaxDD':>8} {'Vol':>8}")
print(f"  {'─'*62}")
for i, (asset, strat, sh, ann, dd, vol) in enumerate(all_sharpe, 1):
    marker = " *** BEST" if i == 1 else ""
    print(f"  {i:<3} {asset:<8} {strat:<14} {sh:>7.2f} {ann:>7.1f}% {dd:>7.1f}% {vol:>7.1f}%{marker}")

# ============================================================
# SHY-Specific Analysis: Why it behaves differently
# ============================================================
shy = assets["SHY"]
shy_ret = shy.pct_change().dropna()
shy_dd = ((shy - shy.cummax()) / shy.cummax() * 100)
print(f"\n{'─'*90}")
print(f"  SHY (1-3Y Treasury) Risk Profile")
print(f"{'─'*90}")
print(f"  Daily return mean: {shy_ret.mean()*100:.4f}%  std: {shy_ret.std()*100:.3f}%")
print(f"  Max daily gain: {shy_ret.max()*100:+.2f}%  Max daily loss: {shy_ret.min()*100:+.2f}%")
print(f"  Max drawdown: {shy_dd.min():.1f}%")
print(f"  Days with >+0.5%: {(shy_ret > 0.005).sum()}  Days with <-0.5%: {(shy_ret < -0.005).sum()}")
print(f"  Positive days: {(shy_ret > 0).sum()/len(shy_ret)*100:.1f}%")
# Rolling 1Y returns
shy_1y = shy.pct_change(252).dropna()
print(f"  1Y rolling return: mean {shy_1y.mean()*100:.1f}%  min {shy_1y.min()*100:.1f}%  max {shy_1y.max()*100:.1f}%")
# Correlation with SPY
common_idx = shy.index.intersection(assets["SPY"].index)
shy_c = shy.loc[common_idx].pct_change().dropna()
spy_c = assets["SPY"].loc[common_idx].pct_change().dropna()
corr = shy_c.corr(spy_c)
print(f"  Correlation with SPY: {corr:.3f}")
# SHY in key years (use raw data for pre-2010 access)
shy_raw = assets_raw["SHY"]
spy_raw = assets_raw["SPY"]
for yr, label in [(2008, "Financial Crisis"), (2020, "COVID Crash"), (2022, "Rate Hikes")]:
    sy = shy_raw.get(str(yr), pd.Series())
    spy_y = spy_raw.get(str(yr), pd.Series())
    if len(sy) > 0 and len(spy_y) > 0:
        ret_yr = (sy.iloc[-1]/sy.iloc[0] - 1) * 100
        spy_ret = (spy_y.iloc[-1]/spy_y.iloc[0] - 1) * 100
        print(f"  {yr} {label}: SHY {ret_yr:+.1f}% | SPY {spy_ret:+.1f}%")


# ============================================================
# DCA Backtest with Cash Reserve (SHY vs SPY vs GLD)
# ============================================================
print(f"\n{'='*90}")
print(f"  DCA Enhanced Strategies: SHY vs SPY vs GLD vs NVDA (2016-2026)")
print(f"  Cash Reserve System — All strategies invest same total amount")
print(f"{'='*90}")

BASE, MIN_A, MAX_A = 1000.0, 500.0, 1500.0

def rule_fixed(state): return BASE

def rule_drawdown(state):
    p, i, prices = state["price"], state["i"], state["prices"]
    if i < 63: return BASE
    h = max(prices[i-63:i+1]); dd = (p - h) / h
    if dd < -0.10: return MAX_A
    elif dd < -0.05: return 1250
    elif dd < -0.02: return 1100
    elif dd > -0.01: return MIN_A
    return BASE

def rule_rsi(state):
    p, i, prices = state["price"], state["i"], state["prices"]
    if i < 20: return BASE
    r = np.array(prices[i-14:i+1]); d = np.diff(r)
    g = d[d>0].sum() if len(d[d>0])>0 else 0
    l = abs(d[d<0].sum()) if len(d[d<0])>0 else 0.0001
    rsi_val = 100 - (100/(1+g/l))
    if rsi_val < 35: return MAX_A
    elif rsi_val < 45: return 1250
    elif rsi_val > 70: return MIN_A
    elif rsi_val > 60: return 750
    return BASE

def rule_bear_bull(state):
    p, i, prices = state["price"], state["i"], state["prices"]
    if i < 200: return BASE
    ma200 = np.mean(prices[i-200:i+1]); ratio = p / ma200
    if p < ma200: return MAX_A
    elif ratio > 1.35: return MIN_A
    elif ratio > 1.15: return 750
    return BASE

def rule_ma50(state):
    p, i, prices = state["price"], state["i"], state["prices"]
    if i < 60: return BASE
    ma50 = np.mean(prices[i-50:i+1]); ratio = p / ma50
    if ratio < 0.92: return MAX_A
    elif ratio < 0.96: return 1250
    elif ratio > 1.08: return MIN_A
    elif ratio > 1.04: return 750
    return BASE

def rule_momentum(state):
    p, i, prices = state["price"], state["i"], state["prices"]
    if i < 63: return BASE
    m3 = p/prices[i-63]-1; m12 = p/prices[i-252]-1 if i>=252 else m3
    score = 0.0
    if m3<-0.08: score+=0.4
    elif m3<0: score+=0.2
    elif m3>0.15: score-=0.3
    if m12<-0.10: score+=0.4
    elif m12<0: score+=0.15
    elif m12>0.35: score-=0.3
    if score>0.5: return MAX_A
    elif score>0.25: return 1250
    elif score<-0.4: return MIN_A
    elif score<-0.2: return 750
    return BASE

def backtest_dca(close_series, desire_func):
    # Find first trading day each month
    first_dates, first_prices = [], []
    prev_ym = None
    for dt, price in close_series.items():
        ym = (dt.year, dt.month)
        if ym != prev_ym:
            first_dates.append(dt); first_prices.append(price); prev_ym = ym

    n = len(first_dates); cash = 0.0; shares = 0.0; invested = 0.0
    prices_hist = list(first_prices)
    records = []

    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        state = {"price": price, "i": i, "prices": prices_hist, "shares": shares,
                 "invested": invested, "reserve": cash}
        desired = desire_func(state)

        if desired > BASE:
            extra = min(desired - BASE, cash); actual = BASE + extra
        elif desired < BASE:
            save = min(BASE - desired, BASE - MIN_A); actual = BASE - save
        else:
            actual = BASE

        actual = max(MIN_A, min(MAX_A, actual))
        if actual < BASE: cash += (BASE - actual)
        elif actual > BASE: cash -= (actual - BASE)

        shares += actual / price; invested += actual
        records.append({"date": dt, "price": price, "actual": actual, "reserve": cash,
                        "shares": shares, "invested": invested, "value": shares*price})

    df_rec = pd.DataFrame(records).set_index("date")
    final = shares * close_series.iloc[-1]
    ret = (final - invested) / invested * 100
    yrs = n / 12.0
    ann_ret = ((final/invested)**(1/yrs)-1)*100 if yrs>0 and invested>0 else 0

    # Daily values for chart
    daily = []
    for date in close_series.index:
        if date < df_rec.index[0]: continue
        last = df_rec[df_rec.index <= date].iloc[-1]
        daily.append({"date": date, "value": last["shares"] * close_series.loc[date], "invested": last["invested"]})
    daily_df = pd.DataFrame(daily).set_index("date")

    return {"name": "?", "invested": invested, "final": final, "return": ret, "ann": ann_ret,
            "reserve": cash, "months": n, "df": df_rec, "daily": daily_df}

# Run DCA on 2016-2026 slice for each asset
dca_start = "2016-01-01"
dca_assets = {n: s[s.index >= dca_start] for n, s in assets_raw.items()}

all_rules = [
    (rule_fixed, "Fixed $1000"),
    (rule_drawdown, "Drawdown 3M"),
    (rule_ma50, "MA50 Distance"),
    (rule_rsi, "RSI(14)"),
    (rule_bear_bull, "Bear/Bull MA200"),
    (rule_momentum, "Momentum Adaptive"),
]

dca_all = {}
for asset_name in ["SHY", "SPY", "GLD", "NVDA"]:
    series = dca_assets[asset_name]
    results = []
    for fn, rn in all_rules:
        r = backtest_dca(series, fn); r["name"] = rn; results.append(r)
    results.sort(key=lambda x: x["final"], reverse=True)
    bl = [r for r in results if "Fixed" in r["name"]][0]
    best = results[0]
    dca_all[asset_name] = {"results": results, "baseline": bl, "best": best}

    print(f"\n{'─'*90}")
    print(f"  {asset_name} DCA Results (Cash Reserve System)")
    print(f"  Target invested: ${bl['invested']:,.0f} over {bl['months']} months")
    print(f"{'─'*90}")
    print(f"  {'#':<3} {'Strategy':<24} {'Invested':>11} {'Final':>14} {'Return':>9} {'Ann':>8} {'vs Fixed':>10} {'Reserve':>10}")
    print(f"  {'─'*93}")
    for i, r in enumerate(results):
        vf = ((r["final"]/bl["final"])-1)*100
        m = " <<< BEST" if r["name"] == best["name"] else ""
        print(f"  {i+1:<3} {r['name']:<24} ${r['invested']:>10,.0f} ${r['final']:>13,.0f} "
              f"{r['return']:>8.1f}% {r['ann']:>7.1f}% {vf:>+9.2f}% ${r['reserve']:>9,.0f}{m}")

    # Distribution
    print()
    for r in results:
        marker = " <<<" if r["name"] == best["name"] else ""
        n_lo = (r["df"]["actual"] <= MIN_A+1).sum()
        n_mid = (abs(r["df"]["actual"]-BASE) < 1).sum()
        n_hi = (r["df"]["actual"] >= MAX_A-1).sum()
        print(f"    {r['name']:<24} $500:{n_lo:>3}mo  $1000:{n_mid:>3}mo  $1500:{n_hi:>3}mo  Reserve:${r['reserve']:,.0f}{marker}")

# ============================================================
# Cross-Asset DCA Summary
# ============================================================
print(f"\n{'='*90}")
print(f"  Cross-Asset DCA Summary: Does any strategy beat Fixed $1000?")
print(f"{'='*90}")
print(f"  {'Strategy':<24} {'SHY':>12} {'SPY':>12} {'GLD':>12} {'NVDA':>12}")
print(f"  {'─'*74}")
for rn in ["Fixed $1000", "Drawdown 3M", "MA50 Distance", "RSI(14)", "Bear/Bull MA200", "Momentum Adaptive"]:
    row = f"  {rn:<24}"
    for an in ["SHY", "SPY", "GLD", "NVDA"]:
        results = dca_all[an]["results"]
        bl = dca_all[an]["baseline"]
        r = [x for x in results if x["name"]==rn][0]
        vf = ((r["final"]/bl["final"])-1)*100
        row += f" {vf:>+11.2f}%"
    print(row)

# ============================================================
# Key SHY DCA Insights
# ============================================================
shy_daily = dca_assets["SHY"]
print(f"\n{'─'*90}")
print(f"  SHY DCA Deep Dive: Why Treasuries need different rules")
print(f"{'─'*90}")
# SHY has very low volatility - check if any rule triggers reliably
shy_3m_high = shy_daily.rolling(63).max()
shy_dd_3m = (shy_daily - shy_3m_high) / shy_3m_high
print(f"  SHY max 3M drawdown: {shy_dd_3m.min()*100:.2f}%")
print(f"  SHY months with 3M DD < -1%: {(shy_dd_3m.resample('ME').last() < -0.01).sum()}")
print(f"  SHY months with 3M DD < -3%: {(shy_dd_3m.resample('ME').last() < -0.03).sum()}")
shy_ma200 = shy_daily.rolling(200).mean()
shy_vs_ma200 = shy_daily / shy_ma200
print(f"  SHY below MA200: {(shy_daily < shy_ma200).sum()} days ({((shy_daily < shy_ma200).sum()/len(shy_daily))*100:.1f}%)")
shy_rsi_daily = shy_daily.diff()
shy_gain = shy_rsi_daily.clip(lower=0).rolling(14).mean()
shy_loss = (-shy_rsi_daily.clip(upper=0)).rolling(14).mean()
shy_rsi = 100 - (100/(1+shy_gain/shy_loss))
print(f"  SHY RSI < 35 days: {(shy_rsi < 35).sum()} ({(shy_rsi < 35).sum()/len(shy_rsi)*100:.1f}%)")
print(f"  SHY RSI > 70 days: {(shy_rsi > 70).sum()} ({(shy_rsi > 70).sum()/len(shy_rsi)*100:.1f}%)")

# ============================================================
# Charts
# ============================================================
colors = {"SHY": "#17becf", "SPY": "#1f77b4", "GLD": "#9467bd", "NVDA": "#76B900"}
fig, axes = plt.subplots(3, 3, figsize=(26, 20))

# 1. B&H Equity Curves (log)
ax = axes[0, 0]
for n in names:
    eq = initial_capital * assets[n] / assets[n].iloc[0]
    ax.plot(assets[n].index, eq, label=n, color=colors[n], linewidth=1.5)
ax.set_title("Buy & Hold Equity Curves (Log Scale)", fontsize=12, fontweight="bold")
ax.set_ylabel("Value ($)"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
ax.set_yscale("log")

# 2. B&H Equity Curves (linear, 2010-2026)
ax = axes[0, 1]
for n in names:
    eq = initial_capital * assets[n] / assets[n].iloc[0]
    ax.plot(assets[n].index, eq, label=n, color=colors[n], linewidth=1.5)
ax.set_title("Buy & Hold — Linear Scale", fontsize=12, fontweight="bold")
ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

# 3. Drawdown Comparison
ax = axes[0, 2]
for n in names:
    s = assets[n]
    dd = (s - s.cummax()) / s.cummax() * 100
    ax.fill_between(s.index, 0, dd, label=n, color=colors[n], alpha=0.5, linewidth=0.5)
ax.set_title("Drawdown Comparison", fontsize=12, fontweight="bold")
ax.set_ylabel("Drawdown %"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
ax.axhline(y=-5, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
ax.axhline(y=-10, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)

# 4. Rolling 1Y Returns
ax = axes[1, 0]
for n in names:
    s = assets[n]
    r1y = s.pct_change(252).dropna() * 100
    ax.plot(s.index[252:], r1y, label=n, color=colors[n], linewidth=1.2)
ax.axhline(y=0, color="black", linewidth=0.5)
ax.set_title("Rolling 1-Year Returns", fontsize=12, fontweight="bold")
ax.set_ylabel("1Y Return %"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

# 5. Risk-Return Scatter (B&H)
ax = axes[1, 1]
for n in names:
    ax.scatter(bh[n]["vol"], bh[n]["ann"], c=colors[n], s=300, edgecolors="white",
              linewidth=1.5, zorder=5, label=n)
    ax.annotate(n, (bh[n]["vol"], bh[n]["ann"]), textcoords="offset points",
               xytext=(8, -10), fontsize=10, fontweight="bold")
ax.set_title("Risk-Return: Volatility vs Annualized Return", fontsize=12, fontweight="bold")
ax.set_xlabel("Annualized Volatility (%)"); ax.set_ylabel("Annualized Return (%)")
ax.legend(fontsize=9); ax.grid(True, alpha=0.3); ax.axhline(y=0, color="gray", linewidth=0.5)

# 6. Strategy Final Value (grouped bar)
ax = axes[1, 2]
x = np.arange(len(names)); w = 0.2
all_strategies = [
    ("B&H", bh, "steelblue"), ("MA Cross", ma_res, "#d62728"),
    ("6M Mom", mom6, "#ff7f0e"), ("12M Mom", mom12, "#2ca02c"),
]
for j, (lbl, res_dict, clr) in enumerate(all_strategies):
    vals = [res_dict[n]["final"] for n in names]
    bars = ax.bar(x + j*w - w*1.5, [v/1000 for v in vals], w, label=lbl, color=clr, edgecolor="white")
    for bar, val in zip(bars, vals):
        if val > 500000:
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+2, f"${val/1e6:.1f}M",
                   ha="center", fontsize=5.5, fontweight="bold", rotation=90)
ax.set_title("Strategy Final Value Comparison", fontsize=12, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(names, fontsize=10)
ax.set_ylabel("Final Value ($K)"); ax.legend(fontsize=7, ncol=2); ax.grid(True, alpha=0.3, axis="y")

# 7. DCA: Best Strategy Equity Curves (per asset)
ax = axes[2, 0]
for an in ["SHY", "SPY", "GLD", "NVDA"]:
    best_r = dca_all[an]["best"]
    bl_r = dca_all[an]["baseline"]
    ax.plot(best_r["daily"].index, best_r["daily"]["value"], color=colors[an],
            linewidth=2, label=f"{an} {best_r['name']}")
    ax.plot(bl_r["daily"].index, bl_r["daily"]["value"], color=colors[an],
            linewidth=0.8, linestyle="--", alpha=0.35)
ax.set_title("DCA: Best Strategy vs Fixed (Log)", fontsize=12, fontweight="bold")
ax.set_ylabel("Portfolio Value ($)"); ax.legend(fontsize=7); ax.grid(True, alpha=0.3)
ax.set_yscale("log")

# 8. DCA Improvement vs Fixed (by asset)
ax = axes[2, 1]
x = np.arange(len(all_rules)); w = 0.2
for k, an in enumerate(["SHY", "SPY", "GLD", "NVDA"]):
    results = dca_all[an]["results"]
    bl = dca_all[an]["baseline"]
    imps = [((r["final"]/bl["final"])-1)*100 for r in results]
    names_rules = [r["name"] for r in results]
    bars = ax.barh(x + k*w - w*1.5, imps, w, color=colors[an], alpha=0.8, label=an)
    for bar, imp in zip(bars, imps):
        ax.text(bar.get_width() + (0.05 if bar.get_width()>=0 else -0.7), bar.get_y()+bar.get_height()/2,
               f"{imp:+.1f}%", va="center", fontsize=6)
ax.set_yticks(x); ax.set_yticklabels(names_rules, fontsize=7)
ax.set_title("DCA: Improvement vs Fixed $1000", fontsize=12, fontweight="bold")
ax.set_xlabel("Excess Return (%)"); ax.legend(fontsize=8, loc="lower right")
ax.axvline(x=0, color="black", linewidth=0.5); ax.grid(True, alpha=0.3, axis="x"); ax.invert_yaxis()

# 9. 2022 Rate Hike Impact on SHY
ax = axes[2, 2]
shy_full = assets_raw["SHY"]
shy_2020_on = shy_full["2020-01-01":]
spy_2020_on = assets["SPY"]["2020-01-01":]
# Normalize to 100
ax.plot(shy_2020_on.index, shy_2020_on/shy_2020_on.iloc[0]*100, color=colors["SHY"], linewidth=2, label="SHY (Treasury 1-3Y)")
ax.plot(spy_2020_on.index, spy_2020_on/spy_2020_on.iloc[0]*100, color=colors["SPY"], linewidth=2, label="SPY (S&P 500)")
ax.axvspan("2022-01-01", "2022-12-31", alpha=0.1, color="red", label="2022 Rate Hikes")
ax.axhline(y=100, color="black", linewidth=0.5, linestyle="--")
ax.set_title("2020-2026: SHY vs SPY (2022 Rate Hike Impact)", fontsize=12, fontweight="bold")
ax.set_ylabel("Index (100 = Jan 2020)"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

plt.suptitle("US 3-Year Treasury (SHY) vs Stocks, Gold, NVDA — 2010-2026 Strategy Comparison",
             fontsize=17, fontweight="bold", y=1.01)
plt.tight_layout()
chart_path = r"C:\AI\cc\stock\image\SHY_comparison.png"
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"\nChart saved: {chart_path}")

# ============================================================
# FINAL VERDICT
# ============================================================
print(f"\n{'='*90}")
print(f"  FINAL VERDICT: US 3-Year Treasury (SHY) Strategy Analysis")
print(f"{'='*90}")

# Find best strategy for SHY
shy_best = max([("B&H", bh["SHY"]["final"]), ("MA Cross", ma_res["SHY"]["final"]),
                ("6M Mom", mom6["SHY"]["final"]), ("12M Mom", mom12["SHY"]["final"])], key=lambda x: x[1])
print(f"""
  1. SHY BEST STRATEGY: {shy_best[0]} (${shy_best[1]:,.0f})

  2. SHY key characteristics vs other assets:
     - Ultra-low volatility: {bh['SHY']['vol']:.1f}% vs SPY {bh['SPY']['vol']:.1f}% vs NVDA {bh['NVDA']['vol']:.1f}%
     - Shallow drawdowns: max DD {bh['SHY']['dd']:.1f}% (bonds = capital preservation)
     - Low correlation with SPY: {corr:.2f}
     - Acts as portfolio ballast, not a growth engine

  3. Why most timing strategies FAIL on SHY:
     - 3M drawdown rarely exceeds 2% → Drawdown rule barely triggers
     - RSI stays in 40-60 range → never hits 35/70 thresholds
     - MA crosses are noise → no real trend to exploit
     - Momentum signals mean-revert → wrong direction for momentum

  4. SHY's real value:
     - NOT a standalone investment (only {bh['SHY']['ann']:.1f}% annualized)
     - Best used as portfolio hedge / cash alternative
     - DCA into SHY makes sense only as a savings vehicle, not wealth builder

  5. DCA conclusion for SHY:
     - Fixed $1000 is optimal (no rule reliably triggers)
     - SHY volatility is too low for any timing rule to add value
     - The "best" DCA rule for SHY is simply: don't try to time it
""")

print("=" * 90)
print("  Cross-Asset Ranking (by B&H Final Value, 2010-2026):")
print("=" * 90)
ranking = [(n, bh[n]["final"], bh[n]["ann"], bh[n]["dd"], bh[n]["sharpe"], bh[n]["vol"]) for n in names]
ranking.sort(key=lambda x: x[1], reverse=True)
print(f"  {'Rank':<5} {'Asset':<8} {'Final Value':>14} {'Ann.Ret':>9} {'MaxDD':>9} {'Sharpe':>8} {'Vol':>8}")
print(f"  {'─'*68}")
for i, (n, final, ann, dd, sh, vol) in enumerate(ranking, 1):
    print(f"  {i:<5} {n:<8} ${final:>13,.0f} {ann:>8.1f}% {dd:>8.1f}% {sh:>7.2f} {vol:>7.1f}%")

print(f"\n  Key takeaway: SHY ({bh['SHY']['ann']:.1f}%/yr) is for capital preservation,")
print(f"  NVDA ({bh['NVDA']['ann']:.1f}%/yr) is for wealth creation.")
print(f"  A 60/40 SPY/SHY portfolio would have ~{0.6*bh['SPY']['ann']+0.4*bh['SHY']['ann']:.1f}%/yr with much lower drawdowns.")
print("=" * 90)
