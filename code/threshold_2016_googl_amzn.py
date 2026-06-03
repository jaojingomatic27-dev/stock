# -*- coding: utf-8 -*-
"""
Scan 7 drawdown thresholds for GOOGL-AMZN rotation, 2016-2026.
Single leg, $1000 initial, start in GOOGL.
Leverage: 3x, 5x. Knock-out at 5% ($50).
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

# ============================================================
# 1. Load data
# ============================================================
googl = pd.read_csv(r"C:\AI\cc\stock\GOOGL_2016_daily.csv", header=[0,1], index_col=0, parse_dates=True)
amzn  = pd.read_csv(r"C:\AI\cc\stock\AMZN_2016_daily.csv", header=[0,1], index_col=0, parse_dates=True)
googl_close = googl[("Close", "GOOGL")].dropna()
amzn_close  = amzn[("Close", "AMZN")].dropna()

# Align dates
common = googl_close.index.intersection(amzn_close.index)
googl_c = googl_close.loc[common]
amzn_c  = amzn_close.loc[common]
googl_r = googl_c.pct_change().fillna(0).values
amzn_r  = amzn_c.pct_change().fillna(0).values
n = len(common)

INVEST = 1000.0
KO_LEVEL = INVEST * 0.05  # $50
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [3, 5]

years = (common[-1] - common[0]).days / 365.25

# ============================================================
# 2. Rotation simulation (single leg, start in GOOGL)
# ============================================================
def run_rotation(lev, threshold):
    """Single-leg rotation: start GOOGL, rotate on drawdown breach."""
    val = INVEST
    peak = INVEST
    holding = "GOOGL"
    rotations = 0
    ko = False

    for i in range(1, n):
        r = googl_r[i] if holding == "GOOGL" else amzn_r[i]
        val *= (1.0 + lev * r)
        if val < 0:
            val = 0.0

        if val <= KO_LEVEL:
            ko = True
            val = 0.0
            break

        if val > peak:
            peak = val

        dd = (val - peak) / peak
        if dd <= -threshold:
            holding = "AMZN" if holding == "GOOGL" else "GOOGL"
            peak = val
            rotations += 1

    return val, rotations, ko

# ============================================================
# 3. Buy & Hold benchmarks
# ============================================================
def bh(lev, ticker):
    rets = googl_r if ticker == "GOOGL" else amzn_r
    val = INVEST
    ko = False
    for r in rets:
        val *= (1.0 + lev * r)
        if val < 0:
            val = 0.0
        if val <= KO_LEVEL:
            ko = True
            val = 0.0
            break
    return val, ko

googl_bh_3x, googl_ko_3x = bh(3, "GOOGL")
amzn_bh_3x,  amzn_ko_3x  = bh(3, "AMZN")
googl_bh_5x, googl_ko_5x = bh(5, "GOOGL")
amzn_bh_5x,  amzn_ko_5x  = bh(5, "AMZN")

# Actual stock (unlevered) BH for reference
googl_stock_final = INVEST * (googl_c.iloc[-1] / googl_c.iloc[0])
amzn_stock_final  = INVEST * (amzn_c.iloc[-1]  / amzn_c.iloc[0])

# ============================================================
# 4. Run all threshold x leverage combinations
# ============================================================
results = {}
for lev in LEVERAGES:
    results[lev] = {}
    for th in THRESHOLDS:
        val, rots, ko = run_rotation(lev, th)
        results[lev][th] = (val, rots, ko)

# ============================================================
# 5. Print results
# ============================================================
print("=" * 100)
print("  Drawdown Threshold Scan: GOOGL-AMZN Rotation Strategy (2016–2026)")
print(f"  Period: {common[0].strftime('%Y-%m-%d')} ~ {common[-1].strftime('%Y-%m-%d')}  ({years:.2f} years, {n} trading days)")
print(f"  Single leg, ${INVEST:,.0f} initial, starts in GOOGL, knock-out at 5% (${KO_LEVEL:,.0f})")
print("=" * 100)

# --- 10-year BH benchmarks ---
print(f"\n  [1] 10-YEAR BUY & HOLD BENCHMARKS (${INVEST:,.0f} initial)")
print(f"  {'─' * 65}")
print(f"  {'Asset':<10} {'Unlevered':>14} {'3x Final':>14} {'3x Ret%':>10} {'5x Final':>14} {'5x Ret%':>10}")
print(f"  {'─'*10} {'─'*14} {'─'*14} {'─'*10} {'─'*14} {'─'*10}")
print(f"  {'GOOGL':<10} ${googl_stock_final:>13,.0f} ${googl_bh_3x:>13,.0f} {(googl_bh_3x/INVEST-1)*100:>9.1f}% ${googl_bh_5x:>13,.0f} {(googl_bh_5x/INVEST-1)*100:>9.1f}%")
print(f"  {'AMZN':<10} ${amzn_stock_final:>13,.0f} ${amzn_bh_3x:>13,.0f} {(amzn_bh_3x/INVEST-1)*100:>9.1f}% ${amzn_bh_5x:>13,.0f} {(amzn_bh_5x/INVEST-1)*100:>9.1f}%")

if googl_ko_3x: print(f"    ⚠ GOOGL 3x BH knocked out!")
if googl_ko_5x: print(f"    ⚠ GOOGL 5x BH knocked out!")
if amzn_ko_3x:  print(f"    ⚠ AMZN 3x BH knocked out!")
if amzn_ko_5x:  print(f"    ⚠ AMZN 5x BH knocked out!")

# --- Main results table ---
print(f"\n  [2] MAIN RESULTS: All Threshold x Leverage Combinations")
print(f"  {'─' * 100}")
header = f"  {'Threshold':>10} | {'3x Final $':>14} {'3x Ret%':>10} {'3x Rot':>7} | {'5x Final $':>14} {'5x Ret%':>10} {'5x Rot':>7} | {'Notes':>12}"
print(header)
print(f"  {'-'*10}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*14} {'-'*10} {'-'*7}-+-{'-'*12}")

best_3x_val, best_3x_th = -1, 0
best_5x_val, best_5x_th = -1, 0

for th in THRESHOLDS:
    v3, r3, ko3 = results[3][th]
    v5, r5, ko5 = results[5][th]
    ret3 = (v3 / INVEST - 1) * 100
    ret5 = (v5 / INVEST - 1) * 100

    notes = ""
    if ko3: notes += "3x-KO"
    if ko5: notes += " 5x-KO" if ko3 else "5x-KO"

    marker3 = ""
    if v3 > best_3x_val:
        best_3x_val, best_3x_th = v3, th
        marker3 = " <<"
    marker5 = ""
    if v5 > best_5x_val:
        best_5x_val, best_5x_th = v5, th
        marker5 = " <<"

    print(f"  {th:>8.0%}   | ${v3:>13,.0f} {ret3:>9.1f}% {r3:>6} {marker3} | ${v5:>13,.0f} {ret5:>9.1f}% {r5:>6} {marker5} | {notes:>12}")

# --- BEST threshold ---
print(f"\n  [3] BEST THRESHOLD PER LEVERAGE")
print(f"  {'─' * 60}")
print(f"    3x BEST: threshold = {best_3x_th:.0%}  →  ${best_3x_val:,.0f}  ({(best_3x_val/INVEST-1)*100:+.1f}%)")
print(f"    5x BEST: threshold = {best_5x_th:.0%}  →  ${best_5x_val:,.0f}  ({(best_5x_val/INVEST-1)*100:+.1f}%)")

# --- Rotation vs BH comparison ---
print(f"\n  [4] ROTATION vs BUY & HOLD: Excess Return")
print(f"  {'─' * 100}")
print(f"  {'Threshold':>10} | {'3x vs GOOGL':>14} {'3x vs AMZN':>14} {'3x vs Worse':>14} {'3x vs Better':>14} | {'5x vs GOOGL':>14} {'5x vs AMZN':>14} {'5x vs Worse':>14} {'5x vs Better':>14}")
print(f"  {'-'*10}-+-{'-'*14} {'-'*14} {'-'*14} {'-'*14}-+-{'-'*14} {'-'*14} {'-'*14} {'-'*14}")

# Determine worse/better BH stock for each leverage
worse_3x = min(googl_bh_3x, amzn_bh_3x)
better_3x = max(googl_bh_3x, amzn_bh_3x)
worse_5x = min(googl_bh_5x, amzn_bh_5x)
better_5x = max(googl_bh_5x, amzn_bh_5x)

for th in THRESHOLDS:
    v3 = results[3][th][0]
    v5 = results[5][th][0]
    print(f"  {th:>8.0%}   | ${v3-googl_bh_3x:>+13,.0f} ${v3-amzn_bh_3x:>+13,.0f} ${v3-worse_3x:>+13,.0f} ${v3-better_3x:>+13,.0f} | ${v5-googl_bh_5x:>+13,.0f} ${v5-amzn_bh_5x:>+13,.0f} ${v5-worse_5x:>+13,.0f} ${v5-better_5x:>+13,.0f}")

# --- Return per rotation efficiency ---
print(f"\n  [5] RETURN PER ROTATION EFFICIENCY")
print(f"  {'─' * 65}")
print(f"  {'Threshold':>10} | {'3x $/Rot':>12} {'3x Ret%/Rot':>12} | {'5x $/Rot':>12} {'5x Ret%/Rot':>12} | {'Winner':>10}")
print(f"  {'-'*10}-+-{'-'*12} {'-'*12}-+-{'-'*12} {'-'*12}-+-{'-'*10}")

for th in THRESHOLDS:
    v3, r3, _ = results[3][th]
    v5, r5, _ = results[5][th]
    gain3 = v3 - INVEST
    gain5 = v5 - INVEST
    ret3 = (v3 / INVEST - 1) * 100
    ret5 = (v5 / INVEST - 1) * 100
    eff3_dollar = gain3 / max(r3, 1)
    eff5_dollar = gain5 / max(r5, 1)
    eff3_pct = ret3 / max(r3, 1)
    eff5_pct = ret5 / max(r5, 1)
    winner = "3x" if eff3_pct > eff5_pct else "5x"
    print(f"  {th:>8.0%}   | ${eff3_dollar:>11,.0f} {eff3_pct:>+11.1f}% | ${eff5_dollar:>11,.0f} {eff5_pct:>+11.1f}% | {winner:>10}")

print(f"\n{'=' * 100}")
print("  Done.")
