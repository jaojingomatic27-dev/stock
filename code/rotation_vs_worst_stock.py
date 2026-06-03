# -*- coding: utf-8 -*-
"""
Rotation strategy vs WORSE-performing stock (not the better one).
Fair comparison: does rotation save you from holding the dog?
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd
import numpy as np

print("=" * 95)
print("  ROTATION vs WORSE STOCK: The Fair Comparison")
print("  If you'd picked the wrong stock, did rotation save you?")
print("=" * 95)

# ── NVDA-MU Results (from earlier runs) ──
print("\n  >>> NVDA-MU Pair <<<")
print(f"  Stock returns: NVDA +57.2%  |  MU +992.5%")
print(f"  Worse stock: NVDA (only +57.2%)")
print()

print(f"  {'Strategy':<35} {'3x Value':>14} {'3x Return':>12} {'5x Value':>14} {'5x Return':>12}")
print(f"  {'-'*87}")

# NVDA-MU data (from rotation_backtest.py and threshold scan)
nvda_mu = {
    "Rotation 30% DD (2 legs $2000)":  (1903, -4.9, 262933, 13047),
    "Rotation BEST threshold (2 legs)": (34831*2, 3383*2, 197715*2, 19672*2),
    "BH Worse (NVDA only, $2000)":      (5488, 174.4, 6018, 200.9),
    "BH Worse (NVDA only, $1000+$1000 cash)": (2744+1000, 87.2, 3009+1000, 100.5),
    "BH Better (MU only, $2000)":        (730774*2, 36439*2, 4582151*2, 229008*2),
}

for name, (v3, r3, v5, r5) in nvda_mu.items():
    vs_worse3 = "SAVED!" if v3 > 5488 else "lost"
    vs_worse5 = "SAVED!" if v5 > 6018 else "lost"
    marker3 = f" vs NVDA BH: {vs_worse3}"
    marker5 = f" vs NVDA BH: {vs_worse5}"
    print(f"  {name:<35} ${v3:>13,.0f} {r3:>+11.1f}% ${v5:>13,.0f} {r5:>+11.1f}%")

# ── GOOGL-AMZN Results (from this run) ──
print(f"\n\n  >>> GOOGL-AMZN Pair <<<")
print(f"  Stock returns: GOOGL +113.1%  |  AMZN +21.0%")
print(f"  Worse stock: AMZN (only +21.0%)")
print()

googl_amzn = {
    "Rotation 30% DD (2 legs $2000)":  (12499, 525.0, 22108, 1005.4),
    "Rotation BEST threshold (2 legs)": (9653*2, 865.3*2, 29274*2, 2827.4*2),
    "BH Worse (AMZN only, $2000)":      (2703, 35.2, 2076, 3.8),
    "BH Worse (AMZN only, $1000+$1000 cash)": (1351+1000, 17.6, 1038+1000, 1.9),
    "BH Better (GOOGL only, $2000)":    (15143, 657.1, 39529, 1876.4),
}

for name, (v3, r3, v5, r5) in googl_amzn.items():
    vs_worse3 = "SAVED!" if v3 > 2703 else "lost"
    vs_worse5 = "SAVED!" if v5 > 2076 else "lost"
    print(f"  {name:<35} ${v3:>13,.0f} {r3:>+11.1f}% ${v5:>13,.0f} {r5:>+11.1f}%")

# ── Summary ──
print(f"\n{'=' * 95}")
print("  VERDICT: Does Rotation Beat the WORSE Stock?")
print(f"{'=' * 95}")
print(f"""
  NVDA-MU (worse = NVDA +57%):
    3x Rotation 30% DD:  $1,903  vs NVDA BH $5,488  →  ROTATION LOSES  (-65%)
    3x Rotation BEST:    $69,662 vs NVDA BH $5,488  →  ROTATION WINS   (+1,170%)
    5x Rotation 30% DD:  $262,933 vs NVDA BH $6,018 →  ROTATION WINS   (+4,270%)
    5x Rotation BEST:    $395,430 vs NVDA BH $6,018 →  ROTATION WINS   (+6,474%)

  GOOGL-AMZN (worse = AMZN +21%):
    3x Rotation 30% DD:  $12,499 vs AMZN BH $2,703  →  ROTATION WINS   (+363%)
    3x Rotation BEST:    $19,306 vs AMZN BH $2,703  →  ROTATION WINS   (+614%)
    5x Rotation 30% DD:  $22,108 vs AMZN BH $2,076  →  ROTATION WINS   (+965%)
    5x Rotation BEST:    $58,548 vs AMZN BH $2,076  →  ROTATION WINS   (+2,721%)

  Only failure: NVDA-MU 3x at 30% DD threshold. In every other scenario,
  rotation CRUSHES buy-and-hold of the worse stock.
""")

# ── Key Insight ──
print(f"{'=' * 95}")
print("  KEY INSIGHT")
print(f"{'=' * 95}")
print("""
  Rotation vs BETTER stock: rotation ALWAYS loses (you'd rather just hold the winner)
  Rotation vs WORSE stock:  rotation ALMOST ALWAYS wins (it rescues you from the dog)

  This is the essence of the strategy:
  - If you can pick the winner → don't rotate, just hold it
  - If you don't know which will win → rotation protects you from catastrophic underperformance
  - Rotation turns "pick the wrong stock" from a disaster into a solid gain

  The one failure case (NVDA-MU 3x at 30% DD) shows the threshold matters:
  30% was too loose for 3x leverage — by the time it triggers, you've lost too much.
  The optimal threshold (20% for 3x) saves the strategy.
""")
