# -*- coding: utf-8 -*-
"""
Annual Rolling Backtest: GOOGL-AMZN Rotation Strategy
Tests each year independently from 2016 to 2026 (June-to-June windows).
Rotation: start in GOOGL, switch to AMZN on drawdown trigger, switch back on next trigger.
Tests leverages [1..6] x thresholds [15%..50%], with 5% knockout.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ── 1. Load data ──────────────────────────────────────────────────────────────
print("Loading data...")
googl_df = pd.read_csv(
    r"C:\AI\cc\stock\GOOGL_2016_daily.csv",
    header=[0, 1], index_col=0, parse_dates=True
)
amzn_df = pd.read_csv(
    r"C:\AI\cc\stock\AMZN_2016_daily.csv",
    header=[0, 1], index_col=0, parse_dates=True
)

googl_close = googl_df[("Close", "GOOGL")].dropna()
amzn_close = amzn_df[("Close", "AMZN")].dropna()

# Align to common trading days
common_idx = googl_close.index.intersection(amzn_close.index)
googl = googl_close[common_idx]
amzn = amzn_close[common_idx]
print(f"  Common trading days: {len(common_idx)}  ({common_idx[0].date()} ~ {common_idx[-1].date()})")

# ── 2. Define annual windows (June → June) ───────────────────────────────────
windows = []
for y in range(2016, 2026):
    start_str = f"{y}-06-01"
    end_str = f"{y+1}-06-01"
    mask = (common_idx >= start_str) & (common_idx < end_str)
    dates_in_window = common_idx[mask]
    if len(dates_in_window) >= 10:  # need enough trading days
        windows.append((y, dates_in_window))
        print(f"  Window {y}: {dates_in_window[0].date()} ~ {dates_in_window[-1].date()}  ({len(dates_in_window)} days)")

# ── 3. Parameters ────────────────────────────────────────────────────────────
leverages = [1, 2, 3, 4, 5, 6]
thresholds_pct = [15, 20, 25, 30, 35, 40, 50]
thresholds = [t / 100.0 for t in thresholds_pct]
INITIAL = 1000.0
KO_LEVEL = 50.0

# ── 4. Backtest engine ───────────────────────────────────────────────────────
def run_rotation(g_ret, a_ret, leverage, threshold):
    """
    Rotation strategy on pre-computed daily return series.
    g_ret, a_ret: pd.Series of daily returns (aligned, same index).
    Returns: (final_value, num_rotations, knocked_out)
    """
    value = INITIAL
    peak = INITIAL
    position = 0  # 0=GOOGL, 1=AMZN
    rotations = 0
    ko = False

    for i in range(len(g_ret)):
        if position == 0:
            daily_ret = leverage * g_ret.iloc[i]
        else:
            daily_ret = leverage * a_ret.iloc[i]

        value *= (1.0 + daily_ret)

        if value <= KO_LEVEL:
            ko = True
            value = 0.0
            break

        if value > peak:
            peak = value

        dd = (value - peak) / peak if peak > 0 else -1.0

        if dd <= -threshold:
            position = 1 - position  # toggle 0↔1
            peak = value
            rotations += 1

    return value, rotations, ko


def run_bh(ret_series, leverage):
    """Buy & Hold: compound daily returns with leverage. Returns (final_value, knocked_out)."""
    value = INITIAL
    for r in ret_series:
        value *= (1.0 + leverage * r)
        if value <= KO_LEVEL:
            return 0.0, True
    return value, False


# ── 5. Run all tests ─────────────────────────────────────────────────────────
print("\nRunning backtests...")

# Storage: results[year][lev][th_pct] = (final_value, rotations, ko)
results = {}

# Storage: bh_results[year][lev]["GOOGL"|"AMZN"] = (final_value, ko)
bh_results = {}

for year, dates in windows:
    # Slice prices and compute daily returns
    g_price = googl[dates]
    a_price = amzn[dates]
    g_ret = g_price.pct_change().dropna()
    a_ret = a_price.pct_change().dropna()
    # Align return indices
    common_ret_idx = g_ret.index.intersection(a_ret.index)
    g_ret = g_ret[common_ret_idx]
    a_ret = a_ret[common_ret_idx]

    if len(g_ret) < 5:
        print(f"  Skipping {year}: only {len(g_ret)} return days")
        continue

    # Buy & Hold
    bh_results[year] = {}
    for lev in leverages:
        googl_val, googl_ko = run_bh(g_ret, lev)
        amzn_val, amzn_ko = run_bh(a_ret, lev)
        bh_results[year][lev] = {"GOOGL": (googl_val, googl_ko), "AMZN": (amzn_val, amzn_ko)}

    # Rotation
    year_results = {}
    for lev in leverages:
        lev_results = {}
        for th in thresholds_pct:
            val, rots, ko = run_rotation(g_ret, a_ret, lev, th / 100.0)
            lev_results[th] = (val, rots, ko)
        year_results[lev] = lev_results
    results[year] = year_results

    print(f"  Year {year}: {len(g_ret)} days, done.")

# ── 6. Helper: find best threshold for a given (year, leverage) ──────────────
def best_for(year, lev):
    """Return (best_threshold_pct, best_value, rotations, ko) for rotation."""
    entries = results[year][lev]
    best_th = max(entries, key=lambda t: entries[t][0])  # max final value
    val, rots, ko = entries[best_th]
    return best_th, val, rots, ko


# ── 7. TABLE 1: Year-by-year summary ─────────────────────────────────────────
print("\n" + "=" * 120)
print("TABLE 1: Year-by-Year Summary (June → June annual windows)")
print("=" * 120)

# Header
header = (
    f"{'Year':>6}  "
    f"{'GOOGL 1x':>9}  {'AMZN 1x':>9}  "
    f"{'BestTh3x':>9}  {'3xRot$':>9}  {'3xRot':>5}  "
    f"{'BestTh5x':>9}  {'5xRot$':>9}  {'5xRot':>5}  "
    f"{'3x BH Win':>11}  {'5x BH Win':>11}  "
    f"{'GOOGL BnR':>10}  {'AMZN BnR':>10}"
)
print(header)
print("-" * 120)

def bh_ret_str(year, ticker, lev):
    val, ko = bh_results[year][lev][ticker]
    if ko:
        return "KO"
    pct = (val / INITIAL - 1) * 100
    return f"{pct:+.1f}%"

def bh_winner(year, lev):
    g_val, g_ko = bh_results[year][lev]["GOOGL"]
    a_val, a_ko = bh_results[year][lev]["AMZN"]
    if g_val > a_val:
        return "GOOGL"
    elif a_val > g_val:
        return "AMZN"
    else:
        return "TIE"

def best_bh_ret(year, lev):
    """Return the better of GOOGL/AMZN BH return as string, or KO."""
    g_val, g_ko = bh_results[year][lev]["GOOGL"]
    a_val, a_ko = bh_results[year][lev]["AMZN"]
    best_val = max(g_val, a_val)
    if best_val <= KO_LEVEL:
        return "KO"
    pct = (best_val / INITIAL - 1) * 100
    ticker = "GOOGL" if g_val >= a_val else "AMZN"
    return f"{ticker} {pct:+.1f}%"

table1_rows = []
for year, dates in windows:
    g_1x = bh_ret_str(year, "GOOGL", 1)
    a_1x = bh_ret_str(year, "AMZN", 1)

    best3_th, best3_val, best3_rot, best3_ko = best_for(year, 3)
    best5_th, best5_val, best5_rot, best5_ko = best_for(year, 5)

    bh3_win = bh_winner(year, 3)
    bh5_win = bh_winner(year, 5)

    googl_bnr = best_bh_ret(year, 3)
    amzn_bnr = best_bh_ret(year, 5)

    def fmt_val(v, ko):
        if ko:
            return "  KO"
        return f"${v:7.0f}"

    def fmt_th(t):
        return f"{t}%"

    row = (
        f"{year:>6}  "
        f"{g_1x:>9}  {a_1x:>9}  "
        f"{fmt_th(best3_th):>9}  {fmt_val(best3_val, best3_ko):>9}  {best3_rot:>4}  "
        f"{fmt_th(best5_th):>9}  {fmt_val(best5_val, best5_ko):>9}  {best5_rot:>4}  "
        f"{bh3_win:>11}  {bh5_win:>11}  "
        f"{googl_bnr:>10}  {amzn_bnr:>10}"
    )
    print(row)
    table1_rows.append({
        "year": year, "g_1x": g_1x, "a_1x": a_1x,
        "best3_th": best3_th, "best3_val": best3_val, "best3_rot": best3_rot, "best3_ko": best3_ko,
        "best5_th": best5_th, "best5_val": best5_val, "best5_rot": best5_rot, "best5_ko": best5_ko,
        "bh3_win": bh3_win, "bh5_win": bh5_win,
    })

# ── 8. TABLE 2: Consistency ──────────────────────────────────────────────────
print("\n" + "=" * 120)
print("TABLE 2: Consistency Analysis")
print("=" * 120)

n_years = len(windows)

# Compute per-leverage stats
for lev in [3, 5, 6]:
    print(f"\n─── Leverage {lev}x ───")

    # Rotation results: best threshold per year
    rot_vals = []
    rot_kos = 0
    best_ths = []
    rot_vs_worse_wins = 0
    rot_vs_better_wins = 0

    for year, dates in windows:
        best_th, best_val, best_rot, best_ko = best_for(year, lev)
        rot_vals.append(best_val)
        best_ths.append(best_th)
        if best_ko:
            rot_kos += 1

        # BH: worse and better
        g_val, g_ko = bh_results[year][lev]["GOOGL"]
        a_val, a_ko = bh_results[year][lev]["AMZN"]
        worse_bh = min(g_val, a_val)
        better_bh = max(g_val, a_val)

        if best_val > worse_bh:
            rot_vs_worse_wins += 1
        if best_val >= better_bh:
            rot_vs_better_wins += 1

    # Most-winning threshold
    from collections import Counter
    th_counter = Counter(best_ths)
    most_common_th = th_counter.most_common(3)

    print(f"  Rotation vs worse BH win rate:  {rot_vs_worse_wins}/{n_years} = {rot_vs_worse_wins/n_years*100:.1f}%")
    print(f"  Rotation vs better BH win rate: {rot_vs_better_wins}/{n_years} = {rot_vs_better_wins/n_years*100:.1f}%")
    print(f"  KO rate (years with KO):        {rot_kos}/{n_years} = {rot_kos/n_years*100:.1f}%")
    print(f"  Top thresholds:                  {most_common_th}")

    # Avg rot value
    avg_rot = np.mean([v for v in rot_vals if v > 0]) if any(v > 0 for v in rot_vals) else 0
    print(f"  Avg final value (non-KO):       ${avg_rot:,.0f}")

# KO rate per leverage (any KO across any threshold)
print(f"\n─── KO Rate per Leverage (any threshold) ───")
for lev in leverages:
    ko_count = 0
    total = 0
    for year, dates in windows:
        for th in thresholds_pct:
            val, rots, ko = results[year][lev][th]
            total += 1
            if ko:
                ko_count += 1
    print(f"  {lev}x: {ko_count}/{total} = {ko_count/total*100:.1f}%")

# Most-winning threshold overall
print(f"\n─── Most-Winning Threshold (across all leverages & years) ───")
all_best_ths = []
for lev in leverages:
    for year, dates in windows:
        best_th, _, _, _ = best_for(year, lev)
        all_best_ths.append((lev, year, best_th))
th_counter_all = Counter([t for _, _, t in all_best_ths])
for th, count in th_counter_all.most_common():
    print(f"  {th}%: {count} times")

# ── 9. TABLE 3: Optimal leverage per year per stock ──────────────────────────
print("\n" + "=" * 120)
print("TABLE 3: Optimal Leverage per Stock per Year (BH, highest non-KO return)")
print("=" * 120)
print(f"{'Year':>6}  {'G Best L':>9}  {'G Ret':>9}  {'A Best L':>9}  {'A Ret':>9}  {'Rot Best L':>11}  {'Rot Ret':>9}")
print("-" * 80)

for year, dates in windows:
    # Best leverage for GOOGL BH
    best_g_lev = 1
    best_g_val = 0
    best_g_ko = True
    for lev in leverages:
        val, ko = bh_results[year][lev]["GOOGL"]
        if val > best_g_val:
            best_g_val = val
            best_g_lev = lev
            best_g_ko = ko

    # Best leverage for AMZN BH
    best_a_lev = 1
    best_a_val = 0
    best_a_ko = True
    for lev in leverages:
        val, ko = bh_results[year][lev]["AMZN"]
        if val > best_a_val:
            best_a_val = val
            best_a_lev = lev
            best_a_ko = ko

    # Best leverage for Rotation (best threshold per leverage, then best leverage)
    best_r_lev = 1
    best_r_val = 0
    best_r_ko = True
    for lev in leverages:
        _, val, _, ko = best_for(year, lev)
        if val > best_r_val:
            best_r_val = val
            best_r_lev = lev
            best_r_ko = ko

    def fmt_opt(lev, val, ko):
        if ko or val <= KO_LEVEL:
            return f"{lev}x KO"
        pct = (val / INITIAL - 1) * 100
        return f"{lev}x {pct:+.1f}%"

    print(f"{year:>6}  {fmt_opt(best_g_lev, best_g_val, best_g_ko):>9}  "
          f"{fmt_opt(best_a_lev, best_a_val, best_a_ko):>9}  "
          f"{fmt_opt(best_r_lev, best_r_val, best_r_ko):>11}")

# ── 10. Detailed leverage sweep per threshold ────────────────────────────────
print("\n" + "=" * 120)
print("DETAIL: Best threshold per leverage per year (final value)")
print("=" * 120)

# Build a compact grid
for lev in leverages:
    print(f"\n─── Leverage {lev}x ───")
    header_line = f"{'Year':>6}"
    for th in thresholds_pct:
        header_line += f"  {th}%:${'>'}8"
    header_line += f"  {'BestTh':>8}  {'BestVal':>9}  {'BH_G':>9}  {'BH_A':>9}"
    print(header_line)
    print("-" * 110)

    for year, dates in windows:
        row_str = f"{year:>6}"
        best_th = None
        best_val = -1
        for th in thresholds_pct:
            val, rots, ko = results[year][lev][th]
            if ko:
                row_str += f"  {'KO':>8}"
            else:
                row_str += f"  ${val:7.0f}"
            if val > best_val:
                best_val = val
                best_th = th
        g_val, g_ko = bh_results[year][lev]["GOOGL"]
        a_val, a_ko = bh_results[year][lev]["AMZN"]
        g_str = "KO" if g_ko else f"${g_val:7.0f}"
        a_str = "KO" if a_ko else f"${a_val:7.0f}"
        row_str += f"  {best_th}%:${best_val:5.0f}" if best_th else "  N/A"
        row_str += f"  {g_str}  {a_str}"
        print(row_str)

# ── 11. Summary ──────────────────────────────────────────────────────────────
print("\n" + "=" * 120)
print("SUMMARY: Most Robust Threshold+Leverage Combo Across Years")
print("=" * 120)

# For each (leverage, threshold) combo, compute:
#   - How many years is it the best threshold for that leverage?
#   - Average final value across years
#   - Win rate vs worse BH
#   - Win rate vs better BH
#   - KO rate

print(f"\n{'Lev':>4} {'Th':>5}  {'#Best':>6}  {'AvgVal':>9}  {'vsWorseBH':>11}  {'vsBetterBH':>11}  {'KORate':>8}  {'AvgRot':>7}")
print("-" * 85)

combo_stats = []
for lev in leverages:
    for th in thresholds_pct:
        count_best = sum(1 for year, _ in windows if best_for(year, lev)[0] == th)
        vals = []
        rots_list = []
        kos = 0
        vs_worse = 0
        vs_better = 0
        for year, _ in windows:
            val, rots, ko = results[year][lev][th]
            vals.append(val)
            rots_list.append(rots)
            if ko:
                kos += 1
            g_val, g_ko = bh_results[year][lev]["GOOGL"]
            a_val, a_ko = bh_results[year][lev]["AMZN"]
            worse_bh = min(g_val, a_val)
            better_bh = max(g_val, a_val)
            if val > worse_bh:
                vs_worse += 1
            if val >= better_bh:
                vs_better += 1

        avg_val = np.mean(vals)
        avg_rot = np.mean(rots_list) if rots_list else 0
        ko_rate = kos / n_years * 100

        combo_stats.append({
            "lev": lev, "th": th,
            "count_best": count_best,
            "avg_val": avg_val,
            "vs_worse": vs_worse,
            "vs_better": vs_better,
            "ko_rate": ko_rate,
            "avg_rot": avg_rot,
        })

        print(f"{lev:>4}x {th:>3}%  {count_best:>4}/{n_years}  ${avg_val:8,.0f}  "
              f"{vs_worse:>4}/{n_years} {vs_worse/n_years*100:4.1f}%  "
              f"{vs_better:>4}/{n_years} {vs_better/n_years*100:4.1f}%  "
              f"{ko_rate:5.1f}%  {avg_rot:5.1f}")

# Top combos by different criteria
print("\n─── Top 5 by #Best (most often optimal threshold) ───")
top_by_best = sorted(combo_stats, key=lambda x: x["count_best"], reverse=True)[:5]
for s in top_by_best:
    print(f"  {s['lev']}x {s['th']}% : best in {s['count_best']}/{n_years} years, "
          f"avg=${s['avg_val']:,.0f}, vsWorse={s['vs_worse']}/{n_years}, vsBetter={s['vs_better']}/{n_years}, KO={s['ko_rate']:.0f}%")

print("\n─── Top 5 by Average Value ───")
top_by_avg = sorted(combo_stats, key=lambda x: x["avg_val"], reverse=True)[:5]
for s in top_by_avg:
    print(f"  {s['lev']}x {s['th']}% : avg=${s['avg_val']:,.0f}, "
          f"best in {s['count_best']}/{n_years}, vsWorse={s['vs_worse']}/{n_years}, vsBetter={s['vs_better']}/{n_years}, KO={s['ko_rate']:.0f}%")

print("\n─── Top 5 by vsBetterBH win rate ───")
top_by_better = sorted(combo_stats, key=lambda x: (x["vs_better"], -x["ko_rate"]), reverse=True)[:5]
for s in top_by_better:
    print(f"  {s['lev']}x {s['th']}% : vsBetter={s['vs_better']}/{n_years}, "
          f"avg=${s['avg_val']:,.0f}, vsWorse={s['vs_worse']}/{n_years}, KO={s['ko_rate']:.0f}%")

# Final recommendation: best trade-off (high vsBetter, low KO)
print("\n─── Recommended: Best trade-off (high vsBetter, low KO, high avg) ───")
scored = []
for s in combo_stats:
    score = s["vs_better"] / n_years * 40 + (1 - s["ko_rate"]/100) * 30 + min(s["avg_val"] / 2000, 1) * 20 + s["count_best"] / n_years * 10
    scored.append((score, s))
scored.sort(reverse=True)
for score, s in scored[:5]:
    print(f"  {s['lev']}x {s['th']}% : score={score:.1f}, "
          f"vsBetter={s['vs_better']}/{n_years}, avg=${s['avg_val']:,.0f}, KO={s['ko_rate']:.0f}%, "
          f"bestIn={s['count_best']}/{n_years}")

print("\nDone.")
