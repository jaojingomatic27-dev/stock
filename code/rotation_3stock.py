# -*- coding: utf-8 -*-
"""3-Stock Rotation: ORCL, MSFT, AMZN. Start $1000 each ($3000 total).
When any leveraged position drops >threshold from peak → sell, split equally to other 2.
2016-2026 annual rolling. Tests multiple thresholds × leverages.
Compares vs same-leverage B&H for each stock (fair comparison)."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

plt.rcParams.update({
    'font.size': 8, 'axes.titlesize': 10, 'axes.labelsize': 9,
    'figure.facecolor': '#1a1a2e', 'axes.facecolor': '#16213e',
    'axes.edgecolor': '#666', 'axes.labelcolor': '#ccc', 'text.color': '#ccc',
    'xtick.color': '#999', 'ytick.color': '#999', 'grid.color': '#333355',
    'grid.alpha': 0.5, 'legend.facecolor': '#1a1a2e', 'legend.edgecolor': '#446',
})

TICKERS = ['ORCL', 'MSFT', 'AMZN']
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [1, 2, 3, 4, 5, 6]
INVEST_PER = 1000.0  # per stock
TOTAL_INVEST = INVEST_PER * 3
KO_LEVEL = TOTAL_INVEST * 0.05

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

def rotation_3stock(close_a, close_b, close_c, lev, th):
    """3-stock rotation: when any position breaches threshold, sell & split to other 2.
    Returns (total_final_value, ko, total_rotations)."""
    aligned = pd.DataFrame({'a': close_a, 'b': close_b, 'c': close_c}).dropna()
    rets_a = aligned['a'].pct_change().fillna(0).values
    rets_b = aligned['b'].pct_change().fillna(0).values
    rets_c = aligned['c'].pct_change().fillna(0).values
    n = len(aligned)

    vals = np.array([INVEST_PER, INVEST_PER, INVEST_PER], dtype=float)
    peaks = vals.copy()
    total_rotations = 0

    for i in range(1, n):
        # Update values
        vals[0] *= (1 + lev * rets_a[i])
        vals[1] *= (1 + lev * rets_b[i])
        vals[2] *= (1 + lev * rets_c[i])
        vals = np.maximum(vals, 0)

        total = vals.sum()
        if total <= KO_LEVEL:
            return 0, True, total_rotations

        # Update peaks
        for j in range(3):
            if vals[j] > peaks[j]:
                peaks[j] = vals[j]

        # Check for breaches
        breached = []
        for j in range(3):
            if peaks[j] > 0 and (vals[j] - peaks[j]) / peaks[j] <= -th:
                breached.append(j)

        if not breached:
            continue

        # Sell all breached positions
        cash = 0.0
        for j in breached:
            cash += vals[j]
            vals[j] = 0.0
            peaks[j] = 0.0
            total_rotations += 1

        # Distribute equally to surviving positions
        survivors = [j for j in range(3) if j not in breached]
        if len(survivors) == 0:
            return 0, True, total_rotations  # all breached
        if len(survivors) == 1:
            # Only 1 survivor - all cash goes there
            vals[survivors[0]] += cash
            peaks[survivors[0]] = vals[survivors[0]]
        else:
            # Split equally
            per_survivor = cash / len(survivors)
            for j in survivors:
                vals[j] += per_survivor
                peaks[j] = vals[j]  # reset peak for new money
        total += 0  # no-op; total will be recomputed next iteration

    return vals.sum(), False, total_rotations

def bh_levered(close, lev):
    val = INVEST_PER  # per-stock BH
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1 + lev * r)
        if val < KO_LEVEL / 3:  # per-stock KO at same proportion
            return 0, True
    return val, False

# ── Load data ──
print("Loading data...")
stock_data = {}
stock_windows = {}
for t in TICKERS:
    stock_data[t] = load(t)
    stock_windows[t] = annual_windows(stock_data[t])
    print(f"  {t}: {len(stock_windows[t])} windows")

close_a, close_b, close_c = stock_data['ORCL'], stock_data['MSFT'], stock_data['AMZN']
wa, wb, wc = stock_windows['ORCL'], stock_windows['MSFT'], stock_windows['AMZN']

# ── Annual Rolling Backtest ──
print(f"\n{'='*150}")
print(f"  3-STOCK ROTATION: {' + '.join(TICKERS)} | ${INVEST_PER:,.0f} each (${TOTAL_INVEST:,.0f} total)")
print(f"  When ANY position drops >threshold from peak → sell, split equally to other 2")
print(f"{'='*150}")

all_years = []

for i_year in range(len(wa)):
    ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']
    if len(ca) < 150 or len(cb) < 150 or len(cc) < 150:
        continue
    ylabel = wa[i_year]['label']

    # B&H 1x (reference only)
    bh1_a = (ca.iloc[-1]/ca.iloc[0] - 1)*100
    bh1_b = (cb.iloc[-1]/cb.iloc[0] - 1)*100
    bh1_c = (cc.iloc[-1]/cc.iloc[0] - 1)*100

    yd = {'label': ylabel, 'bh1_a': bh1_a, 'bh1_b': bh1_b, 'bh1_c': bh1_c}

    # B&H same leverage
    for lev in LEVERAGES:
        v_ko_a = bh_levered(ca, lev)
        v_ko_b = bh_levered(cb, lev)
        v_ko_c = bh_levered(cc, lev)
        yd[f'bh_lev_a_{lev}'] = v_ko_a
        yd[f'bh_lev_b_{lev}'] = v_ko_b
        yd[f'bh_lev_c_{lev}'] = v_ko_c

    # Rotation scan
    for lev in LEVERAGES:
        for th in THRESHOLDS:
            v, ko, rots = rotation_3stock(ca, cb, cc, lev, th)
            yd[(lev, th)] = (v, ko, rots)

    all_years.append(yd)

n_years = len(all_years)

# ── TABLE 1: Annual Results ──
print(f"\n  TABLE 1: Annual 3-Stock Rotation — Best 3x, 5x, 6x vs B&H Same Leverage")
hdr = f"  {'Year':<10} | {'ORCL 1x':>7} {'MSFT 1x':>7} {'AMZN 1x':>7} | {'3x Best Th':>10} {'3x Rot $':>10} {'3x #':>5} {'3x KO':>6} | {'5x Best Th':>10} {'5x Rot $':>10} {'5x #':>5} {'5x KO':>6} | {'6x Best Th':>10} {'6x Rot $':>10} {'6x #':>5} {'6x KO':>6} | Winner"
print(hdr)
print(f"  {'-'*len(hdr)}")

for yd in all_years:
    best_3 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
    best_5 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
    best_6 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}

    for th in THRESHOLDS:
        for lev, bk in [(3, best_3), (5, best_5), (6, best_6)]:
            v, ko, rots = yd[(lev, th)]
            if not ko and v > bk['val']:
                bk['val'] = v; bk['th'] = th; bk['rots'] = rots; bk['ko'] = False
            elif ko and bk['ko'] and v > bk['val']:
                bk['val'] = v; bk['th'] = th; bk['rots'] = rots

    # Find winner among 3x BH and 3x rotation
    bh_keys = [f'bh_lev_a_{lev}' for lev in LEVERAGES]  # placeholder
    candidates_3x = []
    if not best_3['ko']: candidates_3x.append(('Rot3x', best_3['val']))
    bh3_keys = ['bh_lev_a_3', 'bh_lev_b_3', 'bh_lev_c_3']
    for j, t in enumerate(TICKERS):
        v, ko = yd[bh3_keys[j]]
        if not ko: candidates_3x.append((f'BH_{t}3x', v))
    winner_3x = max(candidates_3x, key=lambda x: x[1])[0] if candidates_3x else 'ALL KO'

    ko3 = "KO!" if best_3['ko'] else "OK"
    ko5 = "KO!" if best_5['ko'] else "OK"
    ko6 = "KO!" if best_6['ko'] else "OK"
    print(f"  {yd['label']:<10} | {yd['bh1_a']:>+6.0f}% {yd['bh1_b']:>+6.0f}% {yd['bh1_c']:>+6.0f}% | {best_3['th']:>8.0%} ${best_3['val']:>9,.0f} {best_3['rots']:>4} {ko3:>6} | {best_5['th']:>8.0%} ${best_5['val']:>9,.0f} {best_5['rots']:>4} {ko5:>6} | {best_6['th']:>8.0%} ${best_6['val']:>9,.0f} {best_6['rots']:>4} {ko6:>6} | {winner_3x:>12}")

# ── TABLE 2: KO Rate by Threshold ──
print(f"\n  TABLE 2: KO Rate by Threshold & Leverage ({n_years} years)")
print(f"  {'Threshold':>10} | {'1x KO':>7} {'2x KO':>7} {'3x KO':>7} {'4x KO':>7} {'5x KO':>7} {'6x KO':>7}")
print(f"  {'-'*10}-+-{'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7}")
for th in THRESHOLDS:
    parts = [f"{th:>8.0%}   |"]
    for lev in LEVERAGES:
        n_ko = sum(1 for yd in all_years if yd[(lev, th)][1])
        parts.append(f" {n_ko:>4}/{n_years}")
    print("".join(parts))

# ── TABLE 3: Avg Final $ by Threshold & Leverage (survivors) ──
print(f"\n  TABLE 3: Avg Final $ by Threshold & Leverage (surviving years only)")
print(f"  {'Threshold':>10} | {'1x Avg':>10} {'2x Avg':>10} {'3x Avg':>10} {'4x Avg':>10} {'5x Avg':>10} {'6x Avg':>10}")
print(f"  {'-'*10}-+-{'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
for th in THRESHOLDS:
    parts = [f"{th:>8.0%}   |"]
    for lev in LEVERAGES:
        vals = [yd[(lev, th)][0] for yd in all_years if not yd[(lev, th)][1]]
        avg_v = np.mean(vals) if vals else 0
        parts.append(f" ${avg_v:>9,.0f}")
    print("".join(parts))

# ── TABLE 4: FAIR COMPARISON — Rotation vs Same-Leverage B&H ──
print(f"\n{'='*150}")
print(f"  FAIR COMPARISON: 3-Stock Rotation vs Same-Leverage B&H (each stock at same lev)")
print(f"{'='*150}")

for lev in [3, 5, 6]:
    print(f"\n  ── {lev}x Leverage ──")
    print(f"  {'Threshold':>10} | {'Rot KO':>7} | {'vs ORCL '+str(lev)+'x':>13} {'vs MSFT '+str(lev)+'x':>13} {'vs AMZN '+str(lev)+'x':>13} | {'vs WORSE BH':>12} {'vs BETTER BH':>13} | {'Avg Rot $':>10}")
    print(f"  {'-'*10}-+-{'-'*7}-+-{'-'*13} {'-'*13} {'-'*13}-+-{'-'*12} {'-'*13}-+-{'-'*10}")

    for th in THRESHOLDS:
        rot_wins_orcl = 0; rot_wins_msft = 0; rot_wins_amzn = 0
        rot_wins_worse = 0; rot_wins_better = 0
        both_survive = 0
        surv_vals = []

        for yd in all_years:
            v_rot, ko_rot, _ = yd[(lev, th)]
            if ko_rot: continue
            surv_vals.append(v_rot)

            # Collect same-leverage BH values for 3 stocks
            bh_vals = []
            bh_kos = []
            for ticker_idx in range(3):
                key = f'bh_lev_{chr(97+ticker_idx)}_{lev}'
                v, ko = yd[key]
                bh_vals.append(v)
                bh_kos.append(ko)

            surviving_bh = [bh_vals[j] for j in range(3) if not bh_kos[j]]
            if not surviving_bh:
                continue
            both_survive += 1

            if v_rot > bh_vals[0] and not bh_kos[0]: rot_wins_orcl += 1
            if v_rot > bh_vals[1] and not bh_kos[1]: rot_wins_msft += 1
            if v_rot > bh_vals[2] and not bh_kos[2]: rot_wins_amzn += 1

            if v_rot > min(surviving_bh): rot_wins_worse += 1
            if v_rot > max(surviving_bh): rot_wins_better += 1

        rot_ko = sum(1 for yd in all_years if yd[(lev, th)][1])
        avg_surv = np.mean(surv_vals) if surv_vals else 0

        print(f"  {th:>8.0%}   | {rot_ko:>4}/{n_years} | {rot_wins_orcl:>4}/{both_survive:<8} {rot_wins_msft:>4}/{both_survive:<8} {rot_wins_amzn:>4}/{both_survive:<8} | {rot_wins_worse:>4}/{both_survive:<7} {rot_wins_better:>4}/{both_survive:<8} | ${avg_surv:>9,.0f}")

# ── SUMMARY ──
print(f"\n{'='*150}")
print(f"  SUMMARY: Best Threshold per Leverage")
print(f"{'='*150}")
print(f"  {'Leverage':>8} | {'Best Th':>8} {'Avg Sur $':>10} {'KO Rate':>8} | {'Beat Worse':>10} {'Beat Better':>10} | {'Verdict':>20}")
print(f"  {'-'*8}-+-{'-'*8} {'-'*10} {'-'*8}-+-{'-'*10} {'-'*10}-+-{'-'*20}")
for lev in LEVERAGES:
    best_th = 0; best_avg = 0; best_bw = 0; best_bb = 0
    for th in THRESHOLDS:
        surv = [yd[(lev, th)][0] for yd in all_years if not yd[(lev, th)][1]]
        avg_v = np.mean(surv) if surv else 0
        if avg_v > best_avg:
            best_avg = avg_v; best_th = th

            # Recompute fair comparison for this th
            bw = 0; bb = 0; bs = 0
            for yd in all_years:
                v_rot, ko_rot, _ = yd[(lev, th)]
                if ko_rot: continue
                bh_vals = []
                bh_kos = []
                for ticker_idx in range(3):
                    key = f'bh_lev_{chr(97+ticker_idx)}_{lev}'
                    v, ko = yd[key]
                    bh_vals.append(v)
                    bh_kos.append(ko)
                surviving_bh = [bh_vals[j] for j in range(3) if not bh_kos[j]]
                if not surviving_bh: continue
                bs += 1
                if v_rot > min(surviving_bh): bw += 1
                if v_rot > max(surviving_bh): bb += 1
            best_bw = bw; best_bb = bb

    n_ko = sum(1 for yd in all_years if yd[(lev, best_th)][1])
    if best_avg > 0:
        bw_ratio = best_bw / max(bs, 1)
        if bw_ratio >= 0.7: verdict = "★ Rotation adds value"
        elif bw_ratio >= 0.5: verdict = "△ Marginal"
        else: verdict = "✗ No benefit"
    else:
        verdict = "ALL KO"

    print(f"  {lev:>8}x | {best_th:>8.0%} ${best_avg:>9,.0f} {n_ko:>5}/{n_years} | {best_bw:>4}/{bs:<5} {best_bb:>4}/{bs:<5} | {verdict:>20}")

# ── CHART ──
print(f"\n  Generating chart...")
fig, axes = plt.subplots(2, 3, figsize=(22, 12))
fig.suptitle('3-Stock Rotation: ORCL + MSFT + AMZN\nThreshold & Leverage Scan | 2016–2026 Annual Rolling',
             fontsize=14, color='white', fontweight='bold', y=0.98)

COLORS = {1: '#888888', 2: '#4ecdc4', 3: '#00d4aa', 4: '#ffd93d', 5: '#ff6b6b', 6: '#ff4444'}

for col_idx, metric_type in enumerate(['avg_value', 'ko_rate', 'vs_worse_bh']):
    for row_idx, lev_group in enumerate([[1,2,3], [4,5,6]]):
        ax = axes[row_idx, col_idx]
        x = np.arange(len(THRESHOLDS))

        for lev in lev_group:
            if metric_type == 'avg_value':
                vals = []
                for th in THRESHOLDS:
                    surv = [yd[(lev, th)][0] for yd in all_years if not yd[(lev, th)][1]]
                    vals.append(np.mean(surv) if surv else 0)
                ax.plot(x, vals, 'o-', color=COLORS[lev], linewidth=2, label=f'{lev}x', markersize=5)
                ax.set_ylabel('Avg Final $')
                ax.set_title(f'Avg Return (survivors) — Lev {lev_group[0]}-{lev_group[-1]}x', color='white')

            elif metric_type == 'ko_rate':
                vals = [sum(1 for yd in all_years if yd[(lev, th)][1]) / n_years * 100 for th in THRESHOLDS]
                ax.plot(x, vals, 'o-', color=COLORS[lev], linewidth=2, label=f'{lev}x', markersize=5)
                ax.set_ylabel('KO Rate (%)')
                ax.set_title(f'Knock-Out Rate — Lev {lev_group[0]}-{lev_group[-1]}x', color='white')
                ax.set_ylim(-5, 105)

            else:  # vs_worse_bh
                vals = []
                for th in THRESHOLDS:
                    bw = 0; bs = 0
                    for yd in all_years:
                        v_rot, ko_rot, _ = yd[(lev, th)]
                        if ko_rot: continue
                        bh_vals = []; bh_kos = []
                        for ti in range(3):
                            key = f'bh_lev_{chr(97+ti)}_{lev}'
                            v, ko = yd[key]
                            bh_vals.append(v); bh_kos.append(ko)
                        sv = [bh_vals[j] for j in range(3) if not bh_kos[j]]
                        if not sv: continue
                        bs += 1
                        if v_rot > min(sv): bw += 1
                    vals.append(bw/max(bs,1)*100)
                ax.plot(x, vals, 'o-', color=COLORS[lev], linewidth=2, label=f'{lev}x', markersize=5)
                ax.set_ylabel('Beat Worse BH (%)')
                ax.set_title(f'Beat Worse Same-Lev BH — Lev {lev_group[0]}-{lev_group[-1]}x', color='white')
                ax.axhline(y=50, color='gray', linestyle='--', alpha=0.5)
                ax.set_ylim(-5, 105)

        ax.set_xticks(x)
        ax.set_xticklabels([f'{t:.0%}' for t in THRESHOLDS], fontsize=7)
        ax.legend(fontsize=7, ncol=3, loc='upper left')
        ax.grid(axis='y', alpha=0.3)
        if metric_type == 'avg_value':
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'${y:,.0f}'))
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:.0f}%'))

plt.tight_layout(rect=[0, 0, 1, 0.95])
chart_path = r"C:\AI\cc\stock\image\rotation_3stock_scan.png"
plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"  Chart saved: {chart_path}")
print(f"\n{'='*150}")
print("  Done.")
