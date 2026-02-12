#!/usr/bin/env python3
"""
HyperClaw - Hyperliquid Trading CLI for AI Agents

Usage:
    python hl.py status              # Account balance, positions, PnL
    python hl.py positions           # Detailed position info
    python hl.py price BTC           # Current price
    python hl.py funding BTC         # Funding rate
    python hl.py book BTC            # Order book
    python hl.py buy BTC 0.01        # Market buy
    python hl.py sell BTC 0.01       # Market sell
    python hl.py limit-buy BTC 0.01 85000   # Limit buy
    python hl.py limit-sell BTC 0.01 95000  # Limit sell
    python hl.py close BTC           # Close position
    python hl.py orders              # List open orders
    python hl.py cancel ORDER_ID     # Cancel order
    python hl.py cancel-all          # Cancel all orders
    python hl.py candles BTC          # Historical OHLCV candles
    python hl.py scan                # Scan all perps for opportunities
    python hl.py hip3                # HIP-3 equity perp data
    python hl.py dexes               # List all HIP-3 dexes
    python hl.py history             # Trade history
    python hl.py leverage SOL 5      # Set leverage
    python hl.py margin xyz:TSLA 10  # Add margin to isolated position
    python hl.py modify-order 123 --price 130  # Modify order
    python hl.py schedule-cancel 60  # Auto-cancel orders in 60min
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional
from pathlib import Path

# Load environment variables from .env file
# Priority: HYPERCLAW_ENV env var > cwd/.env > script dir/.env
from dotenv import load_dotenv

_env_path = os.environ.get('HYPERCLAW_ENV')
if _env_path and os.path.isfile(_env_path):
    load_dotenv(_env_path)
elif os.path.isfile('.env'):
    load_dotenv('.env')
else:
    _script_dir = Path(__file__).resolve().parent.parent
    _fallback_env = _script_dir / '.env'
    if _fallback_env.is_file():
        load_dotenv(str(_fallback_env))

# Hyperliquid SDK imports
try:
    from hyperliquid.info import Info
    from hyperliquid.exchange import Exchange
    from hyperliquid.utils import constants
    from eth_account import Account
except ImportError:
    print("Error: hyperliquid-python-sdk not installed.")
    print("Run: pip install hyperliquid-python-sdk")
    sys.exit(1)

# ANSI colors
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def get_config(require_credentials: bool = True):
    """Get Hyperliquid configuration from environment."""
    account_address = os.getenv('HL_ACCOUNT_ADDRESS')
    secret_key = os.getenv('HL_API_WALLET_KEY')
    use_testnet = os.getenv('HL_TESTNET', 'true').lower() == 'true'

    if require_credentials and (not account_address or not secret_key):
        print(f"{Colors.RED}Error: Hyperliquid credentials not configured.{Colors.END}")
        print(f"\nAdd to your .env file:")
        print(f"  HL_ACCOUNT_ADDRESS=0x...  # Your wallet address")
        print(f"  HL_API_WALLET_KEY=0x...   # API wallet private key")
        print(f"  HL_TESTNET=true           # Optional: use testnet")
        sys.exit(1)

    api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL

    return {
        'account_address': account_address or '',
        'secret_key': secret_key or '',
        'api_url': api_url,
        'is_testnet': use_testnet
    }


def get_all_dex_names(api_url: str) -> list:
    """Fetch all available HIP-3 dex names from the API."""
    try:
        basic_info = Info(api_url, skip_ws=True)
        all_dexes = basic_info.perp_dexs()
        dex_names = ['']  # Native perps
        for dex in all_dexes:
            if dex is not None and dex.get('name'):
                dex_names.append(dex.get('name'))
        return dex_names
    except Exception:
        return ['', 'xyz', 'vntl', 'flx', 'hyna', 'km', 'abcd', 'cash']


def setup_info(skip_ws: bool = True, require_credentials: bool = False, include_hip3: bool = True) -> tuple:
    """Setup Info client for read-only operations."""
    config = get_config(require_credentials=require_credentials)
    perp_dexs = get_all_dex_names(config['api_url']) if include_hip3 else None
    info = Info(config['api_url'], skip_ws=skip_ws, perp_dexs=perp_dexs)
    return info, config


def setup_exchange(skip_ws: bool = True, include_hip3: bool = True) -> tuple:
    """Setup Exchange client for trading operations."""
    config = get_config()
    wallet = Account.from_key(config['secret_key'])
    perp_dexs = get_all_dex_names(config['api_url']) if include_hip3 else None
    exchange = Exchange(wallet, config['api_url'], account_address=config['account_address'], perp_dexs=perp_dexs)
    info = Info(config['api_url'], skip_ws=skip_ws, perp_dexs=perp_dexs)
    return exchange, info, config


def format_price(price: float) -> str:
    """Format price for display."""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:.2f}"
    else:
        return f"${price:.6f}"


def format_pnl(pnl: float) -> str:
    """Format PnL with color."""
    if pnl >= 0:
        return f"{Colors.GREEN}+${pnl:,.2f}{Colors.END}"
    else:
        return f"{Colors.RED}-${abs(pnl):,.2f}{Colors.END}"


# ============================================================================
# READ-ONLY COMMANDS
# ============================================================================

def cmd_status(args):
    """Show account status: balance, equity, positions summary."""
    info, config = setup_info(require_credentials=True, include_hip3=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}HYPERLIQUID ACCOUNT STATUS{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")
    print("=" * 60)

    try:
        user_state = info.user_state(config['account_address'])
        xyz_state = info.user_state(config['account_address'], dex='xyz')

        margin_summary = user_state.get('marginSummary', {})
        account_value = float(margin_summary.get('accountValue', 0))
        total_margin = float(margin_summary.get('totalMarginUsed', 0))
        total_pnl = float(margin_summary.get('totalRawUsd', 0))
        withdrawable = float(user_state.get('withdrawable', 0))

        print(f"\n{Colors.BOLD}Account Summary:{Colors.END}")
        print(f"  Account Value:  {format_price(account_value)}")
        print(f"  Margin Used:    {format_price(total_margin)}")
        print(f"  Withdrawable:   {format_price(withdrawable)}")

        positions = user_state.get('assetPositions', [])
        xyz_positions = xyz_state.get('assetPositions', [])
        all_positions = positions + xyz_positions
        open_positions = [p for p in all_positions if float(p['position']['szi']) != 0]

        if open_positions:
            print(f"\n{Colors.BOLD}Open Positions ({len(open_positions)}):{Colors.END}")
            print(f"  {'Asset':<12} {'Side':<6} {'Size':>12} {'Entry':>12} {'Mark':>12} {'PnL':>15}")
            print("  " + "-" * 70)

            total_unrealized = 0
            for pos in open_positions:
                p = pos['position']
                coin = p['coin']
                size = float(p['szi'])
                entry_px = float(p['entryPx'])
                unrealized_pnl = float(p['unrealizedPnl'])
                mark_px = float(p.get('markPx', entry_px))
                side = "LONG" if size > 0 else "SHORT"
                side_color = Colors.GREEN if size > 0 else Colors.RED
                total_unrealized += unrealized_pnl
                print(f"  {coin:<12} {side_color}{side:<6}{Colors.END} {abs(size):>12.4f} {format_price(entry_px):>12} {format_price(mark_px):>12} {format_pnl(unrealized_pnl):>15}")

            print("  " + "-" * 70)
            print(f"  {'Total Unrealized PnL:':<52} {format_pnl(total_unrealized):>15}")
        else:
            print(f"\n{Colors.DIM}No open positions{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching account status: {e}{Colors.END}")


def cmd_positions(args):
    """Show detailed position information."""
    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}POSITION DETAILS{Colors.END}")
    print("=" * 60)

    try:
        user_state = info.user_state(config['account_address'])
        positions = user_state.get('assetPositions', [])
        open_positions = [p for p in positions if float(p['position']['szi']) != 0]

        if not open_positions:
            print(f"\n{Colors.DIM}No open positions{Colors.END}")
            return

        for pos in open_positions:
            p = pos['position']
            coin = p['coin']
            size = float(p['szi'])
            entry_px = float(p['entryPx'])
            unrealized_pnl = float(p['unrealizedPnl'])
            leverage = p.get('leverage', {})
            liq_px = float(p.get('liquidationPx', 0)) if p.get('liquidationPx') else None

            side = "LONG" if size > 0 else "SHORT"
            side_color = Colors.GREEN if size > 0 else Colors.RED

            print(f"\n{Colors.BOLD}{coin}{Colors.END}")
            print(f"  Side:           {side_color}{side}{Colors.END}")
            print(f"  Size:           {abs(size):.4f}")
            print(f"  Entry Price:    {format_price(entry_px)}")
            print(f"  Unrealized PnL: {format_pnl(unrealized_pnl)}")
            if leverage:
                lev_type = leverage.get('type', 'unknown')
                lev_val = leverage.get('value', 0)
                print(f"  Leverage:       {lev_val}x ({lev_type})")
            if liq_px:
                print(f"  Liquidation:    {format_price(liq_px)}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching positions: {e}{Colors.END}")


def cmd_price(args):
    """Get current price for an asset."""
    info, config = setup_info()
    coins = args.coins if args.coins else ['BTC', 'ETH', 'SOL']

    try:
        mids_cache = {}

        def get_price(coin):
            if ':' in coin:
                dex = coin.split(':')[0]
                if dex not in mids_cache:
                    mids_cache[dex] = info.all_mids(dex=dex)
                return mids_cache[dex].get(coin)
            else:
                if '' not in mids_cache:
                    mids_cache[''] = info.all_mids()
                return mids_cache[''].get(coin)

        print(f"\n{Colors.BOLD}Current Prices:{Colors.END}")
        for coin in coins:
            price = get_price(coin)
            if price:
                print(f"  {coin:<20} {format_price(float(price))}")
            else:
                print(f"  {coin:<20} {Colors.DIM}Not found{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching prices: {e}{Colors.END}")


def cmd_funding(args):
    """Get funding rates for assets."""
    info, config = setup_info()
    coins = args.coins if args.coins else ['BTC', 'ETH', 'SOL', 'DOGE', 'HYPE']

    try:
        meta = info.meta_and_asset_ctxs()
        universe = meta[0]['universe']
        asset_ctxs = meta[1]
        name_to_idx = {asset['name']: i for i, asset in enumerate(universe)}

        print(f"\n{Colors.BOLD}Funding Rates:{Colors.END}")
        print(f"  {'Asset':<12} {'Hourly':>12} {'APR':>12} {'Signal':<20}")
        print("  " + "-" * 55)

        for coin in coins:
            if coin in name_to_idx:
                idx = name_to_idx[coin]
                ctx = asset_ctxs[idx]
                funding = float(ctx.get('funding', 0))
                funding_pct = funding * 100
                apr = funding * 24 * 365 * 100

                if funding < -0.0001:
                    signal = f"{Colors.GREEN}Shorts paying (bullish){Colors.END}"
                elif funding > 0.0005:
                    signal = f"{Colors.RED}Longs crowded (bearish){Colors.END}"
                else:
                    signal = f"{Colors.YELLOW}Neutral{Colors.END}"

                print(f"  {coin:<12} {funding_pct:>11.4f}% {apr:>11.1f}% {signal}")
            else:
                # Try HIP-3 perps
                try:
                    all_dexes = info.perp_dexs()
                    hip3_dexes = [d.get('name') for d in all_dexes if d is not None and d.get('name')]
                except Exception:
                    hip3_dexes = ['xyz', 'vntl', 'flx', 'hyna', 'km', 'abcd', 'cash']
                found = False

                if ':' in coin:
                    coins_to_try = [coin]
                else:
                    coins_to_try = [f"{dex}:{coin}" for dex in hip3_dexes]

                import requests
                for try_coin in coins_to_try:
                    try:
                        resp = requests.post(
                            config['api_url'] + "/info",
                            json={"type": "fundingHistory", "coin": try_coin, "startTime": 0},
                            timeout=10
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data:
                                latest = data[-1]
                                funding = float(latest.get('fundingRate', 0))
                                funding_pct = funding * 100
                                apr = funding * 24 * 365 * 100
                                signal = f"{Colors.GREEN}Shorts paying{Colors.END}" if funding < 0 else f"{Colors.YELLOW}Longs paying{Colors.END}"
                                print(f"  {try_coin:<16} {funding_pct:>11.4f}% {apr:>11.1f}% {signal}")
                                found = True
                                break
                    except Exception:
                        pass

                if not found:
                    print(f"  {coin:<12} {Colors.DIM}Not found{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching funding rates: {e}{Colors.END}")


def cmd_book(args):
    """Get order book for an asset."""
    info, config = setup_info()
    coin = args.coin

    try:
        book = info.l2_snapshot(coin)

        print(f"\n{Colors.BOLD}{coin} Order Book:{Colors.END}")
        print(f"  {'Bids':<30} {'Asks':<30}")
        print("  " + "-" * 60)

        bids = book.get('levels', [[]])[0][:5]
        asks = book.get('levels', [[], []])[1][:5]

        for i in range(max(len(bids), len(asks))):
            bid_str = ""
            ask_str = ""
            if i < len(bids):
                bid_str = f"{Colors.GREEN}{format_price(float(bids[i]['px']))} x {bids[i]['sz']}{Colors.END}"
            if i < len(asks):
                ask_str = f"{Colors.RED}{format_price(float(asks[i]['px']))} x {asks[i]['sz']}{Colors.END}"
            print(f"  {bid_str:<40} {ask_str:<40}")

        if bids and asks:
            mid = (float(bids[0]['px']) + float(asks[0]['px'])) / 2
            spread = float(asks[0]['px']) - float(bids[0]['px'])
            spread_pct = (spread / mid) * 100
            print(f"\n  Mid: {format_price(mid)} | Spread: {format_price(spread)} ({spread_pct:.3f}%)")

    except Exception as e:
        print(f"{Colors.RED}Error fetching order book: {e}{Colors.END}")


def cmd_orders(args):
    """List open orders with trigger/TP/SL details."""
    info, config = setup_info(require_credentials=True)

    try:
        open_orders = info.frontend_open_orders(config['account_address'])

        print(f"\n{Colors.BOLD}Open Orders:{Colors.END}")

        if not open_orders:
            print(f"  {Colors.DIM}No open orders{Colors.END}")
            return

        print(f"  {'OID':<12} {'Asset':<12} {'Side':<6} {'Size':>10} {'Price':>12} {'Type':<12} {'Details'}")
        print("  " + "-" * 85)

        for order in open_orders:
            oid = order.get('oid', 'N/A')
            coin = order.get('coin', 'N/A')
            side = "BUY" if order.get('side') == 'B' else "SELL"
            side_color = Colors.GREEN if side == "BUY" else Colors.RED
            sz = order.get('sz', '0')
            px = float(order.get('limitPx', 0))
            order_type = order.get('orderType', 'Limit')
            is_tpsl = order.get('isPositionTpsl', False)
            reduce_only = order.get('reduceOnly', False)
            trigger_px = order.get('triggerPx', '')
            trigger_cond = order.get('triggerCondition', '')

            details = []
            if is_tpsl:
                details.append("TP/SL")
            if reduce_only:
                details.append("reduce-only")
            if trigger_px:
                details.append(f"trigger:{trigger_px}")
            if trigger_cond:
                details.append(trigger_cond)
            detail_str = " | ".join(details) if details else ""

            print(f"  {oid:<12} {coin:<12} {side_color}{side:<6}{Colors.END} {sz:>10} {format_price(px):>12} {order_type:<12} {detail_str}")

            # Show child orders (attached TP/SL)
            children = order.get('children', [])
            for child in children:
                c_oid = child.get('oid', '')
                c_side = "BUY" if child.get('side') == 'B' else "SELL"
                c_sz = child.get('sz', '')
                c_px = float(child.get('limitPx', 0))
                c_type = child.get('orderType', '')
                c_trigger = child.get('triggerPx', '')
                print(f"  {'  └─':<12} {'':<12} {c_side:<6} {c_sz:>10} {format_price(c_px):>12} {c_type:<12} trigger:{c_trigger}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching orders: {e}{Colors.END}")


# ============================================================================
# TRADING COMMANDS
# ============================================================================

def cmd_buy(args):
    """Market buy."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size

    print(f"\n{Colors.BOLD}Market Buy: {size} {coin}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            print(f"Current price: {format_price(current_price)}")
            print(f"Estimated cost: {format_price(current_price * size)}")

        result = exchange.market_open(coin, True, size, None, 0.01)

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'filled' in status:
                    filled = status['filled']
                    print(f"\n{Colors.GREEN}Order filled!{Colors.END}")
                    print(f"  Size: {filled.get('totalSz')}")
                    print(f"  Avg Price: {format_price(float(filled.get('avgPx', 0)))}")
                    print(f"  OID: {filled.get('oid')}")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error executing buy: {e}{Colors.END}")


def cmd_sell(args):
    """Market sell."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size

    print(f"\n{Colors.BOLD}Market Sell: {size} {coin}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            print(f"Current price: {format_price(current_price)}")

        result = exchange.market_open(coin, False, size, None, 0.01)

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'filled' in status:
                    filled = status['filled']
                    print(f"\n{Colors.GREEN}Order filled!{Colors.END}")
                    print(f"  Size: {filled.get('totalSz')}")
                    print(f"  Avg Price: {format_price(float(filled.get('avgPx', 0)))}")
                    print(f"  OID: {filled.get('oid')}")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error executing sell: {e}{Colors.END}")


def cmd_limit_buy(args):
    """Place limit buy order."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    price = args.price

    print(f"\n{Colors.BOLD}Limit Buy: {size} {coin} @ {format_price(price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from limit)")

        result = exchange.order(coin, True, size, price, {"limit": {"tif": "Gtc"}})

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'resting' in status:
                    print(f"\n{Colors.GREEN}Order placed!{Colors.END}")
                    print(f"  OID: {status['resting'].get('oid')}")
                elif 'filled' in status:
                    filled = status['filled']
                    print(f"\n{Colors.GREEN}Order filled immediately!{Colors.END}")
                    print(f"  Size: {filled.get('totalSz')}")
                    print(f"  Avg Price: {format_price(float(filled.get('avgPx', 0)))}")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error placing limit buy: {e}{Colors.END}")


def cmd_limit_sell(args):
    """Place limit sell order."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    price = args.price

    print(f"\n{Colors.BOLD}Limit Sell: {size} {coin} @ {format_price(price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from limit)")

        result = exchange.order(coin, False, size, price, {"limit": {"tif": "Gtc"}})

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'resting' in status:
                    print(f"\n{Colors.GREEN}Order placed!{Colors.END}")
                    print(f"  OID: {status['resting'].get('oid')}")
                elif 'filled' in status:
                    filled = status['filled']
                    print(f"\n{Colors.GREEN}Order filled immediately!{Colors.END}")
                    print(f"  Size: {filled.get('totalSz')}")
                    print(f"  Avg Price: {format_price(float(filled.get('avgPx', 0)))}")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error placing limit sell: {e}{Colors.END}")


def cmd_stop_loss(args):
    """Place a stop-loss trigger order."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    trigger_price = args.trigger_price

    print(f"\n{Colors.BOLD}Stop-Loss: {size} {coin} @ trigger {format_price(trigger_price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((trigger_price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from trigger)")

        is_buy = trigger_price > current_price if coin in all_mids else not args.buy

        order_type = {
            "trigger": {
                "triggerPx": trigger_price,
                "isMarket": True,
                "tpsl": "sl"
            }
        }

        result = exchange.order(coin, is_buy, size, trigger_price, order_type, reduce_only=True)

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'resting' in status:
                    side = "BUY (close short)" if is_buy else "SELL (close long)"
                    print(f"\n{Colors.GREEN}Stop-loss placed!{Colors.END}")
                    print(f"  Side: {side}")
                    print(f"  Trigger: {format_price(trigger_price)}")
                    print(f"  Size: {size}")
                    print(f"  OID: {status['resting'].get('oid')}")
                    print(f"  Type: Market order when triggered")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error placing stop-loss: {e}{Colors.END}")


def cmd_take_profit(args):
    """Place a take-profit trigger order."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    trigger_price = args.trigger_price

    print(f"\n{Colors.BOLD}Take-Profit: {size} {coin} @ trigger {format_price(trigger_price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((trigger_price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from trigger)")

        is_buy = trigger_price < current_price if coin in all_mids else args.buy

        order_type = {
            "trigger": {
                "triggerPx": trigger_price,
                "isMarket": True,
                "tpsl": "tp"
            }
        }

        result = exchange.order(coin, is_buy, size, trigger_price, order_type, reduce_only=True)

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'resting' in status:
                    side = "BUY (close short)" if is_buy else "SELL (close long)"
                    print(f"\n{Colors.GREEN}Take-profit placed!{Colors.END}")
                    print(f"  Side: {side}")
                    print(f"  Trigger: {format_price(trigger_price)}")
                    print(f"  Size: {size}")
                    print(f"  OID: {status['resting'].get('oid')}")
                    print(f"  Type: Market order when triggered")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Order failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error placing take-profit: {e}{Colors.END}")


def cmd_close(args):
    """Close entire position for an asset."""
    exchange, info, config = setup_exchange()
    coin = args.coin

    print(f"\n{Colors.BOLD}Closing {coin} position{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        dex = None
        if ':' in coin:
            dex = coin.split(':')[0]

        if dex:
            user_state = info.user_state(config['account_address'], dex=dex)
        else:
            user_state = info.user_state(config['account_address'])
        positions = user_state.get('assetPositions', [])

        position = None
        for pos in positions:
            if pos['position']['coin'] == coin:
                position = pos['position']
                break

        if not position or float(position['szi']) == 0:
            print(f"{Colors.YELLOW}No open position for {coin}{Colors.END}")
            return

        size = float(position['szi'])
        entry_px = float(position['entryPx'])
        unrealized_pnl = float(position['unrealizedPnl'])

        print(f"Current position: {abs(size):.4f} {'LONG' if size > 0 else 'SHORT'}")
        print(f"Entry: {format_price(entry_px)}")
        print(f"Unrealized PnL: {format_pnl(unrealized_pnl)}")

        result = exchange.market_close(coin)

        if result.get('status') == 'ok':
            statuses = result.get('response', {}).get('data', {}).get('statuses', [])
            for status in statuses:
                if 'filled' in status:
                    filled = status['filled']
                    print(f"\n{Colors.GREEN}Position closed!{Colors.END}")
                    print(f"  Size: {filled.get('totalSz')}")
                    print(f"  Avg Price: {format_price(float(filled.get('avgPx', 0)))}")
                elif 'error' in status:
                    print(f"\n{Colors.RED}Error: {status['error']}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Close failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error closing position: {e}{Colors.END}")


def cmd_cancel(args):
    """Cancel a specific order."""
    exchange, info, config = setup_exchange()
    oid = args.oid

    try:
        open_orders = info.open_orders(config['account_address'])

        order = None
        for o in open_orders:
            if str(o.get('oid')) == str(oid):
                order = o
                break

        if not order:
            print(f"{Colors.YELLOW}Order {oid} not found in open orders{Colors.END}")
            return

        coin = order.get('coin')
        print(f"\n{Colors.BOLD}Canceling order {oid} ({coin}){Colors.END}")

        result = exchange.cancel(coin, oid)

        if result.get('status') == 'ok':
            print(f"{Colors.GREEN}Order canceled!{Colors.END}")
        else:
            print(f"{Colors.RED}Cancel failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error canceling order: {e}{Colors.END}")


def cmd_funding_history(args):
    """Get historical funding rates for an asset."""
    info, config = setup_info()
    coin = args.coin
    days = args.days

    print(f"\n{Colors.BOLD}{coin} Funding History (last {days} days){Colors.END}")
    print("=" * 70)

    try:
        import time as _time
        end_time = int(_time.time() * 1000)
        start_time = end_time - (days * 86400 * 1000)

        history = info.funding_history(coin, start_time, end_time)

        if not history:
            print(f"{Colors.DIM}No funding history available{Colors.END}")
            return

        print(f"  {'Time':<18} {'Rate':>12} {'APR':>12} {'Premium':>12}")
        print("  " + "-" * 55)

        # Show last N entries (funding is every 8h on HL, so ~3/day)
        limit = min(len(history), days * 3)
        recent = history[-limit:]

        rates = []
        for entry in recent:
            ts = entry.get('time', 0)
            dt = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
            rate = float(entry.get('fundingRate', 0))
            premium = float(entry.get('premium', 0))
            apr = rate * 24 * 365 * 100
            rate_pct = rate * 100
            rates.append(rate)

            rate_color = Colors.GREEN if rate < 0 else Colors.RED if rate > 0.0001 else Colors.YELLOW
            print(f"  {dt:<18} {rate_color}{rate_pct:>11.4f}%{Colors.END} {apr:>11.1f}% {premium*100:>11.4f}%")

        # Summary
        if rates:
            avg_rate = sum(rates) / len(rates)
            avg_apr = avg_rate * 24 * 365 * 100
            min_rate = min(rates)
            max_rate = max(rates)
            min_apr = min_rate * 24 * 365 * 100
            max_apr = max_rate * 24 * 365 * 100

            # Trend: compare first half avg to second half avg
            mid = len(rates) // 2
            if mid > 0:
                first_half_avg = sum(rates[:mid]) / mid
                second_half_avg = sum(rates[mid:]) / (len(rates) - mid)
                if second_half_avg < first_half_avg - 0.00001:
                    trend = f"{Colors.GREEN}trending more negative (shorts increasing){Colors.END}"
                elif second_half_avg > first_half_avg + 0.00001:
                    trend = f"{Colors.RED}trending more positive (longs increasing){Colors.END}"
                else:
                    trend = f"{Colors.YELLOW}stable{Colors.END}"
            else:
                trend = "insufficient data"

            print(f"\n  Avg: {avg_apr:+.1f}% APR | Min: {min_apr:+.1f}% | Max: {max_apr:+.1f}%")
            print(f"  Trend: {trend}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching funding history: {e}{Colors.END}")


def cmd_portfolio(args):
    """Show account portfolio performance over time."""
    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}PORTFOLIO PERFORMANCE{Colors.END}")
    print("=" * 60)

    try:
        portfolio = info.portfolio(config['account_address'])

        if not portfolio:
            print(f"{Colors.DIM}No portfolio data available{Colors.END}")
            return

        # Portfolio returns data across timeframes
        for period_key, period_data in portfolio.items():
            if not isinstance(period_data, dict):
                continue

            label = period_key.replace('_', ' ').title()
            account_values = period_data.get('accountValueHistory', [])
            pnl_history = period_data.get('pnlHistory', [])
            vlm = period_data.get('vlm', 0)

            if account_values:
                print(f"\n{Colors.BOLD}{label}:{Colors.END}")

                # Show first and last values
                if len(account_values) >= 2:
                    first_val = float(account_values[0][1]) if isinstance(account_values[0], list) else float(account_values[0].get('accountValue', 0))
                    last_val = float(account_values[-1][1]) if isinstance(account_values[-1], list) else float(account_values[-1].get('accountValue', 0))
                    change = last_val - first_val
                    change_pct = (change / first_val * 100) if first_val > 0 else 0

                    print(f"  Account Value: {format_price(first_val)} → {format_price(last_val)} ({Colors.GREEN if change >= 0 else Colors.RED}{change_pct:+.2f}%{Colors.END})")

                if pnl_history and len(pnl_history) >= 2:
                    first_pnl = float(pnl_history[0][1]) if isinstance(pnl_history[0], list) else 0
                    last_pnl = float(pnl_history[-1][1]) if isinstance(pnl_history[-1], list) else 0
                    print(f"  Cumulative PnL: {format_pnl(last_pnl)}")

                if vlm:
                    print(f"  Volume: ${float(vlm):,.0f}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching portfolio: {e}{Colors.END}")


def cmd_candles(args):
    """Get historical OHLCV candles for an asset."""
    info, config = setup_info()
    coin = args.coin
    interval = args.interval
    count = args.count

    print(f"\n{Colors.BOLD}{coin} Candles ({interval}){Colors.END}")
    print("=" * 80)

    try:
        import time as _time
        end_time = int(_time.time() * 1000)
        # Estimate start time based on interval and count
        interval_ms = {
            '1m': 60000, '5m': 300000, '15m': 900000, '1h': 3600000,
            '4h': 14400000, '1d': 86400000,
        }
        ms = interval_ms.get(interval, 3600000)
        start_time = end_time - (ms * count)

        candles = info.candles_snapshot(coin, interval, start_time, end_time)

        if not candles:
            print(f"{Colors.DIM}No candle data available{Colors.END}")
            return

        # Show most recent candles
        recent = candles[-count:]

        print(f"  {'Time':<18} {'Open':>12} {'High':>12} {'Low':>12} {'Close':>12} {'Volume':>14} {'Change':>8}")
        print("  " + "-" * 90)

        for c in recent:
            ts = datetime.fromtimestamp(c['t'] / 1000).strftime('%Y-%m-%d %H:%M')
            o = float(c['o'])
            h = float(c['h'])
            l = float(c['l'])
            close = float(c['c'])
            vol = float(c['v'])
            change = ((close - o) / o) * 100 if o > 0 else 0
            change_color = Colors.GREEN if change >= 0 else Colors.RED

            print(f"  {ts:<18} {format_price(o):>12} {format_price(h):>12} {format_price(l):>12} {format_price(close):>12} ${vol:>13,.0f} {change_color}{change:>+7.2f}%{Colors.END}")

        # Summary
        if len(recent) >= 2:
            first_open = float(recent[0]['o'])
            last_close = float(recent[-1]['c'])
            total_change = ((last_close - first_open) / first_open) * 100 if first_open > 0 else 0
            high = max(float(c['h']) for c in recent)
            low = min(float(c['l']) for c in recent)
            total_vol = sum(float(c['v']) for c in recent)
            change_color = Colors.GREEN if total_change >= 0 else Colors.RED

            print(f"\n  Period: {format_price(first_open)} → {format_price(last_close)} ({change_color}{total_change:+.2f}%{Colors.END})")
            print(f"  Range: {format_price(low)} - {format_price(high)} | Total Volume: ${total_vol:,.0f}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching candles: {e}{Colors.END}")


def cmd_leverage(args):
    """Set leverage for an asset."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    leverage = args.leverage

    print(f"\n{Colors.BOLD}Set Leverage: {coin} → {leverage}x{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        # HIP-3 assets are always isolated margin
        is_cross = not (':' in coin)

        # Check max leverage from metadata
        dex = coin.split(':')[0] if ':' in coin else None
        try:
            meta = info.meta(dex=dex) if dex else info.meta()
            universe = meta.get('universe', [])
            for asset in universe:
                if asset['name'] == coin:
                    max_lev = asset.get('maxLeverage', 0)
                    margin_mode = asset.get('marginMode', '')
                    if max_lev and leverage > max_lev:
                        print(f"{Colors.RED}Error: {coin} max leverage is {max_lev}x{Colors.END}")
                        return
                    if margin_mode in ('strictIsolated', 'noCross'):
                        is_cross = False
                    print(f"  Max leverage: {max_lev}x | Mode: {'cross' if is_cross else 'isolated'}")
                    break
        except Exception:
            pass

        result = exchange.update_leverage(leverage, coin, is_cross=is_cross)

        if result.get('status') == 'ok':
            mode = "cross" if is_cross else "isolated"
            print(f"\n{Colors.GREEN}Leverage set to {leverage}x ({mode})!{Colors.END}")
        else:
            print(f"\n{Colors.RED}Failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error setting leverage: {e}{Colors.END}")


def cmd_margin(args):
    """Add or remove margin from an isolated position."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    amount = args.amount

    action = "Adding" if amount > 0 else "Removing"
    print(f"\n{Colors.BOLD}{action} ${abs(amount):.2f} margin on {coin}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        result = exchange.update_isolated_margin(amount, coin)

        if result.get('status') == 'ok':
            print(f"\n{Colors.GREEN}Margin updated! {action} ${abs(amount):.2f} on {coin}{Colors.END}")
        else:
            print(f"\n{Colors.RED}Failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error updating margin: {e}{Colors.END}")


def cmd_modify_order(args):
    """Modify an existing order's price and/or size."""
    exchange, info, config = setup_exchange()
    oid = int(args.oid)
    new_price = args.price
    new_size = args.size

    print(f"\n{Colors.BOLD}Modify Order {oid}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        # Find the existing order to get its details
        open_orders = info.open_orders(config['account_address'])

        order = None
        for o in open_orders:
            if o.get('oid') == oid:
                order = o
                break

        if not order:
            print(f"{Colors.YELLOW}Order {oid} not found in open orders{Colors.END}")
            return

        coin = order.get('coin')
        is_buy = order.get('side') == 'B'
        current_sz = float(order.get('sz', 0))
        current_px = float(order.get('limitPx', 0))

        sz = new_size if new_size is not None else current_sz
        px = new_price if new_price is not None else current_px

        print(f"  Asset: {coin}")
        print(f"  Side: {'BUY' if is_buy else 'SELL'}")
        print(f"  Size: {current_sz} → {sz}")
        print(f"  Price: {format_price(current_px)} → {format_price(px)}")

        result = exchange.modify_order(oid, coin, is_buy, sz, px, {"limit": {"tif": "Gtc"}})

        if result.get('status') == 'ok':
            print(f"\n{Colors.GREEN}Order modified!{Colors.END}")
        else:
            print(f"\n{Colors.RED}Failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error modifying order: {e}{Colors.END}")


def cmd_schedule_cancel(args):
    """Schedule auto-cancel of all orders (dead man's switch)."""
    exchange, info, config = setup_exchange()

    if args.clear:
        print(f"\n{Colors.BOLD}Clearing scheduled cancel{Colors.END}")
        try:
            result = exchange.schedule_cancel(None)
            if result.get('status') == 'ok':
                print(f"{Colors.GREEN}Scheduled cancel cleared!{Colors.END}")
            else:
                print(f"{Colors.RED}Failed: {result}{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
        return

    minutes = args.minutes

    print(f"\n{Colors.BOLD}Schedule Cancel: all orders in {minutes} minutes{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        import time as _time
        cancel_time = int(_time.time() * 1000) + (minutes * 60 * 1000)
        cancel_dt = datetime.fromtimestamp(cancel_time / 1000).strftime('%Y-%m-%d %H:%M:%S')

        result = exchange.schedule_cancel(cancel_time)

        if result.get('status') == 'ok':
            print(f"\n{Colors.GREEN}Scheduled! All orders will be canceled at {cancel_dt}{Colors.END}")
            print(f"{Colors.DIM}Max 10 triggers per day. Use --clear to unset.{Colors.END}")
        else:
            print(f"\n{Colors.RED}Failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error scheduling cancel: {e}{Colors.END}")


def cmd_cancel_all(args):
    """Cancel all open orders."""
    exchange, info, config = setup_exchange()

    print(f"\n{Colors.BOLD}Canceling all open orders{Colors.END}")

    try:
        open_orders = info.open_orders(config['account_address'])

        if not open_orders:
            print(f"{Colors.DIM}No open orders to cancel{Colors.END}")
            return

        print(f"Found {len(open_orders)} open orders")

        for order in open_orders:
            coin = order.get('coin')
            oid = order.get('oid')
            try:
                result = exchange.cancel(coin, oid)
                if result.get('status') == 'ok':
                    print(f"  {Colors.GREEN}Canceled {coin} order {oid}{Colors.END}")
                else:
                    print(f"  {Colors.RED}Failed to cancel {coin} order {oid}{Colors.END}")
            except Exception as e:
                print(f"  {Colors.RED}Error canceling {coin} order {oid}: {e}{Colors.END}")

        print(f"\n{Colors.GREEN}Done!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error canceling orders: {e}{Colors.END}")


# ============================================================================
# DATA COMMANDS
# ============================================================================

def cmd_predicted_fundings(args):
    """Get predicted next funding rates across venues."""
    info, config = setup_info()
    import requests as req

    coins = args.coins if args.coins else None

    print(f"\n{Colors.BOLD}{Colors.CYAN}PREDICTED FUNDING RATES{Colors.END}")
    print(f"Cross-venue: Hyperliquid, Binance, Bybit")
    print("=" * 90)

    try:
        resp = req.post(config['api_url'] + "/info", json={"type": "predictedFundings"}, timeout=10)
        if resp.status_code != 200:
            print(f"{Colors.RED}API error: {resp.status_code}{Colors.END}")
            return

        data = resp.json()

        print(f"\n  {'Asset':<12} {'HL Pred':>12} {'HL APR':>10} {'Binance':>12} {'Bybit':>12} {'HL vs Bin':>10}")
        print("  " + "-" * 70)

        for item in data:
            name = item[0] if isinstance(item, list) else item
            venues = item[1] if isinstance(item, list) else []

            if coins and name not in coins:
                continue

            hl_rate = bin_rate = bybit_rate = None
            for venue_name, venue_data in venues:
                rate = float(venue_data.get('fundingRate', 0))
                interval = venue_data.get('fundingIntervalHours', 1)
                # Normalize to hourly
                hourly = rate / interval if interval > 1 else rate
                if 'Hl' in venue_name:
                    hl_rate = hourly
                elif 'Bin' in venue_name:
                    bin_rate = hourly
                elif 'Bybit' in venue_name:
                    bybit_rate = hourly

            if hl_rate is None:
                continue

            hl_apr = hl_rate * 24 * 365 * 100
            hl_str = f"{hl_rate*100:>11.4f}%"
            apr_str = f"{hl_apr:>9.1f}%"
            bin_str = f"{bin_rate*100:>11.4f}%" if bin_rate is not None else f"{'N/A':>12}"
            bybit_str = f"{bybit_rate*100:>11.4f}%" if bybit_rate is not None else f"{'N/A':>12}"

            # Divergence between HL and Binance
            div_str = ""
            if hl_rate is not None and bin_rate is not None:
                div = (hl_rate - bin_rate) * 100
                div_color = Colors.GREEN if div < -0.001 else Colors.RED if div > 0.001 else Colors.YELLOW
                div_str = f"{div_color}{div:>+9.4f}%{Colors.END}"

            funding_color = Colors.GREEN if hl_apr < -20 else Colors.RED if hl_apr > 20 else Colors.YELLOW
            print(f"  {name:<12} {funding_color}{hl_str}{Colors.END} {apr_str} {bin_str} {bybit_str} {div_str}")

        if not coins:
            print(f"\n{Colors.DIM}Showing all assets. Use: predicted-fundings BTC ETH SOL to filter.{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching predicted fundings: {e}{Colors.END}")


def cmd_trades(args):
    """Get recent trades for an asset."""
    info, config = setup_info()
    coin = args.coin
    import requests as req

    print(f"\n{Colors.BOLD}{coin} Recent Trades{Colors.END}")
    print("=" * 80)

    try:
        resp = req.post(
            config['api_url'] + "/info",
            json={"type": "recentTrades", "coin": coin},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"{Colors.RED}API error: {resp.status_code}{Colors.END}")
            return

        trades = resp.json()

        if not trades:
            print(f"{Colors.DIM}No recent trades{Colors.END}")
            return

        print(f"\n  {'Time':<20} {'Side':<6} {'Price':>14} {'Size':>14} {'Value':>14}")
        print("  " + "-" * 70)

        for t in trades:
            ts = datetime.fromtimestamp(t['time'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            side = "BUY" if t['side'] == 'B' else "SELL"
            side_color = Colors.GREEN if side == "BUY" else Colors.RED
            px = float(t['px'])
            sz = float(t['sz'])
            value = px * sz

            print(f"  {ts:<20} {side_color}{side:<6}{Colors.END} {format_price(px):>14} {sz:>14.6f} ${value:>13,.2f}")

        # Summary
        buys = [t for t in trades if t['side'] == 'B']
        sells = [t for t in trades if t['side'] == 'A']
        buy_vol = sum(float(t['sz']) * float(t['px']) for t in buys)
        sell_vol = sum(float(t['sz']) * float(t['px']) for t in sells)
        total_vol = buy_vol + sell_vol

        print(f"\n  Trades: {len(trades)} | Buys: {len(buys)} | Sells: {len(sells)}")
        print(f"  Buy vol: ${buy_vol:,.2f} | Sell vol: ${sell_vol:,.2f} | Ratio: {buy_vol/total_vol*100:.0f}/{sell_vol/total_vol*100:.0f}" if total_vol > 0 else "")

    except Exception as e:
        print(f"{Colors.RED}Error fetching trades: {e}{Colors.END}")


def cmd_max_trade_size(args):
    """Get maximum tradeable size for an asset."""
    info, config = setup_info(require_credentials=True)
    coin = args.coin
    import requests as req

    print(f"\n{Colors.BOLD}Max Trade Size: {coin}{Colors.END}")

    try:
        resp = req.post(
            config['api_url'] + "/info",
            json={"type": "activeAssetData", "user": config['account_address'], "coin": coin},
            timeout=10
        )
        if resp.status_code != 200:
            print(f"{Colors.RED}API error: {resp.status_code}{Colors.END}")
            return

        data = resp.json()

        if not data:
            print(f"{Colors.DIM}No data available{Colors.END}")
            return

        print(json.dumps(data, indent=2))

    except Exception as e:
        print(f"{Colors.RED}Error fetching max trade size: {e}{Colors.END}")


def cmd_user_funding(args):
    """Show funding payments received/paid."""
    info, config = setup_info(require_credentials=True)
    days = args.days

    print(f"\n{Colors.BOLD}{Colors.CYAN}FUNDING PAYMENTS (last {days} days){Colors.END}")
    print("=" * 70)

    try:
        import time as _time
        end_time = int(_time.time() * 1000)
        start_time = end_time - (days * 86400 * 1000)

        history = info.user_funding_history(config['account_address'], start_time, end_time)

        if not history:
            print(f"{Colors.DIM}No funding payments in this period{Colors.END}")
            return

        print(f"\n  {'Time':<18} {'Asset':<14} {'USD Amount':>14} {'Rate':>12}")
        print("  " + "-" * 60)

        totals = {}
        for entry in history:
            ts = entry.get('time', entry.get('startTime', 0))
            dt = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
            coin = entry.get('coin', entry.get('asset', '?'))

            # Parse the delta (USD amount of funding)
            delta_str = entry.get('usdc', entry.get('delta', entry.get('nSamples', '0')))
            delta = float(delta_str) if delta_str else 0
            rate_str = entry.get('fundingRate', '0')
            rate = float(rate_str) if rate_str else 0

            if coin not in totals:
                totals[coin] = 0
            totals[coin] += delta

            color = Colors.GREEN if delta >= 0 else Colors.RED
            print(f"  {dt:<18} {coin:<14} {color}${delta:>+13.4f}{Colors.END} {rate*100:>11.4f}%")

        # Totals by asset
        if totals:
            grand_total = sum(totals.values())
            print(f"\n  {Colors.BOLD}Totals by asset:{Colors.END}")
            for coin, total in sorted(totals.items(), key=lambda x: x[1]):
                color = Colors.GREEN if total >= 0 else Colors.RED
                print(f"    {coin:<14} {color}${total:>+.4f}{Colors.END}")
            color = Colors.GREEN if grand_total >= 0 else Colors.RED
            print(f"    {'TOTAL':<14} {color}${grand_total:>+.4f}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching user funding: {e}{Colors.END}")


def cmd_whale(args):
    """View positions of any Hyperliquid address."""
    info, config = setup_info(require_credentials=False, include_hip3=True)
    address = args.address

    print(f"\n{Colors.BOLD}{Colors.CYAN}WHALE WATCH: {address[:10]}...{address[-6:]}{Colors.END}")
    print("=" * 80)

    try:
        user_state = info.user_state(address)
        margin_summary = user_state.get('marginSummary', {})
        account_value = float(margin_summary.get('accountValue', 0))
        total_margin = float(margin_summary.get('totalMarginUsed', 0))

        print(f"\n  Account Value: {format_price(account_value)}")
        print(f"  Margin Used:   {format_price(total_margin)}")

        positions = user_state.get('assetPositions', [])
        open_positions = [p for p in positions if float(p['position']['szi']) != 0]

        if open_positions:
            print(f"\n  {Colors.BOLD}Positions ({len(open_positions)}):{Colors.END}")
            print(f"  {'Asset':<14} {'Side':<6} {'Size':>12} {'Entry':>12} {'Mark':>12} {'PnL':>15} {'Notional':>12}")
            print("  " + "-" * 85)

            for pos in open_positions:
                p = pos['position']
                coin = p['coin']
                size = float(p['szi'])
                entry_px = float(p['entryPx'])
                unrealized_pnl = float(p['unrealizedPnl'])
                mark_px = float(p.get('markPx', entry_px))
                notional = abs(size) * mark_px
                side = "LONG" if size > 0 else "SHORT"
                side_color = Colors.GREEN if size > 0 else Colors.RED

                print(f"  {coin:<14} {side_color}{side:<6}{Colors.END} {abs(size):>12.4f} {format_price(entry_px):>12} {format_price(mark_px):>12} {format_pnl(unrealized_pnl):>15} ${notional:>11,.0f}")
        else:
            print(f"\n  {Colors.DIM}No open positions{Colors.END}")

        # Also check HIP-3 positions
        try:
            xyz_state = info.user_state(address, dex='xyz')
            xyz_positions = xyz_state.get('assetPositions', [])
            xyz_open = [p for p in xyz_positions if float(p['position']['szi']) != 0]

            if xyz_open:
                print(f"\n  {Colors.BOLD}HIP-3 Positions ({len(xyz_open)}):{Colors.END}")
                print(f"  {'Asset':<14} {'Side':<6} {'Size':>12} {'Entry':>12} {'PnL':>15}")
                print("  " + "-" * 65)

                for pos in xyz_open:
                    p = pos['position']
                    coin = p['coin']
                    size = float(p['szi'])
                    entry_px = float(p['entryPx'])
                    unrealized_pnl = float(p['unrealizedPnl'])
                    side = "LONG" if size > 0 else "SHORT"
                    side_color = Colors.GREEN if size > 0 else Colors.RED

                    print(f"  {coin:<14} {side_color}{side:<6}{Colors.END} {abs(size):>12.4f} {format_price(entry_px):>12} {format_pnl(unrealized_pnl):>15}")
        except Exception:
            pass

    except Exception as e:
        print(f"{Colors.RED}Error fetching whale data: {e}{Colors.END}")


def cmd_user_fees(args):
    """Show fee schedule and volume info."""
    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}FEE SCHEDULE & VOLUME{Colors.END}")
    print("=" * 60)

    try:
        fees = info.user_fees(config['account_address'])

        if not fees:
            print(f"{Colors.DIM}No fee data available{Colors.END}")
            return

        print(json.dumps(fees, indent=2))

    except Exception as e:
        print(f"{Colors.RED}Error fetching fees: {e}{Colors.END}")


def cmd_historical_orders(args):
    """Show full order history with final statuses."""
    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}HISTORICAL ORDERS{Colors.END}")
    print("=" * 90)

    try:
        orders = info.historical_orders(config['account_address'])

        if not orders:
            print(f"{Colors.DIM}No order history{Colors.END}")
            return

        limit = args.limit
        recent = orders[-limit:] if len(orders) > limit else orders

        print(f"\n  {'Time':<18} {'Asset':<12} {'Side':<6} {'Size':>10} {'Price':>12} {'Status':<12} {'Type'}")
        print("  " + "-" * 85)

        for entry in reversed(recent):
            order = entry.get('order', entry)
            status = entry.get('status', 'unknown')
            ts = order.get('timestamp', entry.get('timestamp', 0))
            dt = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M') if ts else 'N/A'
            coin = order.get('coin', '?')
            side = "BUY" if order.get('side') == 'B' else "SELL"
            side_color = Colors.GREEN if side == "BUY" else Colors.RED
            sz = order.get('sz', order.get('origSz', '?'))
            px = order.get('limitPx', '?')
            order_type = order.get('orderType', '?')

            # Color status
            if status == 'filled':
                status_str = f"{Colors.GREEN}{status}{Colors.END}"
            elif status == 'canceled' or status == 'cancelled':
                status_str = f"{Colors.YELLOW}{status}{Colors.END}"
            elif status == 'rejected':
                status_str = f"{Colors.RED}{status}{Colors.END}"
            else:
                status_str = status

            px_str = format_price(float(px)) if px and px != '?' else px
            print(f"  {dt:<18} {coin:<12} {side_color}{side:<6}{Colors.END} {sz:>10} {px_str:>12} {status_str:<21} {order_type}")

        print(f"\n{Colors.DIM}Showing last {len(recent)} orders. Use --limit N for more.{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching historical orders: {e}{Colors.END}")


# ============================================================================
# ANALYSIS COMMANDS
# ============================================================================

def cmd_analyze(args):
    """Comprehensive market analysis with raw data."""
    info, config = setup_info(require_credentials=False)

    default_assets = ['BTC', 'ETH', 'SOL', 'DOGE', 'HYPE']
    xyz_assets = ['xyz:TSLA', 'xyz:NVDA', 'xyz:AAPL']
    coins = args.coins if args.coins else default_assets

    print(f"\n{Colors.BOLD}{Colors.CYAN}COMPREHENSIVE MARKET ANALYSIS{Colors.END}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")
    print("=" * 80)

    try:
        # Account State
        print(f"\n{Colors.BOLD}=== ACCOUNT STATE ==={Colors.END}")
        if config['account_address']:
            user_state = info.user_state(config['account_address'])
            margin_summary = user_state.get('marginSummary', {})

            print(f"Account Value: ${float(margin_summary.get('accountValue', 0)):,.2f}")
            print(f"Total Margin Used: ${float(margin_summary.get('totalMarginUsed', 0)):,.2f}")
            print(f"Withdrawable: ${float(user_state.get('withdrawable', 0)):,.2f}")

            positions = user_state.get('assetPositions', [])
            open_positions = [p for p in positions if float(p['position']['szi']) != 0]

            if open_positions:
                print(f"\nOpen Positions ({len(open_positions)}):")
                for pos in open_positions:
                    p = pos['position']
                    size = float(p['szi'])
                    entry = float(p['entryPx'])
                    pnl = float(p['unrealizedPnl'])
                    lev = p.get('leverage', {})
                    print(f"  {p['coin']}: {size:+.4f} @ ${entry:,.2f} | PnL: ${pnl:+,.2f} | Leverage: {lev}")
            else:
                print("\nNo open positions")
        else:
            print(f"{Colors.DIM}No credentials configured - skipping account state{Colors.END}")

        # Prices
        print(f"\n{Colors.BOLD}=== CURRENT PRICES ==={Colors.END}")
        all_mids = info.all_mids()
        for coin in coins:
            if coin in all_mids:
                print(f"{coin}: ${float(all_mids[coin]):,.2f}")

        # Funding Rates
        print(f"\n{Colors.BOLD}=== FUNDING RATES & MARKET CONTEXT ==={Colors.END}")
        meta = info.meta_and_asset_ctxs()
        universe = meta[0]['universe']
        asset_ctxs = meta[1]
        name_to_idx = {asset['name']: i for i, asset in enumerate(universe)}

        print(f"{'Asset':<10} {'Price':>12} {'Funding/hr':>12} {'Funding APR':>12} {'Open Interest':>15} {'24h Volume':>15}")
        print("-" * 80)

        for coin in coins:
            if coin in name_to_idx:
                idx = name_to_idx[coin]
                ctx = asset_ctxs[idx]
                price = float(ctx.get('markPx', 0))
                funding = float(ctx.get('funding', 0))
                oi = float(ctx.get('openInterest', 0))
                vol = float(ctx.get('dayNtlVlm', 0))
                funding_pct = funding * 100
                funding_apr = funding * 24 * 365 * 100
                print(f"{coin:<10} ${price:>10,.2f} {funding_pct:>11.4f}% {funding_apr:>11.1f}% ${oi:>13,.0f} ${vol:>13,.0f}")

        # HIP-3 Equity Perps
        print(f"\n{Colors.BOLD}=== HIP-3 EQUITY PERPS (trade.xyz) ==={Colors.END}")
        import requests
        for xyz_coin in xyz_assets:
            try:
                resp = requests.post(
                    config['api_url'] + "/info",
                    json={"type": "fundingHistory", "coin": xyz_coin, "startTime": 0},
                    timeout=10
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        latest = data[-1]
                        funding = float(latest.get('fundingRate', 0))
                        funding_pct = funding * 100
                        funding_apr = funding * 24 * 365 * 100

                        book_resp = requests.post(
                            config['api_url'] + "/info",
                            json={"type": "l2Book", "coin": xyz_coin},
                            timeout=10
                        )
                        price = 0
                        if book_resp.status_code == 200:
                            book = book_resp.json()
                            levels = book.get('levels', [])
                            if len(levels) >= 2 and levels[0] and levels[1]:
                                mid = (float(levels[0][0]['px']) + float(levels[1][0]['px'])) / 2
                                price = mid

                        print(f"{xyz_coin:<12} ${price:>10,.2f} | Funding: {funding_pct:.4f}%/hr ({funding_apr:.1f}% APR)")
            except Exception as e:
                print(f"{xyz_coin:<12} Error: {e}")

        # Order Book Summary
        print(f"\n{Colors.BOLD}=== ORDER BOOK SUMMARY ==={Colors.END}")
        for coin in ['BTC', 'ETH', 'SOL']:
            try:
                book = info.l2_snapshot(coin)
                bids = book.get('levels', [[]])[0]
                asks = book.get('levels', [[], []])[1]

                if bids and asks:
                    best_bid = float(bids[0]['px'])
                    best_ask = float(asks[0]['px'])
                    mid = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid
                    spread_bps = (spread / mid) * 10000
                    bid_depth = sum(float(b['sz']) for b in bids[:10])
                    ask_depth = sum(float(a['sz']) for a in asks[:10])
                    imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0
                    print(f"{coin}: Spread {spread_bps:.1f}bps | Bid depth: {bid_depth:.2f} | Ask depth: {ask_depth:.2f} | Imbalance: {imbalance:+.2%}")
            except Exception:
                pass

    except Exception as e:
        print(f"{Colors.RED}Error during analysis: {e}{Colors.END}")
        import traceback
        traceback.print_exc()


def cmd_raw(args):
    """Dump raw JSON data for specified asset."""
    info, config = setup_info()
    coin = args.coin

    print(f"\n{Colors.BOLD}Raw Data Dump: {coin}{Colors.END}")
    print("=" * 60)

    try:
        all_mids = info.all_mids()
        if coin in all_mids:
            print(f"\n--- Price ---")
            print(f"mid_price: {all_mids[coin]}")

        meta = info.meta_and_asset_ctxs()
        universe = meta[0]['universe']
        asset_ctxs = meta[1]
        name_to_idx = {asset['name']: i for i, asset in enumerate(universe)}

        if coin in name_to_idx:
            idx = name_to_idx[coin]
            print(f"\n--- Asset Metadata ---")
            print(json.dumps(universe[idx], indent=2))
            print(f"\n--- Asset Context ---")
            print(json.dumps(asset_ctxs[idx], indent=2))

        print(f"\n--- L2 Book (Top 5) ---")
        book = info.l2_snapshot(coin)
        print(json.dumps({
            'bids': book.get('levels', [[]])[0][:5],
            'asks': book.get('levels', [[], []])[1][:5]
        }, indent=2))

        print(f"\n--- Recent Trades (Last 10) ---")
        import requests
        resp = requests.post(
            config['api_url'] + "/info",
            json={"type": "recentTrades", "coin": coin},
            timeout=10
        )
        if resp.status_code == 200:
            trades = resp.json()[-10:]
            print(json.dumps(trades, indent=2))

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")


def cmd_scan(args):
    """Scan all assets for trading opportunities based on funding rates."""
    info, config = setup_info()

    min_volume = args.min_volume if hasattr(args, 'min_volume') and args.min_volume else 100000
    top_n = args.top if hasattr(args, 'top') and args.top else 20

    print(f"\n{Colors.BOLD}{Colors.CYAN}MARKET SCANNER - ALL HYPERLIQUID PERPS{Colors.END}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Filter: Min 24h volume > ${min_volume:,}")
    print("=" * 90)

    try:
        meta = info.meta_and_asset_ctxs()
        universe = meta[0]['universe']
        contexts = meta[1]

        assets = []
        for i, asset in enumerate(universe):
            ctx = contexts[i]
            name = asset['name']
            funding = float(ctx.get('funding', 0))
            mark_px = float(ctx.get('markPx', 0))
            oi = float(ctx.get('openInterest', 0))
            volume = float(ctx.get('dayNtlVlm', 0))

            prev_day_px = float(ctx.get('prevDayPx', 0))
            oracle_px = float(ctx.get('oraclePx', 0))
            price_chg = ((mark_px - prev_day_px) / prev_day_px * 100) if prev_day_px > 0 else 0
            oracle_div = ((mark_px - oracle_px) / oracle_px * 100) if oracle_px > 0 else 0

            if volume >= min_volume:
                assets.append({
                    'name': name,
                    'price': mark_px,
                    'funding_hr': funding * 100,
                    'funding_apr': funding * 24 * 365 * 100,
                    'oi': oi,
                    'volume': volume,
                    'price_chg': price_chg,
                    'oracle_px': oracle_px,
                    'oracle_div': oracle_div,
                })

        print(f"\nTotal perps: {len(universe)} | With sufficient volume: {len(assets)}")

        assets_by_funding = sorted(assets, key=lambda x: x['funding_apr'])

        # Check OI-capped assets
        import requests as req
        oi_capped = set()
        try:
            resp = req.post(config['api_url'] + "/info", json={"type": "perpsAtOpenInterestCap"}, timeout=5)
            if resp.status_code == 200:
                oi_capped = set(resp.json())
                if oi_capped:
                    print(f"\n{Colors.YELLOW}OI-capped (new positions blocked): {', '.join(sorted(oi_capped))}{Colors.END}")
        except Exception:
            pass

        print(f"\n{Colors.BOLD}{Colors.GREEN}TOP {top_n} NEGATIVE FUNDING (shorts paying longs - LONG opportunities):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'24h Chg':>8} {'Funding/hr':>12} {'APR':>10} {'OI':>15} {'Volume':>15} {'Mk-Orc':>7}")
        print("-" * 95)

        for a in assets_by_funding[:top_n]:
            funding_color = Colors.GREEN if a['funding_apr'] < -50 else Colors.YELLOW if a['funding_apr'] < 0 else Colors.END
            chg_color = Colors.GREEN if a['price_chg'] >= 0 else Colors.RED
            cap_flag = " OI!" if a['name'] in oi_capped else ""
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {chg_color}{a['price_chg']:>+7.1f}%{Colors.END} {funding_color}{a['funding_hr']:>11.4f}%{Colors.END} {a['funding_apr']:>9.1f}% ${a['oi']:>13,.0f} ${a['volume']:>13,.0f} {a['oracle_div']:>+6.2f}%{cap_flag}")

        print(f"\n{Colors.BOLD}{Colors.RED}TOP {top_n} POSITIVE FUNDING (longs paying shorts - SHORT opportunities or avoid):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'24h Chg':>8} {'Funding/hr':>12} {'APR':>10} {'OI':>15} {'Volume':>15} {'Mk-Orc':>7}")
        print("-" * 95)

        for a in assets_by_funding[-top_n:][::-1]:
            funding_color = Colors.RED if a['funding_apr'] > 50 else Colors.YELLOW if a['funding_apr'] > 0 else Colors.END
            chg_color = Colors.GREEN if a['price_chg'] >= 0 else Colors.RED
            cap_flag = " OI!" if a['name'] in oi_capped else ""
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {chg_color}{a['price_chg']:>+7.1f}%{Colors.END} {funding_color}{a['funding_hr']:>11.4f}%{Colors.END} {a['funding_apr']:>9.1f}% ${a['oi']:>13,.0f} ${a['volume']:>13,.0f} {a['oracle_div']:>+6.2f}%{cap_flag}")

        # High volume movers
        assets_by_volume = sorted(assets, key=lambda x: x['volume'], reverse=True)[:10]
        print(f"\n{Colors.BOLD}{Colors.BLUE}TOP 10 BY VOLUME (most liquid):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'Funding APR':>12} {'24h Volume':>15}")
        print("-" * 55)
        for a in assets_by_volume:
            funding_color = Colors.GREEN if a['funding_apr'] < -10 else Colors.RED if a['funding_apr'] > 10 else Colors.YELLOW
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {funding_color}{a['funding_apr']:>11.1f}%{Colors.END} ${a['volume']:>13,.0f}")

        # HIP-3 Equity Perps
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}HIP-3 PERPS (trade.xyz - equities, commodities, forex):{Colors.END}")
        print(f"{'Asset':<14} {'Price':>12} {'Funding/hr':>12} {'APR':>10}")
        print("-" * 50)

        import requests as req

        try:
            hip3_meta = info.meta(dex='xyz')
            hip3_universe = hip3_meta.get('universe', [])
            hip3_assets = [a.get('name', '') for a in hip3_universe if a.get('name')]
        except Exception:
            hip3_assets = [
                'xyz:TSLA', 'xyz:NVDA', 'xyz:AAPL', 'xyz:GOOGL', 'xyz:AMZN',
                'xyz:META', 'xyz:MSFT', 'xyz:HOOD', 'xyz:PLTR', 'xyz:MSTR',
                'xyz:AMD', 'xyz:NFLX', 'xyz:COIN', 'xyz:XYZ100',
                'xyz:GOLD', 'xyz:SILVER', 'xyz:COPPER', 'xyz:NATGAS',
            ]

        hip3_data = []
        for coin in hip3_assets:
            try:
                resp = req.post(
                    config['api_url'] + "/info",
                    json={"type": "fundingHistory", "coin": coin, "startTime": 0},
                    timeout=5
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        latest = data[-1]
                        funding = float(latest.get('fundingRate', 0))

                        book_resp = req.post(
                            config['api_url'] + "/info",
                            json={"type": "l2Book", "coin": coin},
                            timeout=5
                        )
                        price = 0
                        if book_resp.status_code == 200:
                            book = book_resp.json()
                            levels = book.get('levels', [])
                            if len(levels) >= 2 and levels[0] and levels[1]:
                                price = (float(levels[0][0]['px']) + float(levels[1][0]['px'])) / 2

                        funding_hr = funding * 100
                        funding_apr = funding * 24 * 365 * 100
                        hip3_data.append({
                            'name': coin,
                            'price': price,
                            'funding_hr': funding_hr,
                            'funding_apr': funding_apr
                        })

                        funding_color = Colors.GREEN if funding_apr < -10 else Colors.RED if funding_apr > 10 else Colors.YELLOW
                        print(f"{coin:<14} ${price:>10,.2f} {funding_color}{funding_hr:>11.4f}%{Colors.END} {funding_apr:>9.1f}%")
            except Exception:
                pass

        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        negative_funding = [a for a in assets if a['funding_apr'] < -20]
        print(f"  Native perps with funding < -20% APR: {len(negative_funding)}")
        if negative_funding:
            best = min(negative_funding, key=lambda x: x['funding_apr'])
            print(f"  Best native opportunity: {best['name']} at {best['funding_apr']:.1f}% APR (${best['volume']:,.0f} vol)")

        if hip3_data:
            best_hip3 = min(hip3_data, key=lambda x: x['funding_apr'])
            print(f"  Best HIP-3 opportunity: {best_hip3['name']} at {best_hip3['funding_apr']:.1f}% APR")

    except Exception as e:
        print(f"{Colors.RED}Error scanning: {e}{Colors.END}")
        import traceback
        traceback.print_exc()


def cmd_hip3(args):
    """Get detailed data for HIP-3 perps."""
    info, config = setup_info()
    import requests as req

    if not args.coin:
        try:
            meta = info.meta(dex='xyz')
            universe = meta.get('universe', [])
            assets = sorted([a.get('name', '') for a in universe if a.get('name')])
        except Exception:
            assets = [
                'xyz:TSLA', 'xyz:NVDA', 'xyz:AAPL', 'xyz:GOOGL', 'xyz:AMZN',
                'xyz:META', 'xyz:MSFT', 'xyz:HOOD', 'xyz:PLTR', 'xyz:MSTR',
                'xyz:AMD', 'xyz:NFLX', 'xyz:COIN', 'xyz:XYZ100',
                'xyz:GOLD', 'xyz:SILVER', 'xyz:COPPER', 'xyz:NATGAS',
            ]
    else:
        coin = args.coin if args.coin.startswith('xyz:') else f'xyz:{args.coin}'
        assets = [coin]

    print(f"\n{Colors.BOLD}{Colors.MAGENTA}HIP-3 EQUITY PERPS DATA{Colors.END}")
    print("=" * 80)

    for coin in assets:
        try:
            print(f"\n{Colors.BOLD}{coin}{Colors.END}")

            book_resp = req.post(
                config['api_url'] + "/info",
                json={"type": "l2Book", "coin": coin},
                timeout=10
            )

            if book_resp.status_code == 200:
                book = book_resp.json()
                levels = book.get('levels', [])

                if len(levels) >= 2 and levels[0] and levels[1]:
                    best_bid = float(levels[0][0]['px'])
                    best_ask = float(levels[1][0]['px'])
                    mid = (best_bid + best_ask) / 2
                    spread = best_ask - best_bid
                    spread_bps = (spread / mid) * 10000

                    bid_depth = sum(float(b['sz']) * float(b['px']) for b in levels[0][:5])
                    ask_depth = sum(float(a['sz']) * float(a['px']) for a in levels[1][:5])

                    print(f"  Price:       ${mid:,.2f}")
                    print(f"  Bid:         ${best_bid:,.2f}")
                    print(f"  Ask:         ${best_ask:,.2f}")
                    print(f"  Spread:      {spread_bps:.1f} bps (${spread:.2f})")
                    print(f"  Bid Depth:   ${bid_depth:,.0f} (top 5 levels)")
                    print(f"  Ask Depth:   ${ask_depth:,.0f} (top 5 levels)")

            funding_resp = req.post(
                config['api_url'] + "/info",
                json={"type": "fundingHistory", "coin": coin, "startTime": 0},
                timeout=10
            )

            if funding_resp.status_code == 200:
                data = funding_resp.json()
                if data:
                    latest = data[-1]
                    funding = float(latest.get('fundingRate', 0))
                    funding_hr = funding * 100
                    funding_apr = funding * 24 * 365 * 100

                    funding_color = Colors.GREEN if funding < 0 else Colors.RED if funding > 0.0001 else Colors.YELLOW
                    signal = "shorts paying longs" if funding < 0 else "longs paying shorts" if funding > 0 else "neutral"

                    print(f"  Funding:     {funding_color}{funding_hr:.4f}%/hr ({funding_apr:.1f}% APR){Colors.END}")
                    print(f"  Signal:      {signal}")

        except Exception as e:
            print(f"  {Colors.RED}Error: {e}{Colors.END}")


def cmd_dexes(args):
    """List all HIP-3 dexes and their assets."""
    base_info, config = setup_info(require_credentials=False, include_hip3=False)

    print(f"\n{Colors.BOLD}{Colors.CYAN}HIP-3 DEXES{Colors.END}")
    print("=" * 80)

    try:
        all_dexes = base_info.perp_dexs()

        for dex_info in all_dexes:
            if dex_info is None:
                continue

            dex_name = dex_info.get('name', 'unknown')
            full_name = dex_info.get('fullName', dex_name)

            try:
                meta = base_info.meta(dex=dex_name)
                universe = meta.get('universe', [])
                assets = sorted([a.get('name', '').replace(f'{dex_name}:', '') for a in universe if a.get('name')])
                leverages = [a.get('maxLeverage', 0) for a in universe]
            except Exception:
                oi_caps = dex_info.get('assetToStreamingOiCap', [])
                assets = sorted([a[0].split(':')[1] for a in oi_caps if a[0]])
                leverages = []

            print(f"\n{Colors.BOLD}{dex_name.upper()}{Colors.END} ({full_name})")

            if assets:
                print(f"Assets ({len(assets)}): {', '.join(assets)}")
            else:
                print(f"{Colors.DIM}No assets yet{Colors.END}")

            if leverages:
                print(f"Leverage: {min(leverages)}-{max(leverages)}x")

    except Exception as e:
        print(f"{Colors.RED}Error fetching dexes: {e}{Colors.END}")

    print()


def cmd_history(args):
    """Show trade history from Hyperliquid API."""
    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}TRADE HISTORY{Colors.END}")
    print("=" * 80)

    try:
        fills = info.user_fills(config['account_address'])

        if not fills:
            print("No trades found.")
            return

        limit = args.limit if hasattr(args, 'limit') and args.limit else 20
        recent = fills[-limit:]

        print(f"{'Time':<18} {'Side':<6} {'Asset':<14} {'Size':>12} {'Price':>14} {'Value':>12}")
        print("-" * 80)

        for fill in reversed(recent):
            ts = fill.get('time', 0)
            dt = datetime.fromtimestamp(ts/1000).strftime('%Y-%m-%d %H:%M')
            coin = fill.get('coin', '?')
            side = fill.get('side', '?')
            side_str = f"{Colors.GREEN}BUY{Colors.END}" if side == 'B' else f"{Colors.RED}SELL{Colors.END}"
            sz = float(fill.get('sz', 0))
            px = float(fill.get('px', 0))
            value = sz * px

            print(f"{dt:<18} {side_str:<15} {coin:<14} {sz:>12.4f} ${px:>13.4f} ${value:>11.2f}")

        print(f"\n{Colors.DIM}Showing last {len(recent)} trades. Use --limit N for more.{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='HyperClaw - Hyperliquid Trading CLI for AI Agents',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Status commands
    subparsers.add_parser('status', help='Account status and positions summary')
    subparsers.add_parser('positions', help='Detailed position information')
    subparsers.add_parser('orders', help='List open orders')

    # Price/data commands
    price_parser = subparsers.add_parser('price', help='Get current prices')
    price_parser.add_argument('coins', nargs='*', help='Assets to get prices for')

    funding_parser = subparsers.add_parser('funding', help='Get funding rates')
    funding_parser.add_argument('coins', nargs='*', help='Assets to get funding for')

    book_parser = subparsers.add_parser('book', help='Get order book')
    book_parser.add_argument('coin', help='Asset to get order book for')

    # Trading commands
    buy_parser = subparsers.add_parser('buy', help='Market buy')
    buy_parser.add_argument('coin', help='Asset to buy')
    buy_parser.add_argument('size', type=float, help='Size to buy')

    sell_parser = subparsers.add_parser('sell', help='Market sell')
    sell_parser.add_argument('coin', help='Asset to sell')
    sell_parser.add_argument('size', type=float, help='Size to sell')

    limit_buy_parser = subparsers.add_parser('limit-buy', help='Limit buy order')
    limit_buy_parser.add_argument('coin', help='Asset to buy')
    limit_buy_parser.add_argument('size', type=float, help='Size to buy')
    limit_buy_parser.add_argument('price', type=float, help='Limit price')

    limit_sell_parser = subparsers.add_parser('limit-sell', help='Limit sell order')
    limit_sell_parser.add_argument('coin', help='Asset to sell')
    limit_sell_parser.add_argument('size', type=float, help='Size to sell')
    limit_sell_parser.add_argument('price', type=float, help='Limit price')

    sl_parser = subparsers.add_parser('stop-loss', help='Place stop-loss trigger order')
    sl_parser.add_argument('coin', help='Asset')
    sl_parser.add_argument('size', type=float, help='Size to close')
    sl_parser.add_argument('trigger_price', type=float, help='Trigger price')
    sl_parser.add_argument('--buy', action='store_true', help='Force buy side (for closing shorts)')

    tp_parser = subparsers.add_parser('take-profit', help='Place take-profit trigger order')
    tp_parser.add_argument('coin', help='Asset')
    tp_parser.add_argument('size', type=float, help='Size to close')
    tp_parser.add_argument('trigger_price', type=float, help='Trigger price')
    tp_parser.add_argument('--buy', action='store_true', help='Force buy side (for closing shorts)')

    close_parser = subparsers.add_parser('close', help='Close position')
    close_parser.add_argument('coin', help='Asset to close')

    cancel_parser = subparsers.add_parser('cancel', help='Cancel order')
    cancel_parser.add_argument('oid', help='Order ID to cancel')

    subparsers.add_parser('cancel-all', help='Cancel all open orders')

    leverage_parser = subparsers.add_parser('leverage', help='Set leverage for an asset')
    leverage_parser.add_argument('coin', help='Asset (e.g., SOL, xyz:TSLA)')
    leverage_parser.add_argument('leverage', type=int, help='Leverage multiplier (1 to max)')

    margin_parser = subparsers.add_parser('margin', help='Add/remove margin on isolated position')
    margin_parser.add_argument('coin', help='Asset (e.g., xyz:TSLA)')
    margin_parser.add_argument('amount', type=float, help='USD amount (positive=add, negative=remove)')

    modify_parser = subparsers.add_parser('modify-order', help='Modify existing order')
    modify_parser.add_argument('oid', help='Order ID to modify')
    modify_parser.add_argument('--price', type=float, help='New price')
    modify_parser.add_argument('--size', type=float, help='New size')

    schedule_parser = subparsers.add_parser('schedule-cancel', help='Auto-cancel all orders after N minutes')
    schedule_parser.add_argument('minutes', type=int, nargs='?', default=30, help='Minutes until cancel (default: 30)')
    schedule_parser.add_argument('--clear', action='store_true', help='Clear scheduled cancel')

    candles_parser = subparsers.add_parser('candles', help='Historical OHLCV candles')
    candles_parser.add_argument('coin', help='Asset (e.g., BTC, xyz:TSLA)')
    candles_parser.add_argument('--interval', default='1h', help='Interval: 1m, 5m, 15m, 1h, 4h, 1d (default: 1h)')
    candles_parser.add_argument('--count', type=int, default=24, help='Number of candles (default: 24)')

    fh_parser = subparsers.add_parser('funding-history', help='Historical funding rates')
    fh_parser.add_argument('coin', help='Asset (e.g., BTC, xyz:TSLA)')
    fh_parser.add_argument('--days', type=int, default=7, help='Number of days (default: 7)')

    subparsers.add_parser('portfolio', help='Account portfolio performance over time')

    pf_parser = subparsers.add_parser('predicted-fundings', help='Predicted next funding rates (HL, Binance, Bybit)')
    pf_parser.add_argument('coins', nargs='*', help='Filter to specific assets')

    trades_parser = subparsers.add_parser('trades', help='Recent trades for an asset')
    trades_parser.add_argument('coin', help='Asset (e.g., BTC, xyz:TSLA)')

    mts_parser = subparsers.add_parser('max-trade-size', help='Max tradeable size for an asset')
    mts_parser.add_argument('coin', help='Asset (e.g., SOL, xyz:TSLA)')

    uf_parser = subparsers.add_parser('user-funding', help='Funding payments received/paid')
    uf_parser.add_argument('--days', type=int, default=7, help='Number of days (default: 7)')

    whale_parser = subparsers.add_parser('whale', help='View any address positions')
    whale_parser.add_argument('address', help='Hyperliquid wallet address (0x...)')

    subparsers.add_parser('user-fees', help='Fee schedule and volume info')

    ho_parser = subparsers.add_parser('historical-orders', help='Full order history with statuses')
    ho_parser.add_argument('--limit', type=int, default=50, help='Number of orders (default: 50)')

    # Analysis commands
    analyze_parser = subparsers.add_parser('analyze', help='Comprehensive analysis')
    analyze_parser.add_argument('coins', nargs='*', help='Assets to analyze')

    raw_parser = subparsers.add_parser('raw', help='Dump raw JSON data')
    raw_parser.add_argument('coin', help='Asset to dump data for')

    scan_parser = subparsers.add_parser('scan', help='Scan ALL assets for opportunities')
    scan_parser.add_argument('--min-volume', type=float, default=100000, help='Min 24h volume (default: 100000)')
    scan_parser.add_argument('--top', type=int, default=20, help='Top results (default: 20)')

    hip3_parser = subparsers.add_parser('hip3', help='HIP-3 equity perp data')
    hip3_parser.add_argument('coin', nargs='?', help='HIP-3 asset (e.g., META, TSLA)')

    subparsers.add_parser('dexes', help='List all HIP-3 dexes and assets')

    history_parser = subparsers.add_parser('history', help='Trade history')
    history_parser.add_argument('--limit', type=int, default=20, help='Number of trades (default: 20)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        'status': cmd_status,
        'positions': cmd_positions,
        'orders': cmd_orders,
        'price': cmd_price,
        'funding': cmd_funding,
        'book': cmd_book,
        'buy': cmd_buy,
        'sell': cmd_sell,
        'limit-buy': cmd_limit_buy,
        'limit-sell': cmd_limit_sell,
        'stop-loss': cmd_stop_loss,
        'take-profit': cmd_take_profit,
        'close': cmd_close,
        'cancel': cmd_cancel,
        'cancel-all': cmd_cancel_all,
        'leverage': cmd_leverage,
        'margin': cmd_margin,
        'modify-order': cmd_modify_order,
        'schedule-cancel': cmd_schedule_cancel,
        'candles': cmd_candles,
        'funding-history': cmd_funding_history,
        'portfolio': cmd_portfolio,
        'predicted-fundings': cmd_predicted_fundings,
        'trades': cmd_trades,
        'max-trade-size': cmd_max_trade_size,
        'user-funding': cmd_user_funding,
        'whale': cmd_whale,
        'user-fees': cmd_user_fees,
        'historical-orders': cmd_historical_orders,
        'analyze': cmd_analyze,
        'raw': cmd_raw,
        'scan': cmd_scan,
        'hip3': cmd_hip3,
        'dexes': cmd_dexes,
        'history': cmd_history,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
