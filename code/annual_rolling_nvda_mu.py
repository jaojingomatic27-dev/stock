# -*- coding: utf-8 -*-
"""
Annual Rolling Backtest: NVDA-MU Rotation Strategy
Tests each year independently from 2016 to 2026.
Rotation: start NVDA, switch on DD threshold, single-leg $1000.
Tests leverages [1,2,3,4,5,6] x thresholds [15%,20%,25%,30%,35%,40%,50%].
Knock-out at $50 (5% of initial).
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pandas as pd
import numpy as np

# ============================================================
# Load and align data
# ============================================================
nvda_df = pd.read_csv(r"C:\AI\cc\stock\NVDA_2016_daily.csv", header=[0, 1], index_col=0, parse_dates=True)
mu_df   = pd.read_csv(r"C:\AI\cc\stock\MU_2016_daily.csv",   header=[0, 1], index_col=0, parse_dates=True)

nvda_close = nvda_df[("Close", "NVDA")].dropna()
mu_close   = mu_df[("Close", "MU")].dropna()

# Align to common dates
common_idx = nvda_close.index.intersection(mu_close.index)
nvda = nvda_close.loc[common_idx]
mu   = mu_close.loc[common_idx]

print(f"Data range: {common_idx[0].strftime('%Y-%m-%d')} ~ {common_idx[-1].strftime('%Y-%m-%d')}")
print(f"Total trading days: {len(common_idx)}")
print()

# ============================================================
# Generate annual windows (June to June, going backwards from end)
# ============================================================
def find_nearest_trading_day(target_str, dates_series):
    """Find the closest actual trading day to target date string."""
    idx = dates_series.get_indexer([pd.Timestamp(target_str)], method='nearest')
    return dates_series.iloc[idx[0]]

dates_series = pd.Series(common_idx, index=common_idx)

# Build windows going backwards from the end date
windows = []
current_end = common_idx[-1]  # 2026-06-03

while True:
    # Target start: ~1 year before current_end
    target_start = current_end - pd.DateOffset(years=1)
    actual_start = find_nearest_trading_day(target_start.strftime('%Y-%m-%d'), dates_series)

    # Ensure we have a valid window
    if actual_start >= current_end:
        actual_start = common_idx[common_idx < current_end][-1] if len(common_idx[common_idx < current_end]) > 0 else None
        if actual_start is None:
            break

    # Find the actual start index
    mask = (common_idx >= actual_start) & (common_idx <= current_end)
    window_dates = common_idx[mask]
    if len(window_dates) < 50:  # too few days
        break

    windows.append((actual_start, current_end))

    # Move to previous window: end = day before start of current window
    prev_end_idx = common_idx.get_loc(actual_start) - 1
    if prev_end_idx < 0:
        break
    current_end = common_idx[prev_end_idx]

# Sort windows chronologically for display
windows = sorted(windows, key=lambda x: x[0])

print(f"Generated {len(windows)} annual windows:")
for i, (s, e) in enumerate(windows):
    mask = (common_idx >= s) & (common_idx <= e)
    n_days = mask.sum()
    print(f"  Year {i+1}: {s.strftime('%Y-%m-%d')} ~ {e.strftime('%Y-%m-%d')}  ({n_days} trading days)")
print()

# ============================================================
# Core backtest functions
# ============================================================

LEVERAGES = [1, 2, 3, 4, 5, 6]
THRESHOLDS = [15, 20, 25, 30, 35, 40, 50]
INITIAL_CAPITAL = 1000.0
KO_LEVEL = 50.0  # 5% of initial


def run_rotation(window_nvda, window_mu, leverage, threshold_pct):
    """
    Rotation strategy: start in NVDA, switch on DD threshold.
    Single leg $1000. KO at $50.

    Returns: (final_value, num_rotations, was_ko, end_stock)
    """
    capital = INITIAL_CAPITAL
    peak = capital
    current_stock = 'NVDA'
    rotations = 0
    was_ko = False

    prices_nvda = window_nvda.values
    prices_mu = window_mu.values

    # Calculate daily returns
    nvda_rets = np.diff(prices_nvda) / prices_nvda[:-1]
    mu_rets = np.diff(prices_mu) / prices_mu[:-1]

    for i in range(len(nvda_rets)):
        if current_stock == 'NVDA':
            daily_ret = nvda_rets[i]
        else:
            daily_ret = mu_rets[i]

        lev_ret = daily_ret * leverage
        capital *= (1.0 + lev_ret)

        # Clamp negative capital
        if capital <= 0:
            capital = 0.0
            was_ko = True
            break

        # Update peak
        if capital > peak:
            peak = capital

        # Check knock-out
        if capital <= KO_LEVEL:
            was_ko = True
            break

        # Check drawdown threshold
        dd_pct = (capital - peak) / peak * 100.0
        if dd_pct <= -threshold_pct:
            # Switch to the other stock
            current_stock = 'MU' if current_stock == 'NVDA' else 'NVDA'
            rotations += 1
            peak = capital  # reset peak on switch

    return capital, rotations, was_ko, current_stock


def run_buy_hold(window_prices, leverage):
    """
    Buy & hold with leverage. KO at $50.

    Returns: (final_value, was_ko)
    """
    capital = INITIAL_CAPITAL
    prices = window_prices.values
    rets = np.diff(prices) / prices[:-1]

    for i in range(len(rets)):
        lev_ret = rets[i] * leverage
        capital *= (1.0 + lev_ret)

        if capital <= 0:
            capital = 0.0
            return capital, True

        if capital <= KO_LEVEL:
            return capital, True

    return capital, False


# ============================================================
# Run all backtests
# ============================================================

# Store results per year
yearly_results = []

for year_idx, (start_dt, end_dt) in enumerate(windows):
    # Slice data for this window
    mask = (common_idx >= start_dt) & (common_idx <= end_dt)
    w_nvda = nvda[mask]
    w_mu = mu[mask]

    nvda_1x_ret = (w_nvda.iloc[-1] / w_nvda.iloc[0] - 1) * 100
    mu_1x_ret   = (w_mu.iloc[-1] / w_mu.iloc[0] - 1) * 100

    # Store all rotation results: leverage -> threshold -> result
    rot_results = {}  # key: (lev, th) -> (final_val, rotations, ko, end_stock)
    bh_results = {}   # key: (stock, lev) -> (final_val, ko)

    # Run rotation for all leverage x threshold combos
    for lev in LEVERAGES:
        for th in THRESHOLDS:
            final_val, rots, ko, end_stock = run_rotation(w_nvda, w_mu, lev, th)
            rot_results[(lev, th)] = (final_val, rots, ko, end_stock)

        # Buy & hold for this leverage
        nvda_bh_val, nvda_bh_ko = run_buy_hold(w_nvda, lev)
        mu_bh_val, mu_bh_ko = run_buy_hold(w_mu, lev)
        bh_results[('NVDA', lev)] = (nvda_bh_val, nvda_bh_ko)
        bh_results[('MU', lev)] = (mu_bh_val, mu_bh_ko)

    # Find best threshold per leverage (highest final value, non-KO preferred)
    best_per_lev = {}
    for lev in LEVERAGES:
        best_th = None
        best_val = -1
        best_rots = 0
        best_ko = True
        for th in THRESHOLDS:
            val, rots, ko, _ = rot_results[(lev, th)]
            # Prefer non-KO over KO, then higher value
            if not ko and (best_ko or val > best_val):
                best_val = val
                best_th = th
                best_rots = rots
                best_ko = False
            elif ko and best_ko and val > best_val:
                best_val = val
                best_th = th
                best_rots = rots
                best_ko = True
        best_per_lev[lev] = (best_th, best_val, best_rots, best_ko)

    yearly_results.append({
        'year_idx': year_idx + 1,
        'year_label': f"{start_dt.strftime('%Y-%m')}~{end_dt.strftime('%Y-%m')}",
        'start': start_dt,
        'end': end_dt,
        'n_days': len(w_nvda),
        'nvda_1x_ret': nvda_1x_ret,
        'mu_1x_ret': mu_1x_ret,
        'nvda_1x_final': w_nvda.iloc[-1] / w_nvda.iloc[0] * INITIAL_CAPITAL,
        'mu_1x_final': w_mu.iloc[-1] / w_mu.iloc[0] * INITIAL_CAPITAL,
        'rot_results': rot_results,
        'bh_results': bh_results,
        'best_per_lev': best_per_lev,
    })


# ============================================================
# TABLE 1: Year-by-year Summary
# ============================================================
print("=" * 130)
print("  TABLE 1: Year-by-Year Summary — NVDA-MU Rotation Strategy")
print("=" * 130)

header = (
    f"  {'Year':<6} {'Period':<22} "
    f"{'NVDA 1x':>9} {'MU 1x':>9} "
    f"{'Best 3x':>8} {'3x Rot$':>9} {'3x KO':>6} "
    f"{'Best 5x':>8} {'5x Rot$':>9} {'5x KO':>6} "
    f"{'Best 6x':>8} {'6x Rot$':>9} {'6x KO':>6} "
    f"{'NVDA BH3x':>10} {'MU BH3x':>10} {'BH3x Win':>9} "
    f"{'NVDA BH5x':>10} {'MU BH5x':>10} {'BH5x Win':>9}"
)
print(header)
print("-" * 130)

for yr in yearly_results:
    best3 = yr['best_per_lev'][3]
    best5 = yr['best_per_lev'][5]
    best6 = yr['best_per_lev'][6]

    nvda_bh3_val, nvda_bh3_ko = yr['bh_results'][('NVDA', 3)]
    mu_bh3_val, mu_bh3_ko = yr['bh_results'][('MU', 3)]
    nvda_bh5_val, nvda_bh5_ko = yr['bh_results'][('NVDA', 5)]
    mu_bh5_val, mu_bh5_ko = yr['bh_results'][('MU', 5)]

    bh3_winner = "NVDA" if nvda_bh3_val >= mu_bh3_val else "MU"
    if nvda_bh3_ko and mu_bh3_ko:
        bh3_winner = "BOTH KO"
    elif nvda_bh3_ko:
        bh3_winner = "MU"
    elif mu_bh3_ko:
        bh3_winner = "NVDA"

    bh5_winner = "NVDA" if nvda_bh5_val >= mu_bh5_val else "MU"
    if nvda_bh5_ko and mu_bh5_ko:
        bh5_winner = "BOTH KO"
    elif nvda_bh5_ko:
        bh5_winner = "MU"
    elif mu_bh5_ko:
        bh5_winner = "NVDA"

    def fmt_val(v, ko):
        if ko:
            return "     KO"
        if v >= 1000000:
            return f"${v/1e6:>7.1f}M"
        elif v >= 1000:
            return f"${v/1000:>7.1f}K"
        else:
            return f"${v:>8.0f}"

    def fmt_pct(v):
        return f"{v:>+8.1f}%"

    def fmt_ko(ko):
        return "  KO" if ko else "  OK"

    line = (
        f"  {yr['year_idx']:<6} {yr['year_label']:<22} "
        f"{yr['nvda_1x_ret']:>+8.1f}% {yr['mu_1x_ret']:>+8.1f}% "
        f"{best3[0]:>5}%{'>':<2} {fmt_val(best3[1], best3[3]):>9} {fmt_ko(best3[3]):>6} "
        f"{best5[0]:>5}%{'>':<2} {fmt_val(best5[1], best5[3]):>9} {fmt_ko(best5[3]):>6} "
        f"{best6[0]:>5}%{'>':<2} {fmt_val(best6[1], best6[3]):>9} {fmt_ko(best6[3]):>6} "
        f"{fmt_val(nvda_bh3_val, nvda_bh3_ko):>10} {fmt_val(mu_bh3_val, mu_bh3_ko):>10} {bh3_winner:>9} "
        f"{fmt_val(nvda_bh5_val, nvda_bh5_ko):>10} {fmt_val(mu_bh5_val, mu_bh5_ko):>10} {bh5_winner:>9}"
    )
    print(line)

print("-" * 130)
print("  Note: 'KO' = knocked out (portfolio dropped to $50 or below)")
print()

# ============================================================
# TABLE 2: Consistency Analysis
# ============================================================
print("=" * 120)
print("  TABLE 2: Consistency Analysis — How Often Does Rotation Win?")
print("=" * 120)

# For each year, identify the WORSE and BETTER stock at 1x (BH comparison)
def analyze_consistency(leverage):
    """Analyze for a given leverage level."""
    n_years = len(yearly_results)
    beat_worse = 0
    beat_better = 0
    ko_count = 0
    total_rot_better_than_both = 0  # rotation beats BOTH stocks
    total_rot_worse_than_both = 0

    # Count best threshold winner
    th_wins = {th: 0 for th in THRESHOLDS}

    for yr in yearly_results:
        # Which stock is better/worse at this leverage (BH)?
        nvda_val, nvda_ko = yr['bh_results'][('NVDA', leverage)]
        mu_val, mu_ko = yr['bh_results'][('MU', leverage)]

        if nvda_val >= mu_val:
            better_val = nvda_val
            worse_val = mu_val
        else:
            better_val = mu_val
            worse_val = nvda_val

        # Find best rotation result for this leverage
        best_th, best_rot_val, _, best_rot_ko = yr['best_per_lev'][leverage]

        if best_rot_ko:
            ko_count += 1
        else:
            th_wins[best_th] = th_wins.get(best_th, 0) + 1

        # Does rotation beat the worse stock?
        if best_rot_val > worse_val:
            beat_worse += 1

        # Does rotation beat the better stock?
        if best_rot_val > better_val:
            beat_better += 1

        # Does rotation beat BOTH?
        if best_rot_val > max(nvda_val, mu_val):
            total_rot_better_than_both += 1

        # Is rotation worse than BOTH?
        if best_rot_val < min(nvda_val, mu_val) and not best_rot_ko:
            total_rot_worse_than_both += 1

    print(f"\n  --- Leverage {leverage}x ---")
    print(f"  Beat worse stock:   {beat_worse}/{n_years} ({beat_worse/n_years*100:.0f}%)")
    print(f"  Beat better stock:  {beat_better}/{n_years} ({beat_better/n_years*100:.0f}%)")
    print(f"  Beat BOTH stocks:   {total_rot_better_than_both}/{n_years} ({total_rot_better_than_both/n_years*100:.0f}%)")
    print(f"  KO'd (best th):     {ko_count}/{n_years} ({ko_count/n_years*100:.0f}%)")
    if not all(v == 0 for v in th_wins.values()):
        best_winning_th = max(th_wins, key=th_wins.get)
        print(f"  Best threshold:     {best_winning_th}% (won {th_wins[best_winning_th]}/{n_years - ko_count} non-KO years)")
    print(f"  Threshold win counts: {dict(sorted(th_wins.items()))}")

for lev in [1, 3, 5]:
    analyze_consistency(lev)

# Additional: threshold that wins most often across all leverages
print(f"\n  --- Threshold Dominance (across lev 3 and 5) ---")
for th in THRESHOLDS:
    wins = 0
    total = 0
    for yr in yearly_results:
        for lev in [3, 5]:
            val, _, ko, _ = yr['rot_results'][(lev, th)]
            if not ko:
                # Is this threshold the best for this leverage in this year?
                best_val_for_lev = yr['best_per_lev'][lev][1]
                if val >= best_val_for_lev * 0.99:  # within 1% of best
                    wins += 1
                total += 1
    if total > 0:
        print(f"  Threshold {th:>2}%: won or tied in {wins}/{total} year-leverage combos ({wins/total*100:.0f}%)")

print()

# ============================================================
# TABLE 3: Optimal Leverage per Year (Buy & Hold)
# ============================================================
print("=" * 100)
print("  TABLE 3: Optimal Leverage per Year — Buy & Hold NVDA vs MU")
print("=" * 100)

header3 = (
    f"  {'Year':<6} {'Period':<22} "
    f"{'NVDA 1x':>9} {'NV BestL':>9} {'NV Best$':>10} {'NV KO?':>6} "
    f"{'MU 1x':>9} {'MU BestL':>9} {'MU Best$':>10} {'MU KO?':>6}"
)
print(header3)
print("-" * 100)

for yr in yearly_results:
    # Find best leverage for NVDA BH (non-KO preferred)
    nvda_best_lev = 1
    nvda_best_val = yr['bh_results'][('NVDA', 1)][0]
    nvda_best_ko = yr['bh_results'][('NVDA', 1)][1]
    for lev in LEVERAGES:
        val, ko = yr['bh_results'][('NVDA', lev)]
        if not ko and (nvda_best_ko or val > nvda_best_val):
            nvda_best_val = val
            nvda_best_lev = lev
            nvda_best_ko = False
        elif ko and nvda_best_ko and val > nvda_best_val:
            nvda_best_val = val
            nvda_best_lev = lev

    # Find best leverage for MU BH
    mu_best_lev = 1
    mu_best_val = yr['bh_results'][('MU', 1)][0]
    mu_best_ko = yr['bh_results'][('MU', 1)][1]
    for lev in LEVERAGES:
        val, ko = yr['bh_results'][('MU', lev)]
        if not ko and (mu_best_ko or val > mu_best_val):
            mu_best_val = val
            mu_best_lev = lev
            mu_best_ko = False
        elif ko and mu_best_ko and val > mu_best_val:
            mu_best_val = val
            mu_best_lev = lev

    nvda_1x = f"{yr['nvda_1x_ret']:>+8.1f}%"
    mu_1x = f"{yr['mu_1x_ret']:>+8.1f}%"

    nv_ko_str = "  KO" if nvda_best_ko else "  OK"
    mu_ko_str = "  KO" if mu_best_ko else "  OK"

    line = (
        f"  {yr['year_idx']:<6} {yr['year_label']:<22} "
        f"{nvda_1x:>9} {nvda_best_lev:>7}x {fmt_val(nvda_best_val, nvda_best_ko):>10} {nv_ko_str:>6} "
        f"{mu_1x:>9} {mu_best_lev:>7}x {fmt_val(mu_best_val, mu_best_ko):>10} {mu_ko_str:>6}"
    )
    print(line)

print("-" * 100)
print()

# ============================================================
# Summary: "Set and Forget" combo
# ============================================================
print("=" * 120)
print("  SUMMARY: Is there a 'set and forget' threshold + leverage combo?")
print("=" * 120)

# For each (lev, th) combo, score across all years:
# Score = +1 if rotation beats BOTH BH stocks, +0.5 if beats worse, -1 if KO'd
# Find the combo with the highest total score

print(f"\n  {'Leverage':<10} {'Thresh':>8} ", end="")
for yr in yearly_results:
    print(f"{'Y'+str(yr['year_idx']):>8}", end=" ")
print(f"{'Score':>8} {'Avg$':>10} {'KOs':>6} {'BeatBoth':>10}")

print("  " + "-" * (10 + 8 + len(yearly_results) * 9 + 8 + 10 + 6 + 10))

best_combo_score = -999
best_combo = None

for lev in [3, 5]:  # Focus on 3x and 5x
    for th in THRESHOLDS:
        score = 0
        ko_count = 0
        beat_both_count = 0
        beat_worse_count = 0
        total_final = 0
        display_cells = []

        for yr in yearly_results:
            val, rots, ko, _ = yr['rot_results'][(lev, th)]
            nvda_bh_val, _ = yr['bh_results'][('NVDA', lev)]
            mu_bh_val, _ = yr['bh_results'][('MU', lev)]
            better = max(nvda_bh_val, mu_bh_val)
            worse = min(nvda_bh_val, mu_bh_val)

            if ko:
                score -= 2
                ko_count += 1
                display_cells.append("     KO")
            else:
                total_final += val
                if val > better:
                    score += 2
                    beat_both_count += 1
                    display_cells.append(f"${val/1000:>6.1f}K*")
                elif val > worse:
                    score += 1
                    beat_worse_count += 1
                    display_cells.append(f"${val/1000:>6.1f}K")
                else:
                    display_cells.append(f"${val/1000:>6.1f}K ")

        avg_final = total_final / max(len(yearly_results) - ko_count, 1)

        cells_str = " ".join(display_cells)
        print(f"  {lev}x{'':>7} {th:>5}%   {cells_str} {score:>8} ${avg_final/1000:>8.1f}K {ko_count:>6} {beat_both_count:>10}")

        if score > best_combo_score:
            best_combo_score = score
            best_combo = (lev, th, beat_both_count, ko_count)

print()
if best_combo:
    lev, th, beat_both, kos = best_combo
    print(f"  >> Best combo: {lev}x leverage, {th}% threshold")
    print(f"     Score: {best_combo_score} | Beats BOTH in {beat_both}/{len(yearly_results)} years | KOs: {kos}")
    print()

# ============================================================
# Bonus: Detailed year-by-year rotation vs BH for key leverages
# ============================================================
print("=" * 120)
print("  DETAIL: Rotation vs Buy & Hold — All Thresholds for 3x Leverage")
print("=" * 120)

for yr in yearly_results:
    nvda_bh_val, nvda_bh_ko = yr['bh_results'][('NVDA', 3)]
    mu_bh_val, mu_bh_ko = yr['bh_results'][('MU', 3)]

    print(f"\n  Year {yr['year_idx']}: {yr['year_label']}  |  NVDA 1x: {yr['nvda_1x_ret']:+.1f}%  MU 1x: {yr['mu_1x_ret']:+.1f}%")
    print(f"    NVDA BH 3x: {fmt_val(nvda_bh_val, nvda_bh_ko)}  |  MU BH 3x: {fmt_val(mu_bh_val, mu_bh_ko)}")
    print(f"    {'Thresh':>8} {'Rot $':>10} {'#Rot':>6} {'KO':>5} {'vs NVDA':>10} {'vs MU':>10} {'Winner':>10}")
    print(f"    {'─'*65}")

    better_bh = max(nvda_bh_val, mu_bh_val)

    for th in THRESHOLDS:
        val, rots, ko, end_stock = yr['rot_results'][(3, th)]
        vs_nvda = f"{'BEAT' if val > nvda_bh_val else 'lose':>4} {abs(val - nvda_bh_val):>5.0f}"
        vs_mu = f"{'BEAT' if val > mu_bh_val else 'lose':>4} {abs(val - mu_bh_val):>5.0f}"
        beats_best = "*** BEST ***" if val >= better_bh and not ko else ""
        mark = " <-- BEST" if th == yr['best_per_lev'][3][0] else ""
        ko_str = " KO" if ko else "   "
        print(f"    {th:>5}%   {fmt_val(val, ko):>10} {rots:>6}{ko_str:>5} {vs_nvda:>10} {vs_mu:>10} {beats_best}{mark}")

print()
print("=" * 80)
print("  Backtest complete.")
print("=" * 80)
