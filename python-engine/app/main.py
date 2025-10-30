from fastapi import FastAPI
from pydantic import BaseModel
import orjson, logging, pandas as pd
from .config import load_config
from .logging_conf import setup_logging
from .features import build_features
from .models import mean_reversion_decision
from .exec_policy import tp_sl_points, side_from_z
from .risk import RiskState, guards_ok, position_size_lots
from .metrics import MetricsSink

cfg = load_config("config/config.yaml")
setup_logging(cfg["logging"]["dir"], cfg["logging"]["level"], cfg["logging"]["json"])
log = logging.getLogger("engine")
metrics = MetricsSink(cfg["logging"]["dir"])

app = FastAPI()

class DecideIn(BaseModel):
    symbol: str
    tick_info: dict    # {"bid": float, "ask": float, "spread_points": int, "slippage_points": int,
                       #  "point_size": float, "tick_value_per_lot": float, "equity_usd": float}
    ticks: list        # list of [ts_ms, bid, ask, vol]
    bars_1m: list      # list of [ts_ms, open, high, low, close, volume]
    state: dict        # RiskState snapshot: {day_pnl_pct, hit_rate_pct, recent_trades, open_positions, symbol_exposure_pct, last_trade_ts_ms}

class DecideOut(BaseModel):
    action: str        # buy|sell|flat
    lots: float
    tp_points: int
    sl_points: int
    expires_ms: int
    reason: str

@app.post("/decide", response_model=DecideOut)
def decide(req: DecideIn):
    sym = req.symbol
    edge_cfg = cfg["edges"]["mean_reversion_spike"]
    # Convert to DataFrames
    ticks_df = pd.DataFrame(req.ticks, columns=["ts","bid","ask","volume"])
    ticks_df["ts"] = pd.to_datetime(ticks_df["ts"], unit="ms")
    ticks_df.set_index("ts", inplace=True)

    bars_df = pd.DataFrame(req.bars_1m, columns=["ts","open","high","low","close","volume"])
    bars_df["ts"] = pd.to_datetime(bars_df["ts"], unit="ms")
    bars_df.set_index("ts", inplace=True)

    feats = build_features(ticks_df, bars_df, edge_cfg)
    dec = mean_reversion_decision(feats, edge_cfg)

    if dec["side"] == "hold":
        metrics.write({"type":"decision","symbol":sym,"side":"hold","score":dec["score"]})
        return DecideOut(action="flat", lots=0, tp_points=0, sl_points=0, expires_ms=0, reason="no_signal")

    # Risk & guards
    state = RiskState(**req.state)
    spread, slippage = req.tick_info["spread_points"], req.tick_info["slippage_points"]
    ok, why = guards_ok(cfg, state, spread, slippage, sym, next_exposure_pct=cfg["execution"]["max_exposure_per_symbol_pct"]/2)
    if not ok:
        metrics.write({"type":"blocked","symbol":sym,"why":why})
        return DecideOut(action="flat", lots=0, tp_points=0, sl_points=0, expires_ms=0, reason=why)

    # Sizing + TP/SL
    atr_points = max(feats["atr"], 0.0001)
    tp_pts, sl_pts = tp_sl_points(atr_points, edge_cfg["tp_mult"], edge_cfg["sl_mult"], req.tick_info["point_size"])
    lots = position_size_lots(
        account_equity=req.tick_info["equity_usd"],
        risk_pct=cfg["risk"]["per_trade_risk_pct"],
        atr_points=atr_points,
        tp_mult=edge_cfg["tp_mult"], sl_mult=edge_cfg["sl_mult"],
        tick_value_per_lot=req.tick_info["tick_value_per_lot"],
        point_size=req.tick_info["point_size"],
        min_lot=cfg["execution"]["min_lot"], volume_step=cfg["execution"]["volume_step"]
    )

    action = "buy" if dec["side"]=="buy" else "sell"
    expires_ms = req.tick_info.get("ts_ms", 0) + edge_cfg["timeout_seconds"]*1000

    out = DecideOut(action=action, lots=float(lots), tp_points=int(tp_pts), sl_points=int(sl_pts), expires_ms=int(expires_ms), reason="mean_reversion_spike")
    metrics.write({"type":"action","symbol":sym, **out.model_dump()})
    return out
