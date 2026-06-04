# -*- coding: utf-8 -*-
"""DCA 每月定投提醒 + RSI 跟进邮件

每月在最佳买入日（1号+7天后的第一个交易日）发送定投提醒邮件，
一周后自动发送 RSI 跟进邮件，评价当时买入的 RSI 水平。

用法：
  python dca_monthly_reminder.py                # 检查是否到了定投日，是则发邮件
  python dca_monthly_reminder.py --followup      # 检查是否需要发 RSI 跟进
  python dca_monthly_reminder.py --force         # 强制发送（忽略日期检查，测试用）
  python dca_monthly_reminder.py --dry-run       # 预览邮件内容，不发
"""
import sys, io, os, json, smtplib, argparse
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd, numpy as np

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DATA_DIR = r'C:\AI\cc\stock\data'
CODE_DIR = r'C:\AI\cc\stock\code'
ENV_PATH = r'C:\AI\cc\stock\.env'
STATE_PATH = os.path.join(DATA_DIR, 'dca_reminder_state.json')

# ═══════════════════════════════════════════════════════
# 定投组合配置
# ═══════════════════════════════════════════════════════
PORTFOLIO = {
    'name': 'SPY + NVDA + AVGO 定投组合',
    'monthly': 2000,
    'allocation': {
        'SPY':  {'pct': 0.10, 'amount': 200,  'label': '压舱石'},
        'NVDA': {'pct': 0.60, 'amount': 1200, 'label': '主力增长'},
        'AVGO': {'pct': 0.30, 'amount': 600,  'label': '稳健芯片'},
    },
    'ratio_note': 'NVDA = 2× AVGO',
}

# 鼓励语库（每次随机选一条）
CHEER_MSGS = [
    '💪 坚持定投的人，时间终会给他答案。',
    '🚀 今天投的每一分钱，都是未来的自由。',
    '🌱 定投就像种树，最好的时间是十年前，其次是今天。',
    '⚡ 不预测市场，只持续积累。——这是普通人战胜华尔街的唯一方法。',
    '🏔️ 短期波动是噪音，长期趋势是财富。继续前进！',
    '🎯 每月一次的仪式感：把钱交给未来的自己。',
    '💎 在别人恐惧时贪婪很难，但每月闭眼定投很简单。你能做到。',
    '🌟 十年后回看今天，你会感谢这个坚持下去的自己。',
    '🔥 NVDA + AVGO + SPY —— 半导体是AI时代的石油，你在买油田。',
    '📈 复利是世界第八大奇迹。你今天又在创造奇迹。',
]


# ═══════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════

def load_data(ticker):
    """加载日线数据。"""
    for fmt in [f'{ticker}_2016_daily.csv', f'{ticker}_daily.csv']:
        p = os.path.join(DATA_DIR, fmt)
        if os.path.exists(p):
            df = pd.read_csv(p, header=[0,1], index_col=0, parse_dates=True)
            try:
                return df[('Close', ticker)].dropna()
            except:
                df = pd.read_csv(p, index_col=0, parse_dates=True)
                return df['Close'].dropna() if 'Close' in df.columns else df.iloc[:,0].dropna()
    return None


def get_trading_days(close):
    """返回排序后的交易日列表。"""
    return sorted(close.index.tolist())


def compute_rsi(close, period=14):
    """计算 RSI 序列，返回 Series。"""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def rsi_verdict(rsi_val):
    """根据 RSI 值给出评价。"""
    if rsi_val is None or np.isnan(rsi_val):
        return '数据不足', '🤷'
    if rsi_val < 30:
        return '超卖区 — 绝佳买点！别人恐惧时你贪婪了 💎', '🥇'
    elif rsi_val < 40:
        return '偏低 — 不错的入场时机 👍', '🥈'
    elif rsi_val < 60:
        return '中性区间 — 正常定投节奏 ✅', '✅'
    elif rsi_val < 70:
        return '偏高 — 但定投不在乎短期价位 🤞', '⚠️'
    elif rsi_val < 80:
        return '超买区 — 短期偏贵，长期无碍 📈', '🔶'
    else:
        return '严重超买 — 没关系，定投平滑成本 📊', '🔴'


# ═══════════════════════════════════════════════════════
# 邮件配置（复用 rotation_signal.py 的 .env）
# ═══════════════════════════════════════════════════════

def load_env(path):
    env = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

_env = load_env(ENV_PATH)
EMAIL_CFG = {
    'smtp_host': _env.get('SIGNAL_SMTP_HOST', 'smtp.gmail.com'),
    'smtp_port': int(_env.get('SIGNAL_SMTP_PORT', '587')),
    'username': _env.get('SIGNAL_EMAIL_USER', '') or os.environ.get('SIGNAL_EMAIL_USER', ''),
    'password': _env.get('SIGNAL_EMAIL_PASS', '') or os.environ.get('SIGNAL_EMAIL_PASS', ''),
    'to': _env.get('SIGNAL_EMAIL_TO', '') or os.environ.get('SIGNAL_EMAIL_TO', ''),
}


def send_email(subject, body_plain, body_html):
    """发送邮件。成功返回 True。"""
    if not EMAIL_CFG['username']:
        print("  ✗ 邮件未配置（.env 中缺少 SIGNAL_EMAIL_USER）")
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_CFG['username']
        msg['To'] = EMAIL_CFG['to']
        msg['Subject'] = subject
        msg.attach(MIMEText(body_plain, 'plain', 'utf-8'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))
        with smtplib.SMTP(EMAIL_CFG['smtp_host'], EMAIL_CFG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CFG['username'], EMAIL_CFG['password'])
            server.send_message(msg)
        print(f"  📧 邮件已发送 → {EMAIL_CFG['to']}")
        return True
    except Exception as e:
        print(f"  ✗ 邮件发送失败: {e}")
        return False


# ═══════════════════════════════════════════════════════
# 状态管理
# ═══════════════════════════════════════════════════════

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_buy_date': None, 'last_buy_prices': {},
            'rsi_at_buy': {}, 'rsi_followup_sent': False,
            'history': []}


def save_state(state):
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"  💾 状态已保存 → {STATE_PATH}")


# ═══════════════════════════════════════════════════════
# 买入日计算：1号+7天后的第一个交易日
# ═══════════════════════════════════════════════════════

def find_buy_day(year, month, all_trading_days):
    """找到指定月份的定投日。

    规则：当月 1 号 + 7 天后的第一个交易日。
    例如 6月1日 + 7 = 6月8日 → 找 ≥ 6月8日的第一个交易日。

    如果数据不足：返回 None 表示尚未出现。
    """
    first_cal = datetime(year, month, 1)
    wait_until = first_cal + timedelta(days=7)  # 1号+7天

    for dt in sorted(all_trading_days):
        dt_py = dt.to_pydatetime() if hasattr(dt, 'to_pydatetime') else datetime(
            dt.year, dt.month, dt.day)
        if dt_py >= wait_until and dt_py.year == year and dt_py.month == month:
            return dt

    # 未找到：检查是本月的交易数据还没到 wait_until，还是已经过了
    month_days = [d for d in sorted(all_trading_days)
                  if hasattr(d, 'year') and d.year == year and d.month == month]
    if month_days:
        last_day = month_days[-1]
        last_py = last_day.to_pydatetime() if hasattr(last_day, 'to_pydatetime') else datetime(
            last_day.year, last_day.month, last_day.day)
        if last_py < wait_until:
            # 数据还没覆盖到 wait_until（本月尚未到达定投日）
            return None
        # 数据已覆盖但没找到 → 本月已过定投日，返回最后交易日
        return last_day
    return None


def is_buy_day_today(all_trading_days):
    """判断今天是否为定投日。返回 (True, buy_date, None) 或 (False, found_buy_date, next_buy_date)。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    buy_dt = find_buy_day(today.year, today.month, all_trading_days)

    if buy_dt is not None:
        buy_py = buy_dt.to_pydatetime() if hasattr(buy_dt, 'to_pydatetime') else datetime(
            buy_dt.year, buy_dt.month, buy_dt.day)
        if today.date() == buy_py.date():
            return True, buy_dt, None
        if today.date() > buy_py.date():
            # 本月定投日已过，计算下个月的
            pass  # fall through to next_month logic below

    # 计算下个月的定投日
    next_month = today.month + 1
    next_year = today.year
    if next_month > 12:
        next_month = 1
        next_year += 1
    next_buy = find_buy_day(next_year, next_month, all_trading_days)
    return False, buy_dt, next_buy


# ═══════════════════════════════════════════════════════
# 邮件构建
# ═══════════════════════════════════════════════════════

def build_buy_email(prices, buy_date, fx_rate=None):
    """构建定投提醒邮件（HTML + Plain）。"""
    today_str = datetime.now().strftime('%Y年%m月%d日')
    buy_str = buy_date.strftime('%Y年%m月%d日') if hasattr(buy_date, 'strftime') else str(buy_date)[:10]
    import random
    cheer = random.choice(CHEER_MSGS)

    # ── 计算 RSI（在加载时算好了）──
    # 我们稍后在主流程中传入

    # ── 纯文本 ──
    lines = []
    lines.append(f"╔══════════════════════════════════════════╗")
    lines.append(f"║   📬 DCA 每月定投提醒 — {today_str}    ║")
    lines.append(f"╚══════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"📅 定投日：{buy_str}（1号+7天规则）")
    lines.append("")
    lines.append(f"💰 本月投入：${PORTFOLIO['monthly']:,}")
    lines.append(f"📐 持仓比例：NVDA = 2× AVGO")
    lines.append("")
    lines.append(f"  {'标的':<6} {'比例':<8} {'金额':<10} {'定位'}")
    lines.append(f"  {'─'*6} {'─'*8} {'─'*10} {'─'*12}")
    for ticker, cfg in PORTFOLIO['allocation'].items():
        px = prices.get(ticker, 'N/A')
        px_str = f'${px:,.2f}' if isinstance(px, (int, float)) else str(px)
        lines.append(f"  {ticker:<6} {cfg['pct']*100:>5.0f}%   ${cfg['amount']:<9,}  {cfg['label']}  (≈{px_str})")
    lines.append("")
    total_buys = sum(cfg['amount'] / prices[t] for t, cfg in PORTFOLIO['allocation'].items()
                     if t in prices)
    lines.append(f"  🧾 按当前价约买入：")
    for ticker, cfg in PORTFOLIO['allocation'].items():
        if ticker in prices:
            shares = cfg['amount'] / prices[ticker]
            lines.append(f"     {ticker}: {shares:.4f} 股")
    lines.append("")
    lines.append(cheer)
    lines.append("")
    lines.append("📌 下期预告：一周后自动发 RSI 跟进邮件，评价本次买入质量。")
    lines.append("📌 脚本: code/dca_monthly_reminder.py")

    body_plain = '\n'.join(lines)

    # ── HTML ──
    rows_html = ''
    for ticker, cfg in PORTFOLIO['allocation'].items():
        px = prices.get(ticker, 'N/A')
        px_str = f'${px:,.2f}' if isinstance(px, (int, float)) else str(px)
        rows_html += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #e0e0e0"><strong>{ticker}</strong></td>
            <td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;text-align:center">{cfg['pct']*100:.0f}%</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;text-align:right">${cfg['amount']:,}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;text-align:right">{px_str}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e0e0e0;color:#666">{cfg['label']}</td>
        </tr>"""

    body_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f5f5f5">

<div style="background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);color:white;padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="margin:0;font-size:22px">📬 DCA 每月定投提醒</h1>
    <p style="margin:8px 0 0;opacity:0.8">{today_str}</p>
</div>

<div style="background:white;padding:24px;border-radius:0 0 12px 12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

    <div style="background:#e8f5e9;padding:16px;border-radius:8px;margin-bottom:20px;text-align:center">
        <p style="margin:0;font-size:16px">📅 定投日：<strong>{buy_str}</strong></p>
        <p style="margin:4px 0 0;font-size:13px;color:#666">（1号+7天规则 → 避开月初资金流入效应）</p>
    </div>

    <h2 style="border-bottom:2px solid #0f3460;padding-bottom:8px;margin-top:0">
        💰 本月定投计划 <span style="font-size:14px;color:#666;font-weight:normal">总额 ${PORTFOLIO['monthly']:,}</span>
    </h2>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <thead>
            <tr style="background:#f0f4ff">
                <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #0f3460">标的</th>
                <th style="padding:10px 12px;text-align:center;border-bottom:2px solid #0f3460">比例</th>
                <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #0f3460">金额</th>
                <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #0f3460">当前价</th>
                <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #0f3460">定位</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div style="background:#fff3e0;padding:12px;border-radius:8px;margin:16px 0">
        <p style="margin:0;font-size:13px">📐 <strong>配置理念</strong>：NVDA:AVGO = 2:1 | SPY 10% 压舱石 | 均衡型·Sharpe 1.80 | 回撤 -32.4%</p>
    </div>

    <div style="background:linear-gradient(135deg,#e8eaf6,#c5cae9);padding:20px;border-radius:8px;margin:20px 0;text-align:center">
        <p style="margin:0;font-size:17px;font-weight:bold;color:#1a237e">{cheer}</p>
    </div>

    <div style="background:#fafafa;padding:12px;border-radius:8px;margin:16px 0;text-align:center">
        <p style="margin:0;font-size:12px;color:#999">
            📌 预计 7 天后自动发送 RSI 跟进邮件 | 脚本: dca_monthly_reminder.py<br>
            ⚠️ 本邮件仅供信息参考，不构成投资建议。投资有风险，入市需谨慎。
        </p>
    </div>

</div>
</body></html>"""

    return body_plain, body_html


def build_rsi_email(buy_date_str, prices_at_buy, rsi_at_buy, current_prices, current_rsi):
    """构建 RSI 跟进邮件。"""
    today_str = datetime.now().strftime('%Y年%m月%d日')
    import random
    cheer = random.choice(CHEER_MSGS)

    # ── Plain ──
    lines = []
    lines.append(f"╔══════════════════════════════════════════╗")
    lines.append(f"║   🔍 DCA 定投 RSI 跟进 — {today_str}     ║")
    lines.append(f"╚══════════════════════════════════════════╝")
    lines.append("")
    lines.append(f"📅 回顾定投日：{buy_date_str}")
    lines.append(f"⏰ 已过约一周，来看看当时买得怎么样 ——")
    lines.append("")
    lines.append(f"  {'标的':<6} {'买入价':>10} {'买入RSI':>9} {'评价':<30} {'现在价':>10} {'现在RSI':>9} {'涨跌':>8}")
    lines.append(f"  {'─'*6} {'─'*10} {'─'*9} {'─'*30} {'─'*10} {'─'*9} {'─'*8}")
    overall_verdicts = []
    for ticker in ['SPY', 'NVDA', 'AVGO']:
        px_b = prices_at_buy.get(ticker)
        rsi_b = rsi_at_buy.get(ticker)
        px_n = current_prices.get(ticker)
        rsi_n = current_rsi.get(ticker)
        chg = ''
        if px_b and px_n and px_b > 0:
            chg_pct = (px_n / px_b - 1) * 100
            chg = f'{chg_pct:+.1f}%'
        verdict, emoji = rsi_verdict(rsi_b)
        overall_verdicts.append((emoji, verdict))
        px_b_str = f'${px_b:,.2f}' if isinstance(px_b, (int, float)) else 'N/A'
        px_n_str = f'${px_n:,.2f}' if isinstance(px_n, (int, float)) else 'N/A'
        rsi_b_str = f'{rsi_b:.0f}' if isinstance(rsi_b, (int, float)) and not np.isnan(rsi_b) else 'N/A'
        rsi_n_str = f'{rsi_n:.0f}' if isinstance(rsi_n, (int, float)) and not np.isnan(rsi_n) else 'N/A'
        lines.append(f"  {ticker:<6} {px_b_str:>10} {rsi_b_str:>8}  {emoji} {verdict:<28} {px_n_str:>10} {rsi_n_str:>8} {chg:>8}")
    lines.append("")
    lines.append("💡 RSI 解读：")
    lines.append("   < 30 = 极度超卖(绝佳买点) | 30-50 = 偏低至中性")
    lines.append("   50-70 = 中性至偏高 | > 70 = 超买区")
    lines.append("   定投不择时，但知道买入时的估值水平有助于理解长期收益。")
    lines.append("")
    lines.append(cheer)
    lines.append("")
    lines.append("📌 下次定投提醒：下个月 1号+7天 见！")

    body_plain = '\n'.join(lines)

    # ── HTML ──
    rows_html = ''
    for ticker in ['SPY', 'NVDA', 'AVGO']:
        px_b = prices_at_buy.get(ticker)
        rsi_b = rsi_at_buy.get(ticker)
        px_n = current_prices.get(ticker)
        rsi_n = current_rsi.get(ticker)
        chg = ''
        chg_color = '#999'
        if px_b and px_n and px_b > 0:
            chg_pct = (px_n / px_b - 1) * 100
            chg = f'{chg_pct:+.1f}%'
            chg_color = '#2e7d32' if chg_pct >= 0 else '#c62828'
        verdict, emoji = rsi_verdict(rsi_b)
        px_b_str = f'${px_b:,.2f}' if isinstance(px_b, (int, float)) else 'N/A'
        px_n_str = f'${px_n:,.2f}' if isinstance(px_n, (int, float)) else 'N/A'
        rsi_b_str = f'{rsi_b:.0f}' if isinstance(rsi_b, (int, float)) and not np.isnan(rsi_b) else 'N/A'
        rsi_n_str = f'{rsi_n:.0f}' if isinstance(rsi_n, (int, float)) and not np.isnan(rsi_n) else 'N/A'

        # RSI color
        rsi_v = rsi_b if isinstance(rsi_b, (int, float)) and not np.isnan(rsi_b) else 50
        if rsi_v < 30: rsi_color = '#2e7d32'
        elif rsi_v < 50: rsi_color = '#558b2f'
        elif rsi_v < 70: rsi_color = '#f57f17'
        else: rsi_color = '#c62828'

        rows_html += f"""<tr>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0"><strong>{ticker}</strong></td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:right">{px_b_str}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:center;color:{rsi_color};font-weight:bold">{rsi_b_str}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0">{emoji} {verdict}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:right">{px_n_str}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:center">{rsi_n_str}</td>
            <td style="padding:10px 12px;border-bottom:1px solid #e0e0e0;text-align:center;color:{chg_color};font-weight:bold">{chg}</td>
        </tr>"""

    body_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:650px;margin:0 auto;padding:20px;background:#f5f5f5">

<div style="background:linear-gradient(135deg,#263238,#37474f,#455a64);color:white;padding:24px;border-radius:12px 12px 0 0;text-align:center">
    <h1 style="margin:0;font-size:22px">🔍 DCA 定投 RSI 跟进</h1>
    <p style="margin:8px 0 0;opacity:0.8">{today_str}</p>
</div>

<div style="background:white;padding:24px;border-radius:0 0 12px 12px;box-shadow:0 2px 8px rgba(0,0,0,0.1)">

    <div style="background:#e3f2fd;padding:16px;border-radius:8px;margin-bottom:20px;text-align:center">
        <p style="margin:0;font-size:16px">📅 回顾定投日：<strong>{buy_date_str}</strong></p>
        <p style="margin:4px 0 0;font-size:13px;color:#666">已过约一周 | 复盘买入时的 RSI 水平</p>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:16px 0">
        <thead>
            <tr style="background:#f0f4ff">
                <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #37474f">标的</th>
                <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #37474f">买入价</th>
                <th style="padding:10px 12px;text-align:center;border-bottom:2px solid #37474f">买入 RSI</th>
                <th style="padding:10px 12px;text-align:left;border-bottom:2px solid #37474f">评价</th>
                <th style="padding:10px 12px;text-align:right;border-bottom:2px solid #37474f">现在价</th>
                <th style="padding:10px 12px;text-align:center;border-bottom:2px solid #37474f">现在 RSI</th>
                <th style="padding:10px 12px;text-align:center;border-bottom:2px solid #37474f">涨跌</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div style="background:#f3e5f5;padding:16px;border-radius:8px;margin:16px 0">
        <p style="margin:0 0 8px;font-size:14px;font-weight:bold">💡 RSI 速查表</p>
        <table style="width:100%;font-size:12px">
            <tr style="color:#2e7d32"><td>RSI < 30</td><td>🟢 极度超卖</td><td>绝佳买入时机</td></tr>
            <tr style="color:#558b2f"><td>RSI 30-50</td><td>🔵 偏低至中性</td><td>不错的入场区间</td></tr>
            <tr style="color:#f57f17"><td>RSI 50-70</td><td>🟡 中性至偏高</td><td>正常定投节奏</td></tr>
            <tr style="color:#c62828"><td>RSI > 70</td><td>🔴 超买区</td><td>短期偏贵，定投无视</td></tr>
        </table>
        <p style="margin:8px 0 0;font-size:12px;color:#999">定投不择时，RSI 只是帮你了解买入时的市场温度。长期看，择时不如坚持。</p>
    </div>

    <div style="background:linear-gradient(135deg,#e8eaf6,#c5cae9);padding:20px;border-radius:8px;margin:20px 0;text-align:center">
        <p style="margin:0;font-size:17px;font-weight:bold;color:#1a237e">{cheer}</p>
    </div>

    <div style="background:#fafafa;padding:12px;border-radius:8px;margin:16px 0;text-align:center">
        <p style="margin:0;font-size:12px;color:#999">
            📌 下次定投提醒：下个月 1号+7天 见！| 脚本: dca_monthly_reminder.py --followup<br>
            ⚠️ 本邮件仅供信息参考，不构成投资建议。
        </p>
    </div>

</div>
</body></html>"""

    return body_plain, body_html


# ═══════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════

def do_check(prices, all_days, state, dry_run=False):
    """检查是否为定投日，是则发送提醒邮件。"""
    is_buy, buy_dt, next_buy = is_buy_day_today(all_days)

    if not is_buy:
        if buy_dt is not None:
            buy_str = buy_dt.strftime('%Y-%m-%d') if hasattr(buy_dt, 'strftime') else str(buy_dt)[:10]
        else:
            # 数据尚未覆盖到定投日，用日历估算
            est = datetime(datetime.now().year, datetime.now().month, 1) + timedelta(days=7)
            buy_str = est.strftime('%Y-%m-%d') + ' (日历估算，数据未覆盖)'
        if next_buy is not None and hasattr(next_buy, 'strftime'):
            next_str = next_buy.strftime('%Y-%m-%d')
        elif next_buy is not None:
            next_str = str(next_buy)[:10]
        else:
            next_month = datetime.now().month + 1
            next_year = datetime.now().year
            if next_month > 12:
                next_month = 1
                next_year += 1
            est = datetime(next_year, next_month, 1) + timedelta(days=7)
            next_str = est.strftime('%Y-%m-%d') + ' (日历估算)'
        print(f"  📅 今天不是定投日。本月定投日: {buy_str}  |  下月预计: {next_str}")
        return

    # 检查是否今天已经发过
    buy_str = buy_dt.strftime('%Y-%m-%d') if hasattr(buy_dt, 'strftime') else str(buy_dt)[:10]
    if state.get('last_buy_date') == buy_str:
        print(f"  ⚠️ 今天 ({buy_str}) 的定投提醒已发送过，跳过。")
        return

    print(f"  🎯 今天是定投日！{buy_str}")
    print(f"  当前价格: SPY=${prices.get('SPY','?'):,.2f}  "
          f"NVDA=${prices.get('NVDA','?'):,.2f}  "
          f"AVGO=${prices.get('AVGO','?'):,.2f}")

    # 计算 RSI
    rsi = {}
    for t in ['SPY', 'NVDA', 'AVGO']:
        close = load_data(t)
        if close is not None:
            rsi_s = compute_rsi(close)
            if buy_dt in rsi_s.index:
                rsi[t] = float(rsi_s.loc[buy_dt])

    # 构建邮件
    plain, html = build_buy_email(prices, buy_dt)

    if dry_run:
        print("\n  ─── 邮件预览 (纯文本) ───\n")
        print(plain)
        print("\n  ─── 预览结束 ───")
        return

    subject = f"📬 DCA定投提醒 — {buy_str} | SPY 10%+NVDA 60%+AVGO 30%"
    ok = send_email(subject, plain, html)

    if ok:
        # 保存状态
        buy_date_str = buy_dt.strftime('%Y-%m-%d') if hasattr(buy_dt, 'strftime') else str(buy_dt)[:10]
        state['last_buy_date'] = buy_date_str
        state['last_buy_prices'] = {t: round(prices[t], 2) for t in prices}
        state['rsi_at_buy'] = {t: round(rsi[t], 1) if not (np.isnan(rsi[t]) if isinstance(rsi[t], float) else False) else None for t in rsi}
        state['rsi_followup_sent'] = False
        state['history'].append({
            'date': buy_date_str,
            'prices': state['last_buy_prices'],
            'rsi': state['rsi_at_buy'],
            'allocation': {t: c['amount'] for t, c in PORTFOLIO['allocation'].items()},
        })
        save_state(state)
        print(f"  📊 RSI at buy: {state['rsi_at_buy']}")


def do_followup(prices, all_days, state, dry_run=False):
    """检查是否需要发送 RSI 跟进邮件（定投日后约 7 天）。"""
    if not state.get('last_buy_date'):
        print("  ℹ️ 还没有定投记录，无法发送 RSI 跟进。")
        return

    if state.get('rsi_followup_sent'):
        print(f"  ✅ RSI 跟进邮件已发送过（定投日: {state['last_buy_date']}）。")
        return

    # 检查是否已过 7 个自然日
    buy_date = datetime.strptime(state['last_buy_date'], '%Y-%m-%d')
    days_since = (datetime.now() - buy_date).days
    if days_since < 7:
        print(f"  ⏳ 定投日 {state['last_buy_date']} 距今仅 {days_since} 天，再等 {7-days_since} 天后发 RSI 跟进。")
        return

    print(f"  🔍 定投日 {state['last_buy_date']} 已过 {days_since} 天，发送 RSI 跟进...")

    # 计算当前 RSI
    current_rsi = {}
    for t in ['SPY', 'NVDA', 'AVGO']:
        close = load_data(t)
        if close is not None:
            rsi_s = compute_rsi(close)
            if len(rsi_s) > 0:
                current_rsi[t] = float(rsi_s.iloc[-1])

    plain, html = build_rsi_email(
        state['last_buy_date'],
        state.get('last_buy_prices', {}),
        state.get('rsi_at_buy', {}),
        prices,
        current_rsi,
    )

    if dry_run:
        print("\n  ─── RSI 邮件预览 (纯文本) ───\n")
        print(plain)
        print("\n  ─── 预览结束 ───")
        return

    subject = f"🔍 DCA定投RSI跟进 — {state['last_buy_date']}买入复盘"
    ok = send_email(subject, plain, html)

    if ok:
        state['rsi_followup_sent'] = True
        save_state(state)


def main():
    parser = argparse.ArgumentParser(description='DCA 每月定投提醒 + RSI 跟进')
    parser.add_argument('--followup', action='store_true', help='仅发送 RSI 跟进邮件（定投后~7天）')
    parser.add_argument('--check', action='store_true', help='仅检查定投日（默认行为）')
    parser.add_argument('--force', action='store_true', help='强制发送定投提醒，忽略日期检查')
    parser.add_argument('--dry-run', action='store_true', help='预览邮件内容，不实际发送')
    args = parser.parse_args()

    print("=" * 70)
    print("  DCA 每月定投提醒 + RSI 跟进")
    print("=" * 70)

    # 加载共用交易日期
    print("加载数据...")
    sp = {}
    for t in ['SPY', 'NVDA', 'AVGO']:
        sp[t] = load_data(t)
        if sp[t] is None:
            print(f"  ✗ {t}: 数据加载失败")
            return
        print(f"  {t}: {sp[t].index[0].date()} ~ {sp[t].index[-1].date()} ({len(sp[t])}d)")

    # 对齐交易日
    common_idx = sp['NVDA'].index.intersection(sp['SPY'].index).intersection(sp['AVGO'].index)
    all_days = sorted(common_idx.tolist())
    print(f"  共同交易日: {len(all_days)} 天")

    # 当前价格
    prices = {}
    for t in ['SPY', 'NVDA', 'AVGO']:
        prices[t] = float(sp[t].iloc[-1])

    # 加载状态
    state = load_state()

    if args.force:
        # 强制发送：把今天当作定投日
        print("\n  ⚡ 强制模式：发送定投提醒...")
        today = datetime.now()
        today_ts = pd.Timestamp(today.replace(hour=0, minute=0, second=0, microsecond=0))
        buy_dt = today_ts
        if buy_dt not in common_idx:
            for d in all_days:
                if d >= today_ts:
                    buy_dt = d
                    break
        plain, html = build_buy_email(prices, buy_dt)
        if args.dry_run:
            print("\n  ─── 邮件预览 ───\n")
            print(plain)
        else:
            send_email("📬 [测试] DCA定投提醒 — " + buy_dt.strftime('%Y-%m-%d'), plain, html)
        state['last_buy_date'] = buy_dt.strftime('%Y-%m-%d')
        state['last_buy_prices'] = {t: round(prices[t], 2) for t in prices}
        state['rsi_followup_sent'] = False
        save_state(state)
    elif args.followup:
        # 仅 RSI 跟进
        do_followup(prices, all_days, state, dry_run=args.dry_run)
    else:
        # 默认：先检查定投日，再检查是否需要 RSI 跟进
        do_check(prices, all_days, state, dry_run=args.dry_run)
        # 无论是否定投日，都检查 RSI 跟进
        if not args.dry_run:
            print()
            do_followup(prices, all_days, state, dry_run=args.dry_run)

    print("\n" + "=" * 70)
    print("  完成。")
    print("=" * 70)


if __name__ == '__main__':
    main()
