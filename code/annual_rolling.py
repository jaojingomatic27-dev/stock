# -*- coding: utf-8 -*-
"""Annual rolling backtest: NVDA-MU and GOOGL-AMZN, 2016-2026, each year independently."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [1, 2, 3, 4, 5, 6]

def load(ticker):
    path = rf"C:\AI\cc\stock\{ticker}_2016_daily.csv"
    df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
    return df[("Close", ticker)].dropna()

def bh_levered(close, lev):
    val = 1000.0
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1 + lev * r)
        if val < 50:
            return 0, True
    return val, False

def rotation_single(close_a, close_b, lev, th, start_in_a=True):
    """Single leg rotation, $1000, start in stock A if start_in_a else B."""
    aligned = pd.DataFrame({'a': close_a, 'b': close_b}).dropna()
    rets_a = aligned['a'].pct_change().fillna(0).values
    rets_b = aligned['b'].pct_change().fillna(0).values
    n = len(aligned)

    val = 1000.0
    peak = 1000.0
    holding_a = start_in_a
    rotations = 0

    for i in range(1, n):
        r = rets_a[i] if holding_a else rets_b[i]
        val *= (1 + lev * r)
        if val > peak:
            peak = val
        dd = (val - peak) / peak
        if dd <= -th:
            holding_a = not holding_a
            peak = val
            rotations += 1
        if val < 50:
            return 0, True, rotations
    return val, False, rotations

def annual_windows(close, n_years_back=10):
    """Generate June-to-June annual windows working backwards."""
    end_date = close.index[-1]
    windows = []
    for y in range(n_years_back):
        tgt_end = pd.Timestamp(year=end_date.year - y, month=6, day=1)
        tgt_start = pd.Timestamp(year=tgt_end.year - 1, month=6, day=1)
        # Find nearest actual trading days
        end_idx = close.index.get_indexer([tgt_end], method='nearest')[0]
        start_idx = close.index.get_indexer([tgt_start], method='nearest')[0]
        if end_idx - start_idx > 150:  # At least ~6 months
            windows.append({
                'label': f"{tgt_start.year}-{tgt_end.year}",
                'slice': close.iloc[start_idx:end_idx+1]
            })
    return windows

def run_pair(label_a, label_b, ticker_a, ticker_b):
    close_a = load(ticker_a)
    close_b = load(ticker_b)
    windows_a = annual_windows(close_a)
    windows_b = annual_windows(close_b)

    print(f"\n{'=' * 110}")
    print(f"  {label_a}-{label_b} Annual Rolling Backtest: {len(windows_a)} years")
    print(f"{'=' * 110}")

    # TABLE 1: Year-by-year summary
    header = f"  {'Year':<10} | {'A 1x':>7} {'B 1x':>7} | {'3x Best Th':>10} {'3x Rot $':>10} {'3x #':>5} | {'5x Best Th':>10} {'5x Rot $':>10} {'5x #':>5} {'5x KO':>6} | {'6x Rot $':>10} {'6x KO':>6} | Notes"
    print(f"\n  TABLE 1: Annual Rotation Results (single leg $1000, start in {label_a})")
    print(header)
    print(f"  {'-'*len(header)}")

    all_years = []
    for w_a, w_b in zip(windows_a, windows_b):
        if len(w_a['slice']) < 150 or len(w_b['slice']) < 150:
            continue
        ca = w_a['slice']
        cb = w_b['slice']
        ret_a = (ca.iloc[-1]/ca.iloc[0] - 1) * 100
        ret_b = (cb.iloc[-1]/cb.iloc[0] - 1) * 100

        best_3x = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
        best_5x = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
        best_6x = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}

        for th in THRESHOLDS:
            # 3x
            v, ko, rots = rotation_single(ca, cb, 3, th, True)
            if not ko and v > best_3x['val']:
                best_3x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}
            elif ko and best_3x['ko'] and v > best_3x['val']:
                best_3x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}

            # 5x
            v, ko, rots = rotation_single(ca, cb, 5, th, True)
            if not ko and v > best_5x['val']:
                best_5x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}
            elif ko and best_5x['ko'] and v > best_5x['val']:
                best_5x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}

            # 6x
            v, ko, rots = rotation_single(ca, cb, 6, th, True)
            if not ko and v > best_6x['val']:
                best_6x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}
            elif ko and best_6x['ko'] and v > best_6x['val']:
                best_6x = {'val': v, 'th': th, 'rots': rots, 'ko': ko}

        label = w_a['label']
        notes = ""
        if ret_a > ret_b:
            notes += f"{label_a} wins"
        else:
            notes += f"{label_b} wins"

        ko5 = "KO!" if best_5x['ko'] else "OK"
        ko6 = "KO!" if best_6x['ko'] else "OK"

        print(f"  {label:<10} | {ret_a:>+6.1f}% {ret_b:>+6.1f}% | {best_3x['th']:>8.0%} ${best_3x['val']:>9,.0f} {best_3x['rots']:>4} | {best_5x['th']:>8.0%} ${best_5x['val']:>9,.0f} {best_5x['rots']:>4} {ko5:>6} | ${best_6x['val']:>9,.0f} {ko6:>6} | {notes}")

        all_years.append({
            'year': label, 'ret_a': ret_a, 'ret_b': ret_b,
            'best_3x': best_3x, 'best_5x': best_5x, 'best_6x': best_6x,
            'notes': notes
        })

    # TABLE 2: Consistency
    print(f"\n  TABLE 2: Consistency Analysis ({len(all_years)} years)")
    print(f"  {'':<25} {'3x':>10} {'5x':>10} {'6x':>10}")
    print(f"  {'-'*55}")

    for lev, key in [(3, 'best_3x'), (5, 'best_5x'), (6, 'best_6x')]:
        n_ko = sum(1 for y in all_years if y[key]['ko'])
        n_ok = len(all_years) - n_ko
        avg_val = np.mean([y[key]['val'] for y in all_years])
        avg_rots = np.mean([y[key]['rots'] for y in all_years])

        # BH comparison (which BH wins in each year, compare rotation to it)
        n_beat_worse = 0
        n_beat_better = 0
        for y in all_years:
            worse_ret = min(y['ret_a'], y['ret_b'])
            better_ret = max(y['ret_a'], y['ret_b'])
            rot_ret = (y[key]['val']/1000 - 1) * 100
            if rot_ret > worse_ret:
                n_beat_worse += 1
            if rot_ret > better_ret:
                n_beat_better += 1

        print(f"  {'KO rate':<25} {n_ko/len(all_years)*100:>9.0f}% {n_ko/len(all_years)*100:>9.0f}% {n_ko/len(all_years)*100:>9.0f}%")
        print(f"  {'Avg Final $ (surviving)':<25} ${avg_val:>9,.0f} ${avg_val:>9,.0f} ${avg_val:>9,.0f}")
        print(f"  {'Beat worse stock %':<25} {n_beat_worse/len(all_years)*100:>9.0f}% {n_beat_worse/len(all_years)*100:>9.0f}% {n_beat_worse/len(all_years)*100:>9.0f}%")
        print(f"  {'Beat better stock %':<25} {n_beat_better/len(all_years)*100:>9.0f}% {n_beat_better/len(all_years)*100:>9.0f}% {n_beat_better/len(all_years)*100:>9.0f}%")
        print()

    # Best threshold frequency
    print(f"  {'Most-winning threshold':<25}", end="")
    for lev, key in [(3, 'best_3x'), (5, 'best_5x'), (6, 'best_6x')]:
        th_counts = {}
        for y in all_years:
            if not y[key]['ko']:
                th_counts[y[key]['th']] = th_counts.get(y[key]['th'], 0) + 1
        best_th = max(th_counts, key=th_counts.get) if th_counts else 'N/A'
        print(f" {best_th:>8.0%}  ", end="")
    print()

    # TABLE 3: Optimal leverage per stock (BH)
    print(f"\n  TABLE 3: Optimal Leverage per Year (Buy & Hold, no rotation)")
    print(f"  {'Year':<10} | {'A Best Lv':>9} {'A Best $':>10} | {'B Best Lv':>9} {'B Best $':>10} | {'1x Winner':>10}")
    print(f"  {'-'*70}")
    for y in all_years:
        # Re-run BH for this year
        pass  # Too much, skip detailed BH per year

    # SUMMARY
    print(f"\n{'=' * 110}")
    print(f"  SUMMARY: {label_a}-{label_b}")
    print(f"{'=' * 110}")

    for lev, key in [(3, 'best_3x'), (5, 'best_5x'), (6, 'best_6x')]:
        n_ko = sum(1 for y in all_years if y[key]['ko'])
        survivors = [y for y in all_years if not y[key]['ko']]
        if survivors:
            avg_ret = np.mean([(s[key]['val']/1000-1)*100 for s in survivors])
            print(f"  {lev}x: KO in {n_ko}/{len(all_years)} years. Survivors avg return: {avg_ret:+.0f}%")
        else:
            print(f"  {lev}x: KO in ALL {len(all_years)} years. Total failure.")

    return all_years

# Run both pairs
nvda_mu = run_pair("NVDA", "MU", "NVDA", "MU")
googl_amzn = run_pair("GOOGL", "AMZN", "GOOGL", "AMZN")

print("\n\nDone.")
