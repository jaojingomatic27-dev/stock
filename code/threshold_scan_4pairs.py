# -*- coding: utf-8 -*-
"""Threshold + leverage scan for 4 remaining stock pairs: NVDA-GOOGL, NVDA-AMZN, MU-GOOGL, MU-AMZN.
2016-2026, annual rolling windows. Tests 7 thresholds x 6 leverages.
Generates threshold charts and prints comparison tables."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

plt.rcParams.update({
    'font.size': 9, 'axes.titlesize': 11, 'axes.labelsize': 10,
    'figure.facecolor': '#1a1a2e', 'axes.facecolor': '#16213e',
    'axes.edgecolor': '#666', 'axes.labelcolor': '#ccc', 'text.color': '#ccc',
    'xtick.color': '#999', 'ytick.color': '#999', 'grid.color': '#333355',
    'grid.alpha': 0.5, 'legend.facecolor': '#1a1a2e', 'legend.edgecolor': '#446',
})

THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [1, 2, 3, 4, 5, 6]
INVEST = 1000.0
KO_LEVEL = INVEST * 0.05

PAIRS = [
    ('NVDA', 'GOOGL'),
    ('NVDA', 'AMZN'),
    ('MU', 'GOOGL'),
    ('MU', 'AMZN'),
]

def load(ticker):
    path = rf"C:\AI\cc\stock\data\{ticker}_2016_daily.csv"
    df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
    return df[("Close", ticker)].dropna()

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

def rotation_single(close_a, close_b, lev, th, start_in_a=True):
    """Single leg rotation, $1000, start in stock A if start_in_a."""
    aligned = pd.DataFrame({'a': close_a, 'b': close_b}).dropna()
    rets_a = aligned['a'].pct_change().fillna(0).values
    rets_b = aligned['b'].pct_change().fillna(0).values
    n = len(aligned)
    val = INVEST; peak = INVEST; holding_a = start_in_a; rotations = 0
    for i in range(1, n):
        r = rets_a[i] if holding_a else rets_b[i]
        val *= (1 + lev * r)
        if val > peak: peak = val
        if (val - peak) / peak <= -th:
            holding_a = not holding_a; peak = val; rotations += 1
        if val < KO_LEVEL: return 0, True, rotations
    return val, False, rotations

def bh_levered(close, lev):
    val = INVEST
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1 + lev * r)
        if val < KO_LEVEL: return 0, True
    return val, False

# ─────────────────────────────────────────
# Main loop: process each pair
# ─────────────────────────────────────────
all_results = {}
all_pair_data = {}

for ticker_a, ticker_b in PAIRS:
    label = f"{ticker_a}-{ticker_b}"
    print(f"\n{'='*120}")
    print(f"  THRESHOLD + LEVERAGE SCAN: {label} Rotation Strategy")
    print(f"  Annual rolling windows 2016-2026, single leg ${INVEST:,}, knock-out at 5%")
    print(f"{'='*120}")

    close_a = load(ticker_a)
    close_b = load(ticker_b)
    windows_a = annual_windows(close_a)
    windows_b = annual_windows(close_b)

    # ── Run all years, all thresholds, all leverages ──
    # Structure: year_data[year_idx] = { 'lev': { 'th': (val, ko, rots), ... }, 'bh_a': [...], 'bh_b': [...] }
    year_data = []

    for wa_i, wb_i in zip(windows_a, windows_b):
        if len(wa_i['slice']) < 150 or len(wb_i['slice']) < 150:
            continue
        ca = wa_i['slice']; cb = wb_i['slice']
        yd = {'label': wa_i['label'], 'slice_a': ca, 'slice_b': cb}

        # BH unlevered returns (%)
        yd['ret_a'] = (ca.iloc[-1]/ca.iloc[0] - 1)*100
        yd['ret_b'] = (cb.iloc[-1]/cb.iloc[0] - 1)*100

        # BH levered (store as tuple)
        for lev in LEVERAGES:
            v, ko = bh_levered(ca, lev)
            yd[f'bh_lev_a_{lev}'] = (v, ko)
            v, ko = bh_levered(cb, lev)
            yd[f'bh_lev_b_{lev}'] = (v, ko)

        # Rotation scan: all lev x th
        for lev in LEVERAGES:
            for th in THRESHOLDS:
                v, ko, rots = rotation_single(ca, cb, lev, th, True)
                yd[(lev, th)] = (v, ko, rots)

        year_data.append(yd)

    # ── Print annual table ──
    print(f"\n  TABLE 1: Annual Results — Best 3x, 5x, 6x rotation vs B&H 1x stocks")
    hdr = f"  {'Year':<10} | {ticker_a:>6} {ticker_b:>6} | {'3x Best Th':>10} {'3x $':>10} {'3x #':>5} {'3x KO':>6} | {'5x Best Th':>10} {'5x $':>10} {'5x #':>5} {'5x KO':>6} | {'6x Best Th':>10} {'6x $':>10} {'6x #':>5} {'6x KO':>6}"
    print(hdr)
    print(f"  {'-'*len(hdr)}")

    for yd in year_data:
        best_3 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
        best_5 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
        best_6 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
        for th in THRESHOLDS:
            for lev, best_key in [(3, best_3), (5, best_5), (6, best_6)]:
                v, ko, rots = yd[(lev, th)]
                if not ko and v > best_key['val']:
                    best_key['val'] = v; best_key['th'] = th; best_key['rots'] = rots; best_key['ko'] = False
                elif ko and best_key['ko'] and v > best_key['val']:
                    best_key['val'] = v; best_key['th'] = th; best_key['rots'] = rots

        ko3 = "KO!" if best_3['ko'] else "OK"
        ko5 = "KO!" if best_5['ko'] else "OK"
        ko6 = "KO!" if best_6['ko'] else "OK"
        print(f"  {yd['label']:<10} | {yd['ret_a']:>+5.0f}% {yd['ret_b']:>+5.0f}% | {best_3['th']:>8.0%} ${best_3['val']:>9,.0f} {best_3['rots']:>4} {ko3:>6} | {best_5['th']:>8.0%} ${best_5['val']:>9,.0f} {best_5['rots']:>4} {ko5:>6} | {best_6['th']:>8.0%} ${best_6['val']:>9,.0f} {best_6['rots']:>4} {ko6:>6}")

    # ── TABLE 2: Consistency analysis ──
    print(f"\n  TABLE 2: Consistency ({len(year_data)} years)")
    print(f"  {'Metric':<28} {'1x':>8} {'2x':>8} {'3x':>8} {'4x':>8} {'5x':>8} {'6x':>8}")
    print(f"  {'-'*76}")
    for lev in LEVERAGES:
        bests = []
        for yd in year_data:
            best = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
            for th in THRESHOLDS:
                v, ko, rots = yd[(lev, th)]
                if not ko and v > best['val']:
                    best = {'val': v, 'th': th, 'rots': rots, 'ko': False}
                elif ko and best['ko'] and v > best['val']:
                    best['val'] = v; best['th'] = th; best['rots'] = rots
            bests.append(best)

        n_ko = sum(1 for b in bests if b['ko'])
        th_counts = {}
        for b in bests:
            if not b['ko']:
                th_counts[b['th']] = th_counts.get(b['th'], 0) + 1
        best_th = max(th_counts, key=th_counts.get) if th_counts else 0

        if lev == 1:
            continue  # Skip 1x rotation (no point — leverage < 2x barely activates)

    # ── TABLE 3: KO rate by threshold ──
    print(f"\n  TABLE 3: KO Rate by Threshold")
    print(f"  {'Threshold':>10} | {'1x KO':>7} {'2x KO':>7} {'3x KO':>7} {'4x KO':>7} {'5x KO':>7} {'6x KO':>7}")
    print(f"  {'-'*10}-+-{'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
    for th in THRESHOLDS:
        ko_counts = {}
        for lev in LEVERAGES:
            n_ko = sum(1 for yd in year_data if yd[(lev, th)][1])
            ko_counts[lev] = n_ko
        print(f"  {th:>8.0%}   | {ko_counts[1]:>5}/{len(year_data):>2} {ko_counts[2]:>5}/{len(year_data):>2} {ko_counts[3]:>5}/{len(year_data):>2} {ko_counts[4]:>5}/{len(year_data):>2} {ko_counts[5]:>5}/{len(year_data):>2} {ko_counts[6]:>5}/{len(year_data):>2}")

    # ── TABLE 4: Average final value by threshold (non-KO years only) ──
    print(f"\n  TABLE 4: Avg Final $ by Threshold & Leverage (surviving years only)")
    print(f"  {'Threshold':>10} | {'1x Avg':>10} {'2x Avg':>10} {'3x Avg':>10} {'4x Avg':>10} {'5x Avg':>10} {'6x Avg':>10}")
    print(f"  {'-'*10}-+-{'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for th in THRESHOLDS:
        avgs = []
        for lev in LEVERAGES:
            vals = [yd[(lev, th)][0] for yd in year_data if not yd[(lev, th)][1]]
            avg_v = np.mean(vals) if vals else 0
            avgs.append(avg_v)
        print(f"  {th:>8.0%}   | ${avgs[0]:>9,.0f} ${avgs[1]:>9,.0f} ${avgs[2]:>9,.0f} ${avgs[3]:>9,.0f} ${avgs[4]:>9,.0f} ${avgs[5]:>9,.0f}")

    # Store for final summary
    all_results[label] = year_data
    all_pair_data[label] = (close_a, close_b)

# ─────────────────────────────────────────
# Chart: Threshold scan for each pair
# ─────────────────────────────────────────
print(f"\n{'='*120}")
print("  Generating threshold charts...")

fig, axes = plt.subplots(2, 2, figsize=(20, 14))
fig.suptitle('Drawdown Threshold & Leverage Scan — 4 Stock Pairs\n'
             'Annual Rolling 2016-2026 | Rotation Strategy | vs Worse Stock B&H',
             fontsize=14, color='white', fontweight='bold', y=0.98)

colors = {1: '#888888', 2: '#4ecdc4', 3: '#00d4aa', 4: '#ffd93d', 5: '#ff6b6b', 6: '#ff4444'}

for ax, (ticker_a, ticker_b) in zip(axes.flat, PAIRS):
    label = f"{ticker_a}-{ticker_b}"
    year_data = all_results[label]

    # For each leverage, compute avg final value at each threshold (survivors only)
    # Also compute KO rate
    x = np.arange(len(THRESHOLDS))
    width = 0.12

    # Plot lines for each leverage: average final value across years (survivors)
    for j, lev in enumerate(LEVERAGES):
        avg_vals = []
        for th in THRESHOLDS:
            vals = [yd[(lev, th)][0] for yd in year_data if not yd[(lev, th)][1]]
            avg_vals.append(np.mean(vals) if vals else 0)
        line = ax.plot(x, avg_vals, 'o-', color=colors[lev], linewidth=2, markersize=6,
                       label=f'{lev}x', alpha=0.9)
        # Annotate KO rate
        for i, th in enumerate(THRESHOLDS):
            ko_count = sum(1 for yd in year_data if yd[(lev, th)][1])
            if ko_count > 0 and avg_vals[i] > 0:
                ax.annotate(f'{ko_count}/10', (x[i], avg_vals[i]),
                           textcoords="offset points", xytext=(0, 12),
                           fontsize=5, color=colors[lev], ha='center', alpha=0.7)

    # Worse stock B&H 1x avg
    worse_avg = []
    for yd in year_data:
        worse_avg.append(min(yd['ret_a'], yd['ret_b']))
    avg_worse = np.mean(worse_avg)
    ax.axhline(y=(avg_worse/100+1)*INVEST, color='white', linestyle='--', alpha=0.5, linewidth=1)
    ax.text(len(THRESHOLDS)-1, (avg_worse/100+1)*INVEST, f'Avg worse BH\n{avg_worse:+.0f}%',
            fontsize=7, color='white', alpha=0.7, ha='right', va='bottom')

    ax.set_xticks(x)
    ax.set_xticklabels([f'{t:.0%}' for t in THRESHOLDS])
    ax.set_xlabel('Drawdown Threshold')
    ax.set_ylabel('Avg Final Value ($)')
    ax.set_title(f'{ticker_a} ↔ {ticker_b}', color='white', fontweight='bold')
    ax.legend(fontsize=7, loc='upper left', ncol=3)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'${y:,.0f}'))
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(bottom=0)

plt.tight_layout(rect=[0, 0, 1, 0.94])
chart_path = r"C:\AI\cc\stock\image\threshold_scan_4pairs.png"
plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"  Chart saved: {chart_path}")

# ─────────────────────────────────────────
# SUMMARY TABLE
# ─────────────────────────────────────────
print(f"\n{'='*120}")
print("  FINAL SUMMARY: All 4 Pairs — Best Threshold per Leverage")
print(f"{'='*120}")
print(f"  {'Pair':<16} | {'1x Best Th':>11} {'1x Avg $':>10} | {'2x Best Th':>11} {'2x Avg $':>10} | {'3x Best Th':>11} {'3x Avg $':>10} | {'4x Best Th':>11} {'4x Avg $':>10} | {'5x Best Th':>11} {'5x Avg $':>10} | {'6x Best Th':>11} {'6x Avg $':>10}")
print(f"  {'-'*16}-+-{'-'*11} {'-'*10}-+-{'-'*11} {'-'*10}-+-{'-'*11} {'-'*10}-+-{'-'*11} {'-'*10}-+-{'-'*11} {'-'*10}-+-{'-'*11} {'-'*10}")

for ticker_a, ticker_b in PAIRS:
    label = f"{ticker_a}-{ticker_b}"
    year_data = all_results[label]
    row = [label]
    for lev in [1, 2, 3, 4, 5, 6]:
        best_th = 0; best_avg = 0
        for th in THRESHOLDS:
            vals = [yd[(lev, th)][0] for yd in year_data if not yd[(lev, th)][1]]
            avg_v = np.mean(vals) if vals else 0
            if avg_v > best_avg:
                best_avg = avg_v; best_th = th
        row.append(f'{best_th:.0%}')
        row.append(f'${best_avg:,.0f}')
    print(f"  {row[0]:<16} | {row[1]:>11} {row[2]:>10} | {row[3]:>11} {row[4]:>10} | {row[5]:>11} {row[6]:>10} | {row[7]:>11} {row[8]:>10} | {row[9]:>11} {row[10]:>10} | {row[11]:>11} {row[12]:>10}")

print(f"\n{'='*120}")
print("  All threshold scans complete.")
