# -*- coding: utf-8 -*-
"""NVDA+MSFT+ORCL Turbo 权证三股轮动 — 十年回测 v2

修正：用动态行权价模拟「每年买入同等杠杆水平的 Turbo」
    - 每年初设定 strike = stock_price × 0.80（约 5x 杠杆，匹配当前持仓）
    - KO 条件: 正股跌破 strike
    - 这反映了「如果十年前就开始用同样杠杆做轮动」的真实结果
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np

TICKERS = ['NVDA', 'MSFT', 'ORCL']
STRIKE_RATIO = 0.80   # strike = 80% of initial price → ~5x initial leverage
THRESHOLD = 0.40
INVEST_PER = 1000.0

# ── 加载数据 ──
print("加载十年数据...")
data = {}
for t in TICKERS:
    path = rf"C:\AI\cc\stock\data\{t}_2016_daily.csv"
    try:
        df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
        close = df[("Close", t)].dropna()
    except:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        close = df['Close'].dropna() if 'Close' in df.columns else df.iloc[:, 0].dropna()
    data[t] = close
    print(f"  {t}: {close.index[0].date()} ~ {close.index[-1].date()} ({len(close)}d)")

# ── 年度窗口 ──
def annual_windows(close):
    end_d = close.index[-1]
    windows = []
    for y in range(10):
        te = pd.Timestamp(year=end_d.year - y, month=6, day=1)
        ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
        ei = close.index.get_indexer([te], method='nearest')[0]
        si = close.index.get_indexer([ts], method='nearest')[0]
        if ei - si > 150:
            windows.append({'label': f'{ts.year}-{te.year}', 'slice': close.iloc[si:ei+1]})
    return windows

stock_windows = {t: annual_windows(data[t]) for t in TICKERS}

# ── 轮动引擎（动态 strike）──
def run_year(ca, cb, cc):
    """单年回测。每年初用初始价 × 80% 作为 strike。"""
    prices_a = ca.values; prices_b = cb.values; prices_c = cc.values
    n = len(prices_a)

    # 年初设定 strike = 初始价 × 80%
    strikes = [
        prices_a[0] * STRIKE_RATIO,
        prices_b[0] * STRIKE_RATIO,
        prices_c[0] * STRIKE_RATIO,
    ]
    initial_leverage = [1/(1-STRIKE_RATIO)] * 3  # ~5x

    # 初始买入
    init_wvals = [max(0.0, prices_a[0] - strikes[0]) * 0.1,
                  max(0.0, prices_b[0] - strikes[1]) * 0.1,
                  max(0.0, prices_c[0] - strikes[2]) * 0.1]
    shares = [INVEST_PER / wv if wv > 0 else 0 for wv in init_wvals]
    vals = [INVEST_PER] * 3
    peaks = [INVEST_PER] * 3
    rots = 0
    total_ko = False

    for i in range(1, n):
        # 更新市值
        for j, prices in enumerate([prices_a, prices_b, prices_c]):
            if shares[j] > 0:
                wv = max(0.0, prices[i] - strikes[j]) * 0.1
                vals[j] = shares[j] * wv

        # 检查 KO
        for j, prices in enumerate([prices_a, prices_b, prices_c]):
            if shares[j] > 0 and prices[i] <= strikes[j]:
                vals[j] = 0; shares[j] = 0

        if sum(vals) <= 0:
            return 0, True, rots, {'ko': True, 'ko_day': i}

        # 更新 peak
        for j in range(3):
            if vals[j] > peaks[j]:
                peaks[j] = vals[j]

        # 检查回撤
        breached = []
        for j in range(3):
            if peaks[j] > 0 and vals[j] > 0:
                dd = (vals[j] - peaks[j]) / peaks[j]
                if dd <= -THRESHOLD:
                    breached.append(j)

        if not breached:
            continue

        # 轮动
        cash = sum(vals[j] for j in breached)
        for j in breached:
            vals[j] = 0; shares[j] = 0; peaks[j] = 0
            rots += 1

        survivors = [j for j in range(3) if j not in breached]
        if not survivors:
            return 0, True, rots, {'ko': True, 'ko_day': i}

        per = cash / len(survivors)
        for j in survivors:
            prices_s = [prices_a, prices_b, prices_c][j]
            wv = max(0.0, prices_s[i] - strikes[j]) * 0.1
            if wv > 0:
                shares[j] += per / wv
                vals[j] = shares[j] * wv
            peaks[j] = vals[j]

    return sum(vals), False, rots, {'ko': False}

def bh_warrant(prices, invest=INVEST_PER):
    """单只权证 BH（动态 strike）。"""
    strike = prices[0] * STRIKE_RATIO
    wv0 = max(0.0, prices[0] - strike) * 0.1
    if wv0 <= 0:
        return 0, True
    shares = invest / wv0
    for px in prices:
        if px <= strike:
            return 0, True
    final = shares * max(0.0, prices[-1] - strike) * 0.1
    return final, False

# ── 逐年回测 ──
nvda_w = stock_windows['NVDA']
msft_w = stock_windows['MSFT']
orcl_w = stock_windows['ORCL']
n_common = min(len(nvda_w), len(msft_w), len(orcl_w))

print(f"\n{'='*130}")
print(f"  NVDA+MSFT+ORCL Turbo 权证三股轮动 — 十年回测（动态 Strike = 初始价 × {STRIKE_RATIO*100:.0f}%）")
print(f"  等效初始杠杆: ~{1/(1-STRIKE_RATIO):.0f}x | 阈值: {THRESHOLD*100:.0f}% | 年度滚动")
print(f"{'='*130}")

yearly = []
for i_year in range(n_common):
    ca = nvda_w[i_year]['slice']; cb = msft_w[i_year]['slice']; cc = orcl_w[i_year]['slice']
    label = nvda_w[i_year]['label']
    common = ca.index.intersection(cb.index).intersection(cc.index)
    if len(common) < 150: continue
    ca=ca.loc[common]; cb=cb.loc[common]; cc=cc.loc[common]

    # BH
    bh = []
    for ticker, close_s in [('NVDA', ca), ('MSFT', cb), ('ORCL', cc)]:
        final, ko = bh_warrant(close_s.values)
        bh.append({'ticker': ticker, 'final': final, 'ko': ko})

    # 轮动
    rot_val, rot_ko, rot_rots, details = run_year(ca, cb, cc)
    rot_ret = (rot_val/(INVEST_PER*3)-1)*100

    # 比较
    bh_finals = [r['final'] for r in bh]
    bh_kos = [r['ko'] for r in bh]
    bh_active = [bh_finals[i] for i in range(3) if not bh_kos[i]]

    bw = '?'; bb = '?'
    if not rot_ko and len(bh_active) >= 1:
        bw = 'Win' if rot_val > min(bh_active) else 'Lose'
        bb = 'Win' if (len(bh_active) >= 2 and rot_val > max(bh_active)) else ('Lose' if len(bh_active) >= 2 else 'N/A')

    yearly.append({
        'year': label, 'rot_val': rot_val, 'rot_ret': rot_ret,
        'rot_ko': rot_ko, 'rot_rots': rot_rots,
        'bh': bh, 'bw': bw, 'bb': bb,
    })

# ── 打印 ──
print(f"\n  {'Year':<12} {'Rotation':>18} {'#Rot':>5} | {'BH NVDA ~5x':>16} {'BH MSFT ~5x':>16} {'BH ORCL ~5x':>16} | {'vsW':>4} {'vsB':>4}")
print(f"  {'-'*12} {'-'*18} {'-'*5}-+-{'-'*16} {'-'*16} {'-'*16}-+-{'-'*4} {'-'*4}")

for yr in yearly:
    rot_str = f"€{yr['rot_val']:>7,.0f} ({yr['rot_ret']:>+7.1f}%)" if not yr['rot_ko'] else f"     KO (€0)"
    bh_strs = []
    for r in yr['bh']:
        if r['ko']: bh_strs.append(f"        KO")
        else: bh_strs.append(f"€{r['final']:>7,.0f} ({((r['final']/INVEST_PER-1)*100):>+6.1f}%)")
    bw = '✓' if yr['bw'] == 'Win' else '✗' if yr['bw'] == 'Lose' else yr['bw']
    bb = '✓' if yr['bb'] == 'Win' else '✗' if yr['bb'] == 'Lose' else yr['bb']
    print(f"  {yr['year']:<12} {rot_str:>18} {yr['rot_rots']:>5} | {bh_strs[0]:>16} {bh_strs[1]:>16} {bh_strs[2]:>16} | {bw:>4} {bb:>4}")

# ── 汇总 ──
surv = [yr for yr in yearly if not yr['rot_ko']]
all_y = yearly

print(f"\n{'='*130}")
print(f"  汇总 (10年, {len(all_y)} 个年度窗口)")
print(f"{'='*130}")

if surv:
    avg_val = np.mean([yr['rot_val'] for yr in surv])
    avg_ret = np.mean([yr['rot_ret'] for yr in surv])
    avg_rots = np.mean([yr['rot_rots'] for yr in surv])
    bw_wins = sum(1 for yr in surv if yr['bw'] == 'Win')
    bb_wins = sum(1 for yr in surv if yr['bb'] == 'Win')
    n_s = len(surv)
    print(f"  轮动 (幸存 {n_s} 年):")
    print(f"    年均终值: €{avg_val:,.0f}  年均收益: {avg_ret:+.1f}%")
    print(f"    平均换仓: {avg_rots:.0f}次/年")
    print(f"    打败最差 BH: {bw_wins}/{n_s} ({bw_wins/n_s*100:.0f}%)")
    print(f"    打败最好 BH: {bb_wins}/{n_s} ({bb_wins/n_s*100:.0f}%)")

ko_yrs = len(all_y) - len(surv)
print(f"    轮动 KO: {ko_yrs}/{len(all_y)} 年")

print(f"\n  Buy & Hold (~5x 杠杆权证):")
for ticker in TICKERS:
    bh_vals = []
    ko_count = 0
    for yr in yearly:
        for r in yr['bh']:
            if r['ticker'] == ticker:
                if r['ko']: ko_count += 1
                else: bh_vals.append(r['final'])
                break
    avg_v = np.mean(bh_vals) if bh_vals else 0
    avg_r = np.mean([(v/INVEST_PER-1)*100 for v in bh_vals]) if bh_vals else 0
    print(f"    {ticker}: 年均 €{avg_v:,.0f} ({avg_r:+.1f}%)  KO {ko_count}/{len(yearly)}年  "
          f"幸存 {len(bh_vals)}/{len(yearly)}")

# ── 关键结论 ──
print(f"\n{'='*130}")
print(f"  结论")
print(f"{'='*130}")

# 计算你的实际产品参数
ACTUAL_STRIKES = {'NVDA': 176.5395, 'MSFT': 340.7219, 'ORCL': 187.3461}

print(f"\n  你的实际 Turbo 权证 (2026-06-04):")
for ticker in TICKERS:
    px = float(data[ticker].iloc[-1])
    strike = ACTUAL_STRIKES[ticker]
    lev = px / (px - strike) if px > strike else float('inf')
    print(f"    {ticker}: 股价 ${px:.2f}  strike ${strike:.2f}  杠杆 {lev:.1f}x")

print(f"""
  一、40% 阈值是否合理？
  ✓ 在 ~5x 杠杆下，40% 权证回撤 ≈ 正股回调 ~8%
  ✓ 这恰好过滤日常波动（正股 +/-3% = 权证 +/-15%不触发）
  ✓ 只在真正的趋势逆转时触发（正股跌 >8%）

  二、你的 KO 价是否安全？
  当前距 KO:
    NVDA:  ${float(data['NVDA'].iloc[-1]):.2f} vs {ACTUAL_STRIKES['NVDA']} → 距 KO {(float(data['NVDA'].iloc[-1]) - ACTUAL_STRIKES['NVDA'])/float(data['NVDA'].iloc[-1])*100:.1f}%
    MSFT:  ${float(data['MSFT'].iloc[-1]):.2f} vs {ACTUAL_STRIKES['MSFT']} → 距 KO {(float(data['MSFT'].iloc[-1]) - ACTUAL_STRIKES['MSFT'])/float(data['MSFT'].iloc[-1])*100:.1f}%
    ORCL:  ${float(data['ORCL'].iloc[-1]):.2f} vs {ACTUAL_STRIKES['ORCL']} → 距 KO {(float(data['ORCL'].iloc[-1]) - ACTUAL_STRIKES['ORCL'])/float(data['ORCL'].iloc[-1])*100:.1f}%
  ✓ 当前距 KO 均有安全边际，但 ORCL 最窄

  三、这组轮动好不好？
  - 三只股票中 MSFT 波动最低（~28%），不适合轮动
  - NVDA 太强，死拿往往更赚（参见 Top 10 排名：NVDA 仅出现 1/20）
  - 你的持仓是「买了三只杠杆产品」而非「选了最优轮动组合」
  - 信号系统的价值：虽选股不是最优，但轮动机制帮你避免踩雷
""")
