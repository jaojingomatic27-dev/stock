# -*- coding: utf-8 -*-
"""Chart: All 6 pairs of 4 stocks — Rotation 3x/20% vs Buy & Hold Stocks
Annual June-to-June windows, 2016-2026. X-axis = year, Y-axis = return %."""
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

# Color palette
PAIR_COLORS = {
    ('NVDA', 'MU'): '#00d4aa',
    ('NVDA', 'GOOGL'): '#4ecdc4',
    ('NVDA', 'AMZN'): '#45b7d1',
    ('MU', 'GOOGL'): '#f9ca24',
    ('MU', 'AMZN'): '#ff6b6b',
    ('GOOGL', 'AMZN'): '#e056a0',
}
STOCK_COLORS = {'NVDA': '#00d4aa', 'MU': '#ff6b6b', 'GOOGL': '#4ecdc4', 'AMZN': '#ffd93d'}

def load(ticker):
    path = rf"C:\AI\cc\stock\data\{ticker}_2016_daily.csv"
    df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
    return df[("Close", ticker)].dropna()

def rotation_single(close_a, close_b, lev, th):
    aligned = pd.DataFrame({'a': close_a, 'b': close_b}).dropna()
    rets_a = aligned['a'].pct_change().fillna(0).values
    rets_b = aligned['b'].pct_change().fillna(0).values
    n = len(aligned)
    val = 1000.0; peak = 1000.0; holding_a = True; rotations = 0
    for i in range(1, n):
        r = rets_a[i] if holding_a else rets_b[i]
        val *= (1 + lev * r)
        if val > peak: peak = val
        if (val - peak) / peak <= -th:
            holding_a = not holding_a; peak = val; rotations += 1
        if val < 50: return 0, True, rotations
    return val, False, rotations

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

# ── Load all stocks once ──
print("Loading data...")
stock_data = {}
stock_windows = {}
for t in TICKERS:
    stock_data[t] = load(t)
    stock_windows[t] = annual_windows(stock_data[t])
    print(f"  {t}: {len(stock_windows[t])} windows, {stock_data[t].index[0].date()} to {stock_data[t].index[-1].date()}")

# ── Compute for all 6 pairs ──
print("\nComputing all 6 pairs...")
all_data = {}
for ta, tb in ALL_PAIRS:
    wa, wb = stock_windows[ta], stock_windows[tb]
    years, bh_a, bh_b, rot_ret, rot_rots, rot_ko = [], [], [], [], [], []
    for wa_i, wb_i in zip(wa, wb):
        if len(wa_i['slice']) < 150 or len(wb_i['slice']) < 150:
            continue
        years.append(wa_i['label'])
        bh_a.append((wa_i['slice'].iloc[-1]/wa_i['slice'].iloc[0] - 1)*100)
        bh_b.append((wb_i['slice'].iloc[-1]/wb_i['slice'].iloc[0] - 1)*100)
        v, ko, rots = rotation_single(wa_i['slice'], wb_i['slice'], LEV, TH)
        r = (v/1000 - 1)*100 if not ko else -100
        rot_ret.append(r)
        rot_rots.append(rots)
        rot_ko.append(ko)
    all_data[(ta, tb)] = {
        'years': years, 'bh_a': bh_a, 'bh_b': bh_b,
        'rot_ret': rot_ret, 'rot_rots': rot_rots, 'rot_ko': rot_ko,
        'ta': ta, 'tb': tb
    }
    n_ko = sum(rot_ko)
    avg_rot = np.mean([r for r,k in zip(rot_ret, rot_ko) if not k]) if n_ko < len(rot_ret) else 0
    print(f"  {ta}-{tb}: {len(years)} years, {n_ko} KO, avg rot ret (survivors) = {avg_rot:+.0f}%")

# ── CHART: 3x2 grid, one pair per subplot ──
fig, axes = plt.subplots(3, 2, figsize=(22, 14))
fig.suptitle(f'All 6 Stock Pairs — Rotation {LEV}x / {TH:.0%} DD vs Buy & Hold (1x)\n'
             'Annual Comparison: June 2016 – June 2026',
             fontsize=15, color='white', fontweight='bold', y=0.99)

for ax, (ta, tb) in zip(axes.flat, ALL_PAIRS):
    d = all_data[(ta, tb)]
    x = np.arange(len(d['years']))
    w = 0.25

    # Bar chart
    b1 = ax.bar(x - w, d['bh_a'], w, color=STOCK_COLORS[ta], alpha=0.7,
                edgecolor='white', linewidth=0.5, label=f'{ta} B&H (1x)')
    b2 = ax.bar(x, d['bh_b'], w, color=STOCK_COLORS[tb], alpha=0.7,
                edgecolor='white', linewidth=0.5, label=f'{tb} B&H (1x)')
    b3 = ax.bar(x + w, d['rot_ret'], w, color='#ffd700', alpha=0.9,
                edgecolor='white', linewidth=1.2, label=f'Rotation {LEV}x {TH:.0%}')

    # Value labels
    for i, v in enumerate(d['rot_ret']):
        ypos = v + (10 if v >= 0 else -15)
        txt = 'KO!' if v <= -99 else f'{v:+.0f}%'
        color = '#ff4444' if v <= -99 else '#ffd700'
        ax.text(x[i] + w, ypos, txt, ha='center', fontsize=5.5, color=color,
                fontweight='bold', rotation=90)

    # Summary box
    n_ko = sum(d['rot_ko'])
    avg_rot_vals = [r for r, k in zip(d['rot_ret'], d['rot_ko']) if not k]
    avg_rot = np.mean(avg_rot_vals) if avg_rot_vals else -100
    avg_rots = np.mean(d['rot_rots'])
    better_a = sum(1 for r, a in zip(d['rot_ret'], d['bh_a']) if r > a)
    better_b = sum(1 for r, b in zip(d['rot_ret'], d['bh_b']) if r > b)
    worse_bh = [min(a,b) for a,b in zip(d['bh_a'], d['bh_b'])]
    beat_worse = sum(1 for r, wb in zip(d['rot_ret'], worse_bh) if r > wb)

    summary = (f"KO: {n_ko}/{len(d['years'])} | Avg Rot: {avg_rot:+.0f}% | "
               f"Avg #Rot: {avg_rots:.0f} | Beat worse: {beat_worse}/{len(d['years'])} | "
               f"Beat {ta}: {better_a}/{len(d['years'])} | Beat {tb}: {better_b}/{len(d['years'])}")
    ax.text(0.5, 0.98, summary, transform=ax.transAxes, fontsize=6.5, color='#aaa',
            ha='center', va='top', bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a2e',
            edgecolor='#446', alpha=0.8))

    ax.set_xticks(x)
    ax.set_xticklabels(d['years'], fontsize=7, rotation=45)
    ax.set_ylabel('Return (%)')
    ax.set_title(f'{ta} ↔ {tb}', color=PAIR_COLORS[(ta,tb)], fontweight='bold', fontsize=11)
    ax.legend(fontsize=7, loc='upper left', ncol=3)
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax.axhline(y=-100, color='#ff4444', linestyle='--', alpha=0.4, linewidth=0.8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:+.0f}%'))
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.96])
chart_path = r"C:\AI\cc\stock\image\chart_6pairs_annual.png"
plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"\nChart saved: {chart_path}")

# ── SUMMARY TABLE ──
print(f"\n{'='*130}")
print(f"  SUMMARY: All 6 Pairs — Rotation {LEV}x / {TH:.0%} DD vs Buy & Hold")
print(f"{'='*130}")
print(f"  {'Pair':<16} | {'Avg Rot':>9} {'Avg BH A':>9} {'Avg BH B':>9} | {'KO Rate':>8} {'Beat Worse':>10} {'Beat A':>7} {'Beat B':>7} | {'Best Year':>18} {'Worst Year':>18}")
print(f"  {'-'*16}-+-{'-'*9} {'-'*9} {'-'*9}-+-{'-'*8} {'-'*10} {'-'*7} {'-'*7}-+-{'-'*18} {'-'*18}")

for ta, tb in ALL_PAIRS:
    d = all_data[(ta, tb)]
    avg_rot_vals = [r for r, k in zip(d['rot_ret'], d['rot_ko']) if not k]
    avg_rot = np.mean(avg_rot_vals) if avg_rot_vals else -100
    avg_bh_a = np.mean(d['bh_a'])
    avg_bh_b = np.mean(d['bh_b'])
    ko_rate = f"{sum(d['rot_ko'])}/{len(d['years'])}"
    worse_bh = [min(a,b) for a,b in zip(d['bh_a'], d['bh_b'])]
    beat_worse = f"{sum(1 for r, wb in zip(d['rot_ret'], worse_bh) if r > wb)}/{len(d['years'])}"
    beat_a = f"{sum(1 for r, a in zip(d['rot_ret'], d['bh_a']) if r > a)}/{len(d['years'])}"
    beat_b = f"{sum(1 for r, b in zip(d['rot_ret'], d['bh_b']) if r > b)}/{len(d['years'])}"

    # Best and worst year for rotation
    best_idx = np.argmax(d['rot_ret'])
    worst_idx = np.argmin(d['rot_ret'])
    best_str = f"{d['years'][best_idx]}: {d['rot_ret'][best_idx]:+.0f}%"
    worst_str = f"{d['years'][worst_idx]}: {d['rot_ret'][worst_idx]:+.0f}%"

    print(f"  {ta:<6}-{tb:<6} | {avg_rot:>+8.0f}% {avg_bh_a:>+8.0f}% {avg_bh_b:>+8.0f}% | {ko_rate:>8} {beat_worse:>10} {beat_a:>7} {beat_b:>7} | {best_str:>18} {worst_str:>18}")

# ── RANKING ──
print(f"\n  RANKING by Average Rotation Return (non-KO years):")
print(f"  {'Rank':<6} {'Pair':<16} {'Avg Rot Ret':>12} {'KO Rate':>8} {'Beat Worse':>10} {'Verdict':>15}")
print(f"  {'-'*70}")
ranked = []
for ta, tb in ALL_PAIRS:
    d = all_data[(ta, tb)]
    avg_vals = [r for r, k in zip(d['rot_ret'], d['rot_ko']) if not k]
    avg = np.mean(avg_vals) if avg_vals else -100
    ko = sum(d['rot_ko'])
    worse = [min(a,b) for a,b in zip(d['bh_a'], d['bh_b'])]
    bw = sum(1 for r, wb in zip(d['rot_ret'], worse) if r > wb)
    ranked.append((ta, tb, avg, ko, bw))
ranked.sort(key=lambda x: x[2], reverse=True)
for i, (ta, tb, avg, ko, bw) in enumerate(ranked, 1):
    verdict = "★ BEST" if i == 1 else ("✓ Good" if avg > 100 else "△ OK" if avg > 0 else "✗ Poor")
    print(f"  {i:<6} {ta:<6}-{tb:<6} {avg:>+11.0f}% {ko:>4}/10 {bw:>5}/10 {verdict:>15}")

print(f"\n{'='*130}")
print("  Done.")
