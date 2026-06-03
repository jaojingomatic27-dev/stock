# -*- coding: utf-8 -*-
"""Chart: 3x 20% Rotation vs Buy&Hold Stocks, Annual Comparison"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

plt.rcParams.update({
    'font.size': 10, 'axes.titlesize': 13, 'axes.labelsize': 11,
    'figure.facecolor': '#1a1a2e', 'axes.facecolor': '#16213e',
    'axes.edgecolor': '#666', 'axes.labelcolor': '#ccc', 'text.color': '#ccc',
    'xtick.color': '#999', 'ytick.color': '#999', 'grid.color': '#333355',
    'grid.alpha': 0.5, 'legend.facecolor': '#1a1a2e', 'legend.edgecolor': '#446',
})

def load(ticker):
    path = rf"C:\AI\cc\stock\{ticker}_2016_daily.csv"
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

# ── Compute ──
pairs = [
    ('NVDA', 'MU', '#00d4aa', '#ff6b6b'),
    ('GOOGL', 'AMZN', '#4ecdc4', '#ffd93d'),
]

all_data = {}
for ta, tb, ca, cb in pairs:
    ca_full = load(ta); cb_full = load(tb)
    wa = annual_windows(ca_full); wb = annual_windows(cb_full)

    years, bh_a, bh_b, rot = [], [], [], []
    for wa_i, wb_i in zip(wa, wb):
        if len(wa_i['slice']) < 150: continue
        years.append(wa_i['label'])
        bh_a.append((wa_i['slice'].iloc[-1]/wa_i['slice'].iloc[0] - 1)*100)
        bh_b.append((wb_i['slice'].iloc[-1]/wb_i['slice'].iloc[0] - 1)*100)
        v, ko, _ = rotation_single(wa_i['slice'], wb_i['slice'], 3, 0.20)
        rot_ret = (v/1000 - 1)*100 if not ko else -100
        rot.append(rot_ret)

    all_data[f'{ta}-{tb}'] = {
        'years': years, 'bh_a': bh_a, 'bh_b': bh_b, 'rot': rot,
        'ta': ta, 'tb': tb, 'ca': ca, 'cb': cb
    }

# ── Chart ──
fig, axes = plt.subplots(2, 1, figsize=(16, 12))
fig.suptitle('3x Leverage + 20% DD Rotation vs Buy & Hold Stocks\nAnnual Comparison: 2016-2026',
             fontsize=15, color='white', fontweight='bold', y=0.98)

for ax, (key, d) in zip(axes, all_data.items()):
    x = np.arange(len(d['years']))
    w = 0.25

    b1 = ax.bar(x - w, d['bh_a'], w, color=d['ca'], alpha=0.7, edgecolor='white', linewidth=0.5, label=f'{d["ta"]} B&H (1x)')
    b2 = ax.bar(x, d['bh_b'], w, color=d['cb'], alpha=0.7, edgecolor='white', linewidth=0.5, label=f'{d["tb"]} B&H (1x)')
    b3 = ax.bar(x + w, d['rot'], w, color='#ffd700', alpha=0.9, edgecolor='white', linewidth=1.5, label='Rotation 3x 20%')

    # Value labels on rotation bars
    for i, (v, ko_flag) in enumerate(zip(d['rot'], [v < -99 for v in d['rot']])):
        ypos = v + (5 if v >= 0 else -8)
        txt = 'KO!' if v <= -99 else f'{v:+.0f}%'
        color = '#ff4444' if v <= -99 else '#ffd700'
        ax.text(x[i] + w, ypos, txt, ha='center', fontsize=6.5, color=color, fontweight='bold', rotation=90)

    # Value labels on BH bars
    for i, v in enumerate(d['bh_a']):
        if abs(v) > 1000:
            txt = f'{v:+.0f}%'
            ax.text(x[i] - w, 0, txt, ha='center', fontsize=5.5, color=d['ca'], fontweight='bold', rotation=90, va='bottom')
    for i, v in enumerate(d['bh_b']):
        if abs(v) > 1000:
            ax.text(x[i], 0, txt, ha='center', fontsize=5.5, color=d['cb'], fontweight='bold', rotation=90, va='bottom')

    ax.set_xticks(x)
    ax.set_xticklabels(d['years'], fontsize=9)
    ax.set_ylabel('Return (%)')
    ax.set_title(f'{d["ta"]} - {d["tb"]} Pair', color='white', fontweight='bold')
    ax.legend(fontsize=9, loc='upper left')
    ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)
    ax.axhline(y=-100, color='#ff4444', linestyle='--', alpha=0.4, linewidth=1)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda y, _: f'{y:+.0f}%'))
    ax.grid(axis='y', alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.94])
path = r"C:\AI\cc\stock\chart_annual_rotation_vs_bh.png"
plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"Chart saved: {path}")
