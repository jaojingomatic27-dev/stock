# -*- coding: utf-8 -*-
"""Complete 3-stock rotation ranking — ALL stocks mentioned across research.
C(N,3) combos, 3x leverage, 4 thresholds, annual rolling 10 years."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
from itertools import combinations

# ── ALL stocks ──
ALL_STOCKS = [
    'NVDA', 'MU', 'GOOGL', 'AMZN', 'ORCL', 'MSFT',    # original 6
    'TSLA', 'AVGO', 'ASML', 'AMD', 'PLTR',              # screening top picks
    'SMCI', 'MRVL', 'QCOM', 'TSM', 'LRCX',              # semiconductor
    'META', 'NFLX', 'CRM', 'NOW', 'ADBE',               # big tech / SaaS
]
# 21 stocks → C(21,3) = 1330 combos

THRESHOLDS = [0.20, 0.30, 0.40, 0.50]
LEV = 3
INVEST_PER = 1000.0; TOTAL = 3000.0; KO_LEVEL = TOTAL * 0.05

# ── Load ──
print(f"Loading {len(ALL_STOCKS)} stocks...")
data = {}
short_data = set()
for t in ALL_STOCKS:
    path = rf"C:\AI\cc\stock\data\{t}_2016_daily.csv"
    try:
        df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
        try:
            close = df[("Close", t)].dropna()
        except KeyError:
            # Try flat column index
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if 'Close' in df.columns:
                close = df['Close'].dropna()
            else:
                close = df.iloc[:, 0].dropna()  # first column
        data[t] = close
        yrs = (close.index[-1] - close.index[0]).days / 365.25
        flag = "⚠ short" if yrs < 7 else ""
        print(f"  {t}: {close.index[0].date()}~{close.index[-1].date()} ({len(close)}d) {flag}")
        if yrs < 7: short_data.add(t)
    except Exception as e:
        import yfinance as yf
        try:
            df = yf.download(t, start='2016-01-01', end='2026-06-04', progress=False)
            close = df['Close'].iloc[:,0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
            close.to_csv(path)
            data[t] = close
            yrs = (close.index[-1] - close.index[0]).days / 365.25
            flag = "⚠ short" if yrs < 7 else ""
            print(f"  {t}: downloaded {close.index[0].date()}~{close.index[-1].date()} ({len(close)}d) {flag}")
            if yrs < 7: short_data.add(t)
        except Exception as e2:
            print(f"  {t}: SKIP - {e2}")

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

print("\nComputing annual windows...")
stock_windows = {t: annual_windows(data[t]) for t in data}

# ── Engine ──
def rotation_3stock(ca, cb, cc):
    aligned = pd.DataFrame({'a': ca, 'b': cb, 'c': cc}).dropna()
    ra = aligned['a'].pct_change().fillna(0).values
    rb = aligned['b'].pct_change().fillna(0).values
    rc = aligned['c'].pct_change().fillna(0).values
    n = len(aligned)

    # Pre-compute for all thresholds at once
    results = {th: {'vals': np.array([INVEST_PER]*3, dtype=float),
                     'peaks': np.array([INVEST_PER]*3, dtype=float),
                     'rots': 0, 'ko': False, 'done': False} for th in THRESHOLDS}

    for i in range(1, n):
        daily = [ra[i], rb[i], rc[i]]
        all_done = True
        for th in THRESHOLDS:
            r = results[th]
            if r['done']: continue
            all_done = False

            vals = r['vals']; peaks = r['peaks']
            for j in range(3):
                vals[j] *= (1 + LEV * daily[j])
                if vals[j] < 0: vals[j] = 0
            if vals.sum() <= KO_LEVEL:
                r['ko'] = True; r['done'] = True; continue
            for j in range(3):
                if vals[j] > peaks[j]: peaks[j] = vals[j]
            breached = [j for j in range(3) if peaks[j] > 0 and (vals[j]-peaks[j])/peaks[j] <= -th]
            if not breached: continue
            cash = sum(vals[j] for j in breached)
            for j in breached: vals[j] = 0.0; peaks[j] = 0.0; r['rots'] += 1
            survivors = [j for j in range(3) if j not in breached]
            if not survivors:
                r['ko'] = True; r['done'] = True; continue
            per = cash / len(survivors)
            for j in survivors: vals[j] += per; peaks[j] = vals[j]
        if all_done: break

    return {th: (r['vals'].sum(), r['ko'], r['rots']) for th, r in results.items()}

def bh_levered(close):
    val = INVEST_PER
    for r in close.pct_change().fillna(0).values[1:]:
        val *= (1 + LEV * r)
        if val < KO_LEVEL/3: return 0, True
    return val, False

# ── Run all combos ──
tickers = list(data.keys())
combos = list(combinations(tickers, 3))
print(f"\nRunning {len(combos)} combinations ({LEV}x, {len(THRESHOLDS)} thresholds, annual rolling)...")

all_results = []
for idx, (ta, tb, tc) in enumerate(combos):
    wa, wb, wc = stock_windows[ta], stock_windows[tb], stock_windows[tc]
    n_common = min(len(wa), len(wb), len(wc))

    th_data = {th: {'vals': [], 'kos': [], 'rots': [], 'bw': [], 'bb': []} for th in THRESHOLDS}

    for i_year in range(n_common):
        ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']
        common_dates = ca.index.intersection(cb.index).intersection(cc.index)
        if len(common_dates) < 150: continue
        ca=ca.loc[common_dates]; cb=cb.loc[common_dates]; cc=cc.loc[common_dates]

        bh = [bh_levered(c) for c in [ca, cb, cc]]
        bh_vals = [v for v,ko in bh]; bh_kos = [ko for v,ko in bh]
        sv = [bh_vals[j] for j in range(3) if not bh_kos[j]]

        rot_th = rotation_3stock(ca, cb, cc)
        for th in THRESHOLDS:
            v_rot, ko_rot, rots = rot_th[th]
            th_data[th]['vals'].append(v_rot)
            th_data[th]['kos'].append(ko_rot)
            th_data[th]['rots'].append(rots)
            if not ko_rot and sv:
                th_data[th]['bw'].append(1 if v_rot > min(sv) else 0)
                th_data[th]['bb'].append(1 if v_rot > max(sv) else 0)
            elif sv:
                th_data[th]['bw'].append(0); th_data[th]['bb'].append(0)

    # Best threshold
    best_th=0; best_avg=0; best_ko=0; best_bw=0; best_bb=0; best_bn=0; best_rots=0
    for th in THRESHOLDS:
        surv = [th_data[th]['vals'][i] for i in range(len(th_data[th]['vals'])) if not th_data[th]['kos'][i]]
        avg_v = np.mean(surv) if surv else 0
        if avg_v > best_avg:
            best_avg=avg_v; best_th=th
            best_ko=sum(th_data[th]['kos'])
            best_bw=sum(th_data[th]['bw']); best_bb=sum(th_data[th]['bb'])
            best_bn=len(th_data[th]['bw'])
            rots_surv = [th_data[th]['rots'][i] for i in range(len(th_data[th]['rots'])) if not th_data[th]['kos'][i]]
            best_rots=np.mean(rots_surv) if rots_surv else 0

    rot_ret = (best_avg/TOTAL - 1)*100

    # Avg BH for score
    bh_avgs = []
    for j in range(3):
        all_bh = []
        for i_year in range(n_common):
            ca = wa[i_year]['slice']; cb = wb[i_year]['slice']; cc = wc[i_year]['slice']
            common_dates = ca.index.intersection(cb.index).intersection(cc.index)
            if len(common_dates) < 150: continue
            c = [ca,cb,cc][j].loc[common_dates]
            v, ko = bh_levered(c)
            if not ko: all_bh.append(v)
        bh_avgs.append(np.mean(all_bh) if all_bh else 0)

    avg_w = min(bh_avgs)
    score = (best_avg - avg_w) / avg_w * 100 if avg_w > 0 else 0

    short_flag = 1 if (ta in short_data or tb in short_data or tc in short_data) else 0

    all_results.append({
        'combo': (ta, tb, tc), 'th': best_th, 'avg': best_avg, 'ret': rot_ret,
        'ko': best_ko, 'bw': best_bw, 'bb': best_bb, 'bn': best_bn,
        'rots': best_rots, 'score': score, 'short': short_flag,
    })

    if (idx+1) % 200 == 0:
        print(f"  {idx+1}/{len(combos)}...")

# ── RANK ──
all_results.sort(key=lambda x: x['score'], reverse=True)

print(f"\n{'='*140}")
print(f"  🏆 TOP 10 三股轮动排名 ({len(combos)} combinations total)")
print(f"  3x Leverage, Annual Rolling, Fair Comparison vs Same-Leverage Worse BH")
print(f"{'='*140}")
print(f"  {'Rank':<5} {'Combo':<32} {'Th':>5} {'Avg $':>11} {'Ret%':>9} {'KO':>5} {'#Rot':>5} | {'Avg W BH':>10} {'Avg B BH':>10} | {'BW':>5} {'BB':>5} | {'Score':>9} {'Data':>6}")
print(f"  {'-'*5} {'-'*32} {'-'*5} {'-'*11} {'-'*9} {'-'*5} {'-'*5}-+-{'-'*10} {'-'*10}-+-{'-'*5} {'-'*5}-+-{'-'*9} {'-'*6}")

for i, r in enumerate(all_results[:10], 1):
    combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"

    # Compute avg worse/better BH
    bh_vals = []
    for j, t in enumerate(r['combo']):
        close = data[t]
        wa_list = stock_windows[t]
        all_bh = []
        for wy in wa_list:
            v, ko = bh_levered(wy['slice'])
            if not ko: all_bh.append(v)
        bh_vals.append(np.mean(all_bh) if all_bh else 0)
    avg_w = min(bh_vals); avg_b = max(bh_vals)

    bw_str = f"{r['bw']}/{r['bn']}" if r['bn']>0 else '-'
    bb_str = f"{r['bb']}/{r['bn']}" if r['bn']>0 else '-'
    data_note = "⚠ PLTR" if r['short'] else "10Y"

    medal = '🥇' if i==1 else ('🥈' if i==2 else ('🥉' if i==3 else '  '))
    print(f"  {medal}{i:<3} {combo_str:<32} {r['th']:>4.0%} ${r['avg']:>10,.0f} {r['ret']:>+8.1f}% {r['ko']:>3}/{r['bn']:<2} {r['rots']:>4.0f} | ${avg_w:>9,.0f} ${avg_b:>9,.0f} | {bw_str:>5} {bb_str:>5} | {r['score']:>+8.0f}% {data_note:>6}")

# ── TOP 10 WITHOUT PLTR (10-year clean) ──
clean = [r for r in all_results if not r['short']]
print(f"\n{'='*140}")
print(f"  🏆 TOP 10 (10-Year Full Data Only — No PLTR)")
print(f"{'='*140}")
print(f"  {'Rank':<5} {'Combo':<32} {'Th':>5} {'Avg $':>11} {'Ret%':>9} {'KO':>5} {'#Rot':>5} | {'Avg W BH':>10} {'Avg B BH':>10} | {'BW':>5} {'BB':>5} | {'Score':>9}")
print(f"  {'-'*5} {'-'*32} {'-'*5} {'-'*11} {'-'*9} {'-'*5} {'-'*5}-+-{'-'*10} {'-'*10}-+-{'-'*5} {'-'*5}-+-{'-'*9}")

for i, r in enumerate(clean[:10], 1):
    combo_str = f"{r['combo'][0]}+{r['combo'][1]}+{r['combo'][2]}"
    bh_vals = []
    for j, t in enumerate(r['combo']):
        close = data[t]
        wa_list = stock_windows[t]
        all_bh = []
        for wy in wa_list:
            v, ko = bh_levered(wy['slice'])
            if not ko: all_bh.append(v)
        bh_vals.append(np.mean(all_bh) if all_bh else 0)
    avg_w = min(bh_vals); avg_b = max(bh_vals)

    bw_str = f"{r['bw']}/{r['bn']}" if r['bn']>0 else '-'
    bb_str = f"{r['bb']}/{r['bn']}" if r['bn']>0 else '-'
    medal = '🥇' if i==1 else ('🥈' if i==2 else ('🥉' if i==3 else '  '))
    print(f"  {medal}{i:<3} {combo_str:<32} {r['th']:>4.0%} ${r['avg']:>10,.0f} {r['ret']:>+8.1f}% {r['ko']:>3}/{r['bn']:<2} {r['rots']:>4.0f} | ${avg_w:>9,.0f} ${avg_b:>9,.0f} | {bw_str:>5} {bb_str:>5} | {r['score']:>+8.0f}%")

# ── Top stocks frequency ──
print(f"\n{'='*140}")
print(f"  Most Common Stocks in Top 20")
print(f"{'='*140}")
freq = {}
for r in all_results[:20]:
    for t in r['combo']:
        freq[t] = freq.get(t, 0) + 1
for t, c in sorted(freq.items(), key=lambda x: x[1], reverse=True):
    bar = '█' * c
    print(f"  {t:<7} {c:>2}/20 {bar}")

print(f"\n  Total combos tested: {len(combos)}")
print(f"  Full 10Y stocks: {len(tickers) - len(short_data)} | Short data: {len(short_data)} ({', '.join(sorted(short_data))})")
