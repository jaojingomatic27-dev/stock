# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Personal quantitative stock backtesting project. Downloads US stock data via yfinance, runs strategy backtests (MA cross, momentum, enhanced DCA), prints formatted results and generates matplotlib charts saved as PNGs.

**Core finding across all backtests:** Buy & Hold consistently beats active timing strategies. Fixed monthly DCA ($1000) is optimal for strong-trend assets; enhanced DCA rules only add marginal value during deep bear markets.

## Environment

- Python 3 (no venv configured; install dependencies globally with `pip install yfinance pandas numpy matplotlib`)
- No `requirements.txt` or `pyproject.toml`
- Windows paths (`C:\AI\cc\stock\`) are hardcoded throughout — not portable

## Data flow

```
download_*.py  →  yfinance.download()  →  *_daily.csv  (multi-index columns)
                                                            ↓
backtest scripts  ←  pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
                                                            ↓
                   close = df[("Close", "TICKER")].dropna()
                                                            ↓
                   compute signals → print tables → save charts (PNG) + results (CSV)
```

yfinance output on single-ticker downloads produces a flat column index; multi-ticker downloads produce a MultiIndex `(Price, Ticker)`. Scripts access close prices via `df[("Close", "TICKER")]`.

## Script patterns

Every backtest script is **self-contained** — there is no shared library. Common copy-pasted boilerplate:

```python
# UTF-8 stdout wrapper (needed for Chinese characters in Windows console)
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load multi-index CSV
df = pd.read_csv(r"C:\AI\cc\stock\TICKER_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
close = df[("Close", "TICKER")].dropna()

# Filter by date
close = close[close.index >= "2010-01-01"]
```

## Key strategies implemented

| Strategy | Signal | Files |
|---|---|---|
| MA5/MA20 Cross | Golden cross → buy, death cross → sell | `nvda_backtest.py`, `googl_backtest.py`, `all6_backtest.py`, `shy_backtest.py` |
| Momentum (Jegadeesh-Titman) | Past N-month return > 0 → long, else cash. Formation 3M/6M/12M, skip 1M | `nvda_momentum.py`, `googl_backtest.py`, `all6_backtest.py`, `shy_backtest.py` |
| Enhanced DCA ($500–$1500) | 6 timing rules vs Fixed $1000 baseline with cash reserve | `dca_backtest.py`, `dca_optimize.py`, `dca_optimize_v2.py`, `dca_2000_2016.py`, `spy_2000_bear.py`, `shy_backtest.py`, `dca_equal_invested.py` |

DCA timing rules: Fixed, Drawdown (3M high), RSI(14), MA50 Distance, Bear/Bull MA200 regime, Momentum Adaptive.

## Common patterns when writing new backtests

- Aligning multiple assets to a common start date: `s[s.index >= "2010-01-01"]`
- Resampling to monthly for momentum: `close.resample("ME").last()`
- DCA monthly investment days: iterate through prices, detect `(year, month)` changes for first trading day of each month
- Performance metrics pattern: `ann = ((final / initial) ** (1 / years) - 1) * 100`, `sharpe = np.sqrt(12) * monthly_ret.mean() / monthly_ret.std()`, `max_dd = ((vals - vals.cummax()) / vals.cummax() * 100).min()`

## CSV file naming

- Stock data: `{TICKER}_daily.csv` (e.g., `NVDA_daily.csv`, `SPY_daily.csv`)
- Multi-stock downloads: `stocks_daily.csv`
- Strategy results: `{TICKER}_equity.csv`, `{TICKER}_trades.csv`, `{TICKER}_momentum_12M.csv`
- Multi-panel charts: `{DESCRIPTION}.png`

## .gitignore

Ignores: `__pycache__/`, `*.py[cod]`, `.venv/`, `venv/`, `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db`, `.claude/settings.local.json`
