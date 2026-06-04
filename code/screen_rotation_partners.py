# -*- coding: utf-8 -*-
"""Screen best rotation partners for NVDA and MU.
Tests candidates: SMCI, AMD, AVGO, TSLA, MRVL, ARM, PLTR, QCOM, INTC, TSM, LRCX, ASML
Metrics: volatility, correlation, max DD, 3x rotation performance vs same-lev BH."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import yfinance as yf

CANDIDATES = ['SMCI', 'AMD', 'AVGO', 'TSLA', 'MRVL', 'ARM', 'PLTR', 'QCOM', 'INTC', 'TSM', 'LRCX', 'ASML']
ANCHORS = ['NVDA', 'MU']
THRESHOLDS = [0.20, 0.30, 0.40, 0.50]
LEVERAGES = [3, 5]
INVEST = 1000.0

print("Downloading all candidate data (2016-2026)...")
all_tickers = list(set(CANDIDATES + ANCHORS))
data = {}
for t in all_tickers:
    try:
        df = yf.download(t, start='2016-01-01', end='2026-06-04', progress=False)
        if len(df) > 500:
            # Ensure we get a Series
            if isinstance(df['Close'], pd.DataFrame):
                close = df['Close'].iloc[:, 0]
            else:
                close = df['Close']
            data[t] = close
            print(f"  {t}: {df.index[0].date()} ~ {df.index[-1].date()} ({len(df)} days)")
        else:
            print(f"  {t}: insufficient data ({len(df)} days), SKIP")
    except Exception as e:
        print(f"  {t}: ERROR - {e}")

# ── Compute metrics ──
print(f"\n{'='*120}")
print(f"  CANDIDATE SCREENING: Rotation Partner Potential for NVDA and MU")
print(f"{'='*120}")

nvda = data['NVDA'].squeeze(); mu = data['MU'].squeeze()
common_idx = nvda.index.intersection(mu.index)
nvda_c = nvda.loc[common_idx]; mu_c = mu.loc[common_idx]
nvda_r = nvda_c.pct_change().dropna()
mu_r = mu_c.pct_change().dropna()

# NVDA & MU baseline metrics
nvda_vol = nvda_r.std() * np.sqrt(252) * 100
mu_vol = mu_r.std() * np.sqrt(252) * 100
nvda_mu_corr = nvda_r.corr(mu_r)
years = (common_idx[-1] - common_idx[0]).days / 365.25

print(f"\n  BASELINE: NVDA vol={nvda_vol:.1f}%, MU vol={mu_vol:.1f}%, NVDA-MU corr={nvda_mu_corr:.3f}")

# Screen each candidate
results = []
for ticker in CANDIDATES:
    if ticker not in data:
        continue
    s = data[ticker].squeeze()
    common = nvda_c.index.intersection(s.index).intersection(mu_c.index)
    if len(common) < 500:
        print(f"  {ticker}: insufficient overlapping data, SKIP")
        continue
    s_c = s.loc[common]
    s_r = s_c.pct_change().dropna()

    # Align returns
    nvda_common_r = nvda_c.loc[common].pct_change().dropna()
    mu_common_r = mu_c.loc[common].pct_change().dropna()
    common_ret_idx = nvda_common_r.index.intersection(s_r.index).intersection(mu_common_r.index)
    nr = nvda_common_r.loc[common_ret_idx]
    mr = mu_common_r.loc[common_ret_idx]
    sr = s_r.loc[common_ret_idx]

    vol = sr.std() * np.sqrt(252) * 100
    corr_nvda = nr.corr(sr)
    corr_mu = mr.corr(sr)

    # Max drawdown (1x)
    cum = (1 + sr).cumprod()
    peak = cum.cummax()
    dd = ((cum - peak) / peak * 100)
    max_dd = dd.min()
    max_dd_date = dd.idxmin()

    # 10Y BH return (1x)
    total_ret = (s_c.iloc[-1] / s_c.iloc[0] - 1) * 100

    # Quick 2-stock rotation simulation with NVDA (3x, 20%)
    # Full period
    aligned = pd.DataFrame({'nvda': nvda_c.loc[common], 's': s_c}).dropna()
    nvda_rets = aligned['nvda'].pct_change().fillna(0).values
    s_rets = aligned['s'].pct_change().fillna(0).values

    def rotation(lev, th, start_nvda=True):
        val = INVEST; peak = INVEST; holding_nvda = start_nvda; rots = 0
        for i in range(1, len(aligned)):
            r = nvda_rets[i] if holding_nvda else s_rets[i]
            val *= (1 + lev * r)
            if val < 50: return 0, True, rots
            if val > peak: peak = val
            if (val - peak) / peak <= -th:
                holding_nvda = not holding_nvda; peak = val; rots += 1
        return val, False, rots

    def bh_lev(rets, lev):
        val = INVEST
        for r in rets:
            val *= (1 + lev * r)
            if val < 50: return 0, True
        return val, False

    # Scan thresholds for 3x
    best_3x_val, best_3x_th = 0, 0
    for th in THRESHOLDS:
        val, ko, rots = rotation(3, th, True)
        if not ko and val > best_3x_val:
            best_3x_val, best_3x_th = val, th

    # Same-lev BH comparison
    nvda_bh_3x, nvda_ko_3x = bh_lev(nvda_rets[1:], 3)
    s_bh_3x, s_ko_3x = bh_lev(s_rets[1:], 3)

    rot_ret = (best_3x_val / INVEST - 1) * 100
    worse_3x = min(nvda_bh_3x, s_bh_3x) if not nvda_ko_3x and not s_ko_3x else (s_bh_3x if not s_ko_3x else nvda_bh_3x)
    better_3x = max(nvda_bh_3x, s_bh_3x) if not nvda_ko_3x and not s_ko_3x else (s_bh_3x if not s_ko_3x else nvda_bh_3x)

    beats_worse = 'Yes' if (best_3x_val > worse_3x and not (nvda_ko_3x and s_ko_3x)) else 'No'
    beats_better = 'Yes' if (best_3x_val > better_3x and not (nvda_ko_3x and s_ko_3x)) else 'No'

    # Also test with MU
    mu_aligned = pd.DataFrame({'mu': mu_c.loc[common], 's': s_c}).dropna()
    mu_rets_arr = mu_aligned['mu'].pct_change().fillna(0).values
    s_rets_mu = mu_aligned['s'].pct_change().fillna(0).values

    best_mu_val, best_mu_th = 0, 0
    for th in THRESHOLDS:
        val, ko, rots = rotation(3, th, True)  # reuse func but with mu data
        # Actually need to recompute with mu data...
        pass

    # Quick mu rotation
    def rotation_pair(rets_a, rets_b, lev, th):
        val = INVEST; peak = INVEST; holding_a = True; rots = 0
        for i in range(1, len(rets_a)):
            r = rets_a[i] if holding_a else rets_b[i]
            val *= (1 + lev * r)
            if val < 50: return 0, True, rots
            if val > peak: peak = val
            if (val - peak) / peak <= -th:
                holding_a = not holding_a; peak = val; rots += 1
        return val, False, rots

    for th in THRESHOLDS:
        val, ko, rots = rotation_pair(mu_rets_arr[1:], s_rets_mu[1:], 3, th)
        if not ko and val > best_mu_val:
            best_mu_val, best_mu_th = val, th

    mu_bh_3x, mu_ko_3x = bh_lev(mu_rets_arr[1:], 3)
    s_bh_mu_3x, s_ko_mu_3x = bh_lev(s_rets_mu[1:], 3)

    # Composite score: avg of NVDA pair + MU pair rotation returns vs same-lev BH
    nvda_pair_score = (best_3x_val - worse_3x) / INVEST * 100 if best_3x_val > 0 else -100
    mu_pair_score = (best_mu_val - min(mu_bh_3x, s_bh_mu_3x)) / INVEST * 100 if best_mu_val > 0 else -100
    composite = (nvda_pair_score + mu_pair_score) / 2

    results.append({
        'ticker': ticker,
        'vol': vol,
        'corr_nvda': corr_nvda,
        'corr_mu': corr_mu,
        'max_dd': max_dd,
        'total_ret': total_ret,
        'nvda_rot_val': best_3x_val,
        'nvda_rot_th': best_3x_th,
        'nvda_rot_ret': rot_ret,
        'nvda_bh_3x': nvda_bh_3x,
        'nvda_ko_3x': nvda_ko_3x,
        's_bh_nvda_3x': s_bh_3x,
        's_ko_nvda_3x': s_ko_3x,
        'beats_worse_nvda': beats_worse,
        'beats_better_nvda': beats_better,
        'mu_rot_val': best_mu_val,
        'mu_rot_th': best_mu_th,
        'mu_bh_3x': mu_bh_3x,
        'mu_ko_3x': mu_ko_3x,
        's_bh_mu_3x': s_bh_mu_3x,
        's_ko_mu_3x': s_ko_mu_3x,
        'composite': composite,
    })
    print(f"  {ticker}: vol={vol:.1f}% corr_NVDA={corr_nvda:.3f} corr_MU={corr_mu:.3f} maxDD={max_dd:.1f}% 10Y_ret={total_ret:+.0f}% | NVDA_pair=${best_3x_val:,.0f} ({best_3x_th:.0%}) MU_pair=${best_mu_val:,.0f} ({best_mu_th:.0%})")

# ── RANKING ──
results.sort(key=lambda x: x['composite'], reverse=True)

print(f"\n{'='*140}")
print(f"  FINAL RANKING: Best Rotation Partners for NVDA and MU (10Y, 3x Leverage)")
print(f"{'='*140}")
print(f"  {'Rank':<5} {'Ticker':<7} {'Vol':>6} {'Corr NVDA':>10} {'Corr MU':>10} {'MaxDD':>7} {'10Y Ret':>8} | {'+NVDA 3x':>10} {'Th':>5} {'vWorse':>6} {'vBetter':>7} | {'+MU 3x':>10} {'Th':>5} | {'Score':>8} {'Verdict':>20}")
print(f"  {'-'*5} {'-'*7} {'-'*6} {'-'*10} {'-'*10} {'-'*7} {'-'*8}-+-{'-'*10} {'-'*5} {'-'*6} {'-'*7}-+-{'-'*10} {'-'*5}-+-{'-'*8} {'-'*20}")

for i, r in enumerate(results, 1):
    nvda_rot_ret = (r['nvda_rot_val'] / INVEST - 1) * 100
    mu_rot_ret = (r['mu_rot_val'] / INVEST - 1) * 100

    if r['composite'] > 50:
        verdict = '★★★ Top Pick'
    elif r['composite'] > 0:
        verdict = '★★ Good'
    elif r['composite'] > -50:
        verdict = '★ OK'
    else:
        verdict = '✗ Poor'

    print(f"  {i:<5} {r['ticker']:<7} {r['vol']:>5.1f}% {r['corr_nvda']:>10.3f} {r['corr_mu']:>10.3f} {r['max_dd']:>6.1f}% {r['total_ret']:>+7.0f}% | ${r['nvda_rot_val']:>9,.0f} {r['nvda_rot_th']:>4.0%} {r['beats_worse_nvda']:>6} {r['beats_better_nvda']:>7} | ${r['mu_rot_val']:>9,.0f} {r['mu_rot_th']:>4.0%} | {r['composite']:>+7.0f}% {verdict:>20}")

print(f"\n  Score = avg excess return of (NVDA+X) and (MU+X) rotation vs same-lev worse BH")
print(f"  Top picks have: high vol, low correlation with anchors, rotation beats same-lev BH")
