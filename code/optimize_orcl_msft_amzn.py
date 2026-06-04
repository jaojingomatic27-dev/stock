# -*- coding: utf-8 -*-
"""Find better partners for ORCL, MSFT, AMZN trio by replacing 1 or 2 stocks.
Test candidates against the baseline trio, 3x leverage, annual rolling."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import yfinance as yf
from itertools import combinations

BASE = ['ORCL', 'MSFT', 'AMZN']
CANDIDATES = ['NVDA', 'MU', 'TSLA', 'PLTR', 'AVGO', 'ASML', 'AMD',
              'GOOGL', 'META', 'NFLX', 'CRM', 'NOW', 'ADBE', 'QCOM', 'TSM', 'LRCX']
THRESHOLDS = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEV = 3
INVEST_PER = 1000.0; TOTAL = 3000.0
KO_LEVEL = TOTAL * 0.05

# ── Load/download ──
print("Loading/downloading data...")
all_tickers = list(set(BASE + CANDIDATES))
data = {}
for t in all_tickers:
    path = rf"C:\AI\cc\stock\data\{t}_2016_daily.csv"
    try:
        df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
        close = df[("Close", t)].dropna()
        if close.index[-1].year >= 2026 and len(close) > 500:
            data[t] = close; continue
    except: pass
    try:
        df = yf.download(t, start='2016-01-01', end='2026-06-04', progress=False)
        close = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        close.to_csv(path); data[t] = close
        print(f"  Downloaded: {t}")
    except Exception as e:
        print(f"  SKIP {t}: {e}")

# ── Annual windows ──
def annual_windows(close):
    end_d = close.index[-1]; windows = []
    for y in range(10):
        te = pd.Timestamp(year=end_d.year - y, month=6, day=1)
        ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
        ei = close.index.get_indexer([te], method='nearest')[0]
        si = close.index.get_indexer([ts], method='nearest')[0]
        if ei - si > 150:
            windows.append({'label': f'{ts.year}-{te.year}', 'slice': close.iloc[si:ei+1]})
    return windows

stock_windows = {t: annual_windows(data[t]) for t in data}

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
        if val < KO_LEVEL/3: return 0, True
    return val, False

def eval_combo(ta, tb, tc):
    """Evaluate a 3-stock combo. Returns (best_th, avg_val, rot_ret_pct, ko_count, bw, bb, bn, avg_rots)."""
    wa, wb, wc = stock_windows[ta], stock_windows[tb], stock_windows[tc]
    n_common = min(len(wa), len(wb), len(wc))
    th_yearly = {th: {'vals': [], 'kos': [], 'bw': [], 'bb': [], 'rots': []} for th in THRESHOLDS}

    for i_year in range(n_common):
        ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']
        common_dates = ca.index.intersection(cb.index).intersection(cc.index)
        if len(common_dates) < 150: continue
        ca=ca.loc[common_dates]; cb=cb.loc[common_dates]; cc=cc.loc[common_dates]

        bh_vals=[]; bh_kos=[]
        for c in [ca, cb, cc]:
            v, ko = bh_levered(c, LEV); bh_vals.append(v); bh_kos.append(ko)
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
                th_yearly[th]['bw'].append(0); th_yearly[th]['bb'].append(0)

    best_th=0; best_avg=0; best_bw=0; best_bb=0; best_bn=0; best_ko=0; best_rots=0
    for th in THRESHOLDS:
        surv = [th_yearly[th]['vals'][i] for i in range(len(th_yearly[th]['vals'])) if not th_yearly[th]['kos'][i]]
        avg_v = np.mean(surv) if surv else 0
        if avg_v > best_avg:
            best_avg=avg_v; best_th=th
            best_ko=sum(th_yearly[th]['kos'])
            best_bw=sum(th_yearly[th]['bw']); best_bb=sum(th_yearly[th]['bb'])
            best_bn=len(th_yearly[th]['bw'])
            best_rots=np.mean([th_yearly[th]['rots'][i] for i in range(len(th_yearly[th]['rots'])) if not th_yearly[th]['kos'][i]]) if surv else 0

    rot_ret = (best_avg/TOTAL - 1)*100
    return best_th, best_avg, rot_ret, best_ko, best_bw, best_bb, best_bn, best_rots

# ── BASELINE ──
bl_th, bl_avg, bl_ret, bl_ko, bl_bw, bl_bb, bl_bn, bl_rots = eval_combo('ORCL', 'MSFT', 'AMZN')
print(f"\n{'='*130}")
print(f"  BASELINE: ORCL + MSFT + AMZN  |  {bl_th:.0%}  |  ${bl_avg:,.0f} (+{bl_ret:.1f}%)  |  KO {bl_ko}/{bl_bn}  |  BeatW {bl_bw}/{bl_bn}  BeatB {bl_bb}/{bl_bn}")
print(f"{'='*130}")

# ── TEST 1: Replace ONE stock ──
print(f"\n  ── REPLACE 1 STOCK ──")
print(f"  {'Replaced':<8} {'→ New':<7} {'Combo':<30} {'Th':>5} {'Avg $':>10} {'Rot%':>8} {'KO':>5} {'BW':>5} {'BB':>5} | {'vs Baseline':>10} {'Improvement':>12}")
print(f"  {'-'*8} {'-'*7} {'-'*30} {'-'*5} {'-'*10} {'-'*8} {'-'*5} {'-'*5} {'-'*5}-+-{'-'*10} {'-'*12}")

replace1_results = []
for removed in BASE:
    keep = [s for s in BASE if s != removed]
    for new in CANDIDATES:
        if new in BASE: continue
        if new not in data: continue
        combo = tuple(sorted(keep + [new]))
        th, avg, ret, ko, bw, bb, bn, rots = eval_combo(*combo)

        # vs baseline: difference in avg $
        improvement = avg - bl_avg
        vs_base = '+$' if improvement > 0 else '-$'
        vs_base += f'{abs(improvement):,.0f}'

        replace1_results.append({
            'removed': removed, 'new': new, 'combo': combo,
            'th': th, 'avg': avg, 'ret': ret, 'ko': ko, 'bw': bw, 'bb': bb, 'bn': bn,
            'improvement': improvement, 'rots': rots,
        })

# Sort by improvement and show best
replace1_results.sort(key=lambda x: x['improvement'], reverse=True)

# Show top 3 per removed stock + overall top 10
for removed in BASE:
    subset = [r for r in replace1_results if r['removed'] == removed][:3]
    for r in subset:
        combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
        bw_str = f'{r["bw"]}/{r["bn"]}' if r['bn']>0 else '-'
        bb_str = f'{r["bb"]}/{r["bn"]}' if r['bn']>0 else '-'
        print(f"  {r['removed']:<8} → {r['new']:<7} {combo_str:<30} {r['th']:>4.0%} ${r['avg']:>9,.0f} {r['ret']:>+7.1f}% {r['ko']:>3}/{r['bn']:<2} {bw_str:>5} {bb_str:>5} | {'+$' if r['improvement']>0 else '-$'}{abs(r['improvement']):>9,.0f} {'+' if r['improvement']>0 else ''}{r['improvement']/bl_avg*100:>+10.1f}%")

# ── TEST 2: Replace TWO stocks ──
print(f"\n  ── REPLACE 2 STOCKS ──")
print(f"  {'Keep':<7} {'→ New Pair':<18} {'Combo':<30} {'Th':>5} {'Avg $':>10} {'Rot%':>8} {'KO':>5} {'BW':>5} {'BB':>5} | {'vs Baseline':>10} {'Improvement':>12}")
print(f"  {'-'*7} {'-'*18} {'-'*30} {'-'*5} {'-'*10} {'-'*8} {'-'*5} {'-'*5} {'-'*5}-+-{'-'*10} {'-'*12}")

replace2_results = []
for kept in BASE:
    removed = [s for s in BASE if s != kept]
    for new1, new2 in combinations(CANDIDATES, 2):
        if new1 in BASE or new2 in BASE: continue
        if new1 not in data or new2 not in data: continue
        if new1 == new2: continue
        combo = tuple(sorted([kept, new1, new2]))
        th, avg, ret, ko, bw, bb, bn, rots = eval_combo(*combo)
        improvement = avg - bl_avg
        replace2_results.append({
            'kept': kept, 'new': (new1, new2), 'combo': combo,
            'th': th, 'avg': avg, 'ret': ret, 'ko': ko, 'bw': bw, 'bb': bb, 'bn': bn,
            'improvement': improvement, 'rots': rots,
        })

replace2_results.sort(key=lambda x: x['improvement'], reverse=True)
for kept in BASE:
    subset = [r for r in replace2_results if r['kept'] == kept][:3]
    for r in subset:
        combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
        new_str = f"{r['new'][0]}+{r['new'][1]}"
        bw_str = f'{r["bw"]}/{r["bn"]}' if r['bn']>0 else '-'
        bb_str = f'{r["bb"]}/{r["bn"]}' if r['bn']>0 else '-'
        print(f"  {r['kept']:<7} → {new_str:<18} {combo_str:<30} {r['th']:>4.0%} ${r['avg']:>9,.0f} {r['ret']:>+7.1f}% {r['ko']:>3}/{r['bn']:<2} {bw_str:>5} {bb_str:>5} | {'+$' if r['improvement']>0 else '-$'}{abs(r['improvement']):>9,.0f} {'+' if r['improvement']>0 else ''}{r['improvement']/bl_avg*100:>+10.1f}%")

# ── OVERALL TOP 20 ──
print(f"\n{'='*130}")
print(f"  OVERALL TOP 20: Best Improvements over ORCL+MSFT+AMZN Baseline")
print(f"{'='*130}")
all_improvements = replace1_results + replace2_results
all_improvements.sort(key=lambda x: x['improvement'], reverse=True)
print(f"  {'Rank':<5} {'Combo':<32} {'Action':<20} {'Th':>5} {'Avg $':>11} {'Rot%':>8} {'KO':>5} {'BW':>5} {'BB':>5} | {'vs Baseline':>12}")
print(f"  {'-'*5} {'-'*32} {'-'*20} {'-'*5} {'-'*11} {'-'*8} {'-'*5} {'-'*5} {'-'*5}-+-{'-'*12}")
for i, r in enumerate(all_improvements[:20], 1):
    combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
    if 'removed' in r:
        action = f"Out {r['removed']} → In {r['new']}"
    else:
        out = [s for s in BASE if s != r['kept']]
        action = f"Keep {r['kept']}, +{r['new'][0]}+{r['new'][1]}"
    bw_str = f'{r["bw"]}/{r["bn"]}' if r['bn']>0 else '-'
    bb_str = f'{r["bb"]}/{r["bn"]}' if r['bn']>0 else '-'
    print(f"  {i:<5} {combo_str:<32} {action:<20} {r['th']:>4.0%} ${r['avg']:>10,.0f} {r['ret']:>+7.1f}% {r['ko']:>3}/{r['bn']:<2} {bw_str:>5} {bb_str:>5} | {'+$' if r['improvement']>0 else '-$'}{abs(r['improvement']):>10,.0f}")

# ── SUMMARY: Best for each replacement strategy ──
print(f"\n{'='*130}")
print(f"  SUMMARY: Best Strategy Per Approach")
print(f"{'='*130}")
print(f"  {'Approach':<25} {'Best Combo':<32} {'Avg $':>10} {'Rot%':>8} {'BW':>5} {'BB':>5} | {'vs Baseline':>12}")
print(f"  {'-'*25} {'-'*32} {'-'*10} {'-'*8} {'-'*5} {'-'*5}-+-{'-'*12}")

approaches = [
    ('Keep ORCL+MSFT+AMZN', [r for r in all_improvements if 'combo' in r and set(r['combo']) == set(BASE)]),
    ('Replace ORCL (best)', [r for r in replace1_results if r['removed'] == 'ORCL']),
    ('Replace MSFT (best)', [r for r in replace1_results if r['removed'] == 'MSFT']),
    ('Replace AMZN (best)', [r for r in replace1_results if r['removed'] == 'AMZN']),
    ('Keep ORCL (replace 2)', [r for r in replace2_results if r['kept'] == 'ORCL']),
    ('Keep MSFT (replace 2)', [r for r in replace2_results if r['kept'] == 'MSFT']),
    ('Keep AMZN (replace 2)', [r for r in replace2_results if r['kept'] == 'AMZN']),
    ('Best overall', all_improvements),
]
for label, results in approaches:
    if not results: continue
    best = results[0]
    combo_str = f"{best['combo'][0]}+{best['combo'][1]}+{best['combo'][2]}"
    bw_str = f'{best["bw"]}/{best["bn"]}' if best['bn']>0 else '-'
    bb_str = f'{best["bb"]}/{best["bn"]}' if best['bn']>0 else '-'
    vs = '+$' if best['improvement']>0 else '-$'
    print(f"  {label:<25} {combo_str:<32} ${best['avg']:>9,.0f} {best['ret']:>+7.1f}% {bw_str:>5} {bb_str:>5} | {vs}{abs(best['improvement']):>11,.0f}")

print(f"\n  BASELINE reminder: ORCL+MSFT+AMZN = ${bl_avg:,.0f} (+{bl_ret:.1f}%) | BW {bl_bw}/{bl_bn} BB {bl_bb}/{bl_bn} | KO {bl_ko}/{bl_bn}")
