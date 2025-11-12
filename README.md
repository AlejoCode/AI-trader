# AI Trader Micro-Scalper

A production-ready AI trading agent for MetaTrader 5 that executes high-frequency micro-scalping strategies. The system ingests real-time tick data and optional news feeds, builds microstructure features, generates trading signals, and places orders via an MT5 Expert Advisor (EA). It emphasizes risk control and capital preservation while aiming for positive expectancy.

## Overview

This project provides an end‑to‑end framework for building an automated trader that runs as an MT5 EA with a Python decision engine. The EA handles tick events and order execution, while the Python service computes features, applies trading models, enforces risk limits, and returns trade instructions.

Key goals:

- **Capital preservation:** strict per‑trade and daily loss caps, circuit breakers, and position limits.
- **Micro‑scalping edges:** exploit mean‑reversion on short‑term price spikes and other micro‑alpha signals.
- **Observability:** structured JSON logging, metrics sink, and optional Streamlit dashboard for PnL and risk metrics.
- **Extensibility:** add new edges (e.g., momentum, spread‑arb), external data adapters, and models with minimal changes.

## Architecture

- **MT5 Expert Advisor (`mt5-ea/ScalperEA.mq5`):**
  - Listens to ticks via `OnTick`.
  - Collects recent ticks and 1‑minute bars and sends them to the Python service via HTTP `WebRequest`.
  - Receives trade decisions (action, lot size, TP/SL) and executes trades respecting min lot, freeze level, and spread.
  - Supports paper mode for dry runs.
- **Python Engine (`python-engine/app`):**
  - Built with FastAPI and Pydantic for fast request handling.
  - Loads configuration from `config/config.yaml` (symbols, risk limits, edges, news settings, etc.).
  - Builds microstructure features (z‑scores of returns, spread, ATR) from incoming tick/bar data.
  - Implements a rule‑based mean‑reversion edge to decide when to buy/sell.
  - Applies risk gates (daily loss, max positions, spread/slippage guards) and sizes positions based on account equity and ATR.
  - Returns structured decisions to the EA and logs actions for metrics.
- **Configuration (`config/config.yaml`):** centralizes all parameters such as broker info, risk caps, sessions, edges, news blackout windows, logging paths, and alert hooks.

## Installation

1. Clone this repository on your VPS:

   ```bash
   git clone https://github.com/AlejoCode/AI-trader.git
   cd AI-trader
   ```

2. Install Python dependencies (Python ≥ 3.10):

   ```bash
   pip install -r python-engine/requirements.txt
   ```

3. In MetaTrader 5:

   - Add `http://127.0.0.1:8000` to *Tools → Options → Expert Advisors → Allow WebRequest for listed URL*.
   - Open `mt5-ea/ScalperEA.mq5` in MetaEditor and compile it.
   - Attach the compiled EA to each chart you wish to trade (e.g., BTCUSD, ETHUSD, XAUUSD, NAS100).

4. Start the Python decision engine:

   ```bash
   cd python-engine
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

5. Ensure that `config/config.yaml` reflects your broker’s symbol names, min lot sizes, and risk preferences.

## Usage

- **Dry run:** set `execution.mode: paper` in `config/config.yaml` and `PAPER_MODE=true` in the EA inputs. The EA will log decisions without placing real orders.
- **Live trading:** after validating performance, set `execution.mode: live` and `PAPER_MODE=false`. The EA will trade using the smallest lot size permitted and adhere to all risk rules.
- **Dashboard (optional):** run the Streamlit app to visualize decisions and basic metrics:

  ```bash
  streamlit run dashboard/streamlit_app.py
  ```

## Configuration

All runtime parameters live in `config/config.yaml`. You can adjust:

- **Broker and account settings:** name, hedging vs. netting, leverage, commission model.
- **Symbols and sessions:** which instruments to trade and which time windows to avoid (e.g., low‑liquidity rollovers).
- **Risk limits:** per‑trade risk percentage, daily max loss, max open positions, max exposure per symbol.
- **Edges:** enable/disable strategies (e.g., mean‑reversion on spikes) and tune z‑score thresholds, ATR multipliers, and timeouts.
- **News filters:** define blackout periods around high‑impact events (CPI, FOMC, NFP) when no trades will be placed.
- **Logging and alerts:** set log directories, rotation, and optionally configure Slack/Telegram hooks.

## Roadmap

- Add additional micro‑scalping edges such as breakout momentum with trailing stops.
- Integrate external news and sentiment feeds (e.g., economic calendar, crypto fear & greed index) with graceful fallbacks.
- Implement a walk‑forward/backtesting framework to evaluate edges on historical tick data.
- Provide a richer dashboard with PnL curves, hit rate, drawdown, and feature drift monitoring.

## Disclaimer

This project is provided for educational purposes. Trading CFDs, cryptocurrencies, and other leveraged instruments carries significant risk. Use the paper mode to validate strategies before committing real capital, and always adhere to the risk parameters defined in your configuration. The authors take no responsibility for financial losses incurred while using this software.
