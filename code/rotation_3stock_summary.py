# -*- coding: utf-8 -*-
"""Quick summary: annualized returns for 3-stock rotation vs same-lev B&H"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np

TICKERS = ['ORCL', 'MSFT', 'AMZN']
THRESHOLDS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
LEVERAGES = [1, 2, 3, 4, 5, 6]
INVEST_PER = 1000.0; TOTAL = 3000.0

def load(t):
    df = pd.read_csv(rf'C:\AI\cc\stock\data\{t}_2016_daily.csv', header=[0,1], index_col=0, parse_dates=True)
    return df[('Close', t)].dropna()

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

def rotation_3stock(close_a, close_b, close_c, lev, th):
    aligned = pd.DataFrame({'a': close_a, 'b': close_b, 'c': close_c}).dropna()
    ra = aligned['a'].pct_change().fillna(0).values
    rb = aligned['b'].pct_change().fillna(0).values
    rc = aligned['c'].pct_change().fillna(0).values
    n = len(aligned)
    vals = np.array([INVEST_PER]*3, dtype=float)
    peaks = vals.copy(); rots = 0
    for i in range(1, n):
        vals[0] *= (1+lev*ra[i]); vals[1] *= (1+lev*rb[i]); vals[2] *= (1+lev*rc[i])
        vals = np.maximum(vals, 0)
        if vals.sum() <= TOTAL*0.05: return 0, True, rots
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
        if val < TOTAL*0.05/3: return 0, True
    return val, False

stock_data = {t: load(t) for t in TICKERS}
stock_windows = {t: annual_windows(stock_data[t]) for t in TICKERS}
wa, wb, wc = stock_windows['ORCL'], stock_windows['MSFT'], stock_windows['AMZN']

all_years = []
for i in range(len(wa)):
    ca=wa[i]['slice']; cb=wb[i]['slice']; cc=wc[i]['slice']
    if len(ca)<150 or len(cb)<150 or len(cc)<150: continue
    yd = {'label': wa[i]['label']}
    for lev in LEVERAGES:
        for ticker_idx, c in enumerate([ca, cb, cc]):
            v, ko = bh_levered(c, lev)
            yd[f'bh_{ticker_idx}_{lev}'] = (v, ko)
        for th in THRESHOLDS:
            v, ko, rots = rotation_3stock(ca, cb, cc, lev, th)
            yd[(lev, th)] = (v, ko, rots)
    all_years.append(yd)

n = len(all_years)
print("=" * 130)
print(f"  ANNUALIZED RETURNS: 3-Stock Rotation vs Same-Leverage B&H ({n} years)")
print("=" * 130)
print(f"  {'Lev':<5} {'Best Th':>8} | {'Rot Avg $':>10} {'Rot Ret%':>10} {'KO':>4} | {'BH ORCL $':>10} {'BH ORCL%':>9} {'KO':>4} | {'BH MSFT $':>10} {'BH MSFT%':>9} {'KO':>4} | {'BH AMZN $':>10} {'BH AMZN%':>9} {'KO':>4} | {'BeatW':>5} {'BeatB':>5}")
print(f"  {'-'*5}-+-{'-'*8}-+-{'-'*10} {'-'*10} {'-'*4}-+-{'-'*10} {'-'*9} {'-'*4}-+-{'-'*10} {'-'*9} {'-'*4}-+-{'-'*10} {'-'*9} {'-'*4}-+-{'-'*5} {'-'*5}")

for lev in LEVERAGES:
    best_th = 0; best_avg = 0; best_bw = 0; best_bb = 0; best_bs = 0
    for th in THRESHOLDS:
        surv = [yd[(lev, th)][0] for yd in all_years if not yd[(lev, th)][1]]
        avg_v = np.mean(surv) if surv else 0
        if avg_v > best_avg:
            best_avg = avg_v; best_th = th
            best_ko = sum(1 for yd in all_years if yd[(lev, th)][1])
            bw=0; bb=0; bs=0
            for yd in all_years:
                v_rot, ko_rot, _ = yd[(lev, th)]
                if ko_rot: continue
                sv = [yd[f'bh_{j}_{lev}'][0] for j in range(3) if not yd[f'bh_{j}_{lev}'][1]]
                if not sv: continue
                bs+=1
                if v_rot > min(sv): bw+=1
                if v_rot > max(sv): bb+=1
            best_bw=bw; best_bb=bb; best_bs=bs

    rot_pct = (best_avg/TOTAL - 1)*100
    bh_avgs = []
    for j in range(3):
        sv = [yd[f'bh_{j}_{lev}'][0] for yd in all_years if not yd[f'bh_{j}_{lev}'][1]]
        ko = sum(1 for yd in all_years if yd[f'bh_{j}_{lev}'][1])
        avg_v = np.mean(sv) if sv else 0
        bh_avgs.append((avg_v, (avg_v/INVEST_PER - 1)*100, ko))

    print(f"  {lev:<5}x {best_th:>8.0%} | ${best_avg:>9,.0f} {rot_pct:>+9.1f}% {best_ko:>3}/{n} | ${bh_avgs[0][0]:>9,.0f} {bh_avgs[0][1]:>+8.1f}% {bh_avgs[0][2]:>3}/{n} | ${bh_avgs[1][0]:>9,.0f} {bh_avgs[1][1]:>+8.1f}% {bh_avgs[1][2]:>3}/{n} | ${bh_avgs[2][0]:>9,.0f} {bh_avgs[2][1]:>+8.1f}% {bh_avgs[2][2]:>3}/{n} | {best_bw:>3}/{best_bs:<3} {best_bb:>3}/{best_bs}")

print()
print(f"  注: 每只股票初始 $1,000, 三股合计 $3,000")
print(f"       Rot Ret% = 轮动年均收益率 = (Avg Final / 3000 - 1) * 100")
print(f"       BH ORCL/MSFT/AMZN% = 同杠杆单只 B&H 年均收益率 = (Avg Final / 1000 - 1) * 100")
print(f"       BeatW = 打败同杠杆下最差 B&H | BeatB = 打败同杠杆下最好 B&H")

# Also show best year-by-year for 3x
print(f"\n{'='*130}")
print(f"  3x LEVERAGE — YEAR-BY-YEAR DETAIL")
print(f"{'='*130}")
print(f"  {'Year':<10} | {'Rot 3x $':>10} {'Rot Ret':>8} {'KO':>5} | {'BH ORCL 3x':>11} {'Ret':>8} | {'BH MSFT 3x':>11} {'Ret':>8} | {'BH AMZN 3x':>11} {'Ret':>8} | {'vs Worse':>9} {'vs Better':>10}")
print(f"  {'-'*10}-+-{'-'*10} {'-'*8} {'-'*5}-+-{'-'*11} {'-'*8}-+-{'-'*11} {'-'*8}-+-{'-'*11} {'-'*8}-+-{'-'*9} {'-'*10}")

for yd in all_years:
    best_3 = {'val': 0, 'th': 0, 'rots': 0, 'ko': True}
    for th in THRESHOLDS:
        v, ko, rots = yd[(3, th)]
        if not ko and v > best_3['val']:
            best_3 = {'val': v, 'th': th, 'rots': rots, 'ko': False}
        elif ko and best_3['ko'] and v > best_3['val']:
            best_3['val'] = v; best_3['th'] = th; best_3['rots'] = rots

    rot_pct = (best_3['val']/TOTAL - 1)*100
    bh_vals = [yd[f'bh_{j}_3'][0] for j in range(3)]
    bh_kos = [yd[f'bh_{j}_3'][1] for j in range(3)]
    bh_rets = [(v/INVEST_PER - 1)*100 for v in bh_vals]

    sv = [bh_vals[j] for j in range(3) if not bh_kos[j]]
    vs_worse = 'N/A'; vs_better = 'N/A'
    if sv and not best_3['ko']:
        vs_worse = 'Win' if best_3['val'] > min(sv) else 'Lose'
        vs_better = 'Win' if best_3['val'] > max(sv) else 'Lose'

    ko_s = 'OK' if not best_3['ko'] else 'KO!'
    print(f"  {yd['label']:<10} | ${best_3['val']:>9,.0f} {rot_pct:>+7.1f}% {ko_s:>5} | ${bh_vals[0]:>10,.0f} {bh_rets[0]:>+7.1f}% | ${bh_vals[1]:>10,.0f} {bh_rets[1]:>+7.1f}% | ${bh_vals[2]:>10,.0f} {bh_rets[2]:>+7.1f}% | {vs_worse:>9} {vs_better:>10}")

print()
