# -*- coding: utf-8 -*-
"""
Scan drawdown thresholds for NVDA-MU rotation strategy, 2016-2026.
Tests 7 thresholds x 2 leverages to find optimal.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# ── Load data ──────────────────────────────────────────────────────────────
nvda = pd.read_csv(r"C:\AI\cc\stock\NVDA_2016_daily.csv", header=[0,1], index_col=0, parse_dates=True)
mu   = pd.read_csv(r"C:\AI\cc\stock\MU_2016_daily.csv",   header=[0,1], index_col=0, parse_dates=True)
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

# ── Rotation engine ────────────────────────────────────────────────────────
def run_rotation(lev, threshold):
    """Run single-leg rotation. Start in NVDA, knock-out at 5% ($50)."""
    val = INVEST
    peak = INVEST
    holding = "NVDA"
    rotations = 0
    ko = False

    for i in range(1, n):
        r = nvda_r[i] if holding == "NVDA" else mu_r[i]
        val *= (1 + lev * r)

        if val > peak:
            peak = val

        dd = (val - peak) / peak
        if dd <= -threshold:
            holding = "MU" if holding == "NVDA" else "NVDA"
            peak = val   # reset peak on rotation
            rotations += 1

        if val < INVEST * 0.05:   # knock-out
            ko = True
            val = 0.0
            break

    return val, rotations, ko

# ── Buy & Hold benchmarks (levered) ────────────────────────────────────────
def bh(lev, rets):
    val = INVEST
    for r in rets:
        val *= (1 + lev * r)
    return val

nvda_bh_3x = bh(3, nvda_r)
mu_bh_3x   = bh(3, mu_r)
nvda_bh_5x = bh(5, nvda_r)
mu_bh_5x   = bh(5, mu_r)

years = n / 252
nvda_cagr_3x = ((nvda_bh_3x / INVEST) ** (1/years) - 1) * 100
mu_cagr_3x   = ((mu_bh_3x   / INVEST) ** (1/years) - 1) * 100
nvda_cagr_5x = ((nvda_bh_5x / INVEST) ** (1/years) - 1) * 100
mu_cagr_5x   = ((mu_bh_5x   / INVEST) ** (1/years) - 1) * 100

# Also unlevered BH
nvda_bh_1x = bh(1, nvda_r)
mu_bh_1x   = bh(1, mu_r)
nvda_cagr_1x = ((nvda_bh_1x / INVEST) ** (1/years) - 1) * 100
mu_cagr_1x   = ((mu_bh_1x   / INVEST) ** (1/years) - 1) * 100

# ── Run all combinations ───────────────────────────────────────────────────
results = {}
for lev in LEVERAGES:
    results[lev] = {}
    for th in THRESHOLDS:
        val, rots, ko = run_rotation(lev, th)
        results[lev][th] = (val, rots, ko)

# ═══════════════════════════════════════════════════════════════════════════
#  OUTPUT
# ═══════════════════════════════════════════════════════════════════════════

print("=" * 100)
print("  Drawdown Threshold Scan: NVDA-MU Rotation Strategy (2016-2026)")
print(f"  Period: {common[0].strftime('%Y-%m-%d')} ~ {common[-1].strftime('%Y-%m-%d')}  ({n} trading days, {years:.1f} years)")
print("=" * 100)

# ── 1. 10-year Buy & Hold benchmarks ─────────────────────────────────────
print()
print("  [1] 10-Year Buy & Hold Benchmarks ($1,000 initial, single-leg levered)")
print("  " + "-" * 75)
print(f"  {'':>6} | {'1x (Unlevered)':>20} {'3x Levered':>20} {'5x Levered':>20}")
print(f"  {'':>6} | {'Final $':>10} {'CAGR':>9} | {'Final $':>10} {'CAGR':>9} | {'Final $':>10} {'CAGR':>9}")
print(f"  {'':>6} |{'-'*21}+{'-'*21}+{'-'*21}")
print(f"  {'NVDA':>6} | ${nvda_bh_1x:>9,.0f} {nvda_cagr_1x:>8.1f}% | ${nvda_bh_3x:>9,.0f} {nvda_cagr_3x:>8.1f}% | ${nvda_bh_5x:>9,.0f} {nvda_cagr_5x:>8.1f}%")
print(f"  {'MU':>6}   | ${mu_bh_1x:>9,.0f} {mu_cagr_1x:>8.1f}% | ${mu_bh_3x:>9,.0f} {mu_cagr_3x:>8.1f}% | ${mu_bh_5x:>9,.0f} {mu_cagr_5x:>8.1f}%")
print(f"  {'Worse':>6} | ${min(nvda_bh_1x, mu_bh_1x):>9,.0f}              | ${min(nvda_bh_3x, mu_bh_3x):>9,.0f}              | ${min(nvda_bh_5x, mu_bh_5x):>9,.0f}")
print(f"  {'Better':>6}| ${max(nvda_bh_1x, mu_bh_1x):>9,.0f}              | ${max(nvda_bh_3x, mu_bh_3x):>9,.0f}              | ${max(nvda_bh_5x, mu_bh_5x):>9,.0f}")

# ── 2. Main results table ────────────────────────────────────────────────
print()
print("=" * 100)
print("  [2] MAIN RESULTS: All Threshold x Leverage Combinations")
print("=" * 100)
print(f"  {'Threshold':>10} | {'3x Final $':>14} {'3x Ret%':>10} {'3x Rot':>7} | {'5x Final $':>14} {'5x Ret%':>10} {'5x Rot':>7} | {'Notes':>18}")
print(f"  {'-'*10}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*18}")

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

    marker3 = " << BEST" if v3 > best_3x_val else ""
    if v3 > best_3x_val:
        best_3x_val, best_3x_th = v3, th

    marker5 = " << BEST" if v5 > best_5x_val else ""
    if v5 > best_5x_val:
        best_5x_val, best_5x_th = v5, th

    print(f"  {th:>8.0%}   | ${v3:>13,.0f} {ret3:>9.1f}% {r3:>6} {marker3:<9} | ${v5:>13,.0f} {ret5:>9.1f}% {r5:>6} {marker5:<9} | {notes:>18}")

# ── 3. BEST threshold per leverage ────────────────────────────────────────
print()
print("=" * 100)
print("  [3] BEST Threshold per Leverage")
print("=" * 100)
print(f"  3x BEST: threshold={best_3x_th:.0%}  ->  Final ${best_3x_val:,.0f}  ({(best_3x_val/INVEST - 1)*100:.1f}% return, {results[3][best_3x_th][1]} rotations)")
print(f"  5x BEST: threshold={best_5x_th:.0%}  ->  Final ${best_5x_val:,.0f}  ({(best_5x_val/INVEST - 1)*100:.1f}% return, {results[5][best_5x_th][1]} rotations)")

# ── 4. Rotation vs BH comparison ─────────────────────────────────────────
print()
print("=" * 100)
print("  [4] Rotation vs Buy & Hold: Excess Return")
print("=" * 100)
worse_3x = min(nvda_bh_3x, mu_bh_3x)
better_3x = max(nvda_bh_3x, mu_bh_3x)
worse_5x = min(nvda_bh_5x, mu_bh_5x)
better_5x = max(nvda_bh_5x, mu_bh_5x)
worse_name_3x = "NVDA" if nvda_bh_3x < mu_bh_3x else "MU"
better_name_3x = "NVDA" if nvda_bh_3x > mu_bh_3x else "MU"
worse_name_5x = "NVDA" if nvda_bh_5x < mu_bh_5x else "MU"
better_name_5x = "NVDA" if nvda_bh_5x > mu_bh_5x else "MU"

print(f"  {'Threshold':>10} | {'3x vs Worse('+worse_name_3x+')':>18} {'3x vs Better('+better_name_3x+')':>20} | {'5x vs Worse('+worse_name_5x+')':>18} {'5x vs Better('+better_name_5x+')':>20}")
print(f"  {'-'*10}-+-{'-'*18} {'-'*20}-+-{'-'*18} {'-'*20}")

for th in THRESHOLDS:
    v3 = results[3][th][0]
    v5 = results[5][th][0]
    e3_worse  = v3 - worse_3x
    e3_better = v3 - better_3x
    e5_worse  = v5 - worse_5x
    e5_better = v5 - better_5x
    print(f"  {th:>8.0%}   | ${e3_worse:>+17,.0f} ${e3_better:>+19,.0f} | ${e5_worse:>+17,.0f} ${e5_better:>+19,.0f}")

# ── 5. Return per Rotation efficiency ─────────────────────────────────────
print()
print("=" * 100)
print("  [5] Efficiency: Return per Rotation")
print("=" * 100)
print(f"  {'Threshold':>10} | {'3x Ret%':>10} {'3x Rot':>7} {'Ret/Rot':>10} | {'5x Ret%':>10} {'5x Rot':>7} {'Ret/Rot':>10} | {'Better':>8}")
print(f"  {'-'*10}-+-{'-'*10} {'-'*7} {'-'*10}-+-{'-'*10} {'-'*7} {'-'*10}-+-{'-'*8}")

for th in THRESHOLDS:
    v3, r3, _ = results[3][th]
    v5, r5, _ = results[5][th]
    ret3 = (v3/INVEST - 1) * 100
    ret5 = (v5/INVEST - 1) * 100
    eff3 = ret3 / max(r3, 1)
    eff5 = ret5 / max(r5, 1)
    better = "3x" if eff3 > eff5 else "5x"
    print(f"  {th:>8.0%}   | {ret3:>9.1f}% {r3:>6} {eff3:>9.1f}% | {ret5:>9.1f}% {r5:>6} {eff5:>9.1f}% | {better:>8}")

print()
print("Done.")
