# -*- coding: utf-8 -*-
"""
Optimal Constant Leverage Finder — 2016–2026 (10-year) vs 1-year
Stocks: NVDA, MU, GOOGL, AMZN
Daily-reset leveraged warrants. Knock-out threshold: 95% loss (value <= 5% of initial).
Test leverage: 1.0x to 10.0x in 0.5x increments.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ── Parameters ────────────────────────────────────────────────────────────────
START_10Y = "2016-01-01"
END_DATE  = "2026-06-03"          # latest common date
START_1Y  = "2025-06-02"

KNOCKOUT_THRESHOLD = 0.05         # 95% loss → value at 5% of initial
INITIAL = 1000.0                  # dollars
LEVERAGE_RANGE = np.arange(1.0, 10.01, 0.5)  # 1.0, 1.5, ..., 10.0

TICKERS = {
    "NVDA":  r"C:\AI\cc\stock\NVDA_2016_daily.csv",
    "MU":    r"C:\AI\cc\stock\MU_2016_daily.csv",
    "GOOGL": r"C:\AI\cc\stock\GOOGL_2016_daily.csv",
    "AMZN":  r"C:\AI\cc\stock\AMZN_2016_daily.csv",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_close(csv_path, ticker):
    """Load close prices from multi-index CSV."""
    df = pd.read_csv(csv_path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()
    close = close.sort_index()
    return close


def simulate_leveraged(close, leverage, initial=INITIAL):
    """
    Simulate a daily-reset leveraged warrant.
    Returns (final_value, knocked_out, knockout_day, drawdown_path).
    Knock-out triggers when value <= 5% of initial.
    """
    daily_ret = close.pct_change().dropna()
    value = initial
    values = [value]

    for date, ret in daily_ret.items():
        value *= (1.0 + leverage * ret)
        values.append(value)
        if value <= KNOCKOUT_THRESHOLD * initial:
            return value, True, date, np.array(values)

    return value, False, None, np.array(values)


def find_best_leverage(close):
    """Test all leverage levels and return structured results."""
    results = []
    for lev in LEVERAGE_RANGE:
        final_val, knocked, ko_day, val_path = simulate_leveraged(close, lev)
        peak = np.maximum.accumulate(val_path)
        dd_pct = (val_path - peak) / peak * 100
        max_dd = dd_pct.min()

        results.append({
            "leverage":       lev,
            "final_value":    final_val,
            "return_pct":     (final_val / INITIAL - 1) * 100,
            "knocked_out":    knocked,
            "knockout_day":   ko_day,
            "max_dd_pct":     max_dd,
        })

    survivors = [r for r in results if not r["knocked_out"]]
    knocked   = [r for r in results if r["knocked_out"]]
    best = max(survivors, key=lambda r: r["final_value"]) if survivors else None
    return results, best, survivors, knocked


def ticker_stats(close):
    """Compute summary stats for a close series."""
    n = len(close)
    daily_ret = close.pct_change().dropna()
    ret_1x = (close.iloc[-1] / close.iloc[0] - 1) * 100
    vol = daily_ret.std() * 100
    max_dd_day = daily_ret.min() * 100   # worst single day
    max_dg_day = daily_ret.max() * 100   # best single day
    sharpe = (daily_ret.mean() / daily_ret.std()) * np.sqrt(252) if daily_ret.std() > 0 else 0
    years = n / 252
    ann_ret = (((close.iloc[-1] / close.iloc[0]) ** (1 / years)) - 1) * 100 if years > 0 else 0
    return {
        "n_days": n,
        "years": years,
        "start_price": close.iloc[0],
        "end_price": close.iloc[-1],
        "ret_1x": ret_1x,
        "ann_ret": ann_ret,
        "vol": vol,
        "max_dd_day": max_dd_day,
        "max_dg_day": max_dg_day,
        "sharpe": sharpe,
    }


# ── Per-ticker output ─────────────────────────────────────────────────────────

def print_ticker_results(ticker, label, close, results, best, survivors, knocked):
    """Pretty-print full results for one ticker + one period."""
    st = ticker_stats(close)

    print(f"\n{'='*90}")
    print(f"  {ticker}  |  {label}  |  Initial: ${INITIAL:,.0f}")
    print(f"{'='*90}")
    print(f"  Period:                 {close.index[0].strftime('%Y-%m-%d')} → {close.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Trading days:           {st['n_days']}")
    print(f"  Years:                  {st['years']:.1f}")
    print(f"  Start price:            ${st['start_price']:.2f}")
    print(f"  End price:              ${st['end_price']:.2f}")
    print(f"  1x Buy & Hold return:   {st['ret_1x']:+.1f}%")
    print(f"  Annualised return:      {st['ann_ret']:+.1f}%")
    print(f"  1x Max daily drop:      {st['max_dd_day']:+.1f}%")
    print(f"  1x Max daily gain:      {st['max_dg_day']:+.1f}%")
    print(f"  1x Daily vol (std):     {st['vol']:.1f}%")
    print(f"  Sharpe ratio:           {st['sharpe']:.2f}")
    print()

    # ── Full leverage table ────────────────────────────────────────────────
    header = (f"  {'Lev':>6s}  {'Final $':>12s}  {'Return':>12s}  "
              f"{'Max DD':>10s}  {'Status':>28s}")
    print(header)
    sep = f"  {'-'*6}  {'-'*12}  {'-'*12}  {'-'*10}  {'-'*28}"
    print(sep)

    for r in results:
        lev_str = f"{r['leverage']:.1f}x"
        val_str = f"${r['final_value']:,.2f}"
        pct_str = f"{r['return_pct']:+.1f}%"
        dd_str  = f"{r['max_dd_pct']:.1f}%"

        if r["knocked_out"]:
            status = f"KNOCKOUT {r['knockout_day'].strftime('%Y-%m-%d')}"
        else:
            status = "SURVIVED"
        print(f"  {lev_str:>6s}  {val_str:>12s}  {pct_str:>12s}  {dd_str:>10s}  {status:>28s}")

    print()

    # ── Summary ───────────────────────────────────────────────────────────
    if best is not None:
        print(f"  >>> OPTIMAL LEVERAGE:  {best['leverage']:.1f}x")
        print(f"      Final value:       ${best['final_value']:,.2f}")
        print(f"      Total return:      {best['return_pct']:+.1f}%")
        print(f"      Max drawdown:      {best['max_dd_pct']:.1f}%")
        # Multiple of 1x
        unlevered_final = INITIAL * (1 + st['ret_1x'] / 100)
        mult_vs_1x = best['final_value'] / unlevered_final
        print(f"      vs 1x Buy&Hold:    {mult_vs_1x:.2f}x (${best['final_value']:,.0f} vs ${unlevered_final:,.0f})")
    else:
        print(f"  >>> ALL LEVERAGE VALUES KNOCKED OUT! No survivor above 1x.")

    if knocked:
        ko_levs = sorted([r["leverage"] for r in knocked])
        first_ko = knocked[0]
        surv_levs = sorted([r["leverage"] for r in survivors])
        print(f"      First knock-out at:          {ko_levs[0]:.1f}x "
              f"({first_ko['knockout_day'].strftime('%Y-%m-%d')})")
        if surv_levs:
            print(f"      Max leverage without KO:     {max(surv_levs):.1f}x")
        # Which survive 10x?
        survives_10x = any(not r["knocked_out"] and r["leverage"] == 10.0 for r in results)
        print(f"      Survives 10x leverage?       {'YES' if survives_10x else 'NO'}")

    # Un-levered vs best levered
    unlevered_out = results[0]
    if best and unlevered_out["final_value"] > best["final_value"]:
        print(f"      NOTE: 1x unlevered (${unlevered_out['final_value']:,.2f}) "
              f"outperforms optimal levered!")

    # ── Risk metrics at optimal ───────────────────────────────────────────
    if best:
        print(f"\n  Risk metrics at optimal {best['leverage']:.1f}x:")
        daily_ret = close.pct_change().dropna()
        lev_rets = daily_ret * best["leverage"] * 100
        print(f"      Worst daily move:   {lev_rets.min():+.1f}%")
        print(f"      Best daily move:    {lev_rets.max():+.1f}%")
        print(f"      Daily vol (std):    {lev_rets.std():.1f}%")
        print(f"      Max drawdown:       {best['max_dd_pct']:.1f}%")


# ── Cross-ticker comparison ───────────────────────────────────────────────────

def print_cross_comparison(all_data):
    """
    all_data: dict of {ticker: { "10Y": (close, best, stats), "1Y": (close, best, stats) }}
    """
    print(f"\n{'='*100}")
    print(f"  CROSS-STOCK COMPARISON:  10-Year vs 1-Year  Optimal Leverage")
    print(f"{'='*100}")
    print()

    # Header
    header = (f"  {'Stock':<8s}  "
              f"{'10Y 1x Ret':>12s}  {'10Y Opt Lev':>12s}  {'10Y Lev Ret':>14s}  "
              f"{'1Y Opt Lev':>11s}  {'1Y Lev Ret':>13s}  "
              f"{'Surv 10x?':>10s}")
    print(header)
    sep = (f"  {'-'*8}  "
           f"{'-'*12}  {'-'*12}  {'-'*14}  "
           f"{'-'*11}  {'-'*13}  "
           f"{'-'*10}")
    print(sep)

    table_rows = []
    for ticker in ["NVDA", "MU", "GOOGL", "AMZN"]:
        d = all_data[ticker]
        st_10y = d["10Y"]["stats"]
        best_10y = d["10Y"]["best"]
        st_1y = d["1Y"]["stats"]
        best_1y = d["1Y"]["best"]

        ret_1x_10y = st_10y["ret_1x"]
        opt_lev_10y = best_10y["leverage"] if best_10y else float("nan")
        lev_ret_10y = best_10y["return_pct"] if best_10y else ret_1x_10y
        opt_lev_1y = best_1y["leverage"] if best_1y else float("nan")
        lev_ret_1y = best_1y["return_pct"] if best_1y else st_1y["ret_1x"]

        survives_10x_10y = any(not r["knocked_out"] and r["leverage"] == 10.0
                               for r in d["10Y"]["results"])

        print(f"  {ticker:<8s}  "
              f"{ret_1x_10y:>+11.1f}%  "
              f"{opt_lev_10y:>10.1f}x  "
              f"{lev_ret_10y:>+13.1f}%  "
              f"{opt_lev_1y:>9.1f}x  "
              f"{lev_ret_1y:>+12.1f}%  "
              f"{'YES':>10s}" if survives_10x_10y else f"{'NO':>10s}")

        table_rows.append({
            "ticker": ticker,
            "ret_1x_10y": ret_1x_10y,
            "opt_lev_10y": opt_lev_10y,
            "lev_ret_10y": lev_ret_10y,
            "opt_lev_1y": opt_lev_1y,
            "lev_ret_1y": lev_ret_1y,
            "survives_10x": survives_10x_10y,
        })

    print()

    # ── Analysis ───────────────────────────────────────────────────────────
    print(f"  ANALYSIS: How does optimal leverage change over longer horizons?")
    print(f"  {'-'*68}")
    print()

    for ticker, d in all_data.items():
        st_10y = d["10Y"]["stats"]
        best_10y = d["10Y"]["best"]
        best_1y = d["1Y"]["best"]
        st_1y = d["1Y"]["stats"]

        lev_10y = best_10y["leverage"] if best_10y else 1.0
        lev_1y = best_1y["leverage"] if best_1y else 1.0

        if best_10y and best_1y:
            change = lev_10y - lev_1y
            direction = "higher" if change > 0 else ("lower" if change < 0 else "unchanged")
            print(f"  {ticker}: 1Y optimal = {lev_1y:.1f}x  →  10Y optimal = {lev_10y:.1f}x  ({direction} by {abs(change):.1f}x)")
        else:
            print(f"  {ticker}: 1Y optimal = {lev_1y:.1f}x  →  10Y optimal = {lev_10y:.1f}x")

        # Key drivers
        print(f"       10Y: 1x return {st_10y['ret_1x']:+.0f}%, Sharpe {st_10y['sharpe']:.2f}, "
              f"max daily drop {st_10y['max_dd_day']:+.1f}%, vol {st_10y['vol']:.1f}%")
        print(f"       1Y:  1x return {st_1y['ret_1x']:+.0f}%, Sharpe {st_1y['sharpe']:.2f}, "
              f"max daily drop {st_1y['max_dd_day']:+.1f}%, vol {st_1y['vol']:.1f}%")
        print()

    print(f"  KEY INSIGHT:")
    print(f"  - Optimal leverage over 10 years tends to be LOWER than over 1 year.")
    print(f"  - Reason: Over longer horizons, extreme tail events are more likely to occur.")
    print(f"    A leverage level that survives 1 year without hitting the knock-out")
    print(f"    threshold may be wiped out by the worst single-day drop over 10 years.")
    print(f"  - The 10-year max daily drop is the binding constraint — if a stock ever")
    print(f"    has a day that drops -X%, then any leverage > (1/|X|)*0.95 risks knock-out.")
    print(f"  - Stocks with smoother uptrends (lower daily vol relative to return)")
    print(f"    can sustain higher leverage over long periods; jumpy stocks cannot.")
    print()

    # ── Which stocks survive 10x over 10 years? ────────────────────────────
    print(f"  WHICH STOCKS SURVIVE 10X LEVERAGE OVER 10 YEARS?")
    print(f"  {'-'*52}")
    survivors_10x = [r for r in table_rows if r["survives_10x"]]
    if survivors_10x:
        for r in survivors_10x:
            res_10x = [row for row in all_data[r["ticker"]]["10Y"]["results"]
                       if row["leverage"] == 10.0][0]
            print(f"  {r['ticker']}: SURVIVES 10x — final ${res_10x['final_value']:,.0f} "
                  f"({res_10x['return_pct']:+.1f}%), max DD {res_10x['max_dd_pct']:.1f}%")
    else:
        print(f"  NONE of the 4 stocks survive 10x leverage over the full 10-year period.")
    print()
    print(f"  Even if a stock survives 10x, the drawdowns are extreme. A 10% daily drop")
    print(f"  becomes a 100% loss at 10x leverage — instant knock-out. Only stocks with")
    print(f"  no single-day drops >9.5% can theoretically survive 10x over any period")
    print(f"  where such drops occur.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_data = {}

    for ticker, csv_path in TICKERS.items():
        print(f"\n{'#'*90}")
        print(f"#  {ticker}")
        print(f"{'#'*90}")

        close_full = load_close(csv_path, ticker)

        # ── 10-Year period ─────────────────────────────────────────────────
        close_10y = close_full[(close_full.index >= START_10Y) & (close_full.index <= END_DATE)]
        results_10y, best_10y, surv_10y, ko_10y = find_best_leverage(close_10y)
        st_10y = ticker_stats(close_10y)

        print_ticker_results(ticker, f"10-Year ({START_10Y} → {END_DATE})",
                             close_10y, results_10y, best_10y, surv_10y, ko_10y)

        # ── 1-Year period ───────────────────────────────────────────────────
        close_1y = close_full[(close_full.index >= START_1Y) & (close_full.index <= END_DATE)]
        results_1y, best_1y, surv_1y, ko_1y = find_best_leverage(close_1y)
        st_1y = ticker_stats(close_1y)

        print_ticker_results(ticker, f"1-Year ({START_1Y} → {END_DATE})",
                             close_1y, results_1y, best_1y, surv_1y, ko_1y)

        all_data[ticker] = {
            "10Y": {"close": close_10y, "results": results_10y, "best": best_10y, "stats": st_10y},
            "1Y":  {"close": close_1y,  "results": results_1y,  "best": best_1y,  "stats": st_1y},
        }

    print_cross_comparison(all_data)

    # ── Final per-ticker summary ────────────────────────────────────────────
    print(f"\n{'='*100}")
    print(f"  FINAL SUMMARY — ALL 4 STOCKS")
    print(f"{'='*100}")

    for ticker in ["NVDA", "MU", "GOOGL", "AMZN"]:
        d = all_data[ticker]
        best_10y = d["10Y"]["best"]
        best_1y = d["1Y"]["best"]
        st_10y = d["10Y"]["stats"]
        st_1y = d["1Y"]["stats"]

        opt_10y = f"{best_10y['leverage']:.1f}x" if best_10y else "N/A"
        ret_10y = f"{best_10y['return_pct']:+,.0f}%" if best_10y else f"{st_10y['ret_1x']:+,.0f}%"
        opt_1y = f"{best_1y['leverage']:.1f}x" if best_1y else "N/A"
        ret_1y = f"{best_1y['return_pct']:+,.0f}%" if best_1y else f"{st_1y['ret_1x']:+,.0f}%"

        survives_10x = any(not r["knocked_out"] and r["leverage"] == 10.0
                           for r in d["10Y"]["results"])

        print(f"  {ticker:<8s}: "
              f"10Y 1x={st_10y['ret_1x']:+,.0f}%  |  "
              f"10Y opt={opt_10y} ret={ret_10y}  |  "
              f"1Y opt={opt_1y} ret={ret_1y}  |  "
              f"10x survives={'YES' if survives_10x else 'NO'}")

    print()
    print(f"  All 10-year periods: {START_10Y} → {END_DATE}")
    print(f"  All 1-year periods:  {START_1Y} → {END_DATE}")


if __name__ == "__main__":
    main()
