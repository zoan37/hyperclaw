---
name: hyperclaw
description: >-
  Trade perpetual futures on Hyperliquid. Supports 228+ native perps and
  HIP-3 equity/commodity perps (TSLA, GOLD, etc.). Commands for account
  status, market data, funding rates, order book, trading, and market scanning.
user-invocable: true
---

# HyperClaw - Hyperliquid Trading Skill

Trade perpetual futures on Hyperliquid via CLI. Covers native crypto perps (BTC, ETH, SOL, etc.) and HIP-3 builder-deployed perps (equities, commodities, forex).

## Setup

Run the setup script once to create a virtual environment and install dependencies:

```bash
bash <skill-dir>/scripts/setup.sh
```

Then configure `.env` in the skill root directory with your Hyperliquid API credentials:

```
HL_ACCOUNT_ADDRESS=0x_your_wallet_address
HL_API_WALLET_KEY=0x_your_api_wallet_private_key
HL_TESTNET=true
```

Get API keys from: https://app.hyperliquid.xyz/API — use a separate API wallet, not your main wallet private key.

To point to a custom `.env` location, set `HYPERCLAW_ENV=/path/to/.env`.

## How to Run Commands

```bash
<skill-dir>/scripts/.venv/bin/python <skill-dir>/scripts/hl.py <command> [args]
```

## Command Reference

### Account

| Command | Description | Example |
|---------|-------------|---------|
| `status` | Account balance, positions, PnL | `hl.py status` |
| `positions` | Detailed position info (leverage, liquidation) | `hl.py positions` |
| `orders` | Open orders with TP/SL trigger details | `hl.py orders` |
| `user-funding` | Funding payments received/paid (USD) | `hl.py user-funding --days 7` |
| `history` | Trade history from API | `hl.py history --limit 50` |
| `portfolio` | Account value and PnL over time | `hl.py portfolio` |
| `user-fees` | Fee schedule, volume tier, maker/taker rates | `hl.py user-fees` |
| `historical-orders` | Full order history with statuses (filled/canceled/rejected) | `hl.py historical-orders --limit 50` |

### Market Data

| Command | Description | Example |
|---------|-------------|---------|
| `price [COINS...]` | Current prices | `hl.py price BTC ETH SOL` |
| `funding [COINS...]` | Funding rates (hourly + APR) | `hl.py funding BTC SOL DOGE` |
| `book COIN` | L2 order book with spread | `hl.py book SOL` |
| `candles COIN` | Historical OHLCV price candles | `hl.py candles BTC --interval 1d --count 30` |
| `funding-history COIN` | Funding rate history with trend | `hl.py funding-history SOL --days 7` |
| `scan` | Scan all perps (funding, 24h change, OI, oracle divergence, OI caps) | `hl.py scan --top 30 --min-volume 1000000` |
| `analyze [COINS...]` | Comprehensive market data dump | `hl.py analyze BTC ETH SOL` |
| `predicted-fundings [COINS]` | Predicted next funding (HL, Binance, Bybit) | `hl.py predicted-fundings BTC ETH` |
| `trades COIN` | Recent trades with buy/sell flow | `hl.py trades BTC` |
| `max-trade-size COIN` | Available margin to trade per direction | `hl.py max-trade-size SOL` |
| `whale ADDR` | View any wallet's positions | `hl.py whale 0x1234...` |
| `raw COIN` | Raw JSON data for processing | `hl.py raw BTC` |

### HIP-3 (Equity/Commodity Perps)

| Command | Description | Example |
|---------|-------------|---------|
| `hip3 [COIN]` | HIP-3 perp data (price, spread, funding) | `hl.py hip3 TSLA` |
| `hip3` | All xyz dex assets | `hl.py hip3` |
| `dexes` | List all HIP-3 dexes and their assets | `hl.py dexes` |

### Trading

| Command | Description | Example |
|---------|-------------|---------|
| `buy COIN SIZE` | Market buy (long) | `hl.py buy SOL 0.5` |
| `sell COIN SIZE` | Market sell (short) | `hl.py sell SOL 0.5` |
| `limit-buy COIN SIZE PRICE` | Limit buy order | `hl.py limit-buy SOL 1 120` |
| `limit-sell COIN SIZE PRICE` | Limit sell order | `hl.py limit-sell SOL 1 140` |
| `stop-loss COIN SIZE TRIGGER` | Stop-loss trigger (market) | `hl.py stop-loss SOL 0.5 115` |
| `take-profit COIN SIZE TRIGGER` | Take-profit trigger (market) | `hl.py take-profit SOL 0.5 150` |
| `close COIN` | Close entire position | `hl.py close SOL` |
| `cancel OID` | Cancel specific order | `hl.py cancel 12345` |
| `cancel-all` | Cancel all open orders | `hl.py cancel-all` |
| `leverage COIN LEV` | Set leverage (1 to max) | `hl.py leverage xyz:TSLA 3` |
| `margin COIN AMOUNT` | Add/remove margin on isolated position | `hl.py margin xyz:TSLA 10` |
| `modify-order OID` | Modify existing order price/size | `hl.py modify-order 123 --price 130` |
| `schedule-cancel [MIN]` | Dead man's switch - auto-cancel orders | `hl.py schedule-cancel 60` |

### HIP-3 Trading

HIP-3 assets use a dex prefix: `dex:SYMBOL`

```bash
hl.py buy xyz:TSLA 1          # Buy TSLA on xyz dex
hl.py sell vntl:ANTHROPIC 1   # Sell ANTHROPIC on vntl dex
hl.py close xyz:GOLD          # Close GOLD position
hl.py funding xyz:TSLA vntl:SPACEX km:US500
```

**Known HIP-3 dexes:** xyz (equities, commodities), vntl (private companies), flx (crypto/commodities), hyna (crypto), km (indices), abcd, cash. Use `dexes` command to discover all available dexes dynamically.

**HIP-3 differences from native perps:**
- Isolated margin only (no cross margin)
- Per-position liquidation prices
- Higher fees (2x normal)
- Thinner order books (wider spreads)
- Max leverage varies by asset (10x for most equities, 20x for commodities/metals). **The displayed leverage is the maximum, not fixed.** Use `leverage` command to set lower leverage before entering a position (e.g., `hl.py leverage xyz:TSLA 3` for 3x instead of 10x). Lower leverage = more margin = further liquidation price.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HL_ACCOUNT_ADDRESS` | For trading/status | Hyperliquid wallet address |
| `HL_API_WALLET_KEY` | For trading | API wallet private key |
| `HL_TESTNET` | No | `true` for testnet (default), `false` for mainnet |
| `HYPERCLAW_ENV` | No | Custom path to `.env` file |

**Read-only commands** (`price`, `funding`, `book`, `scan`, `hip3`, `dexes`) work without credentials. Trading and account commands require `HL_ACCOUNT_ADDRESS` and `HL_API_WALLET_KEY`.
