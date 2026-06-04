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
PORTFOLIO2_PATH = r'C:\AI\cc\stock\data\portfolio2.json'
DATA_DIR = r'C:\AI\cc\stock\data'
ENV_PATH = r'C:\AI\cc\stock\.env'
DEFAULT_THRESHOLD = 0.40  # 40% 回撤触发轮动


def find_all_portfolios(data_dir: str = None) -> list:
    """查找所有 portfolio*.json 文件，按文件名排序。"""
    import glob
    if data_dir is None:
        data_dir = DATA_DIR
    pattern = os.path.join(data_dir, 'portfolio*.json')
    files = sorted(glob.glob(pattern))
    return files if files else [PORTFOLIO_PATH]

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


def get_rebalance_advice(pos: dict, stock_price: float, fx_rate: float, group_name: str) -> str or None:
    """根据分组策略判断是否需要换仓。返回建议字符串或 None。

    铁三角：杠杆 < 3x 时提醒
    窜天猴：正股累计涨幅 > 70% 时提醒
    """
    strike = pos['strike_usd']
    ratio = pos['ratio']
    if stock_price <= strike or ratio <= 0:
        return None

    leverage = stock_price / (stock_price - strike)

    # 正股累计涨幅（从上次换仓/入场算起）
    ref_stock = pos.get('ref_stock_price')
    if ref_stock is None:
        # 首次：从入场价反推
        ref_stock = strike + pos['entry_price'] * fx_rate / ratio
    stock_gain = (stock_price - ref_stock) / ref_stock if ref_stock and ref_stock > 0 else 0

    if '铁三角' in group_name:
        if leverage < 3.0:
            return (f"💡 建议换仓：{pos['label']} 杠杆已降至 {leverage:.1f}x（铁三角阈值 3.0x），"
                    f"正股累涨 {stock_gain*100:.0f}%")
    elif '窜天猴' in group_name:
        if stock_gain > 0.70:
            return (f"💡 建议换仓：{pos['label']} 正股累涨 {stock_gain*100:.0f}%（窜天猴阈值 70%），"
                    f"杠杆已降至 {leverage:.1f}x")

    return None


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
                'ref_stock_price': p.get('ref_stock_price'),  # 上次换仓时的正股价（None=入场）
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

    def mark_rebalanced(self, label: str, stock_price: float):
        """标记某仓位已换仓，更新 ref_stock_price。"""
        for p in self.data['positions']:
            if p['active'] and p['label'] == label:
                p['ref_stock_price'] = round(stock_price, 2)
                p['transaction_history'].append({
                    'date': date.today().isoformat(),
                    'action': 'REBALANCE (new Turbo)',
                    'price': p['current_price'],
                    'shares': p['shares'],
                    'value': p['current_value'],
                })
                self.save()
                return True
        return False


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


def build_combined_email(all_results: list, all_fx_rates: dict) -> Tuple[str, str]:
    """构建多组轮动的合并邮件（纯文本 + HTML）。

    all_results: [{'name': str, 'positions_data': [...], 'signal': dict, 'total_invested': float, 'threshold': float}, ...]
    all_fx_rates: {'EUR/USD': float, ...}
    """
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    any_signal = any(r['signal']['has_signal'] for r in all_results)

    # ── 纯文本 ──
    lines = [f"杠杆轮动每日报告 — {now}", f"EUR/USD: {all_fx_rates.get('EUR/USD', 'N/A'):.4f}", "=" * 55]

    for grp in all_results:
        lines.append(f"\n▸ {grp['name']}  (阈值: {grp['threshold']*100:.0f}%)")
        lines.append("-" * 40)
        for p in grp['positions_data']:
            dd = p['dd_pct']
            flag = '!! 卖出 !!' if p['breached'] else ('关注' if dd <= -20 else '持有')
            lines.append(f"  {p['label']:<16} EUR {p['current_value']:>9,.2f}  "
                         f"peak EUR {p['peak_value']:>9,.2f}  DD {dd:>+6.1f}%  {flag}")
        total = grp['signal']['total_value']
        pnl = (total - grp['total_invested']) / grp['total_invested'] * 100
        lines.append(f"  总市值: EUR {total:,.2f}  (盈亏 {pnl:+.1f}%)")
        if grp['signal']['has_signal']:
            lines.append(f"  ⚠️ 轮动信号触发！")
        for advice in grp.get('rebalance_advice', []):
            lines.append(f"  {advice}")

    if any_signal:
        lines.append(f"\n!!! 确认执行: python rotation_signal.py --confirm !!!")

    plain = '\n'.join(lines)

    # ── HTML ──
    bg_color = '#FFF3E0' if any_signal else '#F5F5F5'
    html = f"""<html><body style="font-family: Consolas, 'Microsoft YaHei', monospace; background:{bg_color}; padding:15px;">
<h2 style="color:#333;">📊 杠杆轮动每日报告 — {now}</h2>
<p style="color:#666;">EUR/USD: {all_fx_rates.get('EUR/USD', 'N/A'):.4f}</p>"""

    for grp in all_results:
        signal_icon = '⚠️' if grp['signal']['has_signal'] else '✅'
        total = grp['signal']['total_value']
        pnl = (total - grp['total_invested']) / grp['total_invested'] * 100
        pnl_color = '#388E3C' if pnl >= 0 else '#D32F2F'

        html += f"""<h3 style="color:#1565C0; margin-top:20px;">{signal_icon} {grp['name']} <span style="font-weight:normal; font-size:14px; color:#666;">(阈值: {grp['threshold']*100:.0f}%)</span></h3>
<table style="border-collapse:collapse; width:100%; background:white; border-radius:4px; box-shadow:0 1px 3px rgba(0,0,0,0.1); margin-bottom:8px;">
<tr style="background:#37474F; color:white;">
<th style="padding:8px 12px; text-align:left;">仓位</th>
<th style="padding:8px 12px; text-align:right;">权证价</th>
<th style="padding:8px 12px; text-align:right;">市值</th>
<th style="padding:8px 12px; text-align:right;">Peak</th>
<th style="padding:8px 12px; text-align:right;">回撤</th>
<th style="padding:8px 12px; text-align:center;">状态</th>
</tr>"""
        for p in grp['positions_data']:
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
<td style="padding:8px 12px;" colspan="2">总市值: €{total:,.2f}</td>
<td style="padding:8px 12px; text-align:right; color:{pnl_color};" colspan="2">盈亏: {pnl:+.1f}%</td>
<td style="padding:8px 12px;" colspan="2"></td>
</tr></table>"""

        if grp['signal']['has_signal']:
            html += f"""<div style="padding:10px; background:#FFEBEE; border-left:4px solid #D32F2F; border-radius:4px; margin-bottom:8px;">
<strong style="color:#D32F2F;">⚠️ 轮动信号触发！</strong> 运行 <code>python rotation_signal.py -p {grp.get('file','')} --confirm</code></div>"""

        # 换仓建议
        for advice in grp.get('rebalance_advice', []):
            html += f"""<div style="padding:8px 12px; background:#FFF8E1; border-left:4px solid #F57F17; border-radius:4px; margin-bottom:4px; font-size:14px;">
        {advice}</div>"""

    html += f"""<p style="color:#999; font-size:12px; margin-top:20px;">自动生成 | rotation_signal.py | {now}</p></body></html>"""
    return plain, html


def run_single_check(portfolio_path: str, threshold_override: float = None,
                     manual_prices: dict = None, verbose: bool = True) -> dict:
    """对单个 portfolio 执行完整检查。

    Returns:
        {'pf': Portfolio, 'signal': dict, 'stock_prices': dict, 'fx_rate': float,
         'active': list, 'threshold': float, 'error': str|None}
    """
    pf = Portfolio(portfolio_path)
    if not pf.exists():
        return {'error': f'{portfolio_path} 不存在', 'pf': None}

    pf.load()
    threshold = threshold_override if threshold_override is not None else pf.data['threshold']
    active = pf.get_active_positions()
    if not active:
        return {'error': '无活跃仓位', 'pf': pf}

    underlyings = list(set(p['underlying'] for p in active))
    if verbose:
        print(f"\n{C['grey']}  下载市场数据...{C['reset']}")
    stock_prices, fx_rate = fetch_market_data(underlyings)
    pf.update_prices(stock_prices, fx_rate, manual_prices)
    signal = pf.check_signals(threshold)

    # 保存待确认信号
    if signal['has_signal']:
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

    pf.data['check_history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total_value': signal['total_value'],
        'had_signal': signal['has_signal'],
    })
    if len(pf.data['check_history']) > 60:
        pf.data['check_history'] = pf.data['check_history'][-60:]
    pf.save()

    # 换仓建议
    rebalance_advice = []
    grp_name = pf.data.get('name', '')
    for p in active:
        ticker = p['underlying']
        if ticker in stock_prices and stock_prices[ticker] is not None:
            advice = get_rebalance_advice(p, stock_prices[ticker], fx_rate, grp_name)
            if advice:
                rebalance_advice.append(advice)

    return {
        'pf': pf, 'signal': signal, 'stock_prices': stock_prices,
        'fx_rate': fx_rate, 'active': active, 'threshold': threshold, 'error': None,
        'rebalance_advice': rebalance_advice,
    }


def print_single_report(result: dict):
    """打印单个轮动组的终端报告。"""
    pf = result['pf']
    active = result['active']
    stock_prices = result['stock_prices']
    fx_rate = result['fx_rate']
    signal = result['signal']
    threshold = result['threshold']

    name = pf.data.get('name', os.path.basename(pf.path))
    print(f"\n{C['bold']}{C['magenta']}  ▸ {name}{C['reset']}")
    print_header(pf, stock_prices, fx_rate)
    for p in active:
        print_position(p, threshold)
    print_footer(signal, pf)
    if signal.get('details'):
        print(signal['details'])
    # 换仓建议
    for advice in result.get('rebalance_advice', []):
        print(f"  {C['yellow']}{advice}{C['reset']}")

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
    parser.add_argument('--check-all', action='store_true', default=False,
                        help='检查所有轮动组 (portfolio*.json)')
    parser.add_argument('--confirm', action='store_true', help='确认执行本次轮动信号')
    parser.add_argument('--email', action='store_true', help='检查并发送邮件通知')
    parser.add_argument('--manual', type=str, default=None,
                        help='手动输入权证价格 (格式: "标签:价格,标签:价格")')
    parser.add_argument('--threshold', type=float, default=None, help='临时覆盖阈值 (如 --threshold 0.35)')
    parser.add_argument('--reset-peaks', action='store_true', help='重置所有 peak 为当前市值 (Day 1)')
    parser.add_argument('--portfolio', '-p', type=str, default=None,
                        help='指定 portfolio 文件路径 (默认: portfolio.json)')
    parser.add_argument('--mark-rebalanced', type=str, default=None,
                        help='标记仓位已换仓 (如 --mark-rebalanced "NVDA Turbo")')
    args = parser.parse_args()

    # ── --init ──
    if args.init:
        interactive_init()
        return

    # ── --mark-rebalanced ──
    if args.mark_rebalanced:
        label = args.mark_rebalanced
        # 确定要操作的 portfolio
        target_path = args.portfolio if args.portfolio else PORTFOLIO_PATH
        if args.check_all:
            # 遍历所有 portfolio，找到匹配的仓位
            for pf_path in find_all_portfolios():
                pf = Portfolio(pf_path)
                if pf.exists():
                    pf.load()
                    # 需要当前股价来计算 ref_stock_price
                    active = pf.get_active_positions()
                    underlyings = list(set(p['underlying'] for p in active))
                    stock_prices, fx_rate = fetch_market_data(underlyings)
                    for p in active:
                        if p['label'] == label and p['underlying'] in stock_prices:
                            stock_px = stock_prices[p['underlying']]
                            if stock_px:
                                pf.mark_rebalanced(label, stock_px)
                                grp = pf.data.get('name', '')
                                print(f"  {C['green']}✓{C['reset']} [{grp}] {label}: ref_stock_price → ${stock_px:.2f}")
                                return
            print(f"  {C['red']}✗ 未找到仓位: {label}{C['reset']}")
        else:
            pf = Portfolio(target_path)
            if pf.exists():
                pf.load()
                active = pf.get_active_positions()
                underlyings = list(set(p['underlying'] for p in active))
                stock_prices, fx_rate = fetch_market_data(underlyings)
                for p in active:
                    if p['label'] == label and p['underlying'] in stock_prices:
                        stock_px = stock_prices[p['underlying']]
                        if stock_px:
                            if pf.mark_rebalanced(label, stock_px):
                                grp = pf.data.get('name', '')
                                print(f"  {C['green']}✓{C['reset']} [{grp}] {label}: ref_stock_price → ${stock_px:.2f}")
                            else:
                                print(f"  {C['red']}✗ 未找到活跃仓位: {label}{C['reset']}")
                        break
                else:
                    print(f"  {C['red']}✗ 未找到仓位: {label}{C['reset']}")
            else:
                print(f"  {C['red']}✗ {target_path} 不存在{C['reset']}")
        return

    # ── 确定要操作的 portfolio 文件 ──
    if args.portfolio:
        portfolio_files = [args.portfolio]
    elif args.check_all:
        portfolio_files = find_all_portfolios()
    else:
        portfolio_files = [PORTFOLIO_PATH]

    # ── 对每个 portfolio 执行操作 ──
    manual_prices = parse_manual_prices(args.manual) if args.manual else None
    all_results = []
    all_fx_rates = {}

    for pf_path in portfolio_files:
        pf = Portfolio(pf_path)

        # 检查是否存在
        if not pf.exists():
            print(f"\n{C['yellow']}⚠ {pf_path} 不存在，跳过。{C['reset']}")
            continue

        pf.load()
        grp_name = pf.data.get('name', os.path.basename(pf_path))
        threshold = args.threshold if args.threshold is not None else pf.data['threshold']

        # ── --confirm ──
        if args.confirm:
            pf.confirm_signal()
            continue

        # ── --reset-peaks ──
        if args.reset_peaks:
            for p in pf.data['positions']:
                if p['active']:
                    p['peak_price'] = p['current_price']
                    p['peak_value'] = p['current_value']
                    print(f"  {C['green']}✓{C['reset']} [{grp_name}] {p['label']}: peak → EUR {p['current_value']:.2f}")
            pf.save()
            continue

        # ── 默认 --check ──
        result = run_single_check(pf_path, threshold, manual_prices,
                                  verbose=(len(portfolio_files) == 1))
        if result['error']:
            print(f"\n{C['red']}⚠ [{grp_name}] {result['error']}{C['reset']}")
            continue

        all_fx_rates['EUR/USD'] = result['fx_rate']
        print_single_report(result)

        # 收集邮件数据
        active = result['active']
        signal = result['signal']
        pos_data = []
        for p in active:
            dd = (p['current_value'] - p['peak_value']) / p['peak_value'] * 100 if p['peak_value'] > 0 else 0
            breached = signal['has_signal'] and p['id'] in signal.get('breached', [])
            pos_data.append({
                'label': p['label'], 'current_price': p['current_price'],
                'current_value': p['current_value'], 'peak_value': p['peak_value'],
                'dd_pct': dd, 'breached': breached,
            })
        all_results.append({
            'name': grp_name, 'file': pf_path,
            'positions_data': pos_data, 'signal': signal,
            'total_invested': pf.data['total_invested'],
            'threshold': threshold,
            'rebalance_advice': result.get('rebalance_advice', []),
        })

    # ── 操作后处理 ──
    if args.reset_peaks:
        print(f"\n{C['green']}✅ 所有 peak 已重置为当前市值 (Day 1)。{C['reset']}\n")
        return

    if args.confirm:
        return

    if not all_results:
        return

    # ── 邮件（合并发送）──
    if args.email and all_results:
        any_signal = any(r['signal']['has_signal'] for r in all_results)
        all_names = ', '.join(r['name'] for r in all_results)
        subject = '⚠️ 轮动信号触发!' if any_signal else f'📊 每日持仓报告 ({all_names})'
        plain, html = build_combined_email(all_results, all_fx_rates)
        send_email(subject, plain, html)


if __name__ == '__main__':
    main()
