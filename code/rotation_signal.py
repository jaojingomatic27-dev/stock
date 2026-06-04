# -*- coding: utf-8 -*-
"""持仓监控 + 三股轮动信号脚本

每天美股收盘后运行，根据 LEVERAGED_ROTATION_STRATEGY 发出买卖信号。

用法：
  python rotation_signal.py            # 默认 --check
  python rotation_signal.py --init     # 首次创建 portfolio.json
  python rotation_signal.py --check    # 检查价格 + 输出信号
  python rotation_signal.py --confirm  # 确认执行本次信号
  python rotation_signal.py --email    # 检查 + 发送邮件通知
  python rotation_signal.py --manual NVDA:5.71,MSFT:8.30,ORCL:4.20  # 手动输入价格

原理：
  Turbo 权证价格 = max(0, stock_USD - strike_USD) × ratio × FX_EURUSD
  effective_leverage = stock_USD / (stock_USD - strike_USD)

  每日追踪每个仓位的最高点 (peak)，当任一仓位从 peak 回撤 ≥ threshold 时：
  → 卖出该仓位 → 现金平分给幸存仓位 → 重置幸存者 peak

状态文件：data/portfolio.json
"""
import sys, io, os, json, smtplib, argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import yfinance as yf

# ═══════════════════════════════════════════════════════════════
# 配置常量
# ═══════════════════════════════════════════════════════════════

PORTFOLIO_PATH = r'C:\AI\cc\stock\data\portfolio.json'
ENV_PATH = r'C:\AI\cc\stock\.env'
DEFAULT_THRESHOLD = 0.40  # 40% 回撤触发轮动

# 颜色（Windows 终端 ANSI）
C = {
    'reset': '\033[0m', 'bold': '\033[1m',
    'red': '\033[91m', 'green': '\033[92m', 'yellow': '\033[93m',
    'blue': '\033[94m', 'cyan': '\033[96m', 'magenta': '\033[95m',
    'grey': '\033[90m',
}

# 邮件配置（从环境变量或 .env 文件读取）
def _load_env(path: str) -> dict:
    """加载 .env 文件中的键值对。"""
    env = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    env[key.strip()] = val.strip().strip('"').strip("'")
    return env

_env = _load_env(ENV_PATH)
EMAIL_CONFIG = {
    'enabled': bool(_env.get('SIGNAL_EMAIL_USER') or os.environ.get('SIGNAL_EMAIL_USER')),
    'smtp_host': _env.get('SIGNAL_SMTP_HOST', 'smtp.gmail.com'),
    'smtp_port': int(_env.get('SIGNAL_SMTP_PORT', '587')),
    'username': _env.get('SIGNAL_EMAIL_USER', '') or os.environ.get('SIGNAL_EMAIL_USER', ''),
    'password': _env.get('SIGNAL_EMAIL_PASS', '') or os.environ.get('SIGNAL_EMAIL_PASS', ''),
    'to': _env.get('SIGNAL_EMAIL_TO', '') or os.environ.get('SIGNAL_EMAIL_TO', ''),
}

# ═══════════════════════════════════════════════════════════════
# Turbo 权证定价
# ═══════════════════════════════════════════════════════════════

def fetch_market_data(underlyings: List[str]) -> Tuple[Dict[str, float], float]:
    """下载正股收盘价 + EUR/USD 汇率。

    Returns:
        (stock_prices: {ticker: close_price}, fx_eurusd: float)
    """
    prices = {}
    for ticker in underlyings:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period='5d')
            if len(hist) > 0:
                prices[ticker] = float(hist['Close'].iloc[-1])
            else:
                print(f"  {C['yellow']}⚠ {ticker}: 无数据{C['reset']}")
                prices[ticker] = None
        except Exception as e:
            print(f"  {C['red']}✗ {ticker}: {e}{C['reset']}")
            prices[ticker] = None

    # EUR/USD
    try:
        fx = yf.Ticker('EURUSD=X')
        fx_hist = fx.history(period='5d')
        fx_rate = float(fx_hist['Close'].iloc[-1]) if len(fx_hist) > 0 else 0.92
    except:
        fx_rate = 0.92  # fallback

    return prices, fx_rate


def calc_warrant_price(stock_usd: float, strike_usd: float, ratio: float, fx_eurusd: float) -> float:
    """计算 Turbo Call 权证价格 (EUR)。

    warrant_price_eur = max(0, stock_usd - strike_usd) × ratio / fx_eurusd

    fx_eurusd 是 EUR/USD 汇率 (yfinance EURUSD=X)，即 1 EUR = fx_eurusd USD。
    除以 fx_eurusd 将 USD 内价值转换为 EUR。
    """
    intrinsic = max(0.0, stock_usd - strike_usd)
    return intrinsic * ratio / fx_eurusd if fx_eurusd > 0 else 0.0


def calc_effective_leverage(stock_usd: float, strike_usd: float) -> float:
    """计算 Turbo 权证的即时有效杠杆倍数。"""
    if stock_usd <= strike_usd:
        return float('inf')  # 已穿 KO
    return stock_usd / (stock_usd - strike_usd)


# ═══════════════════════════════════════════════════════════════
# Portfolio 管理
# ═══════════════════════════════════════════════════════════════

class Portfolio:
    """持仓状态管理器。"""

    def __init__(self, path: str = PORTFOLIO_PATH):
        self.path = path
        self.data = None

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def load(self) -> dict:
        with open(self.path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        return self.data

    def save(self):
        self.data['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def create(self, positions: List[dict], threshold: float = DEFAULT_THRESHOLD):
        """首次创建 portfolio.json。"""
        total = sum(p['shares'] * p['entry_price'] for p in positions)
        self.data = {
            'version': 1,
            'created': date.today().isoformat(),
            'updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'threshold': threshold,
            'total_invested': round(total, 2),
            'currency': 'EUR',
            'positions': [],
            'pending_signal': None,    # 待确认的信号
            'rotation_history': [],
            'check_history': [],
        }
        for i, p in enumerate(positions):
            self.data['positions'].append({
                'id': i,
                'label': p['label'],
                'underlying': p['underlying'],
                'product_name': p.get('product_name', ''),
                'isin': p.get('isin', ''),
                'strike_usd': p['strike_usd'],
                'ratio': p['ratio'],
                'shares': p['shares'],
                'entry_price': p['entry_price'],
                'entry_date': p.get('entry_date', date.today().isoformat()),
                'peak_price': p['entry_price'],  # 第一天，peak = 买入价
                'current_price': p['entry_price'],
                'current_value': round(p['shares'] * p['entry_price'], 2),
                'peak_value': round(p['shares'] * p['entry_price'], 2),
                'active': True,
                'transaction_history': [{
                    'date': date.today().isoformat(),
                    'action': 'BUY',
                    'price': p['entry_price'],
                    'shares': p['shares'],
                    'value': round(p['shares'] * p['entry_price'], 2),
                }],
            })
        self.save()

    def get_active_positions(self) -> List[dict]:
        return [p for p in self.data['positions'] if p['active']]

    def get_position_value(self, pos: dict) -> float:
        return pos['shares'] * pos['current_price']

    def update_prices(self, stock_prices: Dict[str, float], fx_rate: float,
                      manual_prices: Optional[Dict[str, float]] = None):
        """用正股收盘价更新所有仓位的权证价格。"""
        for pos in self.data['positions']:
            if not pos['active']:
                continue

            ticker = pos['underlying']

            if manual_prices and pos['label'] in manual_prices:
                # 手动输入价格
                pos['current_price'] = manual_prices[pos['label']]
            elif ticker in stock_prices and stock_prices[ticker] is not None:
                # 公式计算
                pos['current_price'] = round(
                    calc_warrant_price(
                        stock_prices[ticker],
                        pos['strike_usd'],
                        pos['ratio'],
                        fx_rate
                    ), 4
                )
            else:
                continue  # 无数据，保持不变

            pos['current_value'] = round(pos['shares'] * pos['current_price'], 2)

    def check_signals(self, threshold: float) -> dict:
        """检查是否触发轮动信号。

        Returns:
            {
                'has_signal': bool,
                'breached': [position_ids],  # 触发卖出的仓位
                'survivors': [position_ids],  # 幸存的仓位
                'total_value': float,
                'details': str,
            }
        """
        active = self.get_active_positions()
        if len(active) < 2:
            return {'has_signal': False, 'breached': [], 'survivors': active,
                    'total_value': sum(p['current_value'] for p in active), 'details': '不足2个活跃仓位，无法轮动'}

        # 更新 peak
        for p in active:
            if p['current_value'] > p['peak_value']:
                p['peak_value'] = round(p['current_value'], 2)
                p['peak_price'] = round(p['current_price'], 4)

        # 检查回撤
        breached = []
        for p in active:
            if p['peak_value'] > 0:
                dd = (p['current_value'] - p['peak_value']) / p['peak_value']
                if dd <= -threshold:
                    breached.append(p)

        if not breached:
            return {'has_signal': False, 'breached': [], 'survivors': active,
                    'total_value': sum(p['current_value'] for p in active),
                    'details': ''}

        # 构建信号
        survivors = [p for p in active if p not in breached]
        if len(survivors) == 0:
            return {'has_signal': True, 'breached': [p['id'] for p in breached],
                    'survivors': [],
                    'total_value': sum(p['current_value'] for p in active),
                    'details': f"{C['red']}🚨 所有仓位同时触发！全部卖出，等待重新入场{C['reset']}"}

        cash = sum(p['current_value'] for p in breached)
        per_survivor = cash / len(survivors)

        lines = []
        lines.append(f"\n{C['red']}{'═'*60}{C['reset']}")
        lines.append(f"{C['red']}  ⚠️  轮动信号触发！{C['reset']}")
        lines.append(f"{C['red']}{'═'*60}{C['reset']}\n")

        for p in breached:
            dd = (p['current_value'] - p['peak_value']) / p['peak_value'] * 100
            lines.append(f"  {C['red']}🔴 卖出 {p['label']}: €{p['current_value']:,.2f} "
                        f"(回撤 {dd:.1f}%，阈值 {threshold*100:.0f}%){C['reset']}")

        lines.append(f"\n  {C['yellow']}💰 释放现金: €{cash:,.2f}{C['reset']}")
        lines.append(f"  {C['yellow']}📊 平分到 {len(survivors)} 只幸存仓位，每只 +€{per_survivor:,.2f}{C['reset']}\n")

        for p in survivors:
            new_value = p['current_value'] + per_survivor
            lines.append(f"  {C['green']}🟢 加仓 {p['label']}: €{p['current_value']:,.2f} → €{new_value:,.2f}{C['reset']}")

        lines.append(f"\n  {C['cyan']}确认执行? 运行: python rotation_signal.py --confirm{C['reset']}")

        return {
            'has_signal': True,
            'breached': [p['id'] for p in breached],
            'survivors': [p for p in survivors],
            'cash': cash,
            'per_survivor': per_survivor,
            'total_value': sum(p['current_value'] for p in active),
            'details': '\n'.join(lines),
        }

    def confirm_signal(self):
        """确认执行信号，更新持仓状态。"""
        if not self.data.get('pending_signal'):
            print(f"{C['yellow']}⚠ 无待确认的信号。先运行 --check。{C['reset']}")
            return

        sig = self.data['pending_signal']
        if not sig.get('has_signal'):
            print(f"{C['yellow']}⚠ 上一个信号无需操作。{C['reset']}")
            self.data['pending_signal'] = None
            return

        breached_ids = sig['breached']
        survivors = {p['id']: p for p in self.data['positions'] if p['active'] and p['id'] not in breached_ids}

        if not survivors:
            # 全部触发 → 全部卖出
            for p in self.data['positions']:
                if p['id'] in breached_ids:
                    p['active'] = False
                    p['transaction_history'].append({
                        'date': date.today().isoformat(),
                        'action': 'SELL (ALL KO)',
                        'price': p['current_price'],
                        'shares': p['shares'],
                        'value': p['current_value'],
                    })
            print(f"{C['red']}🚨 所有仓位已卖出。等待重新建仓。{C['reset']}")
        else:
            cash = sig['cash']
            per_sv = sig['per_survivor']

            # 卖出 breached 仓位
            for p in self.data['positions']:
                if p['id'] in breached_ids:
                    p['active'] = False
                    p['transaction_history'].append({
                        'date': date.today().isoformat(),
                        'action': 'SELL (ROTATION)',
                        'price': p['current_price'],
                        'shares': p['shares'],
                        'value': p['current_value'],
                    })

            # 给幸存者加仓
            for p in self.data['positions']:
                if p['id'] in survivors:
                    # 用加仓金额买新的"虚拟股数"
                    new_shares = per_sv / p['current_price'] if p['current_price'] > 0 else 0
                    p['shares'] = round(p['shares'] + new_shares, 4)
                    p['current_value'] = round(p['current_value'] + per_sv, 2)
                    p['peak_value'] = p['current_value']  # 重置 peak
                    p['peak_price'] = p['current_price']
                    p['transaction_history'].append({
                        'date': date.today().isoformat(),
                        'action': 'ROTATION ADD',
                        'price': p['current_price'],
                        'shares': round(new_shares, 4),
                        'value': round(per_sv, 2),
                    })

        # 记录轮动历史
        self.data['rotation_history'].append({
            'date': date.today().isoformat(),
            'breached': [self._pos_label(pid) for pid in breached_ids],
            'survivors': [p['label'] for p in survivors.values()] if survivors else [],
            'total_value': sig['total_value'],
        })
        self.data['pending_signal'] = None
        self.save()
        print(f"\n{C['green']}✅ 轮动已执行，portfolio.json 已更新。{C['reset']}")

    def _pos_label(self, pid: int) -> str:
        for p in self.data['positions']:
            if p['id'] == pid:
                return p['label']
        return str(pid)


# ═══════════════════════════════════════════════════════════════
# 终端输出
# ═══════════════════════════════════════════════════════════════

def print_header(pf: Portfolio, stock_prices: Dict[str, float], fx_rate: float):
    """打印信号报告头部。"""
    now = datetime.now()
    print(f"\n{C['bold']}{C['cyan']}╔{'═'*58}╗{C['reset']}")
    print(f"{C['bold']}{C['cyan']}║{C['reset']}  📊 美股收盘信号  {now.strftime('%Y-%m-%d %H:%M')} (EST)          {C['bold']}{C['cyan']}║{C['reset']}")
    print(f"{C['bold']}{C['cyan']}║{C['reset']}  策略: 三股轮动  |  阈值: {pf.data['threshold']*100:.0f}%  |  总投入: €{pf.data['total_invested']:,.0f}              {C['bold']}{C['cyan']}║{C['reset']}")
    print(f"{C['bold']}{C['cyan']}╠{'═'*58}╣{C['reset']}")

    # 市场数据
    fx_str = f"EUR/USD {fx_rate:.4f}"
    stocks_str = '  '.join([f"{t} ${p:.2f}" for t, p in stock_prices.items() if p is not None])
    print(f"{C['bold']}{C['cyan']}║{C['reset']}  {C['grey']}{fx_str}  |  {stocks_str}{C['reset']}")
    print(f"{C['bold']}{C['cyan']}╠{'═'*58}╣{C['reset']}")

    # 表头
    print(f"{C['bold']}{C['cyan']}║{C['reset']}  {'仓位':<16} {'权证价':>8} {'市值':>10} {'Peak':>10} {'回撤':>8}  {'状态':<6} {C['bold']}{C['cyan']}║{C['reset']}")
    print(f"{C['bold']}{C['cyan']}╠{'═'*58}╣{C['reset']}")


def print_position(pos: dict, threshold: float):
    """打印单仓位行。"""
    dd = (pos['current_value'] - pos['peak_value']) / pos['peak_value'] * 100 if pos['peak_value'] > 0 else 0

    # 回撤颜色
    if dd <= -threshold * 100:
        dd_color = C['red']
        status = f"{C['red']}🔴 卖出{C['reset']}"
    elif dd <= -20:
        dd_color = C['yellow']
        status = f"{C['yellow']}🟡 关注{C['reset']}"
    else:
        dd_color = C['green']
        status = f"{C['green']}🟢 持有{C['reset']}"

    lev = calc_effective_leverage(
        _get_stock_price(pos),
        pos['strike_usd']
    )

    print(f"{C['bold']}{C['cyan']}║{C['reset']}  {pos['label']:<16} "
          f"€{pos['current_price']:>7.4f} "
          f"€{pos['current_value']:>9,.2f} "
          f"€{pos['peak_value']:>9,.2f} "
          f"{dd_color}{dd:>+7.1f}%{C['reset']}  "
          f"{status} "
          f"{C['grey']}{lev:.1f}x{C['reset']} "
          f"{C['bold']}{C['cyan']}║{C['reset']}")


def _get_stock_price(pos: dict, fx_rate: float = 1.1643) -> float:
    """从权证价格反推正股价格。"""
    if pos['ratio'] > 0:
        return pos['strike_usd'] + pos['current_price'] * fx_rate / pos['ratio']
    return pos['strike_usd'] + 10


def print_footer(signal: dict, pf: Portfolio):
    """打印报告底部。"""
    print(f"{C['bold']}{C['cyan']}╠{'═'*58}╣{C['reset']}")

    total = signal['total_value']
    total_inv = pf.data['total_invested']
    pnl = (total - total_inv) / total_inv * 100
    pnl_color = C['green'] if pnl >= 0 else C['red']
    print(f"{C['bold']}{C['cyan']}║{C['reset']}  总市值: €{total:>,.2f}  |  总盈亏: {pnl_color}{pnl:+.1f}%{C['reset']}              {C['bold']}{C['cyan']}║{C['reset']}")

    print(f"{C['bold']}{C['cyan']}╠{'═'*58}╣{C['reset']}")

    if signal['has_signal']:
        print(f"{C['bold']}{C['cyan']}║{C['reset']}  {C['red']}⚠️  触发轮动信号 — 运行 --confirm 确认执行{C['reset']}        {C['bold']}{C['cyan']}║{C['reset']}")
    else:
        print(f"{C['bold']}{C['cyan']}║{C['reset']}  {C['green']}✅ 无轮动信号，继续持有{C['reset']}                              {C['bold']}{C['cyan']}║{C['reset']}")

    print(f"{C['bold']}{C['cyan']}╚{'═'*58}╝{C['reset']}")

    # 历史摘要
    checks = pf.data.get('check_history', [])
    if len(checks) >= 2:
        prev = checks[-2]
        print(f"\n  {C['grey']}📈 上次检查: {prev['date']} | 总市值: €{prev['total_value']:,.2f} | 信号: {'有' if prev.get('had_signal') else '无'}{C['reset']}")

    print(f"\n  {C['grey']}📌 下次检查: python rotation_signal.py --check{C['reset']}")


# ═══════════════════════════════════════════════════════════════
# 邮件通知
# ═══════════════════════════════════════════════════════════════

def send_email(subject: str, body_plain: str, body_html: str = None, always: bool = False):
    """发送邮件通知。

    Args:
        subject: 邮件主题
        body_plain: 纯文本正文
        body_html: HTML 正文（可选）
        always: True = 即使无信号也发每日摘要；False = 仅触发信号时发
    """
    if not EMAIL_CONFIG['enabled']:
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_CONFIG['username']
        msg['To'] = EMAIL_CONFIG['to']
        msg['Subject'] = subject
        msg.attach(MIMEText(body_plain, 'plain', 'utf-8'))
        if body_html:
            msg.attach(MIMEText(body_html, 'html', 'utf-8'))

        with smtplib.SMTP(EMAIL_CONFIG['smtp_host'], EMAIL_CONFIG['smtp_port']) as server:
            server.starttls()
            server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
            server.send_message(msg)

        print(f"  {C['green']}📧 邮件已发送 → {EMAIL_CONFIG['to']}{C['reset']}")
        return True
    except Exception as e:
        print(f"  {C['red']}✗ 邮件发送失败: {e}{C['reset']}")
        return False


def build_email(positions_data: List[dict], signal: dict, pf: Portfolio, fx_rate: float) -> Tuple[str, str]:
    """构建邮件正文（纯文本 + HTML）。"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    threshold = pf.data['threshold']

    # ── 纯文本 ──
    lines = []
    lines.append(f"三股轮动持仓报告 — {now}")
    lines.append(f"阈值: {threshold*100:.0f}% | EUR/USD: {fx_rate:.4f}")
    lines.append("=" * 45)

    for p in positions_data:
        dd = p['dd_pct']
        flag = '!! 卖出 !!' if p['breached'] else ('关注' if dd <= -20 else '持有')
        lines.append(f"  {p['label']:<16} EUR {p['current_value']:>9,.2f}  "
                     f"peak EUR {p['peak_value']:>9,.2f}  DD {dd:>+6.1f}%  {flag}")

    lines.append("=" * 45)
    lines.append(f"总市值: EUR {signal['total_value']:,.2f}")

    if signal['has_signal']:
        lines.append(f"\n!!! 轮动信号触发 !!!")
        lines.append(f"\n确认执行: python rotation_signal.py --confirm")

    plain = '\n'.join(lines)

    # ── HTML ──
    bg_color = '#FFF3E0' if signal['has_signal'] else '#F5F5F5'
    html = f"""<html><body style="font-family: Consolas, monospace; background:{bg_color}; padding:15px;">
<h2 style="color:#333;">📊 三股轮动持仓报告 — {now}</h2>
<p style="color:#666;">阈值: {threshold*100:.0f}% | EUR/USD: {fx_rate:.4f}</p>
<table style="border-collapse:collapse; width:100%; background:white; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.1);">
<tr style="background:#37474F; color:white;">
<th style="padding:8px 12px; text-align:left;">仓位</th>
<th style="padding:8px 12px; text-align:right;">权证价</th>
<th style="padding:8px 12px; text-align:right;">市值</th>
<th style="padding:8px 12px; text-align:right;">Peak</th>
<th style="padding:8px 12px; text-align:right;">回撤</th>
<th style="padding:8px 12px; text-align:center;">状态</th>
</tr>"""
    for p in positions_data:
        dd = p['dd_pct']
        if p['breached']:
            row_color = '#FFEBEE'; dd_color = '#D32F2F'; status = '🔴 卖出'
        elif dd <= -20:
            row_color = '#FFF8E1'; dd_color = '#F57F17'; status = '🟡 关注'
        else:
            row_color = '#E8F5E9'; dd_color = '#388E3C'; status = '🟢 持有'
        html += f"""<tr style="background:{row_color};">
<td style="padding:8px 12px;">{p['label']}</td>
<td style="padding:8px 12px; text-align:right;">€{p['current_price']:.4f}</td>
<td style="padding:8px 12px; text-align:right;">€{p['current_value']:,.2f}</td>
<td style="padding:8px 12px; text-align:right;">€{p['peak_value']:,.2f}</td>
<td style="padding:8px 12px; text-align:right; color:{dd_color}; font-weight:bold;">{dd:+.1f}%</td>
<td style="padding:8px 12px; text-align:center;">{status}</td>
</tr>"""
    html += f"""<tr style="background:#ECEFF1; font-weight:bold;">
<td style="padding:8px 12px;" colspan="2">总市值: €{signal['total_value']:,.2f}</td>
<td style="padding:8px 12px;" colspan="4"></td>
</tr></table>"""

    if signal['has_signal']:
        html += f"""<div style="margin-top:15px; padding:12px; background:#FFEBEE; border-left:4px solid #D32F2F; border-radius:4px;">
<h3 style="color:#D32F2F; margin:0;">⚠️ 轮动信号触发！</h3><p style="margin:8px 0 0;">运行 <code>python rotation_signal.py --confirm</code> 确认执行。</p></div>"""

    html += f"""<p style="color:#999; font-size:12px; margin-top:20px;">自动生成 | rotation_signal.py | {now}</p></body></html>"""
    return plain, html


# ═══════════════════════════════════════════════════════════════
# 初始化向导
# ═══════════════════════════════════════════════════════════════

def interactive_init():
    """交互式创建 portfolio.json。"""
    print(f"\n{C['bold']}{C['cyan']}╔{'═'*50}╗{C['reset']}")
    print(f"{C['bold']}{C['cyan']}║   🚀 三股轮动持仓初始化                    ║{C['reset']}")
    print(f"{C['bold']}{C['cyan']}╚{'═'*50}╝{C['reset']}\n")

    positions = []

    for i in range(3):
        print(f"{C['bold']}── 仓位 {i+1}/3 ──{C['reset']}")
        label = input(f"  名称 (如 'NVDA Turbo'): ").strip()
        underlying = input(f"  正股代码 (如 'NVDA'): ").strip().upper()
        product = input(f"  产品名称 (可选): ").strip()
        isin = input(f"  ISIN (可选): ").strip()
        strike_str = input(f"  行权价/KO价 (USD): ").strip()
        ratio_str = input(f"  换股比率 Bezugsverhältnis (如 0.1): ").strip()
        shares_str = input(f"  持有股数: ").strip()
        price_str = input(f"  买入价 (EUR): ").strip()

        try:
            strike = float(strike_str)
            ratio = float(ratio_str)
            shares = float(shares_str)
            price = float(price_str)
        except ValueError:
            print(f"{C['red']}  输入无效，跳过。{C['reset']}\n")
            continue

        positions.append({
            'label': label or f'{underlying} Turbo',
            'underlying': underlying,
            'product_name': product,
            'isin': isin,
            'strike_usd': strike,
            'ratio': ratio,
            'shares': shares,
            'entry_price': price,
            'entry_date': date.today().isoformat(),
        })
        print(f"  {C['green']}✓{C['reset']} {label}: {shares}股 × €{price} = €{shares*price:,.2f}\n")

    if len(positions) < 2:
        print(f"{C['red']}至少需要 2 个仓位才能轮动。退出。{C['reset']}")
        return

    # 阈值
    th_str = input(f"  轮动阈值 [{DEFAULT_THRESHOLD*100:.0f}%]: ").strip()
    threshold = float(th_str) / 100 if th_str else DEFAULT_THRESHOLD

    pf = Portfolio()
    pf.create(positions, threshold)

    total = sum(p['shares'] * p['entry_price'] for p in positions)
    print(f"\n{C['green']}{'═'*50}{C['reset']}")
    print(f"{C['green']}  ✅ portfolio.json 已创建{C['reset']}")
    print(f"  📁 {PORTFOLIO_PATH}")
    print(f"  💰 总投入: €{total:,.2f}")
    print(f"  📊 阈值: {threshold*100:.0f}%")
    print(f"  📌 下次运行: python rotation_signal.py --check")
    print(f"{C['green']}{'═'*50}{C['reset']}\n")


# ═══════════════════════════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════════════════════════

def parse_manual_prices(arg: str) -> Dict[str, float]:
    """解析 --manual 参数。格式: 'NVDA Turbo:5.71,MSFT Turbo:8.30'"""
    result = {}
    for part in arg.split(','):
        if ':' in part:
            label, price = part.split(':', 1)
            try:
                result[label.strip()] = float(price.strip())
            except ValueError:
                pass
    return result


def main():
    parser = argparse.ArgumentParser(description='三股轮动持仓信号')
    parser.add_argument('--init', action='store_true', help='首次创建 portfolio.json')
    parser.add_argument('--check', action='store_true', default=False, help='检查价格 + 输出信号 (默认)')
    parser.add_argument('--confirm', action='store_true', help='确认执行本次轮动信号')
    parser.add_argument('--email', action='store_true', help='检查并发送邮件通知')
    parser.add_argument('--manual', type=str, default=None,
                        help='手动输入权证价格 (格式: "标签:价格,标签:价格")')
    parser.add_argument('--threshold', type=float, default=None, help='临时覆盖阈值 (如 --threshold 0.35)')
    parser.add_argument('--reset-peaks', action='store_true', help='重置所有 peak 为当前市值 (Day 1)')
    args = parser.parse_args()

    # ── --init ──
    if args.init:
        interactive_init()
        return

    # ── 检查 portfolio 是否存在 ──
    pf = Portfolio()
    if not pf.exists():
        print(f"\n{C['yellow']}⚠ portfolio.json 不存在。{C['reset']}")
        print(f"  运行 {C['bold']}python rotation_signal.py --init{C['reset']} 创建持仓。\n")
        return

    pf.load()
    threshold = args.threshold if args.threshold is not None else pf.data['threshold']

    # ── --confirm ──
    if args.confirm:
        pf.confirm_signal()
        return

    # ── --reset-peaks ──
    if args.reset_peaks:
        for p in pf.data['positions']:
            if p['active']:
                p['peak_price'] = p['current_price']
                p['peak_value'] = p['current_value']
                print(f"  {C['green']}✓{C['reset']} {p['label']}: peak → EUR {p['current_value']:.2f}")
        pf.save()
        print(f"\n{C['green']}✅ 所有 peak 已重置为当前市值 (Day 1)。{C['reset']}\n")
        return

    # ── 默认 --check（含 --email）──
    active = pf.get_active_positions()
    if not active:
        print(f"\n{C['red']}⚠ 无活跃仓位。所有仓位可能已被卖出。{C['reset']}\n")
        return

    # 获取市场价格
    underlyings = list(set(p['underlying'] for p in active))
    print(f"\n{C['grey']}  下载市场数据...{C['reset']}")
    stock_prices, fx_rate = fetch_market_data(underlyings)

    # 解析手动价格
    manual_prices = parse_manual_prices(args.manual) if args.manual else None

    # 更新权证价格
    pf.update_prices(stock_prices, fx_rate, manual_prices)

    # 检查信号
    signal = pf.check_signals(threshold)

    # 保存待确认信号
    if signal['has_signal']:
        pf.data['pending_signal'] = signal
        # 清理不需要持久化的字段
        pf.data['pending_signal'] = {
            'has_signal': True,
            'breached': signal['breached'],
            'survivors': [p['id'] for p in signal['survivors']],
            'cash': signal.get('cash', 0),
            'per_survivor': signal.get('per_survivor', 0),
            'total_value': signal['total_value'],
        }
    else:
        pf.data['pending_signal'] = None

    # 记录检查历史
    pf.data['check_history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total_value': signal['total_value'],
        'had_signal': signal['has_signal'],
    })
    # 只保留最近 60 条
    if len(pf.data['check_history']) > 60:
        pf.data['check_history'] = pf.data['check_history'][-60:]

    pf.save()

    # ── 输出 ──
    print_header(pf, stock_prices, fx_rate)
    for p in active:
        print_position(p, threshold)
    print_footer(signal, pf)

    # 详细信号
    if signal.get('details'):
        print(signal['details'])

    # ── 邮件 ──
    if args.email:
        # 构建邮件数据
        pos_data = []
        for p in active:
            dd = (p['current_value'] - p['peak_value']) / p['peak_value'] * 100 if p['peak_value'] > 0 else 0
            breached = signal['has_signal'] and p['id'] in signal.get('breached', [])
            pos_data.append({
                'label': p['label'], 'current_price': p['current_price'],
                'current_value': p['current_value'], 'peak_value': p['peak_value'],
                'dd_pct': dd, 'breached': breached,
            })

        subject = '⚠️ 轮动信号触发!' if signal['has_signal'] else '📊 每日持仓报告'
        plain, html = build_email(pos_data, signal, pf, fx_rate)
        send_email(subject, plain, html)
    elif not EMAIL_CONFIG['enabled']:
        pass  # 未配置邮件，静默
    else:
        # 邮件已配置但未指定 --email，提示
        pass


if __name__ == '__main__':
    main()
