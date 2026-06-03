# -*- coding: utf-8 -*-
"""4-Stock Comparison Chart: NVDA, MU, GOOGL, AMZN"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams.update({
    'font.size': 10, 'axes.titlesize': 12, 'axes.labelsize': 10,
    'figure.facecolor': '#1a1a2e', 'axes.facecolor': '#16213e',
    'axes.edgecolor': '#666', 'axes.labelcolor': '#ccc', 'text.color': '#ccc',
    'xtick.color': '#999', 'ytick.color': '#999', 'grid.color': '#333355',
    'grid.alpha': 0.5, 'legend.facecolor': '#1a1a2e', 'legend.edgecolor': '#446',
})

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('4-Stock Leveraged Warrant Analysis: NVDA | MU | GOOGL | AMZN\n'
             '2025-06-02 ~ 2026-06-03 | $1,000 Initial | Daily-Reset Leveraged Model',
             fontsize=14, color='white', fontweight='bold', y=0.98)

colors = {'NVDA': '#00d4aa', 'MU': '#ff6b6b', 'GOOGL': '#4ecdc4', 'AMZN': '#ffd93d'}

# ── Panel 1: Optimal Leverage by Stock ──
ax1 = axes[0, 0]
stocks = ['GOOGL', 'MU', 'NVDA', 'AMZN']
opt_lev = {'GOOGL': 10.0, 'MU': 6.0, 'NVDA': 4.5, 'AMZN': 2.5}
opt_ret = [5918, 286303, 207, 36]
bars = ax1.bar(stocks, [opt_lev[s] for s in stocks], color=[colors[s] for s in stocks], edgecolor='white', alpha=0.85)
ret_map = {'GOOGL': 5918, 'MU': 286303, 'NVDA': 207, 'AMZN': 36}
for bar, s in zip(bars, stocks):
    ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
             f'{opt_lev[s]:.1f}x\n+{ret_map[s]:,.0f}%', ha='center', fontsize=9, fontweight='bold', color='white')
ax1.set_title('Optimal Leverage (Kelly L*)', color='white', fontweight='bold')
ax1.set_ylabel('Leverage Multiplier (x)')
ax1.axhline(y=1, color='gray', linestyle=':', alpha=0.5)
ax1.grid(axis='y', alpha=0.3)

# ── Panel 2: 1-Year Stock Return vs Max Daily Drop ──
ax2 = axes[0, 1]
stock_ret = {'NVDA': 57.2, 'MU': 992.5, 'GOOGL': 113.1, 'AMZN': 21.0}
max_drop = {'NVDA': -5.5, 'MU': -10.9, 'GOOGL': -3.9, 'AMZN': -8.3}
for s in stocks:
    ax2.scatter(max_drop[s], stock_ret[s], s=opt_lev[s]*80, c=colors[s],
                edgecolors='white', linewidths=2, zorder=5, alpha=0.85)
    ax2.annotate(f'{s}\n{opt_lev[s]:.1f}x', (max_drop[s], stock_ret[s]),
                xytext=(5, 5), textcoords='offset points', fontsize=8, color=colors[s], fontweight='bold')
ax2.axhline(y=0, color='gray', alpha=0.5)
ax2.axvline(x=0, color='gray', alpha=0.5)
ax2.set_xlabel('Worst Daily Drop (%)')
ax2.set_ylabel('1-Year Stock Return (%)')
ax2.set_title('Return vs Risk (bubble = optimal leverage)', color='white', fontweight='bold')
ax2.grid(alpha=0.3)

# ── Panel 3: Rotation Strategy Summary (30% DD threshold) ──
ax3 = axes[0, 2]
pairs = ['NVDA-MU\n(earlier)', 'GOOGL-AMZN\n(this run)']
rot_3x = [-4.9, 525.0]  # total return %
rot_5x = [13047, 1005]
x = np.arange(len(pairs))
w = 0.3
ax3.bar(x - w/2, rot_3x, w, color='#00d4aa', alpha=0.8, label='3x Rotation', edgecolor='white')
ax3.bar(x + w/2, rot_5x, w, color='#ff6b6b', alpha=0.8, label='5x Rotation', edgecolor='white')
for i, (v3, v5) in enumerate(zip(rot_3x, rot_5x)):
    ax3.text(i - w/2, v3 + 20, f'{v3:+.0f}%', ha='center', fontsize=7, color='#00d4aa', fontweight='bold')
    ax3.text(i + w/2, v5 + 20, f'{v5:+.0f}%', ha='center', fontsize=7, color='#ff6b6b', fontweight='bold')
ax3.set_xticks(x)
ax3.set_xticklabels(pairs, fontsize=9)
ax3.set_title('30% DD Rotation Strategy Return', color='white', fontweight='bold')
ax3.legend(fontsize=8)
ax3.grid(axis='y', alpha=0.3)

# ── Panel 4: All Stocks Leverage vs Return Curves ──
ax4 = axes[1, 0]
for ticker in ['NVDA', 'MU', 'GOOGL', 'AMZN']:
    if ticker == 'NVDA':
        levs = np.arange(1, 11, 0.5)
        rets = [57.2, 120.0, 174.4, 207.4, 207.4, 163.3, 70.3, -18.5, -58.5]
        rets = rets + [rets[-1]] * (len(levs) - len(rets))
    elif ticker == 'MU':
        rets_vals = [992.5, 2766, 6438, 36439, 59672, 286303, 264000, 240000, 0]
        rets = rets_vals + [rets_vals[-1]] * (19 - len(rets_vals))
        levs = np.arange(1, 10.5, 0.5)
    elif ticker == 'GOOGL':
        rets = [113.1, 201.5, 318.0, 468.1, 657.1, 889.9, 1170.0, 1499.1, 1876.4, 2298.3, 2757.5, 3243.1, 3740.8, 4233.1, 4700.4, 5121.8, 5477.0, 5747.4, 5917.7]
        levs = np.arange(1, 10.5, 0.5)
    elif ticker == 'AMZN':
        rets = [21.0, 28.7, 33.8, 36.0, 35.1, 31.2, 24.3, 15.0, 3.8, -8.7, -21.9, -35.0, -47.5, -59.0, -69.0, -77.5, -95.0, -95.2, -96.4]
        levs = np.arange(1, 10.5, 0.5)

    ax4.plot(levs[:len(rets)], rets, color=colors[ticker], linewidth=2, marker='.', markersize=4, label=ticker)
    # Mark optimal
    opt_idx = int((opt_lev[ticker] - 1) / 0.5)
    if opt_idx < len(rets):
        ax4.scatter([opt_lev[ticker]], [rets[opt_idx]], color=colors[ticker], s=120, zorder=10, edgecolors='white')

ax4.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
ax4.set_xlabel('Leverage (x)')
ax4.set_ylabel('Total Return (%)')
ax4.set_title('Leverage vs Return Curve', color='white', fontweight='bold')
ax4.legend(fontsize=8, loc='upper left')
ax4.grid(alpha=0.3)

# ── Panel 5: Threshold Scan Comparison (optimal thresholds) ──
ax5 = axes[1, 1]
pairs_labels = ['NVDA-MU', 'GOOGL-AMZN']
best_3x_th = [20, 25]  # optimal threshold %
best_5x_th = [15, 40]
best_3x_val = [34831, 9653]
best_5x_val = [197715, 29274]
x5 = np.arange(len(pairs_labels))
w5 = 0.3
ax5.bar(x5 - w5/2, best_3x_th, w5, color='#00d4aa', alpha=0.8, edgecolor='white')
ax5.bar(x5 + w5/2, best_5x_th, w5, color='#ff6b6b', alpha=0.8, edgecolor='white')
for i in range(2):
    ax5.text(i - w5/2, best_3x_th[i] + 1, f'{best_3x_th[i]}%\n${best_3x_val[i]:,.0f}',
             ha='center', fontsize=7, color='#00d4aa', fontweight='bold')
    ax5.text(i + w5/2, best_5x_th[i] + 1, f'{best_5x_th[i]}%\n${best_5x_val[i]:,.0f}',
             ha='center', fontsize=7, color='#ff6b6b', fontweight='bold')
ax5.set_xticks(x5)
ax5.set_xticklabels(pairs_labels, fontsize=9)
ax5.set_title('Best Drawdown Threshold\n(rotation strategy)', color='white', fontweight='bold')
ax5.set_ylabel('Threshold (%)')
ax5.legend(['3x Optimal', '5x Optimal'], fontsize=8)
ax5.grid(axis='y', alpha=0.3)

# ── Panel 6: Summary Table ──
ax6 = axes[1, 2]
ax6.axis('off')
ax6.set_xlim(0, 10)
ax6.set_ylim(0, 10)

table_data = [
    ['Stock', '1Y Ret', 'Opt Lev', 'Lev Ret', 'Best DD Th', 'Rot vs BH?'],
    ['GOOGL', '+113%', '10.0x', '+5,918%', '3x:25% 5x:40%', 'BH wins'],
    ['MU', '+993%', '6.0x', '+286,303%', '3x:20% 5x:15%', 'BH wins'],
    ['NVDA', '+57%', '4.5x', '+207%', '3x:20% 5x:15%', 'BH wins'],
    ['AMZN', '+21%', '2.5x', '+36%', '3x:25% 5x:40%', 'BH wins'],
]

table = ax6.table(cellText=table_data, cellLoc='center', loc='center',
                  colWidths=[0.12, 0.1, 0.1, 0.15, 0.18, 0.12])
table.auto_set_font_size(False)
table.set_fontsize(8)
for key, cell in table.get_celld().items():
    cell.set_facecolor('#16213e')
    cell.set_edgecolor('#444466')
    cell.set_text_props(color='#cccccc')
    if key[0] == 0:  # Header
        cell.set_facecolor('#2a2a4a')
        cell.set_text_props(color='white', fontweight='bold')
    # Color code tickers
    if key[1] == 1 and key[0] == 0:  # GOOGL row
        cell.set_text_props(color=colors['GOOGL'])
    elif key[1] == 2 and key[0] == 0:
        cell.set_text_props(color=colors['MU'])
    elif key[1] == 3 and key[0] == 0:
        cell.set_text_props(color=colors['NVDA'])
    elif key[1] == 4 and key[0] == 0:
        cell.set_text_props(color=colors['AMZN'])

ax6.set_title('Master Comparison', color='white', fontweight='bold', y=0.95)

plt.tight_layout(rect=[0, 0, 1, 0.94])
path = r"C:\AI\cc\stock\image\chart_4stock_comparison.png"
plt.savefig(path, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
plt.close()
print(f"Chart saved: {path}")
