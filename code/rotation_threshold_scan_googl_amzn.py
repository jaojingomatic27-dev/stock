# -*- coding: utf-8 -*-
"""
Scan drawdown thresholds for GOOGL-AMZN warrant rotation strategy.
Tests 7 thresholds x 2 leverages to find optimal.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load data
googl = pd.read_csv(r"C:\AI\cc\stock\data\GOOGL_daily.csv", header=[0,1], index_col=0, parse_dates=True)
amzn  = pd.read_csv(r"C:\AI\cc\stock\data\AMZN_daily.csv", header=[0,1], index_col=0, parse_dates=True)
googl_close = googl[("Close", "GOOGL")].dropna()
amzn_close  = amzn[("Close", "AMZN")].dropna()

# Align dates
common = googl_close.index.intersection(amzn_close.index)
googl_c = googl_close.loc[common]
amzn_c  = amzn_close.loc[common]
googl_r = googl_c.pct_change().fillna(0).values
amzn_r  = amzn_c.pct_change().fillna(0).values
n = len(common)

INVEST = 1000
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [3, 5]

def run_rotation(lev, threshold):
    """Run rotation strategy for given leverage and drawdown threshold."""
    val = INVEST
    peak = INVEST
    holding = "GOOGL"  # Start with GOOGL
    rotations = 0
    ko = False

    for i in range(1, n):
        r = googl_r[i] if holding == "GOOGL" else amzn_r[i]
        val *= (1 + lev * r)

        if val > peak:
            peak = val

        dd = (val - peak) / peak
        if dd <= -threshold:
            # Rotate to the other warrant
            holding = "AMZN" if holding == "GOOGL" else "GOOGL"
            peak = val  # Reset peak
            rotations += 1

        if val < INVEST * 0.05:
            ko = True
            val = 0.0
            break

    return val, rotations, ko

# Run all combinations
results = {}
for lev in LEVERAGES:
    results[lev] = {}
    for th in THRESHOLDS:
        val, rots, ko = run_rotation(lev, th)
        results[lev][th] = (val, rots, ko)

# Buy & Hold benchmarks
def bh(lev, ticker):
    rets = googl_r if ticker == "GOOGL" else amzn_r
    val = INVEST
    for r in rets:
        val *= (1 + lev * r)
    return val

googl_bh_3x = bh(3, "GOOGL")
amzn_bh_3x  = bh(3, "AMZN")
googl_bh_5x = bh(5, "GOOGL")
amzn_bh_5x  = bh(5, "AMZN")

print("=" * 95)
print("  Drawdown Threshold Scan: GOOGL-AMZN Rotation Strategy")
print(f"  Period: {common[0].strftime('%Y-%m-%d')} ~ {common[-1].strftime('%Y-%m-%d')} ({n} days)")
print("=" * 95)

print(f"\n  Buy & Hold Benchmarks (${INVEST} initial):")
print(f"    GOOGL 3x: ${googl_bh_3x:,.0f}  |  AMZN 3x: ${amzn_bh_3x:,.0f}")
print(f"    GOOGL 5x: ${googl_bh_5x:,.0f}  |  AMZN 5x: ${amzn_bh_5x:,.0f}")

# Main results table
print(f"\n{'=' * 95}")
print(f"  MAIN RESULTS: All Threshold x Leverage Combinations")
print(f"{'=' * 95}")
print(f"  {'Threshold':>10} | {'3x Final $':>14} {'3x Ret%':>10} {'3x Rot':>7} | {'5x Final $':>14} {'5x Ret%':>10} {'5x Rot':>7} | {'Notes':>15}")
print(f"  {'-'*10}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*15}")

best_3x_val, best_3x_th = 0, 0
best_5x_val, best_5x_th = 0, 0

for th in THRESHOLDS:
    v3, r3, ko3 = results[3][th]
    v5, r5, ko5 = results[5][th]
    ret3 = (v3/INVEST - 1) * 100
    ret5 = (v5/INVEST - 1) * 100

    notes = ""
    if ko3: notes += "3x KO! "
    if ko5: notes += "5x KO! "

    marker3 = ""
    if v3 > best_3x_val:
        best_3x_val, best_3x_th = v3, th
        marker3 = " <<"
    marker5 = ""
    if v5 > best_5x_val:
        best_5x_val, best_5x_th = v5, th
        marker5 = " <<"

    print(f"  {th:>8.0%}   | ${v3:>13,.0f} {ret3:>9.1f}% {r3:>6} {marker3} | ${v5:>13,.0f} {ret5:>9.1f}% {r5:>6} {marker5} | {notes:>15}")

# Highlight winners
print(f"\n  >>> 3x BEST: threshold={best_3x_th:.0%} -> ${best_3x_val:,.0f}")
print(f"  >>> 5x BEST: threshold={best_5x_th:.0%} -> ${best_5x_val:,.0f}")

# Comparison with buy-and-hold
print(f"\n{'=' * 95}")
print(f"  Rotation vs Buy & Hold: Excess Return")
print(f"{'=' * 95}")
print(f"  {'Threshold':>10} | {'3x vs BH AMZN':>14} {'3x vs BH GOOGL':>14} | {'5x vs BH AMZN':>14} {'5x vs BH GOOGL':>14}")
print(f"  {'-'*10}-+-{'-'*14} {'-'*14}-+-{'-'*14} {'-'*14}")

for th in THRESHOLDS:
    v3 = results[3][th][0]
    v5 = results[5][th][0]
    e3_amzn = v3 - amzn_bh_3x
    e3_googl = v3 - googl_bh_3x
    e5_amzn = v5 - amzn_bh_5x
    e5_googl = v5 - googl_bh_5x
    print(f"  {th:>8.0%}   | ${e3_amzn:>+13,.0f} ${e3_googl:>+13,.0f} | ${e5_amzn:>+13,.0f} ${e5_googl:>+13,.0f}")

# Rotation count vs return trade-off
print(f"\n{'=' * 95}")
print(f"  Efficiency: Return per Rotation")
print(f"{'=' * 95}")
print(f"  {'Threshold':>10} | {'3x Ret/Rot':>12} | {'5x Ret/Rot':>12} | {'Winner':>10}")
print(f"  {'-'*10}-+-{'-'*12}-+-{'-'*12}-+-{'-'*10}")

for th in THRESHOLDS:
    v3, r3, _ = results[3][th]
    v5, r5, _ = results[5][th]
    ret3 = (v3/INVEST - 1) * 100
    ret5 = (v5/INVEST - 1) * 100
    eff3 = ret3 / max(r3, 1)
    eff5 = ret5 / max(r5, 1)
    winner = "3x" if eff3 > eff5 else "5x"
    print(f"  {th:>8.0%}   | {eff3:>+11.1f}% | {eff5:>+11.1f}% | {winner:>10}")

print("\nDone.")
