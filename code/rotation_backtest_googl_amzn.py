# -*- coding: utf-8 -*-
"""
Leveraged Warrant Rotation Backtest: GOOGL vs AMZN
====================================================
- GOOGL vs AMZN leveraged warrants (3x and 5x)
- Two independent rotation legs, $1000 each ($2000 total initial capital)
- Leg A starts in GOOGL, Leg B starts in AMZN
- Rotation rule: if drawdown from peak exceeds 30%, sell current warrant,
  buy the other warrant with all proceeds
- Knock-out: if warrant value < 5% of initial ($50 per leg), value = 0, game over
- Compare against buy-and-hold each warrant, and buy-and-hold the better one
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ============================================================
# 1. Load and align data
# ============================================================
googl_df = pd.read_csv(r"C:\AI\cc\stock\data\GOOGL_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
amzn_df  = pd.read_csv(r"C:\AI\cc\stock\data\AMZN_daily.csv", header=[0, 1], index_col=0, parse_dates=True)

googl_close = googl_df[("Close", "GOOGL")].dropna()
amzn_close  = amzn_df[("Close", "AMZN")].dropna()

# Align to common trading days
common_dates = googl_close.index.intersection(amzn_close.index)
googl_close = googl_close.loc[common_dates]
amzn_close  = amzn_close.loc[common_dates]

# Daily stock returns (first day has no return)
googl_ret = googl_close.pct_change().dropna()
amzn_ret  = amzn_close.pct_change().dropna()

# Re-align after dropping first NaN
common_ret_dates = googl_ret.index.intersection(amzn_ret.index)
googl_ret = googl_ret.loc[common_ret_dates]
amzn_ret  = amzn_ret.loc[common_ret_dates]

start_date = googl_close.index[0]
end_date   = googl_close.index[-1]
years = (end_date - start_date).days / 365.25
n_days = len(common_ret_dates)

print("=" * 80)
print("  LEVERAGED WARRANT ROTATION BACKTEST: GOOGL vs AMZN")
print("=" * 80)
print(f"  Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}  ({years:.2f} years, {n_days} trading days)")
print(f"  GOOGL start: ${googl_close.iloc[0]:.2f}  →  end: ${googl_close.iloc[-1]:.2f}")
print(f"  AMZN  start: ${amzn_close.iloc[0]:.2f}  →  end: ${amzn_close.iloc[-1]:.2f}")
print()

# ============================================================
# 2. Core simulation functions
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


def simulate_rotation_leg(start_ticker, googl_rets, amzn_rets, ret_dates,
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
        ret = googl_rets.iloc[i] if current_ticker == "GOOGL" else amzn_rets.iloc[i]
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
            new_ticker = "AMZN" if current_ticker == "GOOGL" else "GOOGL"
            sold_value = value
            rotations.append({
                "date": date,
                "reason": f"{old_ticker} DD {dd*100:.1f}%",
                "sold_value": sold_value,
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


def compute_combined_metrics(leg_a_values, leg_b_values, combined_values):
    """Compute max drawdown of combined portfolio."""
    peak = combined_values[0]
    max_dd = 0.0
    for v in combined_values:
        if v > peak:
            peak = v
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    return max_dd * 100


def print_rotation_events(label, rotations_a, rotations_b):
    """Print all rotation events in a formatted table."""
    all_rotations = []
    for r in rotations_a:
        all_rotations.append({
            "Leg": "A (GOOGL→AMZN→...)",
            "Date": r["date"],
            "Reason": r["reason"],
            "Sold Value": r["sold_value"],
            "Bought": r["bought_ticker"],
        })
    for r in rotations_b:
        all_rotations.append({
            "Leg": "B (AMZN→GOOGL→...)",
            "Date": r["date"],
            "Reason": r["reason"],
            "Sold Value": r["sold_value"],
            "Bought": r["bought_ticker"],
        })

    if not all_rotations:
        print(f"\n  {label}: NO rotations triggered during the period.")
        return

    # Sort by date then leg
    all_rotations.sort(key=lambda x: (x["Date"], x["Leg"]))

    print(f"\n  {label}:")
    print(f"  {'Leg':<20s} {'Date':<12s} {'Reason':<20s} {'Sold Value':>14s} {'Bought':<6s}")
    print(f"  {'-'*20} {'-'*12} {'-'*20} {'-'*14} {'-'*6}")
    for r in all_rotations:
        print(f"  {r['Leg']:<20s} {r['Date'].strftime('%Y-%m-%d'):<12s} {r['Reason']:<20s} ${r['Sold Value']:>13,.2f} {r['Bought']:<6s}")


def run_leverage_scenario(leverage, googl_rets, amzn_rets, ret_dates, initial_per_leg=1000.0):
    """
    Run the full scenario for a given leverage multiplier.
    Returns a dict with all results for printing.
    """
    L = leverage
    total_initial = initial_per_leg * 2

    # ----- Rotation strategy (two independent legs) -----
    leg_a = simulate_rotation_leg("GOOGL", googl_rets, amzn_rets, ret_dates, L, initial_per_leg)
    leg_b = simulate_rotation_leg("AMZN",  googl_rets, amzn_rets, ret_dates, L, initial_per_leg)
    combined_values = leg_a["values"] + leg_b["values"]
    rot_final = leg_a["final"] + leg_b["final"]
    rot_total_rotations = len(leg_a["rotations"]) + len(leg_b["rotations"])
    rot_max_dd = compute_combined_metrics(leg_a["values"], leg_b["values"], combined_values)
    rot_total_return = (rot_final - total_initial) / total_initial * 100
    rot_annual = (((rot_final / total_initial) ** (1 / years)) - 1) * 100 if rot_final > 0 and years > 0 else -100.0

    # ----- Buy-and-hold each warrant ($2000 initial) -----
    bh_googl = simulate_warrant_bh(googl_rets, L, initial=total_initial)
    bh_amzn  = simulate_warrant_bh(amzn_rets,  L, initial=total_initial)

    bh_googl_return = (bh_googl["final"] - total_initial) / total_initial * 100
    bh_amzn_return  = (bh_amzn["final"] - total_initial) / total_initial * 100
    bh_better_name = "GOOGL" if bh_googl["final"] >= bh_amzn["final"] else "AMZN"
    bh_better_final = max(bh_googl["final"], bh_amzn["final"])
    bh_better_return = (bh_better_final - total_initial) / total_initial * 100
    bh_better_annual = (((bh_better_final / total_initial) ** (1 / years)) - 1) * 100 if bh_better_final > 0 and years > 0 else -100.0

    return {
        "leverage": L,
        "rot_final": rot_final,
        "rot_total_return": rot_total_return,
        "rot_annual": rot_annual,
        "rot_total_rotations": rot_total_rotations,
        "rot_max_dd": rot_max_dd,
        "leg_a": leg_a,
        "leg_b": leg_b,
        "bh_googl": bh_googl,
        "bh_amzn": bh_amzn,
        "bh_better_name": bh_better_name,
        "bh_better_final": bh_better_final,
        "bh_better_return": bh_better_return,
        "bh_better_annual": bh_better_annual,
        "total_initial": total_initial,
    }


# ============================================================
# 3. Run for 3x and 5x leverage
# ============================================================
results_3x = run_leverage_scenario(3, googl_ret, amzn_ret, common_ret_dates)
results_5x = run_leverage_scenario(5, googl_ret, amzn_ret, common_ret_dates)


# ============================================================
# 4. Print results
# ============================================================

def print_scenario(results):
    L = results["leverage"]
    T = results["total_initial"]

    print("=" * 80)
    print(f"  SCENARIO: {L}x LEVERAGED WARRANTS")
    print("=" * 80)

    # --- Starting state ---
    print(f"\n  [1] STARTING STATE  (Total capital: ${T:,.0f})")
    print(f"      Leg A: ${T//2:,.0f} in GOOGL {L}x warrant")
    print(f"      Leg B: ${T//2:,.0f} in AMZN {L}x warrant")
    print(f"      Rotation trigger: -30% drawdown from peak")
    print(f"      Knock-out level: ${T//2 * 0.05:,.0f} per leg (5% of initial)")

    # --- Rotation events ---
    print(f"\n  [2] ROTATION EVENTS")
    print_rotation_events(f"All Rotations ({L}x)", results["leg_a"]["rotations"], results["leg_b"]["rotations"])

    # --- Final state ---
    print(f"\n  [3] FINAL STATE  (at {end_date.strftime('%Y-%m-%d')})")
    la = results["leg_a"]
    lb = results["leg_b"]
    print(f"      Leg A (started GOOGL): ${la['final']:>12,.2f}  |  final holding: {la['final_ticker']}  |  rotations: {len(la['rotations'])}")
    print(f"      Leg B (started AMZN):  ${lb['final']:>12,.2f}  |  final holding: {lb['final_ticker']}  |  rotations: {len(lb['rotations'])}")
    print(f"      {'─' * 60}")
    print(f"      COMBINED ROTATION:    ${results['rot_final']:>12,.2f}  |  rotations: {results['rot_total_rotations']}")

    # --- Performance metrics ---
    print(f"\n  [4] PERFORMANCE METRICS — Rotation Strategy")
    print(f"      Total Return:      {results['rot_total_return']:+.2f}%")
    print(f"      Annualized Return: {results['rot_annual']:+.2f}%")
    print(f"      Max Drawdown:      {results['rot_max_dd']:.2f}%")
    print(f"      Total Rotations:   {results['rot_total_rotations']}")

    # --- Comparison vs buy-and-hold ---
    print(f"\n  [5] COMPARISON: Rotation vs Buy-and-Hold  (each with ${T:,.0f} initial)")
    print(f"      {'Strategy':<35s} {'Final Value':>14s} {'Total Return':>14s} {'Max DD':>10s} {'Knocked Out':>12s}")
    print(f"      {'─'*35} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    rot_ko = "YES" if (la["knocked_out"] or lb["knocked_out"]) else "No"
    print(f"      {'Rotation (GOOGL ↔ AMZN)':<35s} ${results['rot_final']:>13,.2f} {results['rot_total_return']:>13.2f}% {results['rot_max_dd']:>9.2f}% {rot_ko:>12s}")

    bh_g = results["bh_googl"]
    bh_a = results["bh_amzn"]
    print(f"      {'Buy & Hold GOOGL warrant only':<35s} ${bh_g['final']:>13,.2f} {(bh_g['final']-T)/T*100:>13.2f}% {bh_g['max_dd_pct']:>9.2f}% {'YES' if bh_g['knocked_out'] else 'No':>12s}")
    print(f"      {'Buy & Hold AMZN warrant only':<35s} ${bh_a['final']:>13,.2f} {(bh_a['final']-T)/T*100:>13.2f}% {bh_a['max_dd_pct']:>9.2f}% {'YES' if bh_a['knocked_out'] else 'No':>12s}")

    # Better single-warrant BH
    bh_better_label = f"Buy & Hold {results['bh_better_name']} warrant (better)"
    print(f"      {'─'*35} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    print(f"      {bh_better_label:<35s} ${results['bh_better_final']:>13,.2f} {results['bh_better_return']:>13.2f}%")

    # Did rotation help?
    diff_vs_better = results["rot_final"] - results["bh_better_final"]
    if diff_vs_better > 0:
        verdict = f"Rotation BEATS the better single warrant by ${diff_vs_better:+,.2f}"
    elif diff_vs_better < 0:
        verdict = f"Rotation TRAILS the better single warrant by ${diff_vs_better:+,.2f}"
    else:
        verdict = "Rotation TIED with the better single warrant"

    print(f"\n  >>> VERDICT: {verdict}")
    print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_better_name']} warrant: ${results['bh_better_final']:,.2f}")


# Print both scenarios
print_scenario(results_3x)
print("\n")
print_scenario(results_5x)


# ============================================================
# 5. Head-to-head summary
# ============================================================
print("\n")
print("=" * 80)
print("  HEAD-TO-HEAD SUMMARY: 3x vs 5x Rotation (GOOGL ↔ AMZN)")
print("=" * 80)
print(f"  {'Metric':<40s} {'3x Rotation':>18s} {'5x Rotation':>18s}")
print(f"  {'─'*40} {'─'*18} {'─'*18}")
print(f"  {'Initial Capital':<40s} ${results_3x['total_initial']:>17,.0f} ${results_5x['total_initial']:>17,.0f}")
print(f"  {'Final Portfolio Value':<40s} ${results_3x['rot_final']:>17,.2f} ${results_5x['rot_final']:>17,.2f}")
print(f"  {'Total Return':<40s} {results_3x['rot_total_return']:>17.2f}% {results_5x['rot_total_return']:>17.2f}%")
print(f"  {'Annualized Return':<40s} {results_3x['rot_annual']:>17.2f}% {results_5x['rot_annual']:>17.2f}%")
print(f"  {'Max Drawdown':<40s} {results_3x['rot_max_dd']:>17.2f}% {results_5x['rot_max_dd']:>17.2f}%")
print(f"  {'Number of Rotations':<40s} {results_3x['rot_total_rotations']:>18} {results_5x['rot_total_rotations']:>18}")
print(f"  {'Knocked Out':<40s} {'YES' if (results_3x['leg_a']['knocked_out'] or results_3x['leg_b']['knocked_out']) else 'No':>18s} {'YES' if (results_5x['leg_a']['knocked_out'] or results_5x['leg_b']['knocked_out']) else 'No':>18s}")

# Compare rotation vs BH better for each
print(f"\n  {'Rotation vs BH better warrant':<40s}", end="")
diff_3x = results_3x["rot_final"] - results_3x["bh_better_final"]
diff_5x = results_5x["rot_final"] - results_5x["bh_better_final"]
print(f" ${diff_3x:>17,.2f} ${diff_5x:>17,.2f}")

# Which strategy wins?
print(f"\n  {'─'*40} {'─'*18} {'─'*18}")
if results_3x["rot_final"] > results_5x["rot_final"]:
    print(f"  WINNER: 3x Rotation  (by ${results_3x['rot_final'] - results_5x['rot_final']:,.2f})")
elif results_5x["rot_final"] > results_3x["rot_final"]:
    print(f"  WINNER: 5x Rotation  (by ${results_5x['rot_final'] - results_3x['rot_final']:,.2f})")
else:
    print(f"  RESULT: 3x and 5x Rotation TIED")

print("=" * 80)

# ============================================================
# 6. Detailed day-by-day stats
# ============================================================
print(f"\n\n  DAILY PRICE CHANGES SUMMARY")
print(f"  {'─'*60}")
print(f"  GOOGL: mean daily return = {googl_ret.mean()*100:.3f}%  |  std = {googl_ret.std()*100:.3f}%")
print(f"  AMZN:  mean daily return = {amzn_ret.mean()*100:.3f}%  |  std = {amzn_ret.std()*100:.3f}%")
print(f"  GOOGL: total return = {(googl_close.iloc[-1]/googl_close.iloc[0] - 1)*100:.2f}%")
print(f"  AMZN:  total return = {(amzn_close.iloc[-1]/amzn_close.iloc[0] - 1)*100:.2f}%")

# Worst single-day drops (relevant for leveraged knock-out)
googl_worst = googl_ret.min()
amzn_worst = amzn_ret.min()
print(f"\n  WORST SINGLE-DAY DROPS:")
print(f"  GOOGL: {googl_worst*100:.2f}%  →  3x warrant = {googl_worst*3*100:.2f}%  |  5x warrant = {googl_worst*5*100:.2f}%")
print(f"  AMZN:  {amzn_worst*100:.2f}%  →  3x warrant = {amzn_worst*3*100:.2f}%  |  5x warrant = {amzn_worst*5*100:.2f}%")
if googl_worst * 5 < -1.0:
    print(f"  ⚠ GOOGL worst day would wipe out a 5x warrant (daily drop > 20%)")
if amzn_worst * 5 < -1.0:
    print(f"  ⚠ AMZN worst day would wipe out a 5x warrant (daily drop > 20%)")

print()
