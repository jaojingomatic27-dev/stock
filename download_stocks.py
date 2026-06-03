import yfinance as yf
import os

output_dir = r"C:\AI\cc"
os.makedirs(output_dir, exist_ok=True)

# 1. 日线数据: NVDA, MU, SMCI, AMAT 从 2010-01-01 至今
print("正在下载日线数据: NVDA, MU, SMCI, AMAT ...")
df_daily = yf.download(
    ["NVDA", "MU", "SMCI", "AMAT"],
    start="2010-01-01",
    interval="1d"
)
daily_path = os.path.join(output_dir, "stocks_daily.csv")
df_daily.to_csv(daily_path)
print(f"日线数据已保存至: {daily_path}")
print(f"日线数据形状: {df_daily.shape}")
print(df_daily.tail(5))

print("\n" + "=" * 60 + "\n")

# 2. 5分钟数据: MU 近60天
print("正在下载5分钟数据: MU (近60天) ...")
df_5min = yf.download(
    "MU",
    period="60d",
    interval="5m"
)
min5_path = os.path.join(output_dir, "MU_5min.csv")
df_5min.to_csv(min5_path)
print(f"5分钟数据已保存至: {min5_path}")
print(f"5分钟数据形状: {df_5min.shape}")
print(df_5min.tail(5))
