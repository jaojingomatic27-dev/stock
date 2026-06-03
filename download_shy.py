# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd

print("Downloading SHY (1-3 Year Treasury ETF)...")
df = yf.download("SHY", start="2002-01-01", interval="1d")
print(f"SHY {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}  {len(df)} rows")
df.to_csv(r"C:\AI\cc\stock\SHY_daily.csv")
print("Saved to SHY_daily.csv")
