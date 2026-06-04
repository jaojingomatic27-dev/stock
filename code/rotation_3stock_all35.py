# -*- coding: utf-8 -*-
"""All C(7,3)=35 combinations of {NVDA,MU,TSLA,PLTR,AVGO,ASML,AMD}.
3-stock rotation: start $1000 each, breach threshold → sell → split to other 2.
3x leverage, annual rolling 10 years. Rank by beating same-lev worse BH."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import yfinance as yf

TICKERS = ['NVDA', 'MU', 'TSLA', 'PLTR', 'AVGO', 'ASML', 'AMD']
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEV = 3
INVEST_PER = 1000.0; TOTAL = 3000.0
KO_LEVEL = TOTAL * 0.05

# ── Download / load ──
print("Loading data...")
data = {}
for t in TICKERS:
    path = rf"C:\AI\cc\stock\data\{t}_2016_daily.csv"
    try:
        df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
        close = df[("Close", t)].dropna()
        if close.index[-1].year >= 2026 and len(close) > 500:
            data[t] = close
            print(f"  {t}: from cache ({len(close)} days)")
            continue
    except:
        pass
    # Download
    try:
        df = yf.download(t, start='2016-01-01', end='2026-06-04', progress=False)
        if isinstance(df['Close'], pd.DataFrame):
            close = df['Close'].iloc[:, 0]
        else:
            close = df['Close']
        close.to_csv(path)
        data[t] = close
        print(f"  {t}: downloaded ({len(close)} days)")
    except Exception as e:
        print(f"  {t}: ERROR {e}")

# ── Annual windows ──
def annual_windows(close):
    end_d = close.index[-1]; windows = []
    for y in range(10):
        te = pd.Timestamp(year=end_d.year - y, month=6, day=1)
        ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
        ei = close.index.get_indexer([te], method='nearest')[0]
        si = close.index.get_indexer([ts], method='nearest')[0]
        if ei - si > 150:
            windows.append({'label': f"{ts.year}-{te.year}", 'slice': close.iloc[si:ei+1]})
    return windows

stock_windows = {t: annual_windows(data[t]) for t in TICKERS}

# ── Rotation engine ──
def rotation_3stock(ca, cb, cc, lev, th):
    aligned = pd.DataFrame({'a': ca, 'b': cb, 'c': cc}).dropna()
    ra = aligned['a'].pct_change().fillna(0).values
    rb = aligned['b'].pct_change().fillna(0).values
    rc = aligned['c'].pct_change().fillna(0).values
    n = len(aligned)
    vals = np.array([INVEST_PER]*3, dtype=float)
    peaks = vals.copy(); rots = 0
    for i in range(1, n):
        vals[0] *= (1+lev*ra[i]); vals[1] *= (1+lev*rb[i]); vals[2] *= (1+lev*rc[i])
        vals = np.maximum(vals, 0)
        if vals.sum() <= KO_LEVEL: return 0, True, rots
        for j in range(3):
            if vals[j] > peaks[j]: peaks[j] = vals[j]
        breached = [j for j in range(3) if peaks[j] > 0 and (vals[j]-peaks[j])/peaks[j] <= -th]
        if not breached: continue
        cash = sum(vals[j] for j in breached)
        for j in breached: vals[j] = 0.0; peaks[j] = 0.0; rots += 1
        survivors = [j for j in range(3) if j not in breached]
        if not survivors: return 0, True, rots
        per = cash / len(survivors)
        for j in survivors: vals[j] += per; peaks[j] = vals[j]
    return vals.sum(), False, rots

def bh_levered(close, lev):
    val = INVEST_PER
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1+lev*r)
        if val < KO_LEVEL / 3: return 0, True
    return val, False

# ── All combos ──
from itertools import combinations
combos = list(combinations(TICKERS, 3))
print(f"\n{'='*140}")
print(f"  SCREENING ALL {len(combos)} COMBINATIONS (3x leverage, annual rolling, 10 years)")
print(f"{'='*140}")

combo_results = []

for combo_idx, (ta, tb, tc) in enumerate(combos):
    wa, wb, wc = stock_windows[ta], stock_windows[tb], stock_windows[tc]

    # For each threshold, compute per-year results
    th_yearly = {th: {'vals': [], 'kos': [], 'rots': [], 'bw': [], 'bb': []} for th in THRESHOLDS}

    # Only use years where all 3 have data
    n_common_years = min(len(wa), len(wb), len(wc))
    for i_year in range(n_common_years):
        ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']

        # Align dates
        common_dates = ca.index.intersection(cb.index).intersection(cc.index)
        if len(common_dates) < 150: continue
        ca = ca.loc[common_dates]; cb = cb.loc[common_dates]; cc = cc.loc[common_dates]

        # BH same-lev
        bh_vals = []; bh_kos = []
        for c in [ca, cb, cc]:
            v, ko = bh_levered(c, LEV)
            bh_vals.append(v); bh_kos.append(ko)
        sv = [bh_vals[j] for j in range(3) if not bh_kos[j]]

        for th in THRESHOLDS:
            v_rot, ko_rot, rots = rotation_3stock(ca, cb, cc, LEV, th)
            th_yearly[th]['vals'].append(v_rot)
            th_yearly[th]['kos'].append(ko_rot)
            th_yearly[th]['rots'].append(rots)

            if not ko_rot and sv:
                th_yearly[th]['bw'].append(1 if v_rot > min(sv) else 0)
                th_yearly[th]['bb'].append(1 if v_rot > max(sv) else 0)
            elif sv:
                th_yearly[th]['bw'].append(0)
                th_yearly[th]['bb'].append(0)

    # Find best threshold for this combo
    best_th = 0; best_avg = 0; best_bw = 0; best_bb = 0; best_n = 0; best_ko = 0; best_avg_rots = 0
    for th in THRESHOLDS:
        surv = [th_yearly[th]['vals'][i] for i in range(len(th_yearly[th]['vals'])) if not th_yearly[th]['kos'][i]]
        avg_v = np.mean(surv) if surv else 0
        if avg_v > best_avg:
            best_avg = avg_v; best_th = th
            best_ko = sum(th_yearly[th]['kos'])
            best_bw = sum(th_yearly[th]['bw'])
            best_bb = sum(th_yearly[th]['bb'])
            best_n = len(th_yearly[th]['bw'])
            best_avg_rots = np.mean([th_yearly[th]['rots'][i] for i in range(len(th_yearly[th]['rots'])) if not th_yearly[th]['kos'][i]]) if surv else 0

    rot_ret = (best_avg / TOTAL - 1) * 100

    # Average BH returns (use same years as rotation)
    bh_avgs_all = []
    for j, t in enumerate([ta, tb, tc]):
        all_bh = []
        for i_year in range(n_common_years):
            ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']
            common_dates = ca.index.intersection(cb.index).intersection(cc.index)
            if len(common_dates) < 150: continue
            c = [ca, cb, cc][j].loc[common_dates]
            v, ko = bh_levered(c, LEV)
            if not ko: all_bh.append(v)
        avg_bh = np.mean(all_bh) if all_bh else 0
        bh_avgs_all.append(avg_bh)

    avg_worse_bh = min(bh_avgs_all) if bh_avgs_all else 0
    avg_better_bh = max(bh_avgs_all) if bh_avgs_all else 0

    # Score: avg excess vs worse BH as percentage
    score = (best_avg - avg_worse_bh) / avg_worse_bh * 100 if avg_worse_bh > 0 else 0

    combo_results.append({
        'combo': (ta, tb, tc),
        'best_th': best_th, 'avg_val': best_avg, 'rot_ret': rot_ret,
        'ko_count': best_ko, 'n_years': len(th_yearly[THRESHOLDS[0]]['vals']),
        'bw': best_bw, 'bb': best_bb, 'bn': best_n,
        'avg_rots': best_avg_rots,
        'bh_avgs': bh_avgs_all,
        'score': score,
    })

    if (combo_idx + 1) % 5 == 0:
        print(f"  Progress: {combo_idx+1}/{len(combos)}...")

# ── RANKING ──
combo_results.sort(key=lambda x: x['score'], reverse=True)

print(f"\n{'='*150}")
print(f"  TOP 20: Best 3-Stock Rotation Combinations (3x leverage, annual rolling)")
print(f"{'='*150}")
print(f"  {'Rank':<5} {'Combo':<30} {'Best Th':>7} {'Avg Rot $':>10} {'Rot Ret':>8} {'KO':>5} {'#Rot':>5} | {'Avg Worse BH $':>13} {'Avg Better BH $':>14} | {'BeatW':>5} {'BeatB':>5} | {'Score':>8} {'Verdict':>15}")
print(f"  {'-'*5} {'-'*30} {'-'*7} {'-'*10} {'-'*8} {'-'*5} {'-'*5}-+-{'-'*13} {'-'*14}-+-{'-'*5} {'-'*5}-+-{'-'*8} {'-'*15}")

for i, r in enumerate(combo_results[:20], 1):
    # Determine verdict
    if r['bn'] > 0:
        bw_pct = r['bw'] / r['bn'] * 100
        bb_pct = r['bb'] / r['bn'] * 100
    else:
        bw_pct = bb_pct = 0

    if bw_pct >= 90: verdict = '★★★ ELITE'
    elif bw_pct >= 70: verdict = '★★ Excellent'
    elif bw_pct >= 50: verdict = '★ Good'
    else: verdict = '△ OK'

    aw = r['bh_avgs'][0]; ab = r['bh_avgs'][1]; ac = r['bh_avgs'][2] if len(r['bh_avgs']) > 2 else 0
    avg_w = min(r['bh_avgs']); avg_b = max(r['bh_avgs'])

    combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
    print(f"  {i:<5} {combo_str:<30} {r['best_th']:>6.0%} ${r['avg_val']:>9,.0f} {r['rot_ret']:>+7.1f}% {r['ko_count']:>3}/{r['n_years']:<2} {r['avg_rots']:>4.0f} | ${avg_w:>12,.0f} ${avg_b:>13,.0f} | {r['bw']:>3}/{r['bn']:<3} {r['bb']:>3}/{r['bn']:<3} | {r['score']:>+7.0f}% {verdict:>15}")

# ── WORST ──
print(f"\n  BOTTOM 5 (worst combos):")
print(f"  {'Rank':<5} {'Combo':<30} {'Best Th':>7} {'Avg Rot $':>10} {'Rot Ret':>8} {'KO':>5} | {'BeatW':>5} {'BeatB':>5} | {'Score':>8}")
print(f"  {'-'*5} {'-'*30} {'-'*7} {'-'*10} {'-'*8} {'-'*5}-+-{'-'*5} {'-'*5}-+-{'-'*8}")
for i, r in enumerate(combo_results[-5:], len(combo_results)-4):
    combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
    print(f"  {i:<5} {combo_str:<30} {r['best_th']:>6.0%} ${r['avg_val']:>9,.0f} {r['rot_ret']:>+7.1f}% {r['ko_count']:>3}/{r['n_years']:<2} | {r['bw']:>3}/{r['bn']:<3} {r['bb']:>3}/{r['bn']:<3} | {r['score']:>+7.0f}%")

# ── BEST PER ANCHOR ──
print(f"\n{'='*150}")
print(f"  BEST COMBO FOR EACH ANCHOR STOCK")
print(f"{'='*150}")
for anchor in TICKERS:
    relevant = [r for r in combo_results if anchor in r['combo']]
    if relevant:
        best = relevant[0]  # already sorted
        combo_str = f"{best['combo'][0]}+{best['combo'][1]}+{best['combo'][2]}"
        bw_pct = best['bw'] / best['bn'] * 100 if best['bn'] > 0 else 0
        print(f"  {anchor}: best = {combo_str} | {best['best_th']:.0%} | ${best['avg_val']:,.0f} (+{best['rot_ret']:.1f}%) | BeatW {best['bw']}/{best['bn']} ({bw_pct:.0f}%) | KO {best['ko_count']}/{best['n_years']}")

print(f"\n{'='*150}")
print("  Done.")
