# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import os

output_dir = r"C:\AI\cc\stock"
os.makedirs(output_dir, exist_ok=True)

for ticker in ["GOOGL", "GOOG"]:
    print(f"Downloading {ticker} ...")
    df = yf.download(ticker, start="2004-08-19", interval="1d")
    path = os.path.join(output_dir, f"{ticker}_daily.csv")
    df.to_csv(path)

    # Get last close price
    if isinstance(df.columns, pd.MultiIndex):
        last_close = df[("Close", ticker)].iloc[-1]
    else:
        last_close = df["Close"].iloc[-1]

    print(f"  Saved: {path}")
    print(f"  Shape: {df.shape}")
    print(f"  Range: {df.index[0]} ~ {df.index[-1]}")
    print(f"  Last close: ${last_close:.2f}")
    print()
