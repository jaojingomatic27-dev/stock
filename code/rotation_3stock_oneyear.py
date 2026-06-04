# -*- coding: utf-8 -*-
"""3-Stock Rotation: ORCL+MSFT+AMZN — 2025-2026 single year detail"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
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

TICKERS = ['ORCL', 'MSFT', 'AMZN']
STOCK_COLORS = {'ORCL': '#00d4aa', 'MSFT': '#4ecdc4', 'AMZN': '#ffd93d'}
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [1, 2, 3, 4, 5, 6]
INVEST_PER = 1000.0; TOTAL = 3000.0

def load(t):
    df = pd.read_csv(rf'C:\AI\cc\stock\data\{t}_2016_daily.csv', header=[0,1], index_col=0, parse_dates=True)
    return df[('Close', t)].dropna()

def get_recent_year(close):
    """Get the most recent June-to-June year slice."""
    end_d = close.index[-1]
    te = pd.Timestamp(year=end_d.year, month=6, day=1)
    ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
    ei = close.index.get_indexer([te], method='nearest')[0]
    si = close.index.get_indexer([ts], method='nearest')[0]
    return close.iloc[si:ei+1], f"{ts.year}-{te.year}"

def rotation_3stock(close_a, close_b, close_c, lev, th):
    aligned = pd.DataFrame({'a': close_a, 'b': close_b, 'c': close_c}).dropna()
    ra = aligned['a'].pct_change().fillna(0).values
    rb = aligned['b'].pct_change().fillna(0).values
    rc = aligned['c'].pct_change().fillna(0).values
    n = len(aligned)
    vals = np.array([INVEST_PER]*3, dtype=float)
    peaks = vals.copy(); rots = 0
    equity = np.zeros((n, 4))  # col 0-2: each pos, col 3: total
    equity[0, :3] = vals; equity[0, 3] = TOTAL
    history = []  # record rotation events

    for i in range(1, n):
        vals[0] *= (1+lev*ra[i]); vals[1] *= (1+lev*rb[i]); vals[2] *= (1+lev*rc[i])
        vals = np.maximum(vals, 0)
        total = vals.sum()
        equity[i, :3] = vals; equity[i, 3] = total

        if total <= TOTAL*0.05:
            return 0, True, rots, equity[:i+1], history

        for j in range(3):
            if vals[j] > peaks[j]: peaks[j] = vals[j]

        breached = [j for j in range(3) if peaks[j] > 0 and (vals[j]-peaks[j])/peaks[j] <= -th]
        if not breached: continue

        cash = sum(vals[j] for j in breached)
        for j in breached:
            names = TICKERS
            hist_vals = [equity[i, k] for k in range(3)]
            history.append({
                'day': i, 'date': aligned.index[i],
                'sold': [TICKERS[j] for j in breached],
                'cash': cash,
                'remaining_vals': [equity[i, k] for k in range(3)],
                'holding_values': hist_vals,
            })
            vals[j] = 0.0; peaks[j] = 0.0; rots += 1
        survivors = [j for j in range(3) if j not in breached]
        if not survivors: return 0, True, rots, equity[:i+1], history
        per = cash / len(survivors)
        for j in survivors: vals[j] += per; peaks[j] = vals[j]

        # Update equity after redistribution
        equity[i, :3] = vals; equity[i, 3] = vals.sum()

    return vals.sum(), False, rots, equity, history

def bh_levered(close, lev):
    val = INVEST_PER; equity = [val]
    rets = close.pct_change().fillna(0).values[1:]
    for r in rets:
        val *= (1+lev*r)
        equity.append(max(val, 0))
        if val < TOTAL*0.05/3: return 0, True, np.array(equity)
    return val, False, np.array(equity)

# ── Get 2025-2026 data ──
print("Loading 2025-2026 data...")
ca, ylabel = get_recent_year(load('ORCL'))
cb, _ = get_recent_year(load('MSFT'))
cc, _ = get_recent_year(load('AMZN'))
aligned = pd.DataFrame({'a': ca, 'b': cb, 'c': cc}).dropna()
ca, cb, cc = aligned['a'], aligned['b'], aligned['c']

bh1_a = (ca.iloc[-1]/ca.iloc[0]-1)*100
bh1_b = (cb.iloc[-1]/cb.iloc[0]-1)*100
bh1_c = (cc.iloc[-1]/cc.iloc[0]-1)*100

print(f"  Period: {ca.index[0].date()} ~ {ca.index[-1].date()} ({len(ca)} trading days)")
print(f"  ORCL 1x: {bh1_a:+.1f}% | MSFT 1x: {bh1_b:+.1f}% | AMZN 1x: {bh1_c:+.1f}%")

# ── SCAN ──
print(f"\n{'='*120}")
print(f"  3-STOCK ROTATION: {ylabel} — All Threshold x Leverage (${TOTAL:,.0f} total)")
print(f"{'='*120}")

print(f"\n  {'Lev':<4} | {'Threshold':>10} {'Rot Final':>10} {'Rot %':>8} {'#Rot':>5} {'KO':>5} | {'BH ORCL':>10} {'BH MSFT':>10} {'BH AMZN':>10} | {'vs Worst':>9} {'vs Best':>9} | {'Best/Worst':>14}")
print(f"  {'-'*4}-+-{'-'*10} {'-'*10} {'-'*8} {'-'*5} {'-'*5}-+-{'-'*10} {'-'*10} {'-'*10}-+-{'-'*9} {'-'*9}-+-{'-'*14}")

best_overall_val = 0; best_overall_key = (0, 0)

for lev in LEVERAGES:
    # BH same-leverage
    bh_a, ko_a, eq_a = bh_levered(ca, lev)
    bh_b, ko_b, eq_b = bh_levered(cb, lev)
    bh_c, ko_c, eq_c = bh_levered(cc, lev)
    bh_a_pct = (bh_a/INVEST_PER-1)*100 if not ko_a else float('nan')
    bh_b_pct = (bh_b/INVEST_PER-1)*100 if not ko_b else float('nan')
    bh_c_pct = (bh_c/INVEST_PER-1)*100 if not ko_c else float('nan')

    bh_vals = []
    if not ko_a: bh_vals.append(bh_a)
    if not ko_b: bh_vals.append(bh_b)
    if not ko_c: bh_vals.append(bh_c)

    for th in THRESHOLDS:
        val, ko, rots, eq, history = rotation_3stock(ca, cb, cc, lev, th)
        ret_pct = (val/TOTAL - 1)*100 if not ko else float('nan')

        # vs same-leverage BH
        vs_worst = 'N/A'; vs_best = 'N/A'
        if not ko and bh_vals:
            if val > min(bh_vals): vs_worst = 'Win'
            else: vs_worst = 'Lose'
            if val > max(bh_vals): vs_best = 'Win'
            else: vs_best = 'Lose'
        elif ko:
            vs_worst = 'KO'; vs_best = 'KO'

        # Which BH is best/worst
        best_bh = max(bh_vals) if bh_vals else 0
        worst_bh = min(bh_vals) if bh_vals else 0
        best_bh_ticker = [t for j,t in enumerate(TICKERS) if not [ko_a,ko_b,ko_c][j] and [bh_a,bh_b,bh_c][j]==best_bh][0] if bh_vals else '-'
        worst_bh_ticker = [t for j,t in enumerate(TICKERS) if not [ko_a,ko_b,ko_c][j] and [bh_a,bh_b,bh_c][j]==worst_bh][0] if bh_vals else '-'

        marker = ''
        if not ko and val > best_overall_val:
            best_overall_val = val; best_overall_key = (lev, th)
            marker = ' <<'

        ko_s = 'KO!' if ko else 'OK'
        bh_a_s = f"${bh_a:,.0f}" if not ko_a else 'KO'
        bh_b_s = f"${bh_b:,.0f}" if not ko_b else 'KO'
        bh_c_s = f"${bh_c:,.0f}" if not ko_c else 'KO'

        print(f"  {lev:<4}x | {th:>8.0%}   ${val:>9,.0f} {ret_pct:>+7.1f}% {rots:>4} {ko_s:>5} | {bh_a_s:>10} {bh_b_s:>10} {bh_c_s:>10} | {vs_worst:>9} {vs_best:>9} | {best_bh_ticker}/{worst_bh_ticker}{marker}")

print(f"\n  ★ BEST OVERALL: {best_overall_key[0]}x / {best_overall_key[1]:.0%}  →  ${best_overall_val:,.0f} ({(best_overall_val/TOTAL-1)*100:+.1f}%)")

# ── CHART: Best 3x scenario — detailed equity curves ──
print(f"\n  Generating chart...")

# Pick best 3x threshold for the chart
best_3x_th = 0; best_3x_val = 0
for th in THRESHOLDS:
    val, ko, rots, eq, history = rotation_3stock(ca, cb, cc, 3, th)
    if not ko and val > best_3x_val:
        best_3x_val = val; best_3x_th = th; best_3x_eq = eq; best_3x_history = history

_, _, _, eq_rot, history = rotation_3stock(ca, cb, cc, 3, best_3x_th)

fig, axes = plt.subplots(2, 2, figsize=(18, 12))
fig.suptitle(f'3-Stock Rotation: ORCL + MSFT + AMZN | {ylabel}\n'
             f'3x Leverage / {best_3x_th:.0%} Drawdown Threshold | Start ${INVEST_PER:,.0f} each',
             fontsize=13, color='white', fontweight='bold', y=0.99)

# Panel 1: Stock prices (1x unlevered)
ax = axes[0, 0]
for j, t in enumerate(TICKERS):
    c = [ca, cb, cc][j]
    norm = c / c.iloc[0] * 100
    ax.plot(norm.index, norm.values, color=STOCK_COLORS[t], linewidth=1.5, label=f'{t} ({((c.iloc[-1]/c.iloc[0]-1)*100):+.1f}%)')
ax.set_title('Underlying Stocks (1x, normalized to 100)', color='white')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylabel('Value (base=100)')

# Panel 2: BH 3x equity curves (individual stocks)
ax = axes[0, 1]
for j, t in enumerate(TICKERS):
    c = [ca, cb, cc][j]
    _, ko, eq = bh_levered(c, 3)
    ax.plot(eq, color=STOCK_COLORS[t], linewidth=1.5, alpha=0.7,
            label=f'{t} 3x ({((eq[-1]/INVEST_PER-1)*100):+.1f}%)' + (' KO!' if ko else ''))
ax.axhline(y=INVEST_PER, color='gray', linestyle=':', alpha=0.5)
ax.set_title('Same-Leverage B&H (3x each, $1000 start)', color='white')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylabel('Value ($)')

# Panel 3: Rotation equity + per-position breakdown
ax = axes[1, 0]
dates = aligned.index
# Per-position values
for j, t in enumerate(TICKERS):
    ax.plot(dates, eq_rot[:, j], color=STOCK_COLORS[t], linewidth=0.8, alpha=0.5, label=f'{t} position')
# Total
ax.plot(dates, eq_rot[:, 3], color='#ffd700', linewidth=2.5, label=f'Total ${eq_rot[-1,3]:,.0f} (+{(eq_rot[-1,3]/TOTAL-1)*100:.1f}%)')
ax.axhline(y=TOTAL, color='gray', linestyle=':', alpha=0.5)

# Mark rotation events
for h in history:
    ax.axvline(x=h['date'], color='#ff4444', linestyle='--', alpha=0.3, linewidth=0.8)

ax.set_title(f'Rotation 3x/{best_3x_th:.0%}: {len(history)} rotations', color='white')
ax.legend(fontsize=7); ax.grid(alpha=0.3); ax.set_ylabel('Value ($)')

# Panel 4: Rotation vs BH comparison (all 3x)
ax = axes[1, 1]
# BH 3x for each stock
for j, t in enumerate(TICKERS):
    c = [ca, cb, cc][j]
    _, ko, eq = bh_levered(c, 3)
    final_pct = ((eq[-1]/INVEST_PER-1)*100) if not ko else float('nan')
    lbl = f'{t} 3x BH: ${eq[-1]:,.0f}'
    if not ko: lbl += f' ({final_pct:+.1f}%)'
    else: lbl += ' (KO!)'
    ax.plot(eq, color=STOCK_COLORS[t], linewidth=1.5, alpha=0.7, linestyle='--', label=lbl)
# Rotation total
ax.plot(eq_rot[:, 3], color='#ffd700', linewidth=3, label=f'Rotation: ${eq_rot[-1,3]:,.0f} (+{(eq_rot[-1,3]/TOTAL-1)*100:.1f}%)')
ax.axhline(y=TOTAL, color='gray', linestyle=':', alpha=0.5)
ax.set_title('Rotation vs Same-Leverage B&H', color='white')
ax.legend(fontsize=8); ax.grid(alpha=0.3); ax.set_ylabel('Value ($)')
ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'${y:,.0f}'))

plt.tight_layout(rect=[0, 0, 1, 0.95])
chart_path = r"C:\AI\cc\stock\image\rotation_3stock_oneyear.png"
plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"  Chart saved: {chart_path}")

# ── Print rotation events ──
print(f"\n  ROTATION EVENTS (3x/{best_3x_th:.0%}):")
print(f"  {'#':<3} {'Date':<12} {'Sold':<20} {'Cash':>10} {'ORCL $':>10} {'MSFT $':>10} {'AMZN $':>10} {'Total $':>10}")
print(f"  {'-'*3} {'-'*12} {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
for i, h in enumerate(history, 1):
    vals = [h['holding_values'][k] for k in range(3)]
    total = sum(vals)
    sold_str = ' + '.join(h['sold'])
    print(f"  {i:<3} {h['date'].strftime('%Y-%m-%d'):<12} {sold_str:<20} ${h['cash']:>9,.0f} ${vals[0]:>9,.0f} ${vals[1]:>9,.0f} ${vals[2]:>9,.0f} ${total:>9,.0f}")

print(f"\n  SUMMARY: {ylabel} | {len(history)} rotations | Final ${best_3x_val:,.0f} (+{(best_3x_val/TOTAL-1)*100:.1f}%)")
