# -*- coding: utf-8 -*-
import yfinance as yf
import os

output_dir = r"C:\AI\cc\stock"
os.makedirs(output_dir, exist_ok=True)

# SPY = S&P 500 ETF (best for backtesting, has real prices)
# ^GSPC = S&P 500 index (may have issues with yfinance)
tickers = ["SPY", "^GSPC"]

for ticker in tickers:
    print(f"Downloading {ticker} ...")
    try:
        df = yf.download(ticker, start="2010-01-01", interval="1d")
        fname = ticker.replace("^", "").replace(" ", "_")
        path = os.path.join(output_dir, f"{fname}_daily.csv")
        df.to_csv(path)
        print(f"  Saved: {path}")
        print(f"  Shape: {df.shape}")
        print(f"  Range: {df.index[0]} ~ {df.index[-1]}")
        if isinstance(df.columns, pd.MultiIndex):
            last = df.iloc[-1][("Close", ticker)]
        else:
            last = df["Close"].iloc[-1]
        print(f"  Last close: ${last:.2f}")
        print()
    except Exception as e:
        print(f"  FAILED: {e}")
        print()
