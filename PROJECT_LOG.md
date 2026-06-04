# 项目日志 — stock

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
