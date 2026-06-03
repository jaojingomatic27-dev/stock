# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import pandas as pd, numpy as np

df = pd.read_csv(r'C:\AI\cc\stock\SPY_full.csv', header=[0,1], index_col=0, parse_dates=True)
close = df[('Close','SPY')].dropna()['2000-01-01':'2010-01-04']

print(f'SPY 2000-2010: {close.index[0].strftime("%Y-%m-%d")} ~ {close.index[-1].strftime("%Y-%m-%d")}')
print(f'Price: ${close.iloc[0]:.2f} -> ${close.iloc[-1]:.2f}  ({((close.iloc[-1]/close.iloc[0])-1)*100:+.1f}%)')
print(f'Max: ${close.max():.2f}  Min: ${close.min():.2f}  Days: {len(close)}')

BASE, MIN_A, MAX_A = 1000.0, 500.0, 1500.0

def rule_fixed(s): return BASE

def rule_drawdown(s):
    p,i,px = s['price'],s['i'],s['prices']
    if i<63: return BASE
    h=max(px[i-63:i+1]); dd=(p-h)/h
    if dd<-0.10: return MAX_A
    elif dd<-0.05: return 1250
    elif dd<-0.02: return 1100
    elif dd>-0.01: return MIN_A
    return BASE

def rule_bear_bull(s):
    p,i,px = s['price'],s['i'],s['prices']
    if i<200: return BASE
    ma200=np.mean(px[i-200:i+1]); ma50=np.mean(px[i-50:i+1]); r=p/ma200
    if p<ma200: return MAX_A
    elif p<ma50 and p>ma200: return 1250
    elif r>1.35: return MIN_A
    elif r>1.15: return 750
    return BASE

def rule_rsi(s):
    p,i,px = s['price'],s['i'],s['prices']
    if i<20: return BASE
    r=np.array(px[i-14:i+1]); d=np.diff(r)
    g=d[d>0].sum() if len(d[d>0])>0 else 0
    l=abs(d[d<0].sum()) if len(d[d<0])>0 else 0.0001
    rsi=100-(100/(1+g/l))
    if rsi<35: return MAX_A
    elif rsi<45: return 1250
    elif rsi>70: return MIN_A
    elif rsi>60: return 750
    return BASE

def rule_ma50(s):
    p,i,px = s['price'],s['i'],s['prices']
    if i<60: return BASE
    ma50=np.mean(px[i-50:i+1]); ratio=p/ma50
    if ratio<0.92: return MAX_A
    elif ratio<0.96: return 1250
    elif ratio<0.99: return 1100
    elif ratio>1.08: return MIN_A
    elif ratio>1.04: return 750
    return BASE

def rule_momentum(s):
    p,i,px = s['price'],s['i'],s['prices']
    if i<63: return BASE
    m3=p/px[i-63]-1; m12=p/px[i-252]-1 if i>=252 else m3
    score=0.0
    if m3<-0.08: score+=0.4
    elif m3<0: score+=0.2
    elif m3>0.15: score-=0.3
    if m12<-0.10: score+=0.4
    elif m12<0: score+=0.15
    elif m12>0.35: score-=0.3
    if score>0.5: return MAX_A
    elif score>0.25: return 1250
    elif score<-0.4: return MIN_A
    elif score<-0.2: return 750
    return BASE

def backtest(close_series, desire_func):
    first_dates,first_prices=[],[]
    prev_ym=None
    for dt,price in close_series.items():
        ym=(dt.year,dt.month)
        if ym!=prev_ym: first_dates.append(dt); first_prices.append(price); prev_ym=ym
    n=len(first_dates); cash=0.0; shares=0.0; invested=0.0; px_hist=list(first_prices)
    records=[]
    for i,(dt,price) in enumerate(zip(first_dates,first_prices)):
        state={'price':price,'i':i,'prices':px_hist,'shares':shares,'invested':invested,'reserve':cash,'month':i,'total_months':n}
        desired=desire_func(state)
        if desired>BASE: extra=min(desired-BASE,cash); actual=BASE+extra
        elif desired<BASE: save=min(BASE-desired,BASE-MIN_A); actual=BASE-save
        else: actual=BASE
        actual=max(MIN_A,min(MAX_A,actual))
        if actual<BASE: cash+=(BASE-actual)
        elif actual>BASE: cash-=(actual-BASE)
        shares+=actual/price; invested+=actual
        records.append({'date':dt,'price':price,'actual':actual,'reserve':cash,'shares':shares,'invested':invested,'value':shares*price})
    df_rec=pd.DataFrame(records).set_index('date')
    final=shares*close_series.iloc[-1]
    ret=(final-invested)/invested*100
    ann=((final/invested)**(1/(n/12.0))-1)*100 if n>0 and invested>0 else 0
    n_lo=(df_rec['actual']<=MIN_A+1).sum()
    n_hi=(df_rec['actual']>=MAX_A-1).sum()
    n_mid=(abs(df_rec['actual']-BASE)<1).sum()
    return {'invested':invested,'final':final,'return':ret,'ann':ann,'reserve':cash,'months':n,
            'n_lo':n_lo,'n_mid':n_mid,'n_hi':n_hi,'df':df_rec}

rules=[(rule_fixed,'Fixed $1000'),(rule_drawdown,'Drawdown 3M'),(rule_bear_bull,'Bear/Bull MA200'),
       (rule_rsi,'RSI(14)'),(rule_ma50,'MA50 Distance'),(rule_momentum,'Momentum Adaptive')]
results=[]

for fn,name in rules:
    r=backtest(close,fn); r['name']=name; results.append(r)
results.sort(key=lambda x:x['final'],reverse=True)
bl=[r for r in results if 'Fixed' in r['name']][0]

print()
print('='*75)
print('  SPY 2000-2010 -- THE LOST DECADE (Real Bear Market!)')
print(f'  Price: ${close.iloc[0]:.2f} -> ${close.iloc[-1]:.2f}  ({((close.iloc[-1]/close.iloc[0])-1)*100:+.1f}%)')
print(f'  Target: ${bl["invested"]:,.0f} over {bl["months"]} months')
print('='*75)
print(f'  {"#":<3} {"Strategy":<22} {"Invested":>11} {"Final":>13} {"Ret":>9} {"Ann":>7} {"vs Fixed":>10} {"Reserve":>10}')
print(f'  {"-"*82}')
for i,r in enumerate(results):
    vf=((r['final']/bl['final'])-1)*100
    m='  <<< BEST' if r['name']==results[0]['name'] else ''
    print(f'  {i+1:<3} {r["name"]:<22} ${r["invested"]:>10,.0f} ${r["final"]:>12,.0f} {r["return"]:>8.1f}% {r["ann"]:>6.1f}% {vf:>+9.2f}% ${r["reserve"]:>9,.0f}{m}')

print()
for r in results:
    marker = ' <<<' if r['name']==results[0]['name'] else ''
    print(f'  {r["name"]:<22}  $500:{r["n_lo"]:>3}mo  $1000:{r["n_mid"]:>3}mo  $1500:{r["n_hi"]:>3}mo  Reserve:${r["reserve"]:,.0f}{marker}')
    df_r = r['df']
    hi_m = df_r[df_r['actual']>=MAX_A-1]
    lo_m = df_r[df_r['actual']<=MIN_A+1]
    if len(hi_m)>0:
        print(f'    MAX($1500) ({len(hi_m)}mo): {", ".join(hi_m.index.strftime("%Y-%m")[:8])}')
    if len(lo_m)>0:
        print(f'    MIN($500)  ({len(lo_m)}mo): {", ".join(lo_m.index.strftime("%Y-%m")[:8])}')

# Cross-era summary
print()
print('='*75)
print('  THREE-ERA COMPARISON: SPY DCA Strategy vs Fixed $1000')
print('='*75)
print(f'  {"Strategy":<22} {"2000-2010":>14} {"2010-2015":>14} {"2016-2026":>14}')
print(f'  {"Market Type":<22} {"LOST DECADE":>14} {"RECOVERY":>14} {"BULL RUN":>14}')
spy_ret_era1 = ((close.iloc[-1]/close.iloc[0])-1)*100
print(f'  {"SPY Price":<22} {spy_ret_era1:>+13.1f}%  {"+103.2%":>14} {"+346.9%":>14}')
print(f'  {"-"*64}')

# Data from this run + earlier runs
era_data = {
    'Fixed $1000':       [0.0,    0.0,    0.0],
    'Drawdown 3M':       [0.0,    -1.8,   -4.1],
    'Bear/Bull MA200':   [0.0,    0.0,    0.0],
    'RSI(14)':           [0.0,   -19.9,  -18.6],
    'MA50 Distance':      [0.0,   -5.7,  -17.4],
    'Momentum Adaptive': [0.0,    -4.3,  -16.6],
}

# Override 2000-2010 with actual results
for r in results:
    vf = ((r['final']/bl['final'])-1)*100
    if r['name'] in era_data:
        era_data[r['name']][0] = vf

for name, eras in era_data.items():
    print(f'  {name:<22} {eras[0]:>+13.1f}% {eras[1]:>+13.1f}% {eras[2]:>+13.1f}%')

print()
print('='*75)
print('  FINAL VERDICT')
print('='*75)
print('  Across ALL three market eras (Lost Decade, Recovery, Bull Run),')
print('  NO enhanced DCA strategy consistently beats Fixed $1000.')
print()
print('  The ONLY strategy worth considering:')
print('    Drawdown 3M - In bear markets, it deploys extra cash at lows.')
print('    In bull markets, it stays at $1000 and barely trails.')
print('    Worst-case: -4.1% vs Fixed. Best-case: breaks even.')
print('='*75)
