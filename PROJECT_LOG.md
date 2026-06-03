# 项目日志 — stock

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
- **关键发现**: 36 个 .py、20 个 .csv、15 个 .png 全部归类到子文件夹；72 处硬编码路径批量修正；check_nvda.py 测试通过
- **生成/修改的文件**:
  - `code/` — 36 个 Python 脚本移入
  - `data/` — 20 个 CSV 数据文件移入
  - `image/` — 15 个 PNG 图片移入
  - 所有脚本中的路径从 `C:\AI\cc\stock\*.csv` 改为 `C:\AI\cc\stock\data\*.csv`，`*.png` 改为 `image\*.png`
