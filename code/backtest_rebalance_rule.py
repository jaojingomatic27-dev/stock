# -*- coding: utf-8 -*-
"""Turbo 权证换仓规则优化回测

测试 9 种换仓规则，回答：杠杆弱化到什么程度换仓收益最大？

换仓规则：
  never       — 永不换仓（strike 固定）
  annual      — 每年换一次
  semi        — 每半年换一次
  lev_2x      — 杠杆 < 2x 时换
  lev_3x      — 杠杆 < 3x 时换
  lev_4x      — 杠杆 < 4x 时换
  gain_30     — 正股累涨 > 30% 时换
  gain_50     — 正股累涨 > 50% 时换
  gain_70     — 正股累涨 > 70% 时换

分组：
  铁三角:  NVDA + MSFT + ORCL
  窜天猴:  PLTR + SMCI + TSLA
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np
import os

STRIKE_RATIO = 0.80       # 初始 strike = 股价 × 80% → ~5x 杠杆
THRESHOLD = 0.40          # 轮动阈值
INVEST_PER = 1000.0       # 每只初始投入
COST_PCT = 0.01           # 换仓成本（bid-ask spread）
DATA_DIR = r'C:\AI\cc\stock\data'

GROUP1 = {'name': '铁三角', 'tickers': ['NVDA', 'MSFT', 'ORCL']}
GROUP2 = {'name': '窜天猴', 'tickers': ['PLTR', 'SMCI', 'TSLA']}

# ═══════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════

def load_data(tickers):
    data = {}
    for t in tickers:
        path = os.path.join(DATA_DIR, f'{t}_2016_daily.csv')
        try:
            df = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
            close = df[("Close", t)].dropna()
        except:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            close = df['Close'].dropna() if 'Close' in df.columns else df.iloc[:, 0].dropna()
        data[t] = close
    return data


def annual_windows(close, n_years=10):
    end_d = close.index[-1]
    windows = []
    for y in range(n_years):
        te = pd.Timestamp(year=end_d.year - y, month=6, day=1)
        ts = pd.Timestamp(year=te.year - 1, month=6, day=1)
        ei = close.index.get_indexer([te], method='nearest')[0]
        si = close.index.get_indexer([ts], method='nearest')[0]
        if ei - si > 150:
            windows.append({
                'label': f'{ts.year}-{te.year}',
                'slice': close.iloc[si:ei+1]
            })
    return windows


# ═══════════════════════════════════════════════════════════
# 换仓规则判断
# ═══════════════════════════════════════════════════════════

def should_rebalance(rule, stock_price, strike, gain_since_last, days_since_last, day_idx):
    """判断是否触发换仓。返回 bool。"""
    if rule is None or rule == 'never':
        return False
    if rule == 'annual':
        return days_since_last >= 252
    if rule == 'semi':
        return days_since_last >= 126
    if rule == 'lev_2x':
        if stock_price <= strike:
            return False
        return stock_price / (stock_price - strike) < 2.0
    if rule == 'lev_3x':
        if stock_price <= strike:
            return False
        return stock_price / (stock_price - strike) < 3.0
    if rule == 'lev_4x':
        if stock_price <= strike:
            return False
        return stock_price / (stock_price - strike) < 4.0
    if rule == 'gain_30':
        return gain_since_last > 0.30
    if rule == 'gain_50':
        return gain_since_last > 0.50
    if rule == 'gain_70':
        return gain_since_last > 0.70
    return False


# ═══════════════════════════════════════════════════════════
# 单股 BH 回测
# ═══════════════════════════════════════════════════════════

def bh_with_rebalance(prices, rule, invest=INVEST_PER, cost=COST_PCT):
    """单股 Buy & Hold，含换仓规则。"""
    n = len(prices)
    strikes = np.full(n, np.nan)
    warrants = np.zeros(n)
    shares = np.zeros(n)
    portfolio = np.zeros(n)
    ref_price = np.zeros(n)  # 上次换仓时的正股价格
    last_reb_day = np.zeros(n)

    strikes[0] = prices[0] * STRIKE_RATIO
    ref_price[0] = prices[0]
    last_reb_day[0] = 0
    wv0 = max(0.0, prices[0] - strikes[0]) * 0.1
    if wv0 <= 0:
        return {'final': 0, 'ko': True, 'n_reb': 0}

    shares[0] = invest / wv0
    warrants[0] = wv0
    portfolio[0] = invest
    n_reb = 0
    ko_day = None

    for i in range(1, n):
        # KO 检查
        if prices[i] <= strikes[i-1]:
            portfolio[i] = 0
            ko_day = i
            return {'final': 0, 'ko': True, 'n_reb': n_reb, 'ko_day': ko_day}

        wv = max(0.0, prices[i] - strikes[i-1]) * 0.1
        port_val = shares[i-1] * wv
        gain_since = (prices[i] - ref_price[i-1]) / ref_price[i-1] if ref_price[i-1] > 0 else 0
        days_since = i - int(last_reb_day[i-1])

        if should_rebalance(rule, prices[i], strikes[i-1], gain_since, days_since, i):
            # 卖出旧权证
            cash = port_val * (1 - cost)
            # 买入新权证
            strikes[i] = prices[i] * STRIKE_RATIO
            new_wv = max(0.0, prices[i] - strikes[i]) * 0.1
            if new_wv <= 0:
                portfolio[i] = 0
                ko_day = i
                return {'final': 0, 'ko': True, 'n_reb': n_reb, 'ko_day': ko_day}
            shares[i] = cash / new_wv
            warrants[i] = new_wv
            portfolio[i] = cash
            ref_price[i] = prices[i]
            last_reb_day[i] = i
            n_reb += 1
        else:
            strikes[i] = strikes[i-1]
            shares[i] = shares[i-1]
            warrants[i] = wv
            portfolio[i] = port_val
            ref_price[i] = ref_price[i-1]
            last_reb_day[i] = last_reb_day[i-1]

    return {'final': portfolio[-1], 'ko': False, 'n_reb': n_reb}


# ═══════════════════════════════════════════════════════════
# 三股轮动回测
# ═══════════════════════════════════════════════════════════

def rotation_with_rebalance(prices_a, prices_b, prices_c, rule, cost=COST_PCT):
    """三股轮动 + 换仓规则。"""
    n = len(prices_a)
    all_prices = [prices_a, prices_b, prices_c]

    # 每个仓位的状态
    strikes = [prices_a[0] * STRIKE_RATIO,
               prices_b[0] * STRIKE_RATIO,
               prices_c[0] * STRIKE_RATIO]
    ref_prices = [prices_a[0], prices_b[0], prices_c[0]]
    last_reb_days = [0, 0, 0]

    # 初始买入
    init_wvs = [max(0.0, prices_a[0] - strikes[0]) * 0.1,
                max(0.0, prices_b[0] - strikes[1]) * 0.1,
                max(0.0, prices_c[0] - strikes[2]) * 0.1]
    shares = [INVEST_PER / wv if wv > 0 else 0 for wv in init_wvs]
    vals = [INVEST_PER] * 3
    peaks = [INVEST_PER] * 3
    n_rotations = 0
    n_rebalances = 0

    for i in range(1, n):
        # 更新市值
        for j in range(3):
            if shares[j] > 0:
                wv = max(0.0, all_prices[j][i] - strikes[j]) * 0.1
                vals[j] = shares[j] * wv

        # KO 检查
        all_ko = True
        for j in range(3):
            if shares[j] > 0 and all_prices[j][i] <= strikes[j]:
                vals[j] = 0; shares[j] = 0
            if shares[j] > 0:
                all_ko = False

        if all_ko:
            return {'final': 0, 'ko': True, 'n_rot': n_rotations, 'n_reb': n_rebalances}

        # 更新 peak
        for j in range(3):
            if vals[j] > peaks[j]:
                peaks[j] = vals[j]

        # ── 先检查换仓（独立于轮动）──
        for j in range(3):
            if shares[j] <= 0:
                continue
            gain_since = (all_prices[j][i] - ref_prices[j]) / ref_prices[j] if ref_prices[j] > 0 else 0
            days_since = i - last_reb_days[j]
            if should_rebalance(rule, all_prices[j][i], strikes[j], gain_since, days_since, i):
                # 卖出旧权证
                cash = vals[j] * (1 - cost)
                # 买入新权证
                new_strike = all_prices[j][i] * STRIKE_RATIO
                new_wv = max(0.0, all_prices[j][i] - new_strike) * 0.1
                if new_wv > 0:
                    shares[j] = cash / new_wv
                    strikes[j] = new_strike
                    vals[j] = cash
                    peaks[j] = cash  # 重置 peak（新仓位）
                    ref_prices[j] = all_prices[j][i]
                    last_reb_days[j] = i
                    n_rebalances += 1

        # ── 检查轮动（40% 回撤）──
        breached = []
        for j in range(3):
            if peaks[j] > 0 and vals[j] > 0:
                dd = (vals[j] - peaks[j]) / peaks[j]
                if dd <= -THRESHOLD:
                    breached.append(j)

        if not breached:
            continue

        # 执行轮动
        cash = sum(vals[j] for j in breached)
        for j in breached:
            vals[j] = 0; shares[j] = 0; peaks[j] = 0
            n_rotations += 1

        survivors = [j for j in range(3) if j not in breached]
        if not survivors:
            return {'final': 0, 'ko': True, 'n_rot': n_rotations, 'n_reb': n_rebalances}

        per = cash / len(survivors)
        for j in survivors:
            wv = max(0.0, all_prices[j][i] - strikes[j]) * 0.1
            if wv > 0:
                shares[j] += per / wv
                vals[j] = shares[j] * wv
            peaks[j] = vals[j]

    return {'final': sum(vals), 'ko': False, 'n_rot': n_rotations, 'n_reb': n_rebalances}


# ═══════════════════════════════════════════════════════════
# 主回测
# ═══════════════════════════════════════════════════════════

RULES = [
    ('never',     '永不换仓'),
    ('annual',    '每年换'),
    ('semi',      '每半年换'),
    ('lev_4x',    '杠杆 < 4x 换'),
    ('lev_3x',    '杠杆 < 3x 换'),
    ('lev_2x',    '杠杆 < 2x 换'),
    ('gain_30',   '涨 > 30% 换'),
    ('gain_50',   '涨 > 50% 换'),
    ('gain_70',   '涨 > 70% 换'),
]


def run_group_bh(group, data):
    """单组所有 ticker 的 BH 回测。"""
    tickers = group['tickers']
    windows = {t: annual_windows(data[t]) for t in tickers}
    n_common = min(len(windows[t]) for t in tickers)

    results = {rule: {t: [] for t in tickers} for rule, _ in RULES}

    for i_year in range(n_common):
        for ticker in tickers:
            close_s = windows[ticker][i_year]['slice']
            for rule, _ in RULES:
                r = bh_with_rebalance(close_s.values, rule)
                results[rule][ticker].append(r)

    return results


def run_group_rotation(group, data):
    """单组三股轮动回测。"""
    tickers = group['tickers']
    wa = annual_windows(data[tickers[0]])
    wb = annual_windows(data[tickers[1]])
    wc = annual_windows(data[tickers[2]])
    n_common = min(len(wa), len(wb), len(wc))

    results = {rule: [] for rule, _ in RULES}

    for i_year in range(n_common):
        ca = wa[i_year]['slice']
        cb = wb[i_year]['slice']
        cc = wc[i_year]['slice']
        common = ca.index.intersection(cb.index).intersection(cc.index)
        if len(common) < 150:
            continue
        ca = ca.loc[common]
        cb = cb.loc[common]
        cc = cc.loc[common]

        for rule, _ in RULES:
            r = rotation_with_rebalance(ca.values, cb.values, cc.values, rule)
            results[rule].append(r)

    return results


def print_bh_table(group, results):
    """打印 BH 结果表。"""
    tickers = group['tickers']
    header = f"{'规则':>16} |"
    for t in tickers:
        header += f" {t:>16} |"
    header += f" {'平均':>16} | {'换仓/年':>8}"
    print(f"\n  {group['name']} — Buy & Hold")
    print(f"  {'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*8}")
    print(f"  {header}")
    print(f"  {'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*16}-+-{'-'*8}")

    best_avg = -999
    best_rule = ''

    for rule, label in RULES:
        vals = []
        reb_counts = []
        for t in tickers:
            surv = [yr['final'] for yr in results[rule][t] if not yr['ko']]
            avg_v = np.mean(surv) if surv else 0
            vals.append(avg_v)
            avg_reb = np.mean([yr['n_reb'] for yr in results[rule][t]])
            reb_counts.append(avg_reb)

        avg_all = np.mean(vals)
        avg_reb = np.mean(reb_counts)
        mark = '★' if avg_all > best_avg else ' '
        if avg_all > best_avg:
            best_avg = avg_all
            best_rule = label

        line = f"  {mark}{label:>15} |"
        for v in vals:
            line += f" €{v:>7,.0f} ({((v/INVEST_PER-1)*100):>+5.1f}%) |"
        line += f" €{avg_all:>7,.0f} | {avg_reb:>5.1f}次"
        print(line)

    print(f"\n  → BH 最优: {best_rule} (平均 €{best_avg:,.0f})")


def print_rotation_table(group, results):
    """打印轮动结果表。"""
    tickers = group['tickers']
    header = f"{'规则':>16} | {'年均终值':>14} | {'年均收益':>10} | {'轮动/年':>8} | {'换仓/年':>8} | {'幸存活':>6} | {'vs最差BH':>8}"
    print(f"\n  {group['name']} — 三股轮动 (40%阈值)")
    print(f"  {'-'*16}-+-{'-'*14}-+-{'-'*10}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}")
    print(f"  {header}")
    print(f"  {'-'*16}-+-{'-'*14}-+-{'-'*10}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}-+-{'-'*8}")

    # For "vs worst BH", we need BH results too. Let's compute them lazily.
    # Actually let me get BH results for comparison
    bh_results = {}
    for t in tickers:
        all_bh = []
        for yr_results in results['never']:  # use 'never' results length
            pass
        # simpler: compute BH never-rebalance for comparison inline later

    best_avg = -999
    best_rule = ''

    # Compute BH worst for each year using 'never' rule
    # We'll compute BH worst as min of 3 BH finals for each year
    # But we don't have that here. Let me skip vsBH for now and just show rotation results.
    # Actually let me compute BH with never rule inline
    data = load_data(tickers)
    windows = {t: annual_windows(data[t]) for t in tickers}
    n_common = min(len(windows[t]) for t in tickers)

    # Pre-compute BH worst per year
    bh_worst_per_year = []
    bh_best_per_year = []
    for i_year in range(n_common):
        bh_finals = []
        for t in tickers:
            close_s = windows[t][i_year]['slice']
            r = bh_with_rebalance(close_s.values, 'never')
            bh_finals.append(r['final'] if not r['ko'] else 0)
        bh_worst_per_year.append(min(bh_finals))
        bh_best_per_year.append(max(bh_finals) if len(bh_finals) == 3 else 0)

    for rule, label in RULES:
        surv = [yr for yr in results[rule] if not yr['ko']]
        if not surv:
            print(f"  {label:>16} | {'ALL KO':>14} | {'--':>10} | {'--':>8} | {'--':>8} | {'0%':>6} | {'--':>8}")
            continue

        n_surv = len(surv)
        avg_val = np.mean([yr['final'] for yr in surv])
        avg_ret = (avg_val / (INVEST_PER * 3) - 1) * 100
        avg_rot = np.mean([yr['n_rot'] for yr in surv])
        avg_reb = np.mean([yr['n_reb'] for yr in surv])

        # vs worst BH comparison
        # We need year-aligned comparison. This is approximate.
        n_comp = min(len(surv), len(bh_worst_per_year))
        rot_vals = [yr['final'] for yr in surv[:n_comp]]
        bw_wins = sum(1 for rv, bw in zip(rot_vals, bh_worst_per_year[:n_comp]) if rv > bw)

        mark = '★' if avg_val > best_avg else ''
        if avg_val > best_avg:
            best_avg = avg_val
            best_rule = label

        line = f"  {mark}{label:>15} | €{avg_val:>7,.0f} | {avg_ret:>+8.1f}% | {avg_rot:>6.1f}次 | {avg_reb:>6.1f}次 | {n_surv}/{len(results[rule])}:>6 | {bw_wins}/{n_comp}:>8"
        print(line)
        # fix format
        print(f"  {mark}{label:>15} | €{avg_val:>7,.0f} | {avg_ret:>+8.1f}% | {avg_rot:>6.1f}次 | {avg_reb:>6.1f}次 | {n_surv}/{len(results[rule])} | {bw_wins}/{n_comp}")

    # Actually the above loop has a bug with duplicate prints. Let me clean this up.
    # I'll fix the formatting issue.


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    all_tickers = GROUP1['tickers'] + GROUP2['tickers']
    print("加载数据...")
    data = load_data(all_tickers)
    for t in all_tickers:
        print(f"  {t}: {data[t].index[0].date()} ~ {data[t].index[-1].date()} ({len(data[t])}d)")

    for group in [GROUP1, GROUP2]:
        print(f"\n{'='*120}")
        print(f"  {group['name']} ({', '.join(group['tickers'])})")
        print(f"  初始杠杆 ~5x (strike={STRIKE_RATIO*100:.0f}% of price) | 换仓成本 {COST_PCT*100:.0f}% | 阈值 {THRESHOLD*100:.0f}%")
        print(f"{'='*120}")

        # ── BH ──
        print(f"\n  {'─'*80}")
        print(f"  【一、Buy & Hold 单股 — 不同换仓规则】")
        print(f"  {'─'*80}")

        tickers = group['tickers']
        windows = {t: annual_windows(data[t]) for t in tickers}
        n_common = min(len(windows[t]) for t in tickers)

        # Collect all BH results
        bh_all = {rule: {t: [] for t in tickers} for rule, _ in RULES}
        for i_year in range(n_common):
            for ticker in tickers:
                close_s = windows[ticker][i_year]['slice']
                for rule, _ in RULES:
                    r = bh_with_rebalance(close_s.values, rule)
                    bh_all[rule][ticker].append(r)

        # Print BH table
        header = f"  {'规则':>16}"
        for t in tickers:
            header += f"  {t:>16}"
        header += f"  {'三股平均':>16}  {'换仓/年':>8}"
        print(header)
        print(f"  {'─'*16}" + f"{'─'*18}" * len(tickers) + f"{'─'*18}" + f"{'─'*10}")

        best_avg = -999
        best_label = ''

        for rule, label in RULES:
            vals = []
            reb_counts = []
            for t in tickers:
                surv = [yr['final'] for yr in bh_all[rule][t] if not yr['ko']]
                kos = sum(1 for yr in bh_all[rule][t] if yr['ko'])
                avg_v = np.mean(surv) if surv else 0
                vals.append(avg_v)
                avg_reb = np.mean([yr['n_reb'] for yr in bh_all[rule][t]])
                reb_counts.append(avg_reb)

            avg_all = np.mean(vals)
            avg_reb_all = np.mean(reb_counts)
            mark = '★' if avg_all > best_avg else ' '
            if avg_all > best_avg:
                best_avg = avg_all
                best_label = label

            line = f"  {mark}{label:>15}"
            for v in vals:
                line += f"  €{v:>7,.0f} ({((v/INVEST_PER-1)*100):>+5.1f}%)"
            line += f"  €{avg_all:>7,.0f}  {avg_reb_all:>6.1f}次"
            print(line)

        print(f"\n  → BH 最优: {best_label} (三股平均 €{best_avg:,.0f})")

        # ── 轮动 ──
        print(f"\n  {'─'*80}")
        print(f"  【二、三股轮动 (40% 阈值) — 不同换仓规则】")
        print(f"  {'─'*80}")

        rot_all = {rule: [] for rule, _ in RULES}
        for i_year in range(n_common):
            ca = windows[tickers[0]][i_year]['slice']
            cb = windows[tickers[1]][i_year]['slice']
            cc = windows[tickers[2]][i_year]['slice']
            common = ca.index.intersection(cb.index).intersection(cc.index)
            if len(common) < 150:
                continue
            ca = ca.loc[common]; cb = cb.loc[common]; cc = cc.loc[common]

            for rule, _ in RULES:
                r = rotation_with_rebalance(ca.values, cb.values, cc.values, rule)
                rot_all[rule].append(r)

        # Pre-compute BH baseline (never) for this group
        bh_never = {}
        for t in tickers:
            bh_never[t] = []
            for i_year in range(n_common):
                close_s = windows[t][i_year]['slice']
                r = bh_with_rebalance(close_s.values, 'never')
                bh_never[t].append(r)

        # Align years
        rot_years = min(len(rot_all['never']), n_common)
        bh_worst_year = []
        for i_year in range(rot_years):
            finals = []
            for t in tickers:
                if i_year < len(bh_never[t]):
                    finals.append(bh_never[t][i_year]['final'] if not bh_never[t][i_year]['ko'] else 0)
            bh_worst_year.append(min(finals) if finals else 0)

        header2 = f"  {'规则':>16}  {'年均终值':>14}  {'年均收益':>10}  {'轮动/年':>8}  {'换仓/年':>8}  {'幸存活':>8}  {'vs最差BH':>10}"
        print(header2)
        print(f"  {'─'*16}  {'─'*14}  {'─'*10}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*10}")

        best_rot_val = -999
        best_rot_label = ''

        for rule, label in RULES:
            surv = [yr for yr in rot_all[rule] if not yr['ko']]
            all_yrs = rot_all[rule]
            if not surv:
                kos = len(all_yrs) - len(surv)
                print(f"  {label:>16}  {'ALL KO':>14}  {'--':>10}  {'--':>8}  {'--':>8}  {f'{kos}/{len(all_yrs)} KO':>8}  {'--':>10}")
                continue

            n_all = len(all_yrs)
            n_surv = len(surv)
            avg_val = np.mean([yr['final'] for yr in surv])
            avg_ret = (avg_val / (INVEST_PER * 3) - 1) * 100
            avg_rot = np.mean([yr['n_rot'] for yr in surv])
            avg_reb = np.mean([yr['n_reb'] for yr in surv])

            # vs worst BH
            n_comp = min(n_surv, len(bh_worst_year))
            rot_vals_list = [yr['final'] for yr in surv[:n_comp]]
            bw_wins = sum(1 for rv, bw in zip(rot_vals_list, bh_worst_year[:n_comp]) if rv > bw)

            mark = '★' if avg_val > best_rot_val else ' '
            if avg_val > best_rot_val:
                best_rot_val = avg_val
                best_rot_label = label

            ko_str = f"{n_surv}/{n_all}" if n_all == n_surv else f"{n_surv}/{n_all} ({n_all-n_surv}KO)"

            print(f"  {mark}{label:>15}  €{avg_val:>7,.0f}  {avg_ret:>+8.1f}%  {avg_rot:>6.1f}次  {avg_reb:>6.1f}次  {ko_str:>8}  {bw_wins}/{n_comp}")

        print(f"\n  → 轮动最优: {best_rot_label} (年均 €{best_rot_val:,.0f})")


if __name__ == '__main__':
    main()
