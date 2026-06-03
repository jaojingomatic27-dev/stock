# -*- coding: utf-8 -*-
"""
Scan drawdown thresholds for NVDA-MU warrant rotation strategy.
Tests 7 thresholds x 2 leverages to find optimal.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# Load data
nvda = pd.read_csv(r"C:\AI\cc\stock\data\NVDA_daily.csv", header=[0,1], index_col=0, parse_dates=True)
mu   = pd.read_csv(r"C:\AI\cc\stock\data\MU_daily.csv", header=[0,1], index_col=0, parse_dates=True)
nvda_close = nvda[("Close", "NVDA")].dropna()
mu_close   = mu[("Close", "MU")].dropna()

# Align dates
common = nvda_close.index.intersection(mu_close.index)
nvda_c = nvda_close.loc[common]
mu_c   = mu_close.loc[common]
nvda_r = nvda_c.pct_change().fillna(0).values
mu_r   = mu_c.pct_change().fillna(0).values
n = len(common)

INVEST = 1000
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [3, 5]

def run_rotation(lev, threshold):
    """Run rotation strategy for given leverage and drawdown threshold."""
    val = INVEST
    peak = INVEST
    holding = "NVDA"  # Start with NVDA
    rotations = 0
    ko = False

    for i in range(1, n):
        r = nvda_r[i] if holding == "NVDA" else mu_r[i]
        val *= (1 + lev * r)

        if val > peak:
            peak = val

        dd = (val - peak) / peak
        if dd <= -threshold:
            # Rotate to the other warrant
            holding = "MU" if holding == "NVDA" else "NVDA"
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
    rets = nvda_r if ticker == "NVDA" else mu_r
    val = INVEST
    for r in rets:
        val *= (1 + lev * r)
    return val

nvda_bh_3x = bh(3, "NVDA")
mu_bh_3x   = bh(3, "MU")
nvda_bh_5x = bh(5, "NVDA")
mu_bh_5x   = bh(5, "MU")

print("=" * 95)
print("  Drawdown Threshold Scan: NVDA-MU Rotation Strategy")
print(f"  Period: {common[0].strftime('%Y-%m-%d')} ~ {common[-1].strftime('%Y-%m-%d')} ({n} days)")
print("=" * 95)

print(f"\n  Buy & Hold Benchmarks (${INVEST} initial):")
print(f"    NVDA 3x: ${nvda_bh_3x:,.0f}  |  MU 3x: ${mu_bh_3x:,.0f}")
print(f"    NVDA 5x: ${nvda_bh_5x:,.0f}  |  MU 5x: ${mu_bh_5x:,.0f}")

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
print(f"  {'Threshold':>10} | {'3x vs BH MU':>14} {'3x vs BH NVDA':>14} | {'5x vs BH MU':>14} {'5x vs BH NVDA':>14}")
print(f"  {'-'*10}-+-{'-'*14} {'-'*14}-+-{'-'*14} {'-'*14}")

for th in THRESHOLDS:
    v3 = results[3][th][0]
    v5 = results[5][th][0]
    e3_mu = v3 - mu_bh_3x
    e3_nv = v3 - nvda_bh_3x
    e5_mu = v5 - mu_bh_5x
    e5_nv = v5 - nvda_bh_5x
    print(f"  {th:>8.0%}   | ${e3_mu:>+13,.0f} ${e3_nv:>+13,.0f} | ${e5_mu:>+13,.0f} ${e5_nv:>+13,.0f}")

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
