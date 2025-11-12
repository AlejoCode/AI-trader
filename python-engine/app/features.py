import pandas as pd
from .utils import rolling_z, atr_from_ohlc

def build_features(ticks: pd.DataFrame, bars_1m: pd.DataFrame, cfg_edge: dict):
    """
    ticks: columns ['ts','bid','ask','volume']
    bars_1m: columns ['open','high','low','close']
    """
    mid = (ticks['bid'] + ticks['ask']) / 2.0
    ret_1s = mid.pct_change()
    # approximate horizon seconds by number of ticks times 4 tick per second
    N = max(5, int(cfg_edge.get("horizon_seconds",5) * 4))
    z = rolling_z(ret_1s.fillna(0), N)
    last_z = float(z.iloc[-1]) if len(z) else 0.0

    spread = (ticks['ask'] - ticks['bid']).tail(20).mean()
    micro_vol = mid.pct_change().tail(50).std()

    atr = atr_from_ohlc(bars_1m[['open','high','low','close']], n=cfg_edge.get("atr_len",14)).iloc[-1]
    return {
        "last_z": last_z,
        "spread": float(spread if pd.notna(spread) else 0),
        "micro_vol": float(micro_vol if pd.notna(micro_vol) else 0),
        "atr": float(atr if pd.notna(atr) else 0),
        "mid": float(mid.iloc[-1]) if len(mid) else 0.0
    }
