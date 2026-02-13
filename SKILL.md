---
name: hyperclaw
description: Trade on Hyperliquid. Supports 228+ perps, HIP-3 equity/commodity perps (TSLA, GOLD), market scanning, sentiment analysis, and prediction market data. Commands for account status, market data, funding rates, order book, trading, and intelligence gathering.
user-invocable: true
---

# HyperClaw - Hyperliquid Trading Skill

Trade on Hyperliquid via CLI. Covers native crypto perps (BTC, ETH, SOL, etc.), HIP-3 builder-deployed perps (equities, commodities, forex), market scanning, and intelligence tools.

## Setup

Run the setup script once to create a virtual environment and install dependencies:

```bash
bash {baseDir}/scripts/setup.sh
```

Then configure `.env` in the skill root directory with your Hyperliquid API credentials:

```
HL_ACCOUNT_ADDRESS=0x_your_wallet_address
HL_SECRET_KEY=0x_your_api_wallet_private_key
HL_TESTNET=true
```

Get API keys from: https://app.hyperliquid.xyz/API — use a separate API wallet, not your main wallet private key.

Optional for intelligence commands (sentiment, unlocks, devcheck):
```
XAI_API_KEY=xai-...
```

## How to Run Commands

```bash
{baseDir}/scripts/.venv/bin/python {baseDir}/scripts/hyperliquid_tools.py <command> [args]
```

## Command Reference

### Account

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Account balance, positions, PnL (includes HIP-3) | `hyperliquid_tools.py status` |
| `positions` | Detailed position info (leverage, liquidation) | `hyperliquid_tools.py positions` |
| `orders` | Open orders | `hyperliquid_tools.py orders` |

### Market Data

| Command | Description | Example |
|---------|-------------|---------|
| `price [COINS...]` | Current prices (supports HIP-3 dex prefix) | `hyperliquid_tools.py price BTC ETH xyz:TSLA` |
| `funding [COINS...]` | Funding rates (hourly + APR + signal) | `hyperliquid_tools.py funding BTC SOL DOGE` |
| `book COIN` | L2 order book with spread | `hyperliquid_tools.py book SOL` |
| `raw COIN` | Raw JSON data dump for processing | `hyperliquid_tools.py raw BTC` |

### Analysis

| Command | Description | Example |
|---------|-------------|---------|
| `analyze [COINS...]` | Comprehensive market analysis (prices, funding, OI, volume, book depth) | `hyperliquid_tools.py analyze BTC ETH SOL` |
| `scan` | Scan all perps for funding opportunities | `hyperliquid_tools.py scan --top 20 --min-volume 100000` |
| `hip3 [COIN]` | HIP-3 perp data (price, spread, funding) | `hyperliquid_tools.py hip3 TSLA` |
| `hip3` | All HIP-3 dex assets | `hyperliquid_tools.py hip3` |
| `dexes` | List all HIP-3 dexes and their assets | `hyperliquid_tools.py dexes` |
| `history` | Trade history from API | `hyperliquid_tools.py history --limit 20` |

### Trading

| Command | Description | Example |
|---------|-------------|---------|
| `buy COIN SIZE` | Market buy (long) | `hyperliquid_tools.py buy SOL 0.5` |
| `sell COIN SIZE` | Market sell (short) | `hyperliquid_tools.py sell SOL 0.5` |
| `limit-buy COIN SIZE PRICE` | Limit buy order (GTC) | `hyperliquid_tools.py limit-buy SOL 1 120` |
| `limit-sell COIN SIZE PRICE` | Limit sell order (GTC) | `hyperliquid_tools.py limit-sell SOL 1 140` |
| `stop-loss COIN SIZE TRIGGER` | Stop-loss trigger (market, reduce-only) | `hyperliquid_tools.py stop-loss SOL 0.5 115` |
| `take-profit COIN SIZE TRIGGER` | Take-profit trigger (market, reduce-only) | `hyperliquid_tools.py take-profit SOL 0.5 150` |
| `close COIN` | Close entire position (supports HIP-3) | `hyperliquid_tools.py close SOL` |
| `cancel OID` | Cancel specific order | `hyperliquid_tools.py cancel 12345` |
| `cancel-all` | Cancel all open orders | `hyperliquid_tools.py cancel-all` |

### Intelligence (requires XAI_API_KEY)

| Command | Description | Example |
|---------|-------------|---------|
| `sentiment COIN` | Grok web + X/Twitter sentiment analysis | `hyperliquid_tools.py sentiment BTC` |
| `unlocks [COINS...]` | Token unlock schedules (defaults to current positions) | `hyperliquid_tools.py unlocks SOL HYPE` |
| `devcheck COIN` | Developer sentiment and exodus signals | `hyperliquid_tools.py devcheck SOL` |

### Prediction Markets

| Command | Description | Example |
|---------|-------------|---------|
| `polymarket [CATEGORY]` | Polymarket prediction data | `hyperliquid_tools.py polymarket crypto` |

Categories: `crypto`, `btc`, `eth`, `trending`, `macro`

### HIP-3 Trading

HIP-3 assets use a dex prefix: `dex:SYMBOL`

```bash
hyperliquid_tools.py buy xyz:TSLA 1          # Buy TSLA on xyz dex
hyperliquid_tools.py sell vntl:ANTHROPIC 1   # Sell ANTHROPIC on vntl dex
hyperliquid_tools.py close xyz:GOLD          # Close GOLD position
hyperliquid_tools.py funding xyz:TSLA vntl:SPACEX km:US500
```

**Known HIP-3 dexes:** xyz (equities, commodities), vntl (private companies), flx (crypto/commodities), hyna (crypto), km (indices), abcd, cash. Use `dexes` command to discover all available dexes dynamically.

**HIP-3 differences from native perps:**
- Isolated margin only (no cross margin)
- Per-position liquidation prices
- Higher fees (2x normal)
- Thinner order books (wider spreads)
- Max leverage varies by asset (10x for most equities, 20x for commodities/metals)

## Caching Proxy (Recommended)

Each CLI invocation cold-starts the SDK and burns ~40 API weight units just to initialize. With a 1200 weight/min IP limit, agents hit rate limits after ~30 commands. The caching proxy eliminates this.

**Start the proxy before running commands:**

```bash
{baseDir}/scripts/.venv/bin/python {baseDir}/scripts/server.py &
```

Then set `HL_PROXY_URL` so all commands route through it:

```bash
export HL_PROXY_URL=http://localhost:18731
```

Or prefix individual commands:

```bash
HL_PROXY_URL=http://localhost:18731 {baseDir}/scripts/.venv/bin/python {baseDir}/scripts/hyperliquid_tools.py price BTC
```

**Proxy endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Check proxy status and uptime |
| `GET /cache/stats` | Cache hit/miss rates per type |
| `POST /cache/clear` | Clear cache (optional body: `{"type":"..."}` or `{"user":"0x..."}`) |

The proxy caches `/info` responses (metadata 300s, prices 5s, user state 2s) and passes `/exchange` through directly, automatically invalidating user cache on successful trades. Responses include `X-Cache: HIT` or `X-Cache: MISS` headers.

**Proxy env vars:**

| Variable | Default | Description |
|----------|---------|-------------|
| `HL_UPSTREAM_URL` | `https://api.hyperliquid.xyz` | Upstream API |
| `HL_PROXY_PORT` | `18731` | Proxy port |
| `HL_CACHE_WARMUP` | `true` | Pre-warm cache on startup |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HL_ACCOUNT_ADDRESS` | For trading/status | Hyperliquid wallet address |
| `HL_SECRET_KEY` | For trading | API wallet private key |
| `HL_TESTNET` | No | `true` for testnet (default), `false` for mainnet |
| `HL_PROXY_URL` | No | Caching proxy URL (e.g. `http://localhost:18731`) |
| `XAI_API_KEY` | For intelligence | Grok API key for sentiment/unlocks/devcheck |

**Read-only commands** (`price`, `funding`, `book`, `scan`, `hip3`, `dexes`, `raw`, `polymarket`) work without credentials. Trading and account commands require `HL_ACCOUNT_ADDRESS` and `HL_SECRET_KEY`.
