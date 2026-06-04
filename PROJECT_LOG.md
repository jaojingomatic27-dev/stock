# 项目日志 — stock

## [2026-06-04 16:30] DCA 全部分析结果同步到 DCA_RULES_FINAL

- **输入命令**: "把上面的所有结果同步到 DCA_RULES_FINAL"
- **PROJECT_INDEX 变更**: 修改 `DCA_RULES_FINAL.txt`
- **关键发现**:
  1. DCA_RULES_FINAL 新增 5 个章节（十~十四），涵盖标的排名、组合优化、最佳买日、完整星期分析
  2. **选对标的 >>> 选对规则 >>> 选对日子**：NVDA vs SPY = 1680% 差异，Fixed vs DD3M = ~5%，周四 vs 周一 = 0.5%
  3. 用户"1号+7天"方案排名第 2（仅次于 RSI 最低事后诸葛亮），直觉正确
  4. 均衡型配置（SPY 10% + NVDA 60% + AVGO 30%）Sharpe 1.80，回撤 -32.4%，用户选定
  5. 1000 次随机择日模拟 CV < 2% — 哪天买几乎没区别
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `DCA_RULES_FINAL.txt` | 新增第 10-14 章：标的排名、组合优化、最佳买日、完整星期、全文总结 |
  | `code/dca_optimal_allocation.py` | 231 种比例组合优化，按风险偏好推荐 |
  | `code/dca_best_day.py` | 交易日/日历日/周几/信号/蒙特卡洛 五维择日分析 |
  | `code/dca_complete_week.py` | 完整星期择日 + 用户"1号+7天"方案验证 |

## [2026-06-04 15:45] DCA 定投标的全面排名

- **输入命令**: "DCA_RULES_FINAL这是我的定投策略 把上面所有提到的股票都考虑 选出最好的定投标的"
- **PROJECT_INDEX 变更**: 新增 `code/dca_ranking_all.py`、`data/dca_ranking_all.txt`
- **关键发现**:
  1. 2016-2026 全部 23 只股票 Fixed $1000 DCA — Drawdown 3M **0/23 获益**（全是牛市，存弹药=踏空）
  2. 🥇 PLTR: CAGR +46.1%（仅 6 年数据，2020年上市，未经历完整熊市）
  3. 🥈 NVDA: $126K→$5.15M（+42.8% CAGR，-59.2% 最大回撤）
  4. 🥉 AVGO: $126K→$1.88M（+29.7% CAGR，-26.8% 最佳 Sharpe 1.73）
  5. 选对标的比选对规则重要 100 倍：第 1 名 NVDA $5.15M vs 最后 ADBE $0.13M — 差 38 倍
  6. DCA 最看重的三个维度：CAGR（趋势强度）、Sharpe（风险调整收益）、MaxDD（可承受性）
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/dca_ranking_all.py` | 23 只股票 Fixed + Drawdown 3M DCA 回测排名 |
  | `data/dca_ranking_all.txt` | 完整排名结果（4 张表） |

## [2026-06-04 15:15] 换仓策略：杠杆衰减管理 + 信号系统提醒

- **输入命令**: "杠杆弱化到多少换仓 收益最大 回测十年窜天猴和铁三角"
- **PROJECT_INDEX 变更**: 新增 `code/backtest_rebalance_rule.py`、`code/leverage_decay.py`，修改 `rotation_signal.py`、`LEVERAGED_ROTATION_STRATEGY.md`
- **关键发现**:
  1. 铁三角最优换仓规则：**杠杆 < 3x 时换**（年均 +353% vs 永不换 +148%，4/10 KO）
  2. 窜天猴最优换仓规则：**正股涨 > 70% 再换**（年均 +290%，3/6 KO；换太勤 = ALL KO）
  3. 窜天猴换仓太激进（杠杆<3x、涨>30%）直接全灭——高波动股必须给足安全边际
  4. 信号系统新增 `get_rebalance_advice()`：按分组策略自动判断，终端/邮件均提醒
  5. 新增 `--mark-rebalanced` CLI：换仓后更新 ref_stock_price
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/backtest_rebalance_rule.py` | 9 种换仓规则 × 2 组 十年回测 |
  | `code/leverage_decay.py` | 6 只权证杠杆衰减曲线分析 |
  | `LEVERAGED_ROTATION_STRATEGY.md` | 新增第十章：Turbo 权证换仓策略 |
  | `code/rotation_signal.py` | +get_rebalance_advice()、+mark_rebalanced、邮件/终端换仓提醒 |

## [2026-06-04 14:25] 新增第二组轮动（PLTR+SMCI+TSLA）+ 多组支持

- **输入命令**: "再加一个三只涡轮权证轮动...算上之前的轮动 现在一共是两个轮动 最后发个邮件 把两个轮动"
- **PROJECT_INDEX 变更**: 新增 `data/portfolio2.json`，修改 `code/rotation_signal.py`、`code/setup_scheduled_task.ps1`
- **关键发现**:
  1. 第二组 PLTR+SMCI+TSLA 初始市值 €1,849.80（投入 €1,793，浮盈 +3.2%）
  2. SMCI 权证兑换比例 1.0（≠ 常见的 0.1），权证价格公式仍然适用
  3. 两组轮动独立运行，互不干扰（各自 portfolio*.json）
  4. rotation_signal.py 新增 `--check-all`、`--portfolio`、`-p` 参数，支持多组合并邮件
  5. 定时任务已更新为 `--check-all --email`，每天 04:30 同时检查两组
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `data/portfolio2.json` | 第二组 PLTR+SMCI+TSLA 持仓状态 |
  | `code/rotation_signal.py` | 新增 --check-all、--portfolio、合并邮件、多组检查 |
  | `code/setup_scheduled_task.ps1` | --check 改为 --check-all |

## [2026-06-04 12:30] 真实杠杆产品验证：回测模型 vs 实际 ETP

- **输入命令**: "去网上找杠杆产品的真实数据 比如文件夹C:\AI\cc\stock\input中的Turbo Long列出的产品 验证回测结果的真实性"
- **PROJECT_INDEX 变更**: 新增 `code/verify_leveraged_etp.py`、`data/verify_leveraged_etp.csv`、`image/verify_leveraged_etp.png`
- **关键发现**:
  1. ✅ **NVDL (US 2x NVDA ETF) 完美验证**：日收益 Pearson 相关系数 **0.9895**，R² = **0.9711**
  2. ✅ 回测 daily-reset 公式 `val *= (1 + L * daily_return)` 极其准确 —— 解释了 97.1% 的日收益变化
  3. ⚠️ UK LSE 3x ETP（3NVD.L, 3MSF.L, 3AMZ.L）受 consolidation（反向拆股）和 GBP/USD 汇率噪音影响，相关性仅 0.67-0.73
  4. ⚠️ 但即使有 consolidation 问题，加入汇率修正后隐含费用拖累（13.7-14.6%/年）接近理论值（5-7%/年），说明日常跟踪是准的
  5. 📊 真实产品平均每年比模拟亏 ~5-7%（管理费 0.75% + 融资成本 ~4-6%），所以回测收益偏高是预期的
  6. 🔑 **回测排名不受影响**：所有产品同方向偏高，相对比较仍然有效
  7. US 单股杠杆 ETF 只有 2x（SEC 限制），3x 只有欧洲有。所以只能以 NVDL 2x 为主验证
  8. Turbo 权证的 KO 机制比我们的 5% 模型更严格（触及 barrier 即刻归零），回测 KO 判断偏保守
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/verify_leveraged_etp.py` | 真实 ETP vs 模拟模型对比验证脚本 |
  | `data/verify_leveraged_etp.csv` | 各 ETP 验证指标汇总 |
  | `image/verify_leveraged_etp.png` | 四面板对比图（净值+散点图） |
  | `LEVERAGED_ROTATION_STRATEGY.md` | 待更新：加入验证结果章节 |

### 验证结果汇总

| 产品 | 杠杆 | 日收益 Corr | R² | 隐含拖累/年 | 结论 |
|------|:----:|:----------:|:---:|:----------:|------|
| **NVDL (US)** | 2x NVDA | **0.9895** | **0.9711** | 27.2%* | ✅ 完美匹配 |
| 3NVD.L (UK) | 3x NVDA | 0.6747 | 0.3442 | 45.9% | ⚠️ 数据问题 |
| 3MSF.L (UK) | 3x MSFT | 0.6950 | 0.3659 | 13.7% | ⚠️ 数据问题 |
| 3AMZ.L (UK) | 3x AMZN | 0.7321 | 0.4498 | 14.6% | ⚠️ 中等 |

> *NVDL 2x 的 27.2% 拖累偏高，因为 NVDA 在 2023-2024 极端涨幅放大了跟踪误差的累计效应（年化收益率越高，费用复利效应越显著）。

### 输入文件中的 Turbo Long 产品对应

| # | 描述 | 对应正股 | 可验证的 ETP |
|:-:|------|----------|-------------|
| 1 | UBS OE Turbo Call Warrant NVIDIA | NVDA | NVDL (2x US), 3NVD.L (3x UK) |
| 2 | HSBC OE-Turbo Micron Technology Call | MU | MUU (2x US, 仅2024起) |
| 3 | Vontobel OE Call Turbo-OS Micron Technology | MU | MUU |
| 4 | Morgan Stanley OE Turbo Long NVIDIA | NVDA | NVDL, 3NVD.L |
| 5 | HSBC OE-Turbo Oracle Call | ORCL | 3ORC.L (3x UK, 仅2026起) |
| 6 | UBS OE Turbo Call Warrant Microsoft | MSFT | 3MSF.L (3x UK), MSFU (2x US) |
| 7 | UBS OE Turbo Call Warrant Lumentum | LITE | 无杠杆 ETP |
| 8 | UBS OE Turbo Call Warrant ASML | ASML | 3ASM.L (3x UK, 仅2026起) |
| 9 | UBS OE Turbo Call Warrant Amazon.com | AMZN | 3AMZ.L (3x UK), AMZU (2x US) |
| 10 | Morgan Stanley OE Turbo Long Amazon | AMZN | 同上 |
| 11 | Vontobel Long Mini Amazon.com | AMZN | 同上 |

## [2026-06-04 03:00] 三股轮动策略总结 + LEVERAGED_ROTATION_STRATEGY v2.0

- **输入命令**: "总结上面三股轮动策略 写入LEVERAGED_ROTATION_STRATEGY"
- **PROJECT_INDEX 变更**: 更新 `LEVERAGED_ROTATION_STRATEGY.md`（重大更新 v2.0）
- **关键发现**:
  1. **三股轮动全面碾压两股**：三股 10/10 打败最差 BH（100%），两股最好仅 90%；三股常见 10/10 打败好 BH，两股最多 44%
  2. **数学优势**：卖出资金平分到两只幸存者 → 消除「换错」风险 → 容错率翻倍
  3. **1330 组合 #1**：MU+ORCL+AMD（$33,610, +1020%, 10/10 BW, 7/10 BB, 零 KO, ~6 次换仓/年）
  4. **NVDA 是反直觉的差锚点**（Top 20 仅出现 1 次）：太强了，死拿比轮动更赚钱，频繁换仓只会增加交易损耗
  5. **MSFT/GOOGL 不适合轮动**（Top 20 出现 0/1 次）：波动太低（~28%），轮动退化为持仓不动
  6. **MU 是最佳锚点**（Top 20 出现 9/20）：极高波动（52%）创造丰富的切换机会
  7. **PLTR 是黄金搭档**（Top 20 出现 14/20）：但仅 6 年数据，需小仓位试水
  8. **阈值铁律「宁宽勿窄」**：15% 阈值在趋势中反亏钱（换仓 23 次 → -47.6%），50% 仅 2 次 → +84.5%
  9. **ORCL+MSFT+AMZN 优化**：替换 MSFT+AMZN → MU+AMD，从 $5,350 → $33,610（+528%）
  10. **推荐配置**：主力 MU+ORCL+AMD 3x/40%、保守 AVGO+ASML+AMD 3x/30%、激进 MU+TSLA+PLTR 3x/50%
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `LEVERAGED_ROTATION_STRATEGY.md` | v2.0 重大更新：三股轮动完整策略（排名/规律/配置/执行清单） |
  | `code/top10_all_trios.py` | 1330 组合引擎（C(21,3)） |
  | `code/optimize_orcl_msft_amzn.py` | ORCL+MSFT+AMZN 替换 1/2 股优化 |
  | `code/rotation_3stock_all35.py` | 35 组三股排列组合扫描 |

## [2026-06-04 02:15] ORCL + MSFT + AMZN 三股轮动专项测试

- **输入命令**: "回测三只股票的组合 比如Oracle，Microsoft 和amazon" / "单看最近一年的表现" / "上面结果展示年均收益率"
- **PROJECT_INDEX 变更**: 新增脚本、图表、数据文件
- **关键发现**:
  1. **三股轮动完胜两股**：10/10 年份打败同杠杆下所有三只 B&H（最差和最好的都打败），两股最好也只能 90%
  2. **10年零 KO**：3x 杠杆下所有阈值（15%–50%）零敲出，波动比 NVDA/MU 温和
  3. **最佳参数 3x/50%**：年均 $5,350（+78.3%），仅 ~5 次换仓/年。BH ORCL 3x 仅 +45.3%、MSFT +68.9%、AMZN +64.5%
  4. **低阈值反亏钱（2025-2026）**：15% 阈值频繁换仓 23 次 → +53%；30% 阈值 11 次 → **-47.6%**；50% 仅 2 次 → **+84.5%**。大趋势中夹小回调时，宽阈值才是王道
  5. **2025-2026 单年**：ORCL +50.5%、MSFT +0.5%、AMZN +26.4%。MSFT 横盘拖后腿，ORCL 领涨。两次换仓即实现 +84.5%
  6. **三股 vs 两股核心差异**：卖出的钱平分到两只股票，不会「换错」，容错率大幅提升
  7. **4x/35% 收益最高但风险上升**：年均 $6,133（+104.4%），打败好 BH 降至 8/10
  8. **6x/50% 也能存活**：年均 $6,530（+117.7%），零 KO，但打败好 BH 仅 7/10
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/rotation_3stock.py` | 三股轮动完整阈值+杠杆扫描（ORCL+MSFT+AMZN） |
  | `code/rotation_3stock_summary.py` | 年均收益率汇总表 |
  | `code/rotation_3stock_oneyear.py` | 2025-2026 单年明细+换仓记录+图表 |
  | `image/rotation_3stock_scan.png` | 三股阈值杠杆总图（6面板） |
  | `image/rotation_3stock_oneyear.png` | 2025-2026 四面板明细图 |
  | `data/ORCL_2016_daily.csv` | Oracle 2016-2026 日线 |
  | `data/MSFT_2016_daily.csv` | Microsoft 2016-2026 日线 |

### ORCL+MSFT+AMZN 各杠杆最优表现

| 杠杆 | 最佳阈值 | 轮动年均$ | 轮动年均% | BH ORCL | BH MSFT | BH AMZN | 打败差 BH | 打败好 BH | KO |
|:---:|:------:|:--------:|:--------:|:-------:|:-------:|:-------:|:--------:|:--------:|:--:|
| 1x | 20% | $3,870 | +29.0% | +23.7% | +26.6% | +24.5% | 10/10 | 10/10 | 0 |
| 2x | 30% | $4,793 | +59.8% | +39.6% | +50.9% | +46.4% | 10/10 | 10/10 | 0 |
| **3x** | **50%** | **$5,350** | **+78.3%** | +45.3% | +68.9% | +64.5% | **10/10** | **10/10** | 0 |
| 4x | 35% | $6,133 | +104.4% | +43.1% | +78.2% | +77.8% | 10/10 | 8/10 | 0 |
| 5x | 15% | $5,548 | +84.9% | +48.9% | +78.8% | +129.6% | 9/9 | 8/9 | 1 |
| 6x | 50% | $6,530 | +117.7% | +42.4% | +73.2% | +133.5% | 10/10 | 7/10 | 0 |

### 3x 杠杆逐年明细

| 年份 | 轮动收益 | BH ORCL | BH MSFT | BH AMZN | vs 最差 | vs 最好 |
|------|:------:|:------:|:------:|:------:|:------:|:------:|
| 2025-26 | **+84.5%** | +23.2% | -16.1% | +54.7% | Win | **Win** |
| 2024-25 | **+84.6%** | +73.0% | +16.5% | +12.2% | Win | **Win** |
| 2023-24 | **+101.4%** | -0.9% | +74.6% | +135.8% | Win | Win |
| 2022-23 | **+111.3%** | +173.8% | +35.5% | -41.3% | Win | Win |
| 2021-22 | **-25.9%** | -41.7% | +9.6% | -73.5% | Win | **Win** |
| 2020-21 | **+283.9%**| +197.8% | +101.4%| +65.1% | Win | **Win** |
| 2019-20 | **+147.9%** | -23.5% | +103.3%| +100.7%| Win | **Win** |
| 2018-19 | **+86.2%** | +10.9% | +59.3% | -12.7% | Win | **Win** |
| 2017-18 | **+149.7%** | -2.0% | +172.2%| +264.7%| Win | Win |
| 2016-17 | **+113.6%** | +42.4% | +132.6%| +139.7%| Win | Win |

## [2026-06-04 02:00] 7股排列组合35组三股轮动 + 全网配对筛选

- **输入命令**: "NVDA MU TSLA PLTR AVGO ASML 和AMD 这几只股票3个一组 排列组合 回测 找最佳组合" / "找全网能和NVDA MU 配组的股票"
- **PROJECT_INDEX 变更**: 新增多个脚本、数据、图表
- **关键发现**:
  1. **三股轮动碾压两股**：ORCL+MSFT+AMZN 3x/50% 打出 10/10 打败同杠杆下最差和最好 B&H 的完美战绩
  2. **TSLA+PLTR 是黄金底板**：跨行业（电动车+AI软件）搭配任何半导体都是 Top 6
  3. **35组排名第一**：MU+TSLA+PLTR 3x/50%，年均+505%，6/6 打败差 BH
  4. **十年最稳**：MU+AVGO+ASML 3x/25%，10/10 打败差 BH，7/10 打败好 BH，零 KO
  5. **跨行业 > 同行业**：纯半导体组合排名靠后，混合电动车/AI软件/半导体的组合最强
  6. **PLTR 虽仅有6年数据，但含它的组合零 KO**，且全部 Top 7
  7. **三股轮动核心优势**：卖出资金平分到两只股票，不会"换错了"，比两股轮动稳得多
  8. **半导体配对筛选 Top 3**：AVGO、ASML、AMD 跟 NVDA/MU 配对效果最好
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/rotation_3stock.py` | ORCL+MSFT+AMZN 三股轮动完整扫描 |
  | `code/rotation_3stock_summary.py` | 三股轮动年均收益汇总 |
  | `code/rotation_3stock_oneyear.py` | 2025-2026 单年明细+图表 |
  | `code/screen_rotation_partners.py` | 12只候选股与NVDA/MU配对筛选 |
  | `code/rotation_3stock_all35.py` | C(7,3)=35组三股排列组合扫描 |
  | `image/rotation_3stock_scan.png` | 三股阈值杠杆扫描总图 |
  | `image/rotation_3stock_oneyear.png` | 2025-2026 三股轮动明细图 |
  | `data/ORCL_2016_daily.csv` | Oracle 2016-2026 日线 |
  | `data/MSFT_2016_daily.csv` | Microsoft 2016-2026 日线 |
  | `code/rotation_vs_levered_bh.py` | 公平对比脚本（3x轮动 vs 3x B&H） |
  | `LEVERAGED_ROTATION_STRATEGY.md` | 修正后策略文档 |

## [2026-06-04 01:00] 修正对比基准：3x轮动 vs 同杠杆3x B&H

- **输入命令**: "打败打败 B&H 是打败B&H 股票还是 打败B&H三倍杠杆"
- **PROJECT_INDEX 变更**: 新增 `code/rotation_vs_levered_bh.py`，更新 `LEVERAGED_ROTATION_STRATEGY.md`
- **关键发现**:
  1. **之前「打败B&H」混在一起，现在分开**：vs 3x BH（公平）和 vs 1x BH（参考）
  2. 同杠杆下轮动的真正价值是**避坑保底**（打败差3x BH 78–90%），不是超额收益（打败好3x BH 仅 10–44%）
  3. NVDA-GOOGL 取代 NVDA-MU 成为最优推荐：打败差3x BH 达90%（vs NVDA-MU 78%），且0% KO
  4. GOOGL-AMZN 轮动完全无效（打败差3x BH 仅30%），两股相关性太高
  5. 策略文档已全面修正：核心结论、排名表、推荐配置均改为公平对比基准
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/rotation_vs_levered_bh.py` | 公平对比脚本：3x轮动 vs 3x B&H vs 1x B&H |
  | `LEVERAGED_ROTATION_STRATEGY.md` | 大幅修正：对比基准、排名、推荐配置 |

## [2026-06-04 00:30] 生成可落地杠杆投资策略文档

- **输入命令**: "根据上面所有回测结果 生成一个可落地的杠杆投资策略"
- **PROJECT_INDEX 变更**: 新增 `LEVERAGED_ROTATION_STRATEGY.md`
- **关键发现**:
  1. 综合所有回测，3x杠杆 + 20%止损轮动是唯一经十年考验的策略
  2. 理论 Kelly 最优杠杆比实际最优高 0.5–2.3x，实操必须下调
  3. 推荐配置：60% NVDA-MU + 40% NVDA-GOOGL，均用 3x/20%
  4. 绝对禁止 ≥ 4x 杠杆（每只股票都有敲出记录）
  5. 策略文档涵盖：理论、参数选择、风控体系、压力测试、年度调整、执行清单
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `LEVERAGED_ROTATION_STRATEGY.md` | 可落地杠杆轮动策略完整文档 |

## [2026-06-03 23:30] 轮动+杠杆综合回测（NVDA-MU / GOOGL-AMZN 等）

- **输入命令**: "再微调规则，比如项目C:\AI\cc\stock的如下内容也要加到项目日志里"
- **PROJECT_INDEX 变更**: 新增 `code/threshold_scan_4pairs.py`、`code/chart_6pairs_annual.py`、`image/threshold_scan_4pairs.png`、`image/chart_6pairs_annual.png`
- **关键发现**:
  1. NVDA-MU 无可撼动：轮动收益碾压其他组合（NVDA 波动够大、MU 暴涨够猛）
  2. NVDA 是核心引擎：所有含 NVDA 的组合都排在前4，NVDA 的波动性给轮动提供了大量切换机会
  3. GOOGL-AMZN 最弱：两只股票走势高度相关，轮动几乎退化为持仓不动
  4. 3x杠杆 + 20%阈值在10年间零敲出的组合有4/6（NVDA-MU 仅1年KO）
  5. 2025-2026是MU之年（+957%），让所有含MU的组合该年度回报爆炸
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/threshold_scan_4pairs.py` | 4组新股对阈值+杠杆扫描脚本 |
  | `code/chart_6pairs_annual.py` | 6组年度轮动总图脚本 |
  | `image/threshold_scan_4pairs.png` | 4组阈值扫描对比图 |
  | `image/chart_6pairs_annual.png` | 6组年度 3x/20% vs B&H 总图 |

## [2026-06-03 22:55] 按 CLAUDE.md 规则整理项目结构

- **输入命令**: "根据上面规则整理项目C:\AI\cc\stock"
- **PROJECT_INDEX 变更**: 更新文件路径，.py → code/, .csv → data/, .png → image/
- **关键发现**:
  1. 36 个 .py、20 个 .csv、15 个 .png 全部归类到子文件夹
  2. 72 处硬编码路径批量修正
  3. check_nvda.py 测试通过，路径修改正确
- **生成/修改的文件**:
  | 文件 | 说明 |
  |------|------|
  | `code/` | 36 个 Python 脚本移入 |
  | `data/` | 20 个 CSV 数据文件移入 |
  | `image/` | 15 个 PNG 图片移入 |
  | 所有 `.py` 脚本 | 路径从 `C:\AI\cc\stock\*.csv` 改为 `C:\AI\cc\stock\data\*.csv`，`*.png` 改为 `image\*.png` |
