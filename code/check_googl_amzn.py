import pandas as pd
for t in ['GOOGL','AMZN']:
    df = pd.read_csv(rf'C:\AI\cc\stock\{t}_daily.csv', header=[0,1], index_col=0, parse_dates=True)
    c = df[('Close',t)].dropna()
    print(f'{t}: {c.index[0].date()} ~ {c.index[-1].date()}  ({len(c)}d)  ${c.iloc[0]:.2f} -> ${c.iloc[-1]:.2f}')
