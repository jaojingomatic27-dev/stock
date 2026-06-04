# -*- coding: utf-8 -*-
"""Fair comparison: 3x/20% Rotation vs 3x Levered Buy & Hold (same leverage level).
Answers: does the rotation MECHANISM actually add value, or is it just leverage?
Also compares vs 1x BH for reference."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

TICKERS = ['NVDA', 'MU', 'GOOGL', 'AMZN']
ALL_PAIRS = [
    ('NVDA', 'MU'),
    ('NVDA', 'GOOGL'),
    ('NVDA', 'AMZN'),
    ('MU', 'GOOGL'),
    ('MU', 'AMZN'),
    ('GOOGL', 'AMZN'),
]
LEV = 3
TH = 0.20
INVEST = 1000.0

def load(ticker):
    path = rf"C:\AI\cc\stock\data\{ticker}_2016_daily.csv"
    df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
    return df[("Close", ticker)].dropna()

def rotation_single(close_a, close_b, lev, th):
    aligned = pd.DataFrame({'a': close_a, 'b': close_b}).dropna()
    rets_a = aligned['a'].pct_change().fillna(0).values
    rets_b = aligned['b'].pct_change().fillna(0).values
    n = len(aligned)
    val = INVEST; peak = INVEST; holding_a = True; rotations = 0
    for i in range(1, n):
        r = rets_a[i] if holding_a else rets_b[i]
        val *= (1 + lev * r)
        if val > peak: peak = val
        if (val - peak) / peak <= -th:
            holding_a = not holding_a; peak = val; rotations += 1
        if val < 50: return 0, True, rotations
    return val, False, rotations

def bh_levered(close, lev):
    val = INVEST
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1 + lev * r)
        if val < 50: return 0, True
    return val, False

def annual_windows(close):
    end_d = close.index[-1]
    windows = []
    for y in range(10):
        te = pd.Timestamp(year=end_d.year - y, month=6, day=1)
        ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
        ei = close.index.get_indexer([te], method='nearest')[0]
        si = close.index.get_indexer([ts], method='nearest')[0]
        if ei - si > 150:
            windows.append({
                'label': f"{ts.year}-{te.year}",
                'slice': close.iloc[si:ei+1]
            })
    return windows

# Load all
stock_data = {t: load(t) for t in TICKERS}
stock_windows = {t: annual_windows(stock_data[t]) for t in TICKERS}

print("=" * 140)
print(f"  FAIR COMPARISON: Rotation {LEV}x/{TH:.0%} DD vs {LEV}x Levered B&H vs 1x B&H")
print(f"  Same leverage level — rotation mechanism is the ONLY difference")
print("=" * 140)

all_results = {}

for ta, tb in ALL_PAIRS:
    wa, wb = stock_windows[ta], stock_windows[tb]
    years = []
    rot_vals = []; rot_kos = []; rot_rots = []
    bh_a_3x = []; bh_a_3x_ko = []
    bh_b_3x = []; bh_b_3x_ko = []
    bh_a_1x = []; bh_b_1x = []

    for wa_i, wb_i in zip(wa, wb):
        if len(wa_i['slice']) < 150 or len(wb_i['slice']) < 150:
            continue
        ca = wa_i['slice']; cb = wb_i['slice']
        years.append(wa_i['label'])

        # Rotation 3x
        v, ko, rots = rotation_single(ca, cb, LEV, TH)
        rot_vals.append(v); rot_kos.append(ko); rot_rots.append(rots)

        # B&H 3x levered (each stock)
        v, ko = bh_levered(ca, LEV)
        bh_a_3x.append(v); bh_a_3x_ko.append(ko)
        v, ko = bh_levered(cb, LEV)
        bh_b_3x.append(v); bh_b_3x_ko.append(ko)

        # B&H 1x unlevered (reference)
        bh_a_1x.append((ca.iloc[-1]/ca.iloc[0] - 1)*100)
        bh_b_1x.append((cb.iloc[-1]/cb.iloc[0] - 1)*100)

    n = len(years)
    all_results[(ta, tb)] = {
        'years': years, 'rot_vals': rot_vals, 'rot_kos': rot_kos, 'rot_rots': rot_rots,
        'bh_a_3x': bh_a_3x, 'bh_a_3x_ko': bh_a_3x_ko,
        'bh_b_3x': bh_b_3x, 'bh_b_3x_ko': bh_b_3x_ko,
        'bh_a_1x': bh_a_1x, 'bh_b_1x': bh_b_1x,
    }

    # ── Print per-pair breakdown ──
    print(f"\n{'─' * 140}")
    print(f"  {ta} ↔ {tb}")
    print(f"{'─' * 140}")
    print(f"  {'Year':<10} | {'Rot 3x $':>10} {'Rot KO':>7} {'#Rot':>5} | {'B&H '+ta+' 3x':>12} {ta+' KO':>6} | {'B&H '+tb+' 3x':>12} {tb+' KO':>6} | {'1x '+ta:>8} {'1x '+tb:>8} | {'Winner':>18}")
    print(f"  {'-'*10}-+-{'-'*10} {'-'*7} {'-'*5}-+-{'-'*12} {'-'*6}-+-{'-'*12} {'-'*6}-+-{'-'*8} {'-'*8}-+-{'-'*18}")

    for i in range(n):
        # Determine winner among the 3 (non-KO only)
        candidates = []
        if not rot_kos[i]: candidates.append(('Rot3x', rot_vals[i]))
        if not bh_a_3x_ko[i]: candidates.append((f'BH_{ta}3x', bh_a_3x[i]))
        if not bh_b_3x_ko[i]: candidates.append((f'BH_{tb}3x', bh_b_3x[i]))
        winner = max(candidates, key=lambda x: x[1])[0] if candidates else 'ALL KO'
        ko_flag = "KO!" if rot_kos[i] else "OK"
        a_ko_flag = "KO!" if bh_a_3x_ko[i] else "OK"
        b_ko_flag = "KO!" if bh_b_3x_ko[i] else "OK"
        print(f"  {years[i]:<10} | ${rot_vals[i]:>9,.0f} {ko_flag:>7} {rot_rots[i]:>4}  | ${bh_a_3x[i]:>11,.0f} {a_ko_flag:>6} | ${bh_b_3x[i]:>11,.0f} {b_ko_flag:>6} | {bh_a_1x[i]:>+7.0f}% {bh_b_1x[i]:>+7.0f}% | {winner:>18}")

    # ── Summary stats ──
    rot_ret = [(v/INVEST - 1)*100 for v, k in zip(rot_vals, rot_kos)]
    bh_a_ret = [(v/INVEST - 1)*100 for v, k in zip(bh_a_3x, bh_a_3x_ko)]
    bh_b_ret = [(v/INVEST - 1)*100 for v, k in zip(bh_b_3x, bh_b_3x_ko)]

    # Count wins: rotation vs 3x BH A, vs 3x BH B, vs worse 3x BH, vs better 3x BH
    # Only count years where both survive
    rot_wins_vs_a3x = sum(1 for i in range(n) if not rot_kos[i] and not bh_a_3x_ko[i] and rot_vals[i] > bh_a_3x[i])
    rot_wins_vs_b3x = sum(1 for i in range(n) if not rot_kos[i] and not bh_b_3x_ko[i] and rot_vals[i] > bh_b_3x[i])

    # vs worse/better 3x BH (among non-KO years for both)
    rot_wins_vs_worse3x = 0
    rot_wins_vs_better3x = 0
    both_survive = 0
    for i in range(n):
        if rot_kos[i] or (bh_a_3x_ko[i] and bh_b_3x_ko[i]):
            continue
        # if only one BH survived, compare vs that one
        surviving_bhs = []
        if not bh_a_3x_ko[i]: surviving_bhs.append(bh_a_3x[i])
        if not bh_b_3x_ko[i]: surviving_bhs.append(bh_b_3x[i])
        if not surviving_bhs:
            continue
        both_survive += 1
        worse = min(surviving_bhs)
        better = max(surviving_bhs)
        if rot_vals[i] > worse: rot_wins_vs_worse3x += 1
        if rot_vals[i] > better: rot_wins_vs_better3x += 1

    # vs 1x BH (for reference)
    rot_wins_vs_a1x = sum(1 for i in range(n) if not rot_kos[i] and rot_ret[i] > bh_a_1x[i])
    rot_wins_vs_b1x = sum(1 for i in range(n) if not rot_kos[i] and rot_ret[i] > bh_b_1x[i])

    avg_rot_survivors = np.mean([rot_ret[i] for i in range(n) if not rot_kos[i]]) if not all(rot_kos) else float('nan')
    avg_bh_a_3x_surv = np.mean([bh_a_ret[i] for i in range(n) if not bh_a_3x_ko[i]]) if not all(bh_a_3x_ko) else float('nan')
    avg_bh_b_3x_surv = np.mean([bh_b_ret[i] for i in range(n) if not bh_b_3x_ko[i]]) if not all(bh_b_3x_ko) else float('nan')

    print(f"\n  ── SUMMARY: {ta}-{tb} ──")
    print(f"  Rotation KO rate:        {sum(rot_kos)}/{n}")
    print(f"  B&H {ta} 3x KO rate:      {sum(bh_a_3x_ko)}/{n}")
    print(f"  B&H {tb} 3x KO rate:      {sum(bh_b_3x_ko)}/{n}")
    print(f"  Rotation avg (survivors): {avg_rot_survivors:+.0f}%")
    print(f"  B&H {ta} 3x avg (surv):   {avg_bh_a_3x_surv:+.0f}%")
    print(f"  B&H {tb} 3x avg (surv):   {avg_bh_b_3x_surv:+.0f}%")
    print(f"  ── FAIR COMPARISON (both 3x leverage) ──")
    print(f"  Rotation beats {ta} 3x B&H:   {rot_wins_vs_a3x}/{both_survive} ({rot_wins_vs_a3x/max(both_survive,1)*100:.0f}%)")
    print(f"  Rotation beats {tb} 3x B&H:   {rot_wins_vs_b3x}/{both_survive} ({rot_wins_vs_b3x/max(both_survive,1)*100:.0f}%)")
    print(f"  Rotation beats WORSE 3x BH:   {rot_wins_vs_worse3x}/{both_survive} ({rot_wins_vs_worse3x/max(both_survive,1)*100:.0f}%)")
    print(f"  Rotation beats BETTER 3x BH:  {rot_wins_vs_better3x}/{both_survive} ({rot_wins_vs_better3x/max(both_survive,1)*100:.0f}%)")
    print(f"  ── REFERENCE (3x rot vs 1x BH) ──")
    print(f"  Rotation beats {ta} 1x BH:    {rot_wins_vs_a1x}/{n}")
    print(f"  Rotation beats {tb} 1x BH:    {rot_wins_vs_b1x}/{n}")

# ── FINAL CROSS-PAIR SUMMARY ──
print(f"\n{'=' * 140}")
print(f"  FINAL CROSS-PAIR SUMMARY")
print(f"{'=' * 140}")
print(f"  {'Pair':<16} | {'Rot vs Worse 3x':>16} {'Rot vs Better 3x':>17} | {'Rot vs Worse 1x':>16} {'Rot vs Better 1x':>17} | {'Rot KO':>7} {'Best 3x BH KO':>13} | {'Verdict':>20}")
print(f"  {'-'*16}-+-{'-'*16} {'-'*17}-+-{'-'*16} {'-'*17}-+-{'-'*7} {'-'*13}-+-{'-'*20}")

for ta, tb in ALL_PAIRS:
    d = all_results[(ta, tb)]
    n = len(d['years'])

    # 3x comparison
    both3x_survive = 0
    rot_wins_worse3x = 0; rot_wins_better3x = 0
    for i in range(n):
        if d['rot_kos'][i]: continue
        surviving = []
        if not d['bh_a_3x_ko'][i]: surviving.append(d['bh_a_3x'][i])
        if not d['bh_b_3x_ko'][i]: surviving.append(d['bh_b_3x'][i])
        if not surviving: continue
        both3x_survive += 1
        if d['rot_vals'][i] > min(surviving): rot_wins_worse3x += 1
        if d['rot_vals'][i] > max(surviving): rot_wins_better3x += 1

    # 1x comparison
    rot_wins_worse1x = 0; rot_wins_better1x = 0
    for i in range(n):
        if d['rot_kos'][i]: continue
        ret_1x_a = d['bh_a_1x'][i]
        ret_1x_b = d['bh_b_1x'][i]
        rot_ret_pct = (d['rot_vals'][i]/INVEST - 1)*100
        if rot_ret_pct > min(ret_1x_a, ret_1x_b): rot_wins_worse1x += 1
        if rot_ret_pct > max(ret_1x_a, ret_1x_b): rot_wins_better1x += 1

    rot_ko = sum(d['rot_kos'])
    best_bh_ko = min(sum(d['bh_a_3x_ko']), sum(d['bh_b_3x_ko']))

    # Verdict
    if rot_wins_worse3x / max(both3x_survive, 1) >= 0.7:
        verdict = "★ Rotation adds value"
    elif rot_wins_worse3x / max(both3x_survive, 1) >= 0.5:
        verdict = "△ Marginal benefit"
    else:
        verdict = "✗ Rotation doesn't help"

    print(f"  {ta:<6}-{tb:<6} | {rot_wins_worse3x:>4}/{both3x_survive:<10} {rot_wins_better3x:>4}/{both3x_survive:<10}  | {rot_wins_worse1x:>4}/{n:<10} {rot_wins_better1x:>4}/{n:<10}  | {rot_ko:>4}/{n:<2} {best_bh_ko:>4}/{n:<2}      | {verdict:>20}")

print(f"\n{'=' * 140}")
print("  Done.")
