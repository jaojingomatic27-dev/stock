#!/usr/bin/env python3
"""
Optimal Constant Leverage Finder (daily-reset leveraged warrants)
Knock-out threshold: 95% loss (i.e., value drops to <= 5% of initial capital)
Test leverage: 1.0x to 10.0x in 0.5x increments
Period: 2025-06-02 to 2026-06-03
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

START_DATE = "2025-06-02"
END_DATE = "2026-06-03"
KNOCKOUT_THRESHOLD = 0.05  # 95% loss = value at 5% of initial
LEVERAGE_RANGE = np.arange(1.0, 10.01, 0.5)  # 1.0, 1.5, ..., 10.0

EVENTS = {
    "NVDA": {"start_price": 137.35, "end_price": 215.88, "max_day_drop": -5.5, "max_day_gain": 7.9},
    "MU":   {"start_price": 97.95,  "end_price": 1070.04, "max_day_drop": -10.9, "max_day_gain": 19.3},
}


def load_close(csv_path, ticker):
    df = pd.read_csv(csv_path, header=[0, 1], index_col=0, parse_dates=True)
    close = df[("Close", ticker)].dropna()
    close = close.sort_index()
    return close


def simulate_leveraged(close, leverage, initial=1.0):
    """
    Simulate a daily-reset leveraged warrant.
    Returns (final_value, knocked_out, knockout_day).
    Knock-out triggers when value <= 5% of initial (95% loss).
    """
    daily_ret = close.pct_change().dropna()
    value = initial
    for date, ret in daily_ret.items():
        value *= (1.0 + leverage * ret)
        if value <= KNOCKOUT_THRESHOLD * initial:
            return value, True, date
    return value, False, None


def find_best_leverage(close, ticker_name):
    results = []
    for lev in LEVERAGE_RANGE:
        final_val, knocked, ko_day = simulate_leveraged(close, lev)
        mult = final_val  # multiple of initial capital
        results.append({
            "leverage": lev,
            "final_multiple": mult,
            "final_pct": (mult - 1) * 100,
            "knocked_out": knocked,
            "knockout_day": ko_day,
        })

    # Separate survivors and knock-outs
    survivors = [r for r in results if not r["knocked_out"]]
    knocked = [r for r in results if r["knocked_out"]]

    best = max(survivors, key=lambda r: r["final_multiple"]) if survivors else None
    return results, best, survivors, knocked


def main():
    tickers = {
        "NVDA": r"C:\AI\cc\stock\data\NVDA_daily.csv",
        "MU":   r"C:\AI\cc\stock\data\MU_daily.csv",
    }

    for ticker, path in tickers.items():
        print(f"\n{'='*70}")
        print(f"  {ticker}  |  {START_DATE} → {END_DATE}")
        print(f"{'='*70}")

        close_full = load_close(path, ticker)
        close = close_full[(close_full.index >= START_DATE) & (close_full.index <= END_DATE)]

        n_days = len(close)
        actual_ret = (close.iloc[-1] / close.iloc[0] - 1) * 100
        daily_rets = close.pct_change().dropna()
        max_dd_actual = daily_rets.min() * 100
        max_dg_actual = daily_rets.max() * 100

        print(f"  Trading days: {n_days}")
        print(f"  Actual 1x buy & hold return: {actual_ret:.1f}%")
        print(f"  Actual max daily drop: {max_dd_actual:.1f}%")
        print(f"  Actual max daily gain: {max_dg_actual:.1f}%")
        print()

        results, best, survivors, knocked = find_best_leverage(close, ticker)

        # Full table
        header = f"  {'Leverage':>8s}  {'Final x':>10s}  {'Return %':>10s}  {'Status':>12s}"
        print(header)
        print(f"  {'-'*8}  {'-'*10}  {'-'*10}  {'-'*12}")
        for r in results:
            lev_str = f"{r['leverage']:.1f}x"
            mult_str = f"{r['final_multiple']:.4f}"
            pct_str = f"{r['final_pct']:+.1f}%"
            if r["knocked_out"]:
                status = f"KNOCKOUT {r['knockout_day'].strftime('%Y-%m-%d')}"
            else:
                status = "SURVIVED"
            print(f"  {lev_str:>8s}  {mult_str:>10s}  {pct_str:>10s}  {status:>12s}")

        print()

        # Summary
        if best is not None:
            print(f"  >>> OPTIMAL LEVERAGE: {best['leverage']:.1f}x")
            print(f"      Final multiple:  {best['final_multiple']:.4f}x initial capital")
            print(f"      Total return:    {best['final_pct']:+.1f}%")
        else:
            print(f"  >>> ALL LEVERAGE VALUES KNOCKED OUT! No survivor above 1x.")

        # Highest knock-out leverage that survives
        if knocked:
            ko_levs = sorted([r["leverage"] for r in knocked])
            print(f"      First knock-out at: {ko_levs[0]:.1f}x ({knocked[0]['knockout_day'].strftime('%Y-%m-%d')})")
            # Find max leverage before first knock-out
            surv_levs = sorted([r["leverage"] for r in survivors])
            if surv_levs:
                max_surv = max(surv_levs)
                print(f"      Max leverage without knock-out: {max_surv:.1f}x")

        # Check if un-leveraged beats best levered
        unlevered = results[0]  # 1.0x
        if best and unlevered["final_multiple"] > best["final_multiple"]:
            print(f"      NOTE: 1x unlevered ({unlevered['final_pct']:+.1f}%) outperforms optimal levered!")

        # Daily drawdown spectrum at optimal
        if best:
            print(f"\n  Risk metrics at optimal {best['leverage']:.1f}x:")
            daily_ret = close.pct_change().dropna()
            lev_rets = daily_ret * best["leverage"] * 100  # percent
            print(f"      Worst daily move:  {lev_rets.min():+.1f}%")
            print(f"      Best daily move:   {lev_rets.max():+.1f}%")
            print(f"      Daily vol (std):   {lev_rets.std():.1f}%")
            # Max drawdown of levered path
            lev_cum = (1.0 + daily_ret * best["leverage"]).cumprod()
            peak = lev_cum.cummax()
            dd = (lev_cum - peak) / peak * 100
            print(f"      Max drawdown:      {dd.min():.1f}%")


if __name__ == "__main__":
    main()
