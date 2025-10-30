import time, math, numpy as np, pandas as pd

def rolling_z(x: pd.Series, win: int) -> pd.Series:
    mu = x.rolling(win, min_periods=win).mean()
    sd = x.rolling(win, min_periods=win).std(ddof=0).replace(0, np.nan)
    return (x - mu)/sd

def atr_from_ohlc(df: pd.DataFrame, n=14):
    # df: columns ['open','high','low','close']
    h_l = df['high'] - df['low']
    h_pc = (df['high'] - df['close'].shift()).abs()
    l_pc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([h_l, h_pc, l_pc], axis=1).max(axis=1)
    atr = tr.rolling(n, min_periods=n).mean()
    return atr

def clamp(v, lo, hi): return max(lo, min(hi, v))
def now_ms(): return int(time.time()*1000)
