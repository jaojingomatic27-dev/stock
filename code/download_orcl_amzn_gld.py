# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import os

output_dir = r"C:\AI\cc\stock"
os.makedirs(output_dir, exist_ok=True)

for ticker in ["ORCL", "AMZN", "GLD"]:
    print(f"Downloading {ticker} ...")
    df = yf.download(ticker, start="2010-01-01", interval="1d")
    path = os.path.join(output_dir, f"{ticker}_daily.csv")
    df.to_csv(path)
    last = df[("Close", ticker)].iloc[-1] if isinstance(df.columns, pd.MultiIndex) else df["Close"].iloc[-1]
    print(f"  Saved: {path}")
    print(f"  Shape: {df.shape}  |  {df.index[0]} ~ {df.index[-1]}")
    print(f"  Last close: ${last:.2f}")
    print()
