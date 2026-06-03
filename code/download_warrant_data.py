# -*- coding: utf-8 -*-
"""Download 1-year daily data for warrant underlyings."""
import yfinance as yf
import pandas as pd

for ticker in ["NVDA", "MU", "ORCL"]:
    print(f"Downloading {ticker}...")
    df = yf.download(ticker, start="2025-06-01", interval="1d")
    path = rf"C:\AI\cc\stock\{ticker}_daily.csv"
    df.to_csv(path)

    # Read back to get stats (handles both MultiIndex and flat columns)
    df2 = pd.read_csv(path, header=[0, 1], index_col=0, parse_dates=True)
    close = df2[("Close", ticker)].dropna()

    print(f"  Saved: {path}")
    print(f"  Rows: {len(close)}")
    print(f"  Range: {close.index[0].strftime('%Y-%m-%d')} to {close.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Last Close: ${float(close.iloc[-1]):.2f}")
    print()

print("Download complete.")
