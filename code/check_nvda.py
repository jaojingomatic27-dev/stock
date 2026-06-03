import pandas as pd

df = pd.read_csv(r"C:\AI\cc\stock\data\NVDA_daily.csv", header=[0,1], index_col=0, parse_dates=True)
close = df[("Close", "NVDA")].dropna()
print(f"NVDA first 10 days:")
for i in range(min(10, len(close))):
    dt = close.index[i].strftime("%Y-%m-%d")
    print(f"  {dt}  ${close.iloc[i]:.2f}")
print(f"NVDA min: ${close.min():.2f} at {close.idxmin().strftime('%Y-%m-%d')}")
print(f"NVDA max: ${close.max():.2f} at {close.idxmax().strftime('%Y-%m-%d')}")
print(f"NVDA last: ${close.iloc[-1]:.2f}")
print(f"Days below 172.21: {(close < 172.21).sum()} / {len(close)}")
