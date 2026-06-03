# -*- coding: utf-8 -*-
"""
Leveraged Warrant Rotation Backtest: NVDA-MU Pair, 2016-2026
=============================================================
- 3x and 5x daily-reset leveraged warrants
- Two independent rotation legs, $1000 each ($2000 total)
- Leg A starts in NVDA, Leg B starts in MU
- Rotation trigger: -30% drawdown from peak → sell, buy the other
- Knock-out: value < 5% of initial ($50 per leg) → game over
- Peak resets on every rotation
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ============================================================
# 1. Load and align data
# ============================================================
nvda_df = pd.read_csv(r"C:\AI\cc\stock\NVDA_2016_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
mu_df   = pd.read_csv(r"C:\AI\cc\stock\MU_2016_daily.csv",   header=[0, 1], index_col=0, parse_dates=True)

nvda_close = nvda_df[("Close", "NVDA")].dropna()
mu_close   = mu_df[("Close", "MU")].dropna()

# Align to common trading days
common_dates = nvda_close.index.intersection(mu_close.index)
nvda_close = nvda_close.loc[common_dates]
mu_close   = mu_close.loc[common_dates]

# Stock-level metrics (no leverage)
nvda_stock_return = (nvda_close.iloc[-1] / nvda_close.iloc[0] - 1) * 100
mu_stock_return   = (mu_close.iloc[-1] / mu_close.iloc[0] - 1) * 100
nvda_stock_cagr = (((nvda_close.iloc[-1] / nvda_close.iloc[0]) ** (1 / ((common_dates[-1] - common_dates[0]).days / 365.25))) - 1) * 100
mu_stock_cagr   = (((mu_close.iloc[-1] / mu_close.iloc[0]) ** (1 / ((common_dates[-1] - common_dates[0]).days / 365.25))) - 1) * 100

# Daily stock returns (first day has no return)
nvda_ret = nvda_close.pct_change().dropna()
mu_ret   = mu_close.pct_change().dropna()

# Re-align after dropping first NaN
common_ret_dates = nvda_ret.index.intersection(mu_ret.index)
nvda_ret = nvda_ret.loc[common_ret_dates]
mu_ret   = mu_ret.loc[common_ret_dates]

start_date = nvda_close.index[0]
end_date   = nvda_close.index[-1]
years = (end_date - start_date).days / 365.25
n_days = len(common_ret_dates)

# ============================================================
# 2. Output Section 1: Date range and stock summary
# ============================================================
print("=" * 80)
print("  LEVERAGED WARRANT ROTATION BACKTEST: NVDA vs MU  (2016-2026)")
print("=" * 80)
print(f"  [SECTION 1] DATE RANGE & STOCK SUMMARY")
print(f"  Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}  ({years:.2f} years, {n_days} trading days)")
print(f"  NVDA: ${nvda_close.iloc[0]:.2f} → ${nvda_close.iloc[-1]:.2f}  |  Return: {nvda_stock_return:+.2f}%  |  CAGR: {nvda_stock_cagr:+.2f}%")
print(f"  MU:   ${mu_close.iloc[0]:.2f} → ${mu_close.iloc[-1]:.2f}  |  Return: {mu_stock_return:+.2f}%  |  CAGR: {mu_stock_cagr:+.2f}%")
print(f"  Worse stock: {'NVDA' if nvda_stock_return < mu_stock_return else 'MU'}  |  Better stock: {'NVDA' if nvda_stock_return >= mu_stock_return else 'MU'}")
print()

# ============================================================
# 3. Core simulation functions
# ============================================================

def simulate_warrant_bh(stock_rets, leverage, initial=1000.0, knock_out_pct=0.05):
    """
    Buy and hold a single leveraged warrant.
    Returns: (final_value, values_array, knocked_out, max_drawdown_pct)
    """
    knock_out_level = initial * knock_out_pct
    values = [initial]
    peak = initial
    max_dd = 0.0
    knocked_out = False

    for ret in stock_rets:
        if knocked_out:
            values.append(0.0)
            continue

        new_val = values[-1] * (1.0 + leverage * ret)
        if new_val < 0.0:
            new_val = 0.0

        if new_val <= knock_out_level:
            values.append(0.0)
            knocked_out = True
        else:
            values.append(new_val)
            if new_val > peak:
                peak = new_val
            dd = (new_val - peak) / peak
            if dd < max_dd:
                max_dd = dd

    return {
        "final": values[-1],
        "values": np.array(values),
        "knocked_out": knocked_out,
        "max_dd_pct": max_dd * 100,
    }


def simulate_rotation_leg(start_ticker, nvda_rets, mu_rets, ret_dates,
                          leverage, initial=1000.0, dd_threshold=0.30,
                          knock_out_pct=0.05):
    """
    Simulate ONE rotation leg that starts in `start_ticker` and rotates
    to the other warrant whenever drawdown from peak exceeds `dd_threshold`.

    Returns dict with results.
    """
    knock_out_level = initial * knock_out_pct  # $50

    current_ticker = start_ticker
    value = initial
    peak = initial
    values = [initial]
    rotations = []
    knocked_out = False
    max_dd = 0.0

    for i, date in enumerate(ret_dates):
        if knocked_out:
            values.append(0.0)
            continue

        # Apply daily return
        ret = nvda_rets.iloc[i] if current_ticker == "NVDA" else mu_rets.iloc[i]
        value = value * (1.0 + leverage * ret)
        if value < 0.0:
            value = 0.0

        # Check knock-out
        if value <= knock_out_level:
            value = 0.0
            knocked_out = True
            values.append(value)
            continue

        # Update peak
        if value > peak:
            peak = value

        # Track max drawdown
        dd = (value - peak) / peak
        if dd < max_dd:
            max_dd = dd

        # Check rotation trigger
        if dd <= -dd_threshold:
            old_ticker = current_ticker
            new_ticker = "MU" if current_ticker == "NVDA" else "NVDA"
            sold_value = value
            rotations.append({
                "date": date,
                "dd_pct": dd * 100,
                "sold_value": sold_value,
                "sold_ticker": old_ticker,
                "bought_ticker": new_ticker,
            })
            # Rotate: keep same dollar value, switch ticker
            current_ticker = new_ticker
            peak = value  # reset peak for new position

        values.append(value)

    return {
        "final": values[-1],
        "final_ticker": current_ticker if not knocked_out else "KNOCKED OUT",
        "values": np.array(values),
        "rotations": rotations,
        "knocked_out": knocked_out,
        "max_dd_pct": max_dd * 100,
    }


def print_rotation_events(label, rotations_a, rotations_b):
    """Print all rotation events in a formatted table."""
    all_rotations = []
    for r in rotations_a:
        all_rotations.append({
            "Leg": "A (NVDA→MU→...)",
            "Date": r["date"],
            "Sold Ticker": r["sold_ticker"],
            "DD%": f"{r['dd_pct']:.1f}%",
            "Sold Value": r["sold_value"],
            "Bought": r["bought_ticker"],
        })
    for r in rotations_b:
        all_rotations.append({
            "Leg": "B (MU→NVDA→...)",
            "Date": r["date"],
            "Sold Ticker": r["sold_ticker"],
            "DD%": f"{r['dd_pct']:.1f}%",
            "Sold Value": r["sold_value"],
            "Bought": r["bought_ticker"],
        })

    if not all_rotations:
        print(f"\n  {label}: NO rotations triggered during the period.")
        return

    all_rotations.sort(key=lambda x: (x["Date"], x["Leg"]))

    print(f"\n  {label}:")
    print(f"  {'Leg':<22s} {'Date':<12s} {'Sold':<6s} {'DD%':>8s} {'Sold Value':>14s} {'Bought':<6s}")
    print(f"  {'-'*22} {'-'*12} {'-'*6} {'-'*8} {'-'*14} {'-'*6}")
    for r in all_rotations:
        print(f"  {r['Leg']:<22s} {r['Date'].strftime('%Y-%m-%d'):<12s} {r['Sold Ticker']:<6s} {r['DD%']:>8s} ${r['Sold Value']:>13,.2f} {r['Bought']:<6s}")


def run_leverage_scenario(leverage, nvda_rets, mu_rets, ret_dates, initial_per_leg=1000.0):
    """
    Run the full scenario for a given leverage multiplier.
    Returns a dict with all results for printing.
    """
    L = leverage
    total_initial = initial_per_leg * 2

    # ----- Rotation strategy (two independent legs) -----
    leg_a = simulate_rotation_leg("NVDA", nvda_rets, mu_rets, ret_dates, L, initial_per_leg)
    leg_b = simulate_rotation_leg("MU",   nvda_rets, mu_rets, ret_dates, L, initial_per_leg)
    combined_values = leg_a["values"] + leg_b["values"]
    rot_final = leg_a["final"] + leg_b["final"]
    rot_total_rotations = len(leg_a["rotations"]) + len(leg_b["rotations"])
    rot_max_dd = _compute_max_dd(combined_values)
    rot_total_return = (rot_final - total_initial) / total_initial * 100
    rot_annual = (((rot_final / total_initial) ** (1 / years)) - 1) * 100 if rot_final > 0 and years > 0 else -100.0

    # ----- Buy-and-hold each warrant ($2000 initial) -----
    bh_nvda = simulate_warrant_bh(nvda_rets, L, initial=total_initial)
    bh_mu   = simulate_warrant_bh(mu_rets,   L, initial=total_initial)

    bh_nvda_return = (bh_nvda["final"] - total_initial) / total_initial * 100
    bh_mu_return   = (bh_mu["final"] - total_initial) / total_initial * 100
    bh_worse_name = "NVDA" if bh_nvda["final"] < bh_mu["final"] else "MU"
    bh_worse_final = min(bh_nvda["final"], bh_mu["final"])
    bh_worse_return = (bh_worse_final - total_initial) / total_initial * 100
    bh_better_name = "NVDA" if bh_nvda["final"] >= bh_mu["final"] else "MU"
    bh_better_final = max(bh_nvda["final"], bh_mu["final"])
    bh_better_return = (bh_better_final - total_initial) / total_initial * 100
    bh_better_annual = (((bh_better_final / total_initial) ** (1 / years)) - 1) * 100 if bh_better_final > 0 and years > 0 else -100.0

    # ----- Per-leg BH ($1000 each) for "worse stock" comparison -----
    bh_nvda_1k = simulate_warrant_bh(nvda_rets, L, initial=initial_per_leg)
    bh_mu_1k   = simulate_warrant_bh(mu_rets,   L, initial=initial_per_leg)

    return {
        "leverage": L,
        "rot_final": rot_final,
        "rot_total_return": rot_total_return,
        "rot_annual": rot_annual,
        "rot_total_rotations": rot_total_rotations,
        "rot_max_dd": rot_max_dd,
        "leg_a": leg_a,
        "leg_b": leg_b,
        "bh_nvda": bh_nvda,
        "bh_mu": bh_mu,
        "bh_nvda_1k": bh_nvda_1k,
        "bh_mu_1k": bh_mu_1k,
        "bh_worse_name": bh_worse_name,
        "bh_worse_final": bh_worse_final,
        "bh_worse_return": bh_worse_return,
        "bh_better_name": bh_better_name,
        "bh_better_final": bh_better_final,
        "bh_better_return": bh_better_return,
        "bh_better_annual": bh_better_annual,
        "total_initial": total_initial,
    }


def _compute_max_dd(values):
    """Compute max drawdown of a values array."""
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd * 100


def print_scenario(results):
    L = results["leverage"]
    T = results["total_initial"]

    print("=" * 80)
    print(f"  [SECTION 2] SCENARIO: {L}x LEVERAGED WARRANTS")
    print("=" * 80)

    # --- Starting state ---
    print(f"\n  Starting State  (Total capital: ${T:,.0f})")
    print(f"      Leg A: ${T//2:,.0f} in NVDA {L}x warrant")
    print(f"      Leg B: ${T//2:,.0f} in MU {L}x warrant")
    print(f"      Rotation trigger: -30% drawdown from peak")
    print(f"      Knock-out level: ${T//2 * 0.05:,.0f} per leg (5% of initial)")

    # --- Rotation events ---
    print(f"\n  Rotation Events")
    print_rotation_events(f"All Rotations ({L}x)", results["leg_a"]["rotations"], results["leg_b"]["rotations"])

    # --- Final state ---
    print(f"\n  Final State  (at {end_date.strftime('%Y-%m-%d')})")
    la = results["leg_a"]
    lb = results["leg_b"]
    print(f"      Leg A (started NVDA): ${la['final']:>12,.2f}  |  final holding: {la['final_ticker']}  |  rotations: {len(la['rotations'])}")
    print(f"      Leg B (started MU):   ${lb['final']:>12,.2f}  |  final holding: {lb['final_ticker']}  |  rotations: {len(lb['rotations'])}")
    print(f"      {'─' * 62}")
    print(f"      COMBINED ROTATION:    ${results['rot_final']:>12,.2f}  |  total rotations: {results['rot_total_rotations']}")

    # --- Performance metrics ---
    print(f"\n  Performance Metrics — Rotation Strategy")
    print(f"      Total Return:      {results['rot_total_return']:+.2f}%")
    print(f"      Annualized Return: {results['rot_annual']:+.2f}%")
    print(f"      Max Drawdown:      {results['rot_max_dd']:.2f}%")
    print(f"      Total Rotations:   {results['rot_total_rotations']}")
    ko_a = la["knocked_out"]
    ko_b = lb["knocked_out"]
    print(f"      Knocked Out:       Leg A: {'YES' if ko_a else 'No'}, Leg B: {'YES' if ko_b else 'No'}")

    # --- Comparison vs buy-and-hold ---
    print(f"\n  Comparison: Rotation vs Buy-and-Hold  (each with ${T:,.0f} initial)")
    print(f"      {'Strategy':<40s} {'Final Value':>14s} {'Total Return':>14s} {'Max DD':>10s} {'Knocked Out':>12s}")
    print(f"      {'─'*40} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    rot_ko = "YES" if (la["knocked_out"] or lb["knocked_out"]) else "No"
    print(f"      {'Rotation (NVDA ↔ MU)':<40s} ${results['rot_final']:>13,.2f} {results['rot_total_return']:>13.2f}% {results['rot_max_dd']:>9.2f}% {rot_ko:>12s}")

    bh_n = results["bh_nvda"]
    bh_m = results["bh_mu"]
    print(f"      {'Buy & Hold NVDA warrant only':<40s} ${bh_n['final']:>13,.2f} {(bh_n['final']-T)/T*100:>13.2f}% {bh_n['max_dd_pct']:>9.2f}% {'YES' if bh_n['knocked_out'] else 'No':>12s}")
    print(f"      {'Buy & Hold MU warrant only':<40s} ${bh_m['final']:>13,.2f} {(bh_m['final']-T)/T*100:>13.2f}% {bh_m['max_dd_pct']:>9.2f}% {'YES' if bh_m['knocked_out'] else 'No':>12s}")

    # --- Verdict: Rotation vs better stock ---
    print(f"\n  Verdict: Rotation vs BETTER stock ({results['bh_better_name']})")
    diff_vs_better = results["rot_final"] - results["bh_better_final"]
    if diff_vs_better > 0:
        print(f"      Rotation BEATS the better single warrant by ${diff_vs_better:+,.2f}")
        print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_better_name']}: ${results['bh_better_final']:,.2f}")
    elif diff_vs_better < 0:
        print(f"      Rotation TRAILS the better single warrant by ${diff_vs_better:+,.2f}")
        print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_better_name']}: ${results['bh_better_final']:,.2f}")
    else:
        print(f"      Rotation TIED with the better single warrant")

    # --- Verdict: Rotation vs worse stock ---
    print(f"\n  Verdict: Rotation vs WORSE stock ({results['bh_worse_name']})")
    diff_vs_worse = results["rot_final"] - results["bh_worse_final"]
    if diff_vs_worse > 0:
        print(f"      Rotation BEATS the worse single warrant by ${diff_vs_worse:+,.2f}  →  ROTATION SAVES YOU")
        print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_worse_name']}: ${results['bh_worse_final']:,.2f}")
    elif diff_vs_worse < 0:
        print(f"      Rotation TRAILS the worse single warrant by ${diff_vs_worse:+,.2f}  →  ROTATION FAILS")
        print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_worse_name']}: ${results['bh_worse_final']:,.2f}")
    else:
        print(f"      Rotation TIED with the worse single warrant")


# ============================================================
# 4. Run for 3x and 5x leverage
# ============================================================
results_3x = run_leverage_scenario(3, nvda_ret, mu_ret, common_ret_dates)
results_5x = run_leverage_scenario(5, nvda_ret, mu_ret, common_ret_dates)

# Print both scenarios
print_scenario(results_3x)
print("\n")
print_scenario(results_5x)


# ============================================================
# 5. Output Section 3: Comparison table
# ============================================================
print("\n")
print("=" * 80)
print("  [SECTION 3] COMPARISON TABLE: Rotation vs BH NVDA vs BH MU")
print("=" * 80)
print(f"  {'Strategy':<35s} {'3x Final':>14s} {'3x Return':>12s} {'5x Final':>14s} {'5x Return':>12s}")
print(f"  {'─'*35} {'─'*14} {'─'*12} {'─'*14} {'─'*12}")
print(f"  {'Rotation (NVDA ↔ MU)':<35s} ${results_3x['rot_final']:>13,.2f} {results_3x['rot_total_return']:>+11.2f}% ${results_5x['rot_final']:>13,.2f} {results_5x['rot_total_return']:>+11.2f}%")
print(f"  {'BH NVDA warrant only':<35s} ${results_3x['bh_nvda']['final']:>13,.2f} {(results_3x['bh_nvda']['final']-2000)/2000*100:>+11.2f}% ${results_5x['bh_nvda']['final']:>13,.2f} {(results_5x['bh_nvda']['final']-2000)/2000*100:>+11.2f}%")
print(f"  {'BH MU warrant only':<35s} ${results_3x['bh_mu']['final']:>13,.2f} {(results_3x['bh_mu']['final']-2000)/2000*100:>+11.2f}% ${results_5x['bh_mu']['final']:>13,.2f} {(results_5x['bh_mu']['final']-2000)/2000*100:>+11.2f}%")
print(f"  {'BH BETTER warrant':<35s} ${results_3x['bh_better_final']:>13,.2f} {results_3x['bh_better_return']:>+11.2f}% ${results_5x['bh_better_final']:>13,.2f} {results_5x['bh_better_return']:>+11.2f}%")
print(f"  {'BH WORSE warrant':<35s} ${results_3x['bh_worse_final']:>13,.2f} {results_3x['bh_worse_return']:>+11.2f}% ${results_5x['bh_worse_final']:>13,.2f} {results_5x['bh_worse_return']:>+11.2f}%")


# ============================================================
# 6. Output Section 4: Head-to-head 3x vs 5x
# ============================================================
print("\n")
print("=" * 80)
print("  [SECTION 4] HEAD-TO-HEAD: 3x vs 5x Rotation")
print("=" * 80)
print(f"  {'Metric':<45s} {'3x Rotation':>18s} {'5x Rotation':>18s}")
print(f"  {'─'*45} {'─'*18} {'─'*18}")
print(f"  {'Initial Capital':<45s} ${results_3x['total_initial']:>17,.0f} ${results_5x['total_initial']:>17,.0f}")
print(f"  {'Final Portfolio Value':<45s} ${results_3x['rot_final']:>17,.2f} ${results_5x['rot_final']:>17,.2f}")
print(f"  {'Total Return':<45s} {results_3x['rot_total_return']:>17.2f}% {results_5x['rot_total_return']:>17.2f}%")
print(f"  {'Annualized Return':<45s} {results_3x['rot_annual']:>17.2f}% {results_5x['rot_annual']:>17.2f}%")
print(f"  {'Max Drawdown':<45s} {results_3x['rot_max_dd']:>17.2f}% {results_5x['rot_max_dd']:>17.2f}%")
print(f"  {'Number of Rotations':<45s} {results_3x['rot_total_rotations']:>18} {results_5x['rot_total_rotations']:>18}")
ko_3x = "YES" if (results_3x['leg_a']['knocked_out'] or results_3x['leg_b']['knocked_out']) else "No"
ko_5x = "YES" if (results_5x['leg_a']['knocked_out'] or results_5x['leg_b']['knocked_out']) else "No"
print(f"  {'Any Leg Knocked Out':<45s} {ko_3x:>18s} {ko_5x:>18s}")

# Rotation vs BH better for each
diff_better_3x = results_3x["rot_final"] - results_3x["bh_better_final"]
diff_better_5x = results_5x["rot_final"] - results_5x["bh_better_final"]
print(f"  {'Rotation vs BH better warrant':<45s} ${diff_better_3x:>17,.2f} ${diff_better_5x:>17,.2f}")

# Rotation vs BH worse for each
diff_worse_3x = results_3x["rot_final"] - results_3x["bh_worse_final"]
diff_worse_5x = results_5x["rot_final"] - results_5x["bh_worse_final"]
print(f"  {'Rotation vs BH worse warrant':<45s} ${diff_worse_3x:>17,.2f} ${diff_worse_5x:>17,.2f}")

# Winner
print(f"\n  {'─'*45} {'─'*18} {'─'*18}")
if results_3x["rot_final"] > results_5x["rot_final"]:
    winner = "3x"
    margin = results_3x['rot_final'] - results_5x['rot_final']
elif results_5x["rot_final"] > results_3x["rot_final"]:
    winner = "5x"
    margin = results_5x['rot_final'] - results_3x['rot_final']
else:
    winner = "TIED"
    margin = 0
if winner == "TIED":
    print(f"  RESULT: 3x and 5x Rotation TIED")
else:
    print(f"  WINNER: {winner} Rotation  (by ${margin:,.2f})")


# ============================================================
# 7. Output Section 5: Legend — Does rotation beat the worse/better stock?
# ============================================================
print("\n")
print("=" * 80)
print("  [SECTION 5] LEGEND: Does Rotation Beat the WORSE Stock? The BETTER Stock?")
print("=" * 80)

# Determine which stock is worse/better
worse_name = "NVDA" if nvda_stock_return < mu_stock_return else "MU"
better_name = "NVDA" if nvda_stock_return >= mu_stock_return else "MU"

print(f"""
  Stock-level returns (unleveraged, 2016-2026):
    NVDA: {nvda_stock_return:+.2f}% total, {nvda_stock_cagr:+.2f}% CAGR
    MU:   {mu_stock_return:+.2f}% total, {mu_stock_cagr:+.2f}% CAGR

  Worse stock: {worse_name}  |  Better stock: {better_name}
""")

# Check 3x results
print(f"  ── 3x Leverage ──")
rot_final_3x = results_3x["rot_final"]
bh_worse_final_3x = results_3x["bh_worse_final"]
bh_better_final_3x = results_3x["bh_better_final"]

if rot_final_3x > bh_worse_final_3x:
    print(f"  Rotation (3x): ${rot_final_3x:,.2f}  >  BH {worse_name}: ${bh_worse_final_3x:,.2f}")
    print(f"    → Rotation BEATS the worse stock ({worse_name}). You are saved from holding the dog.")
else:
    print(f"  Rotation (3x): ${rot_final_3x:,.2f}  <  BH {worse_name}: ${bh_worse_final_3x:,.2f}")
    print(f"    → Rotation LOSES to the worse stock ({worse_name}). Even rotating couldn't save you.")

if rot_final_3x > bh_better_final_3x:
    print(f"  Rotation (3x): ${rot_final_3x:,.2f}  >  BH {better_name}: ${bh_better_final_3x:,.2f}")
    print(f"    → Rotation BEATS the better stock ({better_name}) — extremely rare and impressive!")
else:
    print(f"  Rotation (3x): ${rot_final_3x:,.2f}  <  BH {better_name}: ${bh_better_final_3x:,.2f}")
    print(f"    → Rotation LOSES to the better stock ({better_name}). You'd rather just hold the winner.")

# Check 5x results
print(f"\n  ── 5x Leverage ──")
rot_final_5x = results_5x["rot_final"]
bh_worse_final_5x = results_5x["bh_worse_final"]
bh_better_final_5x = results_5x["bh_better_final"]

if rot_final_5x > bh_worse_final_5x:
    print(f"  Rotation (5x): ${rot_final_5x:,.2f}  >  BH {worse_name}: ${bh_worse_final_5x:,.2f}")
    print(f"    → Rotation BEATS the worse stock ({worse_name}). You are saved from holding the dog.")
else:
    print(f"  Rotation (5x): ${rot_final_5x:,.2f}  <  BH {worse_name}: ${bh_worse_final_5x:,.2f}")
    print(f"    → Rotation LOSES to the worse stock ({worse_name}). Even rotating couldn't save you.")

if rot_final_5x > bh_better_final_5x:
    print(f"  Rotation (5x): ${rot_final_5x:,.2f}  >  BH {better_name}: ${bh_better_final_5x:,.2f}")
    print(f"    → Rotation BEATS the better stock ({better_name}) — extremely rare and impressive!")
else:
    print(f"  Rotation (5x): ${rot_final_5x:,.2f}  <  BH {better_name}: ${bh_better_final_5x:,.2f}")
    print(f"    → Rotation LOSES to the better stock ({better_name}). You'd rather just hold the winner.")

# Summary insight
print(f"""
  ── KEY INSIGHT ──
  Rotation strategies are insurance against picking the wrong stock:
  - If you know which stock will win → DON'T rotate, just buy & hold the winner
  - If you DON'T know → rotation protects you from catastrophic underperformance
  - The strategy converts "I picked the wrong stock" from disaster into survival
  - Leverage amplifies both the upside and the rotation risk
""")

print("=" * 80)
print("  BACKTEST COMPLETE")
print("=" * 80)
print()
