import traceback, pandas as pd, numpy as np

for ticker in ['NVDA', 'MU', 'ORCL']:
    path = rf'C:\AI\cc\stock\{ticker}_daily.csv'
    df = pd.read_csv(path, header=[0,1], index_col=0, parse_dates=True)
    close = df[('Close', ticker)].dropna()
    print(f'{ticker}: type={type(close).__name__}, len={len(close)}')
    try:
        rets = close.pct_change().fillna(0)
        equity = (1 + rets).cumprod() * 10000
        years = len(close) / 252
        final = float(equity.iloc[-1])
        print(f'  Equity final: ${final:,.0f}')

        # Test max_dd calc
        dd = ((equity - equity.cummax()) / equity.cummax() * 100).min()
        print(f'  MaxDD: {float(dd):.1f}%')
    except Exception as e:
        traceback.print_exc()
        print(f'  ERROR: {e}')
