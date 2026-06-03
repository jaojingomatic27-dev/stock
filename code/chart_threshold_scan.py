# -*- coding: utf-8 -*-
"""Chart: Optimal drawdown threshold for NVDA-MU warrant rotation"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ── Data (from rotation_threshold_scan.py results) ──
thresholds = [15, 20, 25, 30, 35, 40, 50]
results_3x = {
    'final':  [9225, 34831, 5707, 1084, 7307, 23154, 26938],
    'ret':    [822.5, 3383.1, 470.7, 8.4, 630.7, 2215.4, 2593.8],
    'rots':   [21, 12, 8, 4, 4, 4, 1],
}
results_5x = {
    'final':  [197715, 9182, 12152, 131465, 34292, 842, 543],
    'ret':    [19671.5, 818.2, 1115.2, 13046.5, 3329.2, -15.8, -45.7],
    'rots':   [39, 25, 21, 14, 12, 8, 4],
}

# Benchmarks
bh_mu_3x  = 365387
bh_mu_5x  = 2291075
bh_nvda_3x = 2744
bh_nvda_5x = 3009

# ── Style ──
plt.rcParams.update({
    'font.size': 10,
    'axes.titlesize': 13,
    'axes.labelsize': 11,
    'figure.facecolor': '#1a1a2e',
    'axes.facecolor': '#16213e',
    'axes.edgecolor': '#666666',
    'axes.labelcolor': '#cccccc',
    'text.color': '#cccccc',
    'xtick.color': '#999999',
    'ytick.color': '#999999',
    'grid.color': '#333355',
    'grid.alpha': 0.5,
    'legend.facecolor': '#1a1a2e',
    'legend.edgecolor': '#444466',
    'legend.labelcolor': '#cccccc',
})

fig, axes = plt.subplots(2, 2, figsize=(16, 12))
fig.suptitle('Optimal Drawdown Threshold: NVDA-MU Warrant Rotation Strategy\n'
             '2025-06-02 ~ 2026-06-03 | $1,000 Initial | 3x vs 5x Leverage',
             fontsize=15, color='white', fontweight='bold', y=0.98)

colors_3x = '#00d4aa'
colors_5x = '#ff6b6b'
marker_3x = 'D'
marker_5x = 'o'

# ── Panel 1: Final Value vs Threshold ──
ax1 = axes[0, 0]
ax1.plot(thresholds, results_3x['final'], color=colors_3x, marker=marker_3x,
         markersize=10, linewidth=2.5, label='3x Leverage', zorder=5)
ax1.plot(thresholds, results_5x['final'], color=colors_5x, marker=marker_5x,
         markersize=10, linewidth=2.5, label='5x Leverage', zorder=5)

# Highlight best points
best_3x_idx = 1  # 20%
best_5x_idx = 0  # 15%
ax1.scatter([thresholds[best_3x_idx]], [results_3x['final'][best_3x_idx]],
            color=colors_3x, s=300, zorder=10, edgecolors='white', linewidths=2)
ax1.scatter([thresholds[best_5x_idx]], [results_5x['final'][best_5x_idx]],
            color=colors_5x, s=300, zorder=10, edgecolors='white', linewidths=2)
ax1.annotate(f"BEST: 20%\n${results_3x['final'][best_3x_idx]:,}",
             (thresholds[best_3x_idx], results_3x['final'][best_3x_idx]),
             xytext=(27, results_3x['final'][best_3x_idx]*1.3),
             color=colors_3x, fontsize=9, fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=colors_3x, lw=1.5))
ax1.annotate(f"BEST: 15%\n${results_5x['final'][best_5x_idx]:,}",
             (thresholds[best_5x_idx], results_5x['final'][best_5x_idx]),
             xytext=(22, results_5x['final'][best_5x_idx]*1.2),
             color=colors_5x, fontsize=9, fontweight='bold',
             arrowprops=dict(arrowstyle='->', color=colors_5x, lw=1.5))

# Benchmarks
ax1.axhline(y=bh_mu_3x, color=colors_3x, linestyle='--', alpha=0.4, linewidth=1)
ax1.axhline(y=bh_mu_5x, color=colors_5x, linestyle='--', alpha=0.4, linewidth=1)
ax1.text(48, bh_mu_3x*1.3, f'BH MU 3x\n${bh_mu_3x:,.0f}', color=colors_3x, fontsize=7, alpha=0.7)
ax1.text(48, bh_mu_5x*1.1, f'BH MU 5x\n${bh_mu_5x:,.0f}', color=colors_5x, fontsize=7, alpha=0.7)

ax1.set_xlabel('Drawdown Threshold (%)')
ax1.set_ylabel('Final Portfolio Value ($)')
ax1.set_title('Final Value vs Threshold', color='white', fontweight='bold')
ax1.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'${x:,.0f}'))
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_xlim(12, 52)

# ── Panel 2: Total Return % vs Threshold ──
ax2 = axes[0, 1]
x = np.arange(len(thresholds))
width = 0.35
bars1 = ax2.bar(x - width/2, results_3x['ret'], width, color=colors_3x, alpha=0.85, label='3x Leverage', edgecolor='white', linewidth=0.5)
bars2 = ax2.bar(x + width/2, results_5x['ret'], width, color=colors_5x, alpha=0.85, label='5x Leverage', edgecolor='white', linewidth=0.5)

# Value labels on bars
for bar, val in zip(bars1, results_3x['ret']):
    ypos = bar.get_height() + (100 if val >= 0 else -300)
    color = colors_3x if val >= 0 else '#ff4444'
    ax2.text(bar.get_x() + bar.get_width()/2, ypos, f'{val:+.0f}%',
             ha='center', va='bottom' if val >= 0 else 'top', fontsize=7, color=color, fontweight='bold')
for bar, val in zip(bars2, results_5x['ret']):
    ypos = bar.get_height() + (200 if val >= 0 else -400)
    color = colors_5x if val >= 0 else '#ff4444'
    ax2.text(bar.get_x() + bar.get_width()/2, ypos, f'{val:+,.0f}%',
             ha='center', va='bottom' if val >= 0 else 'top', fontsize=7, color=color, fontweight='bold')

# BH reference lines
ax2.axhline(y=(bh_mu_3x/1000-1)*100, color=colors_3x, linestyle=':', alpha=0.5)
ax2.axhline(y=(bh_mu_5x/1000-1)*100, color=colors_5x, linestyle=':', alpha=0.5)

ax2.set_xticks(x)
ax2.set_xticklabels([f'{t}%' for t in thresholds])
ax2.set_ylabel('Total Return (%)')
ax2.set_title('Return % vs Threshold', color='white', fontweight='bold')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3, axis='y')

# ── Panel 3: Number of Rotations vs Threshold ──
ax3 = axes[1, 0]
ax3.plot(thresholds, results_3x['rots'], color=colors_3x, marker=marker_3x,
         markersize=10, linewidth=2.5, label='3x Leverage')
ax3.plot(thresholds, results_5x['rots'], color=colors_5x, marker=marker_5x,
         markersize=10, linewidth=2.5, label='5x Leverage')

# Fill between
ax3.fill_between(thresholds, results_3x['rots'], alpha=0.1, color=colors_3x)
ax3.fill_between(thresholds, results_5x['rots'], alpha=0.1, color=colors_5x)

# Annotate each point with count
for t, r in zip(thresholds, results_3x['rots']):
    ax3.annotate(str(r), (t, r), textcoords="offset points", xytext=(0, 12),
                ha='center', fontsize=8, color=colors_3x, fontweight='bold')
for t, r in zip(thresholds, results_5x['rots']):
    ax3.annotate(str(r), (t, r), textcoords="offset points", xytext=(0, -18),
                ha='center', fontsize=8, color=colors_5x, fontweight='bold')

ax3.set_xlabel('Drawdown Threshold (%)')
ax3.set_ylabel('Number of Rotations')
ax3.set_title('Rotation Frequency vs Threshold', color='white', fontweight='bold')
ax3.legend(loc='upper right')
ax3.grid(True, alpha=0.3)
ax3.set_xlim(12, 52)

# ── Panel 4: Efficiency (Return per Rotation) & Combined Score ──
ax4 = axes[1, 1]

# Normalize both metrics to 0-1 for combined view
eff_3x = [max(r, 0) for r in results_3x['ret']]  # return per rotation
eff_5x = [max(r, 0) for r in results_5x['ret']]

# Plot scatter: x=rotations, y=return, size=final_value
sizes_3x = [max(v/500, 20) for v in results_3x['final']]
sizes_5x = [max(v/500, 20) for v in results_5x['final']]

scatter3 = ax4.scatter(results_3x['rots'], results_3x['ret'],
                       s=sizes_3x, c=colors_3x, alpha=0.7, edgecolors='white',
                       linewidths=1, label='3x Leverage', zorder=5)
scatter5 = ax4.scatter(results_5x['rots'], results_5x['ret'],
                       s=sizes_5x, c=colors_5x, alpha=0.7, edgecolors='white',
                       linewidths=1, label='5x Leverage', zorder=5)

# Label each point with threshold
for i, t in enumerate(thresholds):
    ax4.annotate(f'{t}%', (results_3x['rots'][i], results_3x['ret'][i]),
                xytext=(7, 7), textcoords="offset points", fontsize=7,
                color=colors_3x, alpha=0.9)
    ax4.annotate(f'{t}%', (results_5x['rots'][i], results_5x['ret'][i]),
                xytext=(7, -12), textcoords="offset points", fontsize=7,
                color=colors_5x, alpha=0.9)

# Pareto frontier annotation
ax4.annotate('IDEAL ZONE\n(high return,\nfew rotations)', xy=(5, 2500), fontsize=10,
            color='#ffd700', ha='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1a1a2e', edgecolor='#ffd700', alpha=0.8))

ax4.set_xlabel('Number of Rotations')
ax4.set_ylabel('Total Return (%)')
ax4.set_title('Efficiency Map: Return vs Rotation Count\n(bubble size = final value)', color='white', fontweight='bold')
ax4.legend(loc='lower left')
ax4.grid(True, alpha=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.94])
path = r"C:\AI\cc\stock\image\threshold_scan_chart.png"
plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"Chart saved: {path}")
