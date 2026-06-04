# PROJECT_INDEX — stock

最后更新: 2026-06-04 20:00

## code/ — Python 脚本

### 轮动策略 (Rotation)

| 文件 | 说明 |
|------|------|
| `rotation_signal.py` | 每日轮动信号系统（Turbo 权证监控、邮件通知、多组合支持） |
| `rotation_3stock.py` | 三股轮动回测核心引擎 |
| `rotation_3stock_all35.py` | 35 组三股轮动全扫描 |
| `rotation_3stock_oneyear.py` | 一年期三股轮动扫描 |
| `rotation_3stock_summary.py` | 三股轮动结果汇总 |
| `rotation_backtest.py` | 轮动策略回测（主脚本） |
| `rotation_backtest_googl_amzn.py` | GOOGL+AMZN 轮动回测 |
| `rotation_2016_nvda_mu.py` | NVDA+MU 2016年起轮动 |
| `rotation_2016_googl_amzn.py` | GOOGL+AMZN 2016年起轮动 |
| `rotation_vs_levered_bh.py` | 轮动 vs 杠杆 Buy&Hold 对比 |
| `rotation_vs_worst_stock.py` | 轮动 vs 最差成分股对比 |
| `rotation_threshold_scan.py` | 轮动阈值扫描 |
| `rotation_threshold_scan_googl_amzn.py` | GOOGL+AMZN 阈值扫描 |
| `threshold_scan_4pairs.py` | 4 组阈值扫描 |
| `threshold_2016_nvda_mu.py` | NVDA+MU 2016年阈值 |
| `threshold_2016_googl_amzn.py` | GOOGL+AMZN 2016年阈值 |
| `top10_all_trios.py` | Top 10 所有三股组合扫描 |
| `screen_rotation_partners.py` | 轮动候选股筛选 |
| `backtest_nvda_msft_orcl_turbo.py` | 铁三角 Turbo 权证回测 |
| `backtest_rebalance_rule.py` | 换仓规则回测（9规则×2组 十年） |
| `leverage_decay.py` | 6 只权证杠杆衰减曲线分析 |

### 杠杆策略 (Leverage)

| 文件 | 说明 |
|------|------|
| `leverage_optimize.py` | 杠杆倍数优化 |
| `leverage_optimize_googl_amzn.py` | GOOGL+AMZN 杠杆优化 |
| `leverage_2016_all4.py` | NVDA/MU/GOOGL/AMZN 杠杆回测 |
| `warrant_3x_vs_5x.py` | 3x vs 5x 权证对比 |
| `warrant_5x_compare.py` | 5x 权证对比分析 |
| `warrants_backtest.py` | 权证回测 |
| `warrants_full_backtest.py` | 权证完整回测 |
| `verify_leveraged_etp.py` | 真实杠杆产品验证 (NVDL/3NVD.L等) |
| `volatility_decay_demo.py` | 波动率衰减演示 |

### DCA 定投 (Dollar Cost Averaging)

| 文件 | 说明 |
|------|------|
| `dca_backtest.py` | DCA 基础回测 |
| `dca_optimize.py` | DCA 策略优化 |
| `dca_optimize_v2.py` | DCA 优化 v2 (6 种规则) |
| `dca_equal_invested.py` | 等额投入 DCA 对比 |
| `dca_2000_2016.py` | 2016年起 $2000 DCA |
| `dca_ranking_all.py` | 23 只股票 DCA 排名 (Fixed vs DD3M) |
| `dca_optimal_allocation.py` | NVDA+AVGO+SPY 231 种比例优化 |
| `dca_best_day.py` | 最佳买入日分析（交易日/日历日/周几/信号/蒙特卡洛） |
| `dca_complete_week.py` | 完整星期择日 + 用户"1号+7天"方案验证 |
| `dca_monthly_reminder.py` | 月度定投邮件提醒 + RSI 跟进 |

### 数据下载 (Download)

| 文件 | 说明 |
|------|------|
| `download_stocks.py` | 美股数据下载 (yfinance) |
| `download_google.py` | Google 数据下载 |
| `download_sp500.py` | S&P 500 指数下载 |
| `download_orcl_amzn_gld.py` | ORCL/AMZN/GLD 下载 |
| `download_shy.py` | SHY 国债 ETF 下载 |
| `download_warrant_data.py` | 权证数据下载 |

### 图表与分析 (Chart & Analysis)

| 文件 | 说明 |
|------|------|
| `all6_backtest.py` | MA5/MA20 + 动量策略全回测 |
| `annual_rolling.py` | 年度滚动回测 |
| `annual_rolling_nvda_mu.py` | NVDA+MU 年度滚动 |
| `annual_rolling_googl_amzn.py` | GOOGL+AMZN 年度滚动 |
| `chart_4stock_comparison.py` | 4 股对比图 |
| `chart_6pairs_annual.py` | 6 组年度对比图 |
| `chart_annual_rotation_vs_bh.py` | 年度轮动 vs B&H 图 |
| `chart_threshold_scan.py` | 阈值扫描图 |
| `check_nvda.py` | NVDA 数据检查 |
| `check_googl_amzn.py` | GOOGL+AMZN 数据检查 |
| `googl_backtest.py` | GOOGL 回测 |
| `googl_backtest_2010.py` | GOOGL 2010年起回测 |
| `nvda_backtest.py` | NVDA 回测 |
| `nvda_chart.py` | NVDA 图表 |
| `nvda_momentum.py` | NVDA 动量分析 |
| `optimize_orcl_msft_amzn.py` | ORCL+MSFT+AMZN 优化 |
| `shy_backtest.py` | SHY 国债回测 |
| `spy_backtest.py` | SPY 回测 |
| `spy_2000_bear.py` | SPY 2000年熊市回测 |

### 系统配置 (System)

| 文件 | 说明 |
|------|------|
| `setup_scheduled_task.ps1` | 轮动信号定时任务（每天 04:30） |
| `setup_dca_scheduled_task.ps1` | DCA 定投提醒定时任务（每天 09:00） |
| `debug_test.py` | 调试测试 |

---

## data/ — 数据文件

### 日线行情 (Daily Price)

| 文件 | 标的 | 周期 |
|------|------|------|
| `NVDA_daily.csv` | NVIDIA | 全历史 |
| `NVDA_2016_daily.csv` | NVIDIA | 2016- |
| `AMD_2016_daily.csv` | AMD | 2016- |
| `MU_daily.csv` | Micron | 全历史 |
| `MU_2016_daily.csv` | Micron | 2016- |
| `AVGO_2016_daily.csv` | Broadcom | 2016- |
| `LRCX_2016_daily.csv` | Lam Research | 2016- |
| `TSM_2016_daily.csv` | TSMC | 2016- |
| `ASML_2016_daily.csv` | ASML | 2016- |
| `MRVL_2016_daily.csv` | Marvell | 2016- |
| `QCOM_2016_daily.csv` | Qualcomm | 2016- |
| `MSFT_2016_daily.csv` | Microsoft | 2016- |
| `ORCL_daily.csv` | Oracle | 全历史 |
| `ORCL_2016_daily.csv` | Oracle | 2016- |
| `CRM_2016_daily.csv` | Salesforce | 2016- |
| `NOW_2016_daily.csv` | ServiceNow | 2016- |
| `ADBE_2016_daily.csv` | Adobe | 2016- |
| `PLTR_2016_daily.csv` | Palantir | 2020- |
| `SMCI_daily.csv` | Super Micro | 全历史 |
| `SMCI_2016_daily.csv` | Super Micro | 2016- |
| `TSLA_2016_daily.csv` | Tesla | 2016- |
| `GOOGL_daily.csv` | Alphabet A | 全历史 |
| `GOOGL_2016_daily.csv` | Alphabet A | 2016- |
| `GOOG_daily.csv` | Alphabet C | 全历史 |
| `AMZN_daily.csv` | Amazon | 全历史 |
| `AMZN_2016_daily.csv` | Amazon | 2016- |
| `META_2016_daily.csv` | Meta | 2016- |
| `NFLX_2016_daily.csv` | Netflix | 2016- |
| `SPY_daily.csv` | S&P 500 ETF | 2010- |
| `SPY_full.csv` | S&P 500 ETF | 全历史 |
| `GSPC_daily.csv` | S&P 500 指数 | - |
| `GLD_daily.csv` | Gold ETF | - |
| `SHY_daily.csv` | Treasury ETF | - |
| `stocks_daily.csv` | 多股合并行情 | - |

### 持仓状态 (Portfolio State)

| 文件 | 说明 |
|------|------|
| `portfolio.json` | 铁三角 (NVDA+MSFT+ORCL) Turbo 权证持仓 |
| `portfolio2.json` | 窜天猴 (PLTR+SMCI+TSLA) Turbo 权证持仓 |
| `dca_reminder_state.json` | DCA 定投提醒状态（上次定投日/价格/RSI/历史） |

### 回测结果 (Backtest Results)

| 文件 | 说明 |
|------|------|
| `NVDA_equity.csv` | NVDA 回测权益曲线 |
| `NVDA_trades.csv` | NVDA 回测交易记录 |
| `NVDA_momentum_12M.csv` | NVDA 12月动量数据 |
| `GOOGL_ma_cross.csv` | GOOGL MA 交叉信号 |
| `GOOGL_ma_trades.csv` | GOOGL MA 交易记录 |
| `GOOGL_momentum_12M.csv` | GOOGL 12月动量数据 |
| `verify_leveraged_etp.csv` | 杠杆 ETP 验证数据 |
| `dca_ranking_all.txt` | 23 股 DCA 排名结果 |

### 其他数据

| 文件 | 说明 |
|------|------|
| `financial_products.txt` | 项目全部金融产品名录（~55个） |
| `MU_5min.csv` | MU 5分钟行情 |

---

## input/ — 权证产品信息

| 文件 | 说明 |
|------|------|
| `NVDA.csv` | NVDA Turbo 权证参数 |
| `Microsoft.csv` | MSFT Turbo 权证参数 |
| `Oracle.csv` | ORCL Turbo 权证参数 |
| `Palantir.csv` | PLTR Turbo 权证参数 |
| `Super Micro Computer.csv` | SMCI Turbo 权证参数 |
| `Tesla.csv` | TSLA Turbo 权证参数 |
| `Turbo Long.txt` | 候选 Turbo 权证列表（11个产品） |

---

## 文档 (Documentation)

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | 项目级 Claude 规则 |
| `PROJECT_LOG.md` | 项目日志（按时间倒序） |
| `DCA_RULES_FINAL.txt` | DCA 定投最终规则与完整回测结论（14章） |
| `LEVERAGED_ROTATION_STRATEGY.md` | 杠杆轮动策略文档 |
| `top10_3stock_rotation.txt` | Top 10 三股轮动结果 |
| `新建文本文档.txt` | 杂项笔记 |
| `新建文本文档 (2).txt` | 杂项笔记 |

---

---

## image/ — 图表与网页

| 文件 | 说明 |
|------|------|
| `strategy_rankings.html` | 📊 策略回测排行榜网页（三股轮动/B&H/DCA/换仓/杠杆，含搜索和排序） |
| `verify_leveraged_etp.png` | 杠杆 ETP 模型验证 4 面板对比图 |
| `leverage_decay.png` | 6 只权证杠杆衰减曲线图 |
| `NVDA_ma_cross.png` | NVDA MA5/MA20 交叉信号图 |
| `chart_4stock_comparison.png` | NVDA/MU/GOOGL/AMZN 4 股对比图 |
| `chart_threshold_scan.png` | NVDA+MU 阈值扫描热力图 |

---

## 统计

| 类型 | 数量 |
|------|:---:|
| Python 脚本 | 65 |
| 行情 CSV | 34 |
| 回测结果 CSV | 7 |
| 持仓 JSON | 3 |
| 权证输入 | 7 |
| 文档 | 7 |
| HTML 网页 | 1 |
| PNG 图表 | ~10 |
| PowerShell | 2 |
| **合计** | **~136** |
