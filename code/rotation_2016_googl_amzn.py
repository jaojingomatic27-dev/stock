# -*- coding: utf-8 -*-
"""
Rotation Backtest: GOOGL vs AMZN Pair (2016-2026)
===================================================
- Two legs, each $1000 ($2000 total). Leg A starts GOOGL, Leg B starts AMZN
- 3x and 5x daily-reset leveraged warrants
- Rotation trigger: -30% drawdown from peak -> sell, buy the other
- Knock-out: value < 5% of initial ($50)
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
googl_df = pd.read_csv(r"C:\AI\cc\stock\GOOGL_2016_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
amzn_df  = pd.read_csv(r"C:\AI\cc\stock\AMZN_2016_daily.csv", header=[0, 1], index_col=0, parse_dates=True)

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

# Underlying stock total returns
googl_total_ret = (googl_close.iloc[-1] / googl_close.iloc[0] - 1) * 100
amzn_total_ret  = (amzn_close.iloc[-1] / amzn_close.iloc[0] - 1) * 100
googl_annual_ret = (((googl_close.iloc[-1] / googl_close.iloc[0]) ** (1 / years)) - 1) * 100
amzn_annual_ret  = (((amzn_close.iloc[-1] / amzn_close.iloc[0]) ** (1 / years)) - 1) * 100

# Identify worse/better stock (by total return)
worse_stock = "GOOGL" if googl_total_ret < amzn_total_ret else "AMZN"
better_stock = "AMZN" if googl_total_ret < amzn_total_ret else "GOOGL"
worse_ret = googl_total_ret if worse_stock == "GOOGL" else amzn_total_ret
better_ret = amzn_total_ret if better_stock == "AMZN" else googl_total_ret

print("=" * 80)
print("  LEVERAGED WARRANT ROTATION BACKTEST: GOOGL vs AMZN (2016-2026)")
print("=" * 80)
print()
print("  [1] DATE RANGE AND STOCK SUMMARY")
print("  " + "-" * 70)
print(f"  Period: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
print(f"  Duration: {years:.2f} years  |  {n_days:,} common trading days")
print(f"  GOOGL:  ${googl_close.iloc[0]:.2f} -> ${googl_close.iloc[-1]:.2f}")
print(f"          10-year Total Return: {googl_total_ret:+.2f}%  |  Annualized: {googl_annual_ret:+.2f}%")
print(f"  AMZN:   ${amzn_close.iloc[0]:.2f} -> ${amzn_close.iloc[-1]:.2f}")
print(f"          10-year Total Return: {amzn_total_ret:+.2f}%  |  Annualized: {amzn_annual_ret:+.2f}%")
print(f"  Worse  underlying: {worse_stock} ({worse_ret:+.2f}%)")
print(f"  Better underlying: {better_stock} ({better_ret:+.2f}%)")
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
            "Leg": "A (GOOGL->AMZN...)",
            "Date": r["date"],
            "Reason": r["reason"],
            "Sold Value": r["sold_value"],
            "Bought": r["bought_ticker"],
        })
    for r in rotations_b:
        all_rotations.append({
            "Leg": "B (AMZN->GOOGL...)",
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
    print(f"  {'Leg':<22s} {'Date':<12s} {'Trigger (DD%)':<20s} {'Sold Value':>14s} {'Bought':<6s}")
    print(f"  {'-'*22} {'-'*12} {'-'*20} {'-'*14} {'-'*6}")
    for r in all_rotations:
        print(f"  {r['Leg']:<22s} {r['Date'].strftime('%Y-%m-%d'):<12s} {r['Reason']:<20s} ${r['Sold Value']:>13,.2f} {r['Bought']:<6s}")


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
    bh_worse_name = "AMZN" if bh_better_name == "GOOGL" else "GOOGL"
    bh_worse_final = min(bh_googl["final"], bh_amzn["final"])
    bh_worse_return = (bh_worse_final - total_initial) / total_initial * 100

    # ----- Buy-and-hold underlying STOCKS (no leverage, $2000 initial) -----
    stock_bh_googl_final = total_initial * (googl_close.iloc[-1] / googl_close.iloc[0])
    stock_bh_amzn_final  = total_initial * (amzn_close.iloc[-1] / amzn_close.iloc[0])
    stock_bh_googl_return = (stock_bh_googl_final - total_initial) / total_initial * 100
    stock_bh_amzn_return  = (stock_bh_amzn_final - total_initial) / total_initial * 100
    stock_worse_final = stock_bh_googl_final if googl_total_ret < amzn_total_ret else stock_bh_amzn_final
    stock_better_final = stock_bh_amzn_final if googl_total_ret < amzn_total_ret else stock_bh_googl_final
    stock_worse_return = googl_total_ret if googl_total_ret < amzn_total_ret else amzn_total_ret
    stock_better_return = amzn_total_ret if googl_total_ret < amzn_total_ret else googl_total_ret

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
        "bh_worse_name": bh_worse_name,
        "bh_worse_final": bh_worse_final,
        "bh_worse_return": bh_worse_return,
        "stock_bh_googl_final": stock_bh_googl_final,
        "stock_bh_amzn_final": stock_bh_amzn_final,
        "stock_bh_googl_return": stock_bh_googl_return,
        "stock_bh_amzn_return": stock_bh_amzn_return,
        "stock_worse_final": stock_worse_final,
        "stock_better_final": stock_better_final,
        "stock_worse_return": stock_worse_return,
        "stock_better_return": stock_better_return,
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
    print(f"\n  [2a] STARTING STATE  (Total capital: ${T:,.0f})")
    print(f"      Leg A: ${T//2:,.0f} in GOOGL {L}x warrant")
    print(f"      Leg B: ${T//2:,.0f} in AMZN {L}x warrant")
    print(f"      Rotation trigger: -30% drawdown from peak")
    print(f"      Knock-out level: ${T//2 * 0.05:,.0f} per leg (5% of initial)")
    print(f"      Peak resets on every rotation")

    # --- Rotation events ---
    print(f"\n  [2b] ROTATION EVENTS")
    print_rotation_events(f"All Rotations ({L}x)", results["leg_a"]["rotations"], results["leg_b"]["rotations"])

    # --- Final state ---
    print(f"\n  [2c] FINAL STATE  (at {end_date.strftime('%Y-%m-%d')})")
    la = results["leg_a"]
    lb = results["leg_b"]
    print(f"      Leg A (started GOOGL): ${la['final']:>12,.2f}  |  final holding: {la['final_ticker']}  |  rotations: {len(la['rotations'])}")
    print(f"      Leg B (started AMZN):  ${lb['final']:>12,.2f}  |  final holding: {lb['final_ticker']}  |  rotations: {len(lb['rotations'])}")
    print(f"      {'─' * 65}")
    print(f"      COMBINED ROTATION:    ${results['rot_final']:>12,.2f}  |  total rotations: {results['rot_total_rotations']}")

    # --- Performance metrics ---
    print(f"\n  [2d] PERFORMANCE METRICS — Rotation Strategy")
    print(f"      Total Return:      {results['rot_total_return']:+.2f}%")
    print(f"      Annualized Return: {results['rot_annual']:+.2f}%")
    print(f"      Max Drawdown:      {results['rot_max_dd']:.2f}%")
    print(f"      Total Rotations:   {results['rot_total_rotations']}")

    # --- Comparison: Rotation vs BH Warrant GOOGL vs BH Warrant AMZN ---
    print(f"\n  [3] COMPARISON TABLE: Rotation vs BH {L}x GOOGL vs BH {L}x AMZN")
    print(f"      (each with ${T:,.0f} initial capital)")
    print(f"      {'Strategy':<35s} {'Final Value':>14s} {'Total Return':>14s} {'Max DD':>10s} {'Knocked Out':>12s}")
    print(f"      {'─'*35} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    rot_ko = "YES" if (la["knocked_out"] or lb["knocked_out"]) else "No"
    print(f"      {'Rotation (GOOGL <-> AMZN)':<35s} ${results['rot_final']:>13,.2f} {results['rot_total_return']:>13.2f}% {results['rot_max_dd']:>9.2f}% {rot_ko:>12s}")

    bh_g = results["bh_googl"]
    bh_a = results["bh_amzn"]
    print(f"      {'Buy & Hold GOOGL warrant only':<35s} ${bh_g['final']:>13,.2f} {(bh_g['final']-T)/T*100:>13.2f}% {bh_g['max_dd_pct']:>9.2f}% {'YES' if bh_g['knocked_out'] else 'No':>12s}")
    print(f"      {'Buy & Hold AMZN warrant only':<35s} ${bh_a['final']:>13,.2f} {(bh_a['final']-T)/T*100:>13.2f}% {bh_a['max_dd_pct']:>9.2f}% {'YES' if bh_a['knocked_out'] else 'No':>12s}")
    print(f"      {'─'*35} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    print(f"      {'BH underlying GOOGL (no lev)':<35s} ${results['stock_bh_googl_final']:>13,.2f} {results['stock_bh_googl_return']:>13.2f}%")
    print(f"      {'BH underlying AMZN (no lev)':<35s} ${results['stock_bh_amzn_final']:>13,.2f} {results['stock_bh_amzn_return']:>13.2f}%")

    # Did rotation beat BH warrant?
    bh_better_label = f"BH {results['bh_better_name']} warrant (better)"
    print(f"      {'─'*35} {'─'*14} {'─'*14} {'─'*10} {'─'*12}")
    print(f"      {bh_better_label:<35s} ${results['bh_better_final']:>13,.2f} {results['bh_better_return']:>13.2f}%")

    diff_vs_better = results["rot_final"] - results["bh_better_final"]
    if diff_vs_better > 0:
        verdict = f"Rotation BEATS the better {L}x warrant by ${diff_vs_better:+,.2f}"
    elif diff_vs_better < 0:
        verdict = f"Rotation TRAILS the better {L}x warrant by ${diff_vs_better:+,.2f}"
    else:
        verdict = f"Rotation TIED with the better {L}x warrant"

    print(f"\n  >>> Rotation vs Better {L}x Warrant: {verdict}")
    print(f"      Rotation: ${results['rot_final']:,.2f}  vs  BH {results['bh_better_name']} {L}x: ${results['bh_better_final']:,.2f}")

    # --- Return comparison dict for head-to-head and vs worse/better ---
    return results


# Print both scenarios
res3 = print_scenario(results_3x)
print("\n")
res5 = print_scenario(results_5x)


# ============================================================
# 5. Head-to-head: 3x vs 5x
# ============================================================
print("\n")
print("=" * 80)
print("  [4] HEAD-TO-HEAD: 3x vs 5x Rotation (GOOGL <-> AMZN)")
print("=" * 80)
print(f"  {'Metric':<40s} {'3x Rotation':>18s} {'5x Rotation':>18s}")
print(f"  {'─'*40} {'─'*18} {'─'*18}")
print(f"  {'Initial Capital':<40s} ${res3['total_initial']:>17,.0f} ${res5['total_initial']:>17,.0f}")
print(f"  {'Final Portfolio Value':<40s} ${res3['rot_final']:>17,.2f} ${res5['rot_final']:>17,.2f}")
print(f"  {'Total Return':<40s} {res3['rot_total_return']:>17.2f}% {res5['rot_total_return']:>17.2f}%")
print(f"  {'Annualized Return':<40s} {res3['rot_annual']:>17.2f}% {res5['rot_annual']:>17.2f}%")
print(f"  {'Max Drawdown':<40s} {res3['rot_max_dd']:>17.2f}% {res5['rot_max_dd']:>17.2f}%")
print(f"  {'Number of Rotations':<40s} {res3['rot_total_rotations']:>18} {res5['rot_total_rotations']:>18}")
ko3 = "YES" if (res3['leg_a']['knocked_out'] or res3['leg_b']['knocked_out']) else "No"
ko5 = "YES" if (res5['leg_a']['knocked_out'] or res5['leg_b']['knocked_out']) else "No"
print(f"  {'Knocked Out':<40s} {ko3:>18s} {ko5:>18s}")

# Rotation vs BH better warrant
print(f"\n  {'Rotation vs BH better warrant':<40s}", end="")
diff3 = res3["rot_final"] - res3["bh_better_final"]
diff5 = res5["rot_final"] - res5["bh_better_final"]
print(f" ${diff3:>17,.2f} ${diff5:>17,.2f}")

# Rotation vs BH worse warrant
print(f"  {'Rotation vs BH worse warrant':<40s}", end="")
diff3w = res3["rot_final"] - res3["bh_worse_final"]
diff5w = res5["rot_final"] - res5["bh_worse_final"]
print(f" ${diff3w:>17,.2f} ${diff5w:>17,.2f}")

# Which strategy wins?
print(f"\n  {'─'*40} {'─'*18} {'─'*18}")
if res3["rot_final"] > res5["rot_final"]:
    print(f"  WINNER: 3x Rotation  (by ${res3['rot_final'] - res5['rot_final']:,.2f})")
elif res5["rot_final"] > res3["rot_final"]:
    print(f"  WINNER: 5x Rotation  (by ${res5['rot_final'] - res3['rot_final']:,.2f})")
else:
    print(f"  RESULT: 3x and 5x Rotation TIED")


# ============================================================
# 6. Does Rotation beat the WORSE stock? The BETTER stock?
# ============================================================
print("\n")
print("=" * 80)
print("  [5] DOES ROTATION BEAT THE WORSE STOCK? THE BETTER STOCK?")
print("=" * 80)

print(f"""
  Reminder — Underlying stock performance (2016-2026):
    GOOGL: {googl_total_ret:+.2f}% total  ({googl_annual_ret:+.2f}% annualized)
    AMZN:  {amzn_total_ret:+.2f}% total  ({amzn_annual_ret:+.2f}% annualized)
    WORSE  stock: {worse_stock}  ({worse_ret:+.2f}%)
    BETTER stock: {better_stock}  ({better_ret:+.2f}%)
""")

print(f"  {'Scenario':<35s} {'3x Rotation':>16s} {'5x Rotation':>16s}")
print(f"  {'─'*35} {'─'*16} {'─'*16}")

# --- vs WORSE underlying stock (no leverage) ---
print(f"\n  --- vs WORSE underlying stock (BH ${res3['total_initial']:,.0f} in {worse_stock}, no leverage) ---")
print(f"  {'Worse stock BH final value':<35s} ${res3['stock_worse_final']:>15,.2f} ${res5['stock_worse_final']:>15,.2f}")
print(f"  {'Worse stock BH total return':<35s} {res3['stock_worse_return']:>15.2f}% {res5['stock_worse_return']:>15.2f}%")

beat_worse_unlev_3x = "YES (+${:+,.0f})".format(res3['rot_final'] - res3['stock_worse_final']) if res3['rot_final'] > res3['stock_worse_final'] else "NO (-${:,.0f})".format(res3['stock_worse_final'] - res3['rot_final'])
beat_worse_unlev_5x = "YES (+${:+,.0f})".format(res5['rot_final'] - res5['stock_worse_final']) if res5['rot_final'] > res5['stock_worse_final'] else "NO (-${:,.0f})".format(res5['stock_worse_final'] - res5['rot_final'])
print(f"  {'Rotation beats worse stock?':<35s} {beat_worse_unlev_3x:>16s} {beat_worse_unlev_5x:>16s}")

# --- vs BETTER underlying stock (no leverage) ---
print(f"\n  --- vs BETTER underlying stock (BH ${res3['total_initial']:,.0f} in {better_stock}, no leverage) ---")
print(f"  {'Better stock BH final value':<35s} ${res3['stock_better_final']:>15,.2f} ${res5['stock_better_final']:>15,.2f}")
print(f"  {'Better stock BH total return':<35s} {res3['stock_better_return']:>15.2f}% {res5['stock_better_return']:>15.2f}%")

beat_better_unlev_3x = "YES (+${:+,.0f})".format(res3['rot_final'] - res3['stock_better_final']) if res3['rot_final'] > res3['stock_better_final'] else "NO (-${:,.0f})".format(res3['stock_better_final'] - res3['rot_final'])
beat_better_unlev_5x = "YES (+${:+,.0f})".format(res5['rot_final'] - res5['stock_better_final']) if res5['rot_final'] > res5['stock_better_final'] else "NO (-${:,.0f})".format(res5['stock_better_final'] - res5['rot_final'])
print(f"  {'Rotation beats better stock?':<35s} {beat_better_unlev_3x:>16s} {beat_better_unlev_5x:>16s}")

# --- vs WORSE leveraged warrant ---
print(f"\n  --- vs WORSE leveraged warrant (BH ${res3['total_initial']:,.0f} in {res3['bh_worse_name']} {3}x/{5}x) ---")
print(f"  {'Worse warrant BH final value':<35s} ${res3['bh_worse_final']:>15,.2f} ${res5['bh_worse_final']:>15,.2f}")

beat_worse_lev_3x = "YES (+${:+,.0f})".format(res3['rot_final'] - res3['bh_worse_final']) if res3['rot_final'] > res3['bh_worse_final'] else "NO (-${:,.0f})".format(res3['bh_worse_final'] - res3['rot_final'])
beat_worse_lev_5x = "YES (+${:+,.0f})".format(res5['rot_final'] - res5['bh_worse_final']) if res5['rot_final'] > res5['bh_worse_final'] else "NO (-${:,.0f})".format(res5['bh_worse_final'] - res5['rot_final'])
print(f"  {'Rotation beats worse warrant?':<35s} {beat_worse_lev_3x:>16s} {beat_worse_lev_5x:>16s}")

# --- vs BETTER leveraged warrant ---
print(f"\n  --- vs BETTER leveraged warrant (BH ${res3['total_initial']:,.0f} in {res3['bh_better_name']} {3}x/{5}x) ---")
print(f"  {'Better warrant BH final value':<35s} ${res3['bh_better_final']:>15,.2f} ${res5['bh_better_final']:>15,.2f}")

beat_better_lev_3x = "YES (+${:+,.0f})".format(res3['rot_final'] - res3['bh_better_final']) if res3['rot_final'] > res3['bh_better_final'] else "NO (-${:,.0f})".format(res3['bh_better_final'] - res3['rot_final'])
beat_better_lev_5x = "YES (+${:+,.0f})".format(res5['rot_final'] - res5['bh_better_final']) if res5['rot_final'] > res5['bh_better_final'] else "NO (-${:,.0f})".format(res5['bh_better_final'] - res5['rot_final'])
print(f"  {'Rotation beats better warrant?':<35s} {beat_better_lev_3x:>16s} {beat_better_lev_5x:>16s}")


# ============================================================
# 7. Summary verdict
# ============================================================
print(f"\n\n{'=' * 80}")
print("  SUMMARY VERDICT")
print(f"{'=' * 80}")

# Build verdict strings for each leverage
for L, res in [(3, res3), (5, res5)]:
    print(f"\n  {L}x Rotation:")
    parts = []

    # vs worse underlying
    if res['rot_final'] > res['stock_worse_final']:
        parts.append(f"BEATS worse underlying stock ({worse_stock} BH: ${res['stock_worse_final']:,.0f}) by ${res['rot_final'] - res['stock_worse_final']:+,.0f}")
    else:
        parts.append(f"TRAILS worse underlying stock ({worse_stock} BH: ${res['stock_worse_final']:,.0f}) by ${res['stock_worse_final'] - res['rot_final']:,.0f}")

    # vs better underlying
    if res['rot_final'] > res['stock_better_final']:
        parts.append(f"BEATS better underlying stock ({better_stock} BH: ${res['stock_better_final']:,.0f}) by ${res['rot_final'] - res['stock_better_final']:+,.0f}")
    else:
        parts.append(f"TRAILS better underlying stock ({better_stock} BH: ${res['stock_better_final']:,.0f}) by ${res['stock_better_final'] - res['rot_final']:,.0f}")

    # vs worse warrant
    if res['rot_final'] > res['bh_worse_final']:
        parts.append(f"BEATS worse {L}x warrant ({res['bh_worse_name']} BH: ${res['bh_worse_final']:,.0f}) by ${res['rot_final'] - res['bh_worse_final']:+,.0f}")
    else:
        parts.append(f"TRAILS worse {L}x warrant ({res['bh_worse_name']} BH: ${res['bh_worse_final']:,.0f}) by ${res['bh_worse_final'] - res['rot_final']:,.0f}")

    # vs better warrant
    if res['rot_final'] > res['bh_better_final']:
        parts.append(f"BEATS better {L}x warrant ({res['bh_better_name']} BH: ${res['bh_better_final']:,.0f}) by ${res['rot_final'] - res['bh_better_final']:+,.0f}")
    else:
        parts.append(f"TRAILS better {L}x warrant ({res['bh_better_name']} BH: ${res['bh_better_final']:,.0f}) by ${res['bh_better_final'] - res['rot_final']:,.0f}")

    for p in parts:
        print(f"    {p}")


# ============================================================
# 8. Daily price stats (for understanding leverage risk)
# ============================================================
print(f"\n\n{'=' * 80}")
print("  DAILY PRICE STATISTICS")
print(f"{'=' * 80}")
print(f"  GOOGL: mean daily return = {googl_ret.mean()*100:.4f}%  |  std = {googl_ret.std()*100:.3f}%")
print(f"  AMZN:  mean daily return = {amzn_ret.mean()*100:.4f}%  |  std = {amzn_ret.std()*100:.3f}%")

# Worst single-day drops
googl_worst = googl_ret.min()
amzn_worst = amzn_ret.min()
googl_best = googl_ret.max()
amzn_best = amzn_ret.max()
print(f"\n  WORST / BEST SINGLE-DAY RETURNS:")
print(f"  GOOGL: worst = {googl_worst*100:.2f}%  |  best = {googl_best*100:.2f}%")
print(f"         3x levered worst = {googl_worst*3*100:.2f}%  |  5x levered worst = {googl_worst*5*100:.2f}%")
print(f"  AMZN:  worst = {amzn_worst*100:.2f}%  |  best = {amzn_best*100:.2f}%")
print(f"         3x levered worst = {amzn_worst*3*100:.2f}%  |  5x levered worst = {amzn_worst*5*100:.2f}%")

if googl_worst * 5 < -1.0:
    print(f"  ⚠ WARNING: GOOGL worst day ({googl_worst*100:.2f}%) would wipe out a 5x warrant (>100% loss in one day)")
if amzn_worst * 5 < -1.0:
    print(f"  ⚠ WARNING: AMZN worst day ({amzn_worst*100:.2f}%) would wipe out a 5x warrant (>100% loss in one day)")

print()
print("Done.")
