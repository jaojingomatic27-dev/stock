import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

# 读取数据
df = pd.read_csv(r"C:\AI\cc\stock\data\NVDA_daily.csv", header=[0, 1], index_col=0, parse_dates=True)

# 提取 NVDA 的 Close 价格
close = df[("Close", "NVDA")].dropna()

# 计算均线
ma5 = close.rolling(window=5).mean()
ma10 = close.rolling(window=10).mean()
ma20 = close.rolling(window=20).mean()

# 绘图
fig, ax = plt.subplots(figsize=(16, 9))

ax.plot(close.index, close, label="NVDA Close", color="black", linewidth=0.8, alpha=0.7)
ax.plot(ma5.index, ma5, label="MA 5", color="blue", linewidth=1.0)
ax.plot(ma10.index, ma10, label="MA 10", color="orange", linewidth=1.0)
ax.plot(ma20.index, ma20, label="MA 20", color="red", linewidth=1.0)

# 格式化日期轴
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax.xaxis.set_major_locator(mdates.YearLocator())
plt.xticks(rotation=45)

ax.set_title("NVDA Daily Close with 5/10/20 MA", fontsize=16)
ax.set_ylabel("Price (USD)", fontsize=12)
ax.legend(loc="upper left")
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_path = r"C:\AI\cc\stock\image\NVDA_chart.png"
plt.savefig(output_path, dpi=150)
print(f"图已保存至: {output_path}")
plt.close()
