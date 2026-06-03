---
name: quant-backtest
description: Quantitative stock backtesting system. Use when the user asks to backtest trading strategies (MA crossover, momentum, DCA), compare assets, optimize investment rules, download data from yfinance, or analyze US stock performance. Covers download → backtest → compare → optimize → validate workflow.
user-invocable: true
allowed-tools: Read, Write, Edit, Grep, Glob, WebSearch, WebFetch, PowerShell
---

# Quantitative Stock Backtesting System

Complete pipeline for downloading stock data, running quantitative strategy backtests, and comparing results across assets and market eras.

## Supported Strategies

| Strategy | Description | Key Parameters |
|----------|-------------|----------------|
| MA5/MA20 Cross | Golden cross buy, death cross sell | MA windows: 5, 20 |
| Jegadeesh-Titman Momentum | Past N-month return > 0 → long | Formation: 3/6/12M, Skip: 1M |
| Buy & Hold | Baseline comparison | — |
| DCA Fixed | Equal monthly investment | — |
| DCA Enhanced | Variable $500-$1500/mo with cash reserve | 7 rule variants |

## DCA Optimization Rules (Cash Reserve System)

All enhanced DCA strategies use a **cash reserve** to ensure equal total investment:
- Invest $500 → save $500 to reserve
- Invest $1500 → pull $500 from reserve
- All strategies end with ~same total invested as Fixed $1000

### Rule Catalog

```
1. Fixed $1000 (baseline)
2. Drawdown 3M: Price < 3M high -10% → $1500, at new high → $500
3. MA50 Distance: Below MA50 → $1500, far above → $500
4. RSI(14): RSI < 35 → $1500, RSI > 70 → $500
5. Bear/Bull MA200: Below MA200 → $1500, >1.35x MA200 → $500
6. Volatility Panic: 1M vol > 1.5x 1Y avg → $1500
7. Momentum Adaptive: 3M/12M weighted score → adjust amount
```

## Workflow

### Step 1: Download Data

```python
import yfinance as yf
import pandas as pd

# Single stock
df = yf.download("SPY", start="1993-01-01", interval="1d")
df.to_csv(r"C:\AI\cc\stock\SPY_daily.csv")

# Multiple stocks
for ticker in ["NVDA", "GOOGL", "ORCL", "AMZN", "GLD"]:
    df = yf.download(ticker, start="2004-01-01", interval="1d")
    df.to_csv(rf"C:\AI\cc\stock\{ticker}_daily.csv")
```

**Critical**: yfinance returns MultiIndex columns `(Price, Ticker)`. Load with:
```python
df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "TICKER")].dropna()
```

### Step 2: Single Asset Backtest

See `C:\AI\cc\stock\` for complete scripts:
- `nvda_backtest.py` — MA5/MA20 cross with metrics
- `nvda_momentum.py` — Jegadeesh-Titman 3M/6M/12M
- `dca_equal_invested.py` — Equal-total DCA with all 7 rules

Core metrics: Total Return, Annualized Return, Max Drawdown, Sharpe Ratio, Win Rate

### Step 3: Multi-Asset Comparison

Use `all6_backtest.py` pattern — loop over assets dict, collect results, rank by final value.

### Step 4: Multi-Era Validation

Test strategies across distinct market regimes:
- **Lost Decade** (2000-2010): Dot-com + Financial Crisis
- **Recovery** (2010-2015): Choppy, range-bound
- **Bull Run** (2016-2026): Strong uptrend

See `spy_2000_bear.py` for era-split pattern.

### Step 5: Generate Report

Write final rules + comparison tables to text file (see `DCA_RULES_FINAL.txt` format).

## Critical Implementation Patterns

### Windows Unicode Fix
Every `.py` file must start with:
```python
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
```

### DCA Monthly Date Detection
Never use `pd.Grouper(freq="MS")` — it generates dates not in the price index. Instead:
```python
first_dates, first_prices = [], []
prev_ym = None
for dt, price in close_series.items():
    ym = (dt.year, dt.month)
    if ym != prev_ym:
        first_dates.append(dt)
        first_prices.append(price)
        prev_ym = ym
```

### RSI Calculation (from scratch, no TA-lib)
```python
recent = np.array(prices[i-14:i+1])
deltas = np.diff(recent)
gains = deltas[deltas > 0].sum() if len(deltas[deltas > 0]) > 0 else 0
losses = abs(deltas[deltas < 0].sum()) if len(deltas[deltas < 0]) > 0 else 0.0001
rsi = 100 - (100 / (1 + gains/losses))
```

### Cash Reserve Backtest Loop
```python
def backtest_equal_invested(close_series, desire_func, name):
    # ... find first_dates, first_prices ...
    cash_reserve = 0.0
    for i, (dt, price) in enumerate(zip(first_dates, first_prices)):
        state = {"price": price, "i": i, "prices": prices_history, ...}
        desired = desire_func(state)

        if desired > BASE:
            extra = min(desired - BASE, cash_reserve)
            actual = BASE + extra
        elif desired < BASE:
            save = min(BASE - desired, BASE - MIN_A)
            actual = BASE - save
        else:
            actual = BASE

        if actual < BASE: cash_reserve += (BASE - actual)
        elif actual > BASE: cash_reserve -= (actual - BASE)

        shares += actual / price
        invested += actual
```

## Known Findings (reference for conclusions)

1. **B&H beats all timing strategies** on strong-trend assets (NVDA, AMZN, GOOGL)
2. **No enhanced DCA rule consistently beats Fixed $1000** across all market eras
3. **Drawdown 3M is the only strategy to ever beat Fixed** (+0.51% in 2000-2010 Lost Decade), by deploying $1500 during 8 months of the 2008 financial crisis
4. **RSI is the worst DCA rule** — it hoards cash (RSI rarely triggers < 35) and misses bull markets
5. **MA200 thresholds are too wide** — SPY barely touched MA200 in 2010-2026
6. **Any rule that reduces investment in a bull market permanently loses** — the opportunity cost of uninvested cash compounds against you
7. **NVDA-specific**: Trend is too strong for ANY timing — Fixed $1000 always wins
8. **SPY recommendation**: Fixed $1000 primary; Drawdown 3M optional for bear protection

## Output Files

| File | Purpose |
|------|---------|
| `*_daily.csv` | Raw yfinance data |
| `*_backtest.py` | Single-asset strategy backtest |
| `*_chart.png` | Equity curves, drawdown, signals |
| `DCA_RULES_FINAL.txt` | Final report with era comparison tables |

## Common Pitfalls

- **Never** use emoji or special Unicode in print statements on Windows (use ASCII: `BEST`, `<<<`, `***`)
- **Never** pipe `pd.Grouper("MS")` into dates — use manual (year, month) iteration
- **Never** compare nested dicts containing DataFrames with `==` — compare string keys instead
- **Always** verify total_invested is within 1% across all strategies when using cash reserve
- **Always** use `header=[0,1]` in `pd.read_csv` for yfinance MultiIndex output
- Chart `labels` parameter is deprecated in matplotlib bar charts — accept the warning
