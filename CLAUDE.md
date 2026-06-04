# CLAUDE.md — stock 项目

量化回测系统。下载美股数据 (yfinance)，运行策略回测，输出图表 (PNG) 和结果 (CSV)。

**核心发现**：Buy & Hold 持续跑赢择时策略。固定月供 DCA ($1000) 对强趋势资产最优；增强 DCA 仅在深度熊市有边际价值。

## 环境

- Python 3，全局 `pip install yfinance pandas numpy matplotlib`
- Windows 路径硬编码 (`C:\AI\cc\stock\`)，不可移植
- UTF-8 输出包装: `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`

## 数据加载

```python
df = pd.read_csv(r"C:\AI\cc\stock\data\TICKER_daily.csv", header=[0,1], index_col=0, parse_dates=True)
close = df[("Close", "TICKER")].dropna()
```

yfinance 单 ticker 输出扁平列，多 ticker 输出 MultiIndex `(Price, Ticker)`。

## 文件命名

| 类型 | 格式 |
|------|------|
| 股票数据 | `data/{TICKER}_daily.csv` |
| 多股下载 | `data/stocks_daily.csv` |
| 回测结果 | `data/{TICKER}_equity.csv`, `_trades.csv` |
| 图表 | `image/{DESCRIPTION}.png` |
| Turbo 输入 | `input/{Name}.csv` |

## 已实现策略

| 策略 | 信号 | 关键文件 |
|------|------|----------|
| MA5/MA20 交叉 | 金叉买入，死叉卖出 | `all6_backtest.py` |
| 动量 (Jegadeesh-Titman) | 过去 N 月收益 > 0 做多，3M/6M/12M，skip 1M | `all6_backtest.py` |
| 增强 DCA | 6 种规则 vs 固定 $1000 基准 | `dca_backtest.py`, `dca_optimize_v2.py` |
| 杠杆轮动 (3 股) | 40% 回撤阈值 + 权证/KO 建模 | `top10_all_trios.py`, `rotation_signal.py`, `backtest_nvda_msft_orcl_turbo.py` |

## 常用公式

```python
ann = ((final / initial) ** (1 / years) - 1) * 100
sharpe = np.sqrt(12) * monthly_ret.mean() / monthly_ret.std()
max_dd = ((vals - vals.cummax()) / vals.cummax() * 100).min()
# Turbo 权证: warrant = max(0, stock_usd - strike_usd) * ratio / fx_eurusd
# 有效杠杆: stock_usd / (stock_usd - strike_usd)
```
