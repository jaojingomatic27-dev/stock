# 项目日志 — stock

## [2026-06-03 22:55] 按 CLAUDE.md 规则整理项目结构

- **输入命令**: "根据上面规则整理项目C:\AI\cc\stock"
- **PROJECT_INDEX 变更**: 更新文件路径，.py → code/, .csv → data/, .png → image/
- **关键发现**: 36 个 .py、20 个 .csv、15 个 .png 全部归类到子文件夹；72 处硬编码路径批量修正；check_nvda.py 测试通过
- **生成/修改的文件**:
  - `code/` — 36 个 Python 脚本移入
  - `data/` — 20 个 CSV 数据文件移入
  - `image/` — 15 个 PNG 图片移入
  - 所有脚本中的路径从 `C:\AI\cc\stock\*.csv` 改为 `C:\AI\cc\stock\data\*.csv`，`*.png` 改为 `image\*.png`
