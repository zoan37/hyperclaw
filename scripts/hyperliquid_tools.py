#!/usr/bin/env python3
"""
Hyperliquid Trading Toolkit - CLI for Claude Code to trade on Hyperliquid.

Usage:
    python hyperliquid_tools.py status              # Account balance, positions, PnL
    python hyperliquid_tools.py positions           # Detailed position info
    python hyperliquid_tools.py price BTC           # Current price
    python hyperliquid_tools.py funding BTC         # Funding rate
    python hyperliquid_tools.py book BTC            # Order book
    python hyperliquid_tools.py buy BTC 0.01        # Market buy
    python hyperliquid_tools.py sell BTC 0.01       # Market sell
    python hyperliquid_tools.py limit-buy BTC 0.01 85000   # Limit buy
    python hyperliquid_tools.py limit-sell BTC 0.01 95000  # Limit sell
    python hyperliquid_tools.py close BTC           # Close position
    python hyperliquid_tools.py orders              # List open orders
    python hyperliquid_tools.py cancel ORDER_ID     # Cancel order
    python hyperliquid_tools.py cancel-all          # Cancel all orders
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
    secret_key = os.getenv('HL_SECRET_KEY')
    use_testnet = os.getenv('HL_TESTNET', 'true').lower() == 'true'

    if require_credentials and (not account_address or not secret_key):
        print(f"{Colors.RED}Error: Hyperliquid credentials not configured.{Colors.END}")
        print(f"\nAdd to your .env file:")
        print(f"  HL_ACCOUNT_ADDRESS=0x...  # Your wallet address")
        print(f"  HL_SECRET_KEY=0x...       # API wallet private key")
        print(f"  HL_TESTNET=true           # Optional: use testnet")
        sys.exit(1)

    base_api_url = constants.TESTNET_API_URL if use_testnet else constants.MAINNET_API_URL
    api_url = os.getenv('HL_PROXY_URL') or base_api_url

    return {
        'account_address': account_address or '',
        'secret_key': secret_key or '',
        'api_url': api_url,
        'base_api_url': base_api_url,
        'is_testnet': use_testnet
    }


def get_all_dex_names(api_url: str) -> list:
    """Fetch all available HIP-3 dex names from the API."""
    try:
        # Create a basic Info client to query available dexes
        basic_info = Info(api_url, skip_ws=True)
        all_dexes = basic_info.perp_dexs()
        # Extract dex names, add '' for native perps
        dex_names = ['']  # Native perps
        for dex in all_dexes:
            if dex is not None and dex.get('name'):
                dex_names.append(dex.get('name'))
        return dex_names
    except Exception:
        # Fallback to known dexes if API call fails
        return ['', 'xyz', 'vntl', 'flx', 'hyna', 'km', 'abcd', 'cash']


def setup_info(skip_ws: bool = True, require_credentials: bool = False, include_hip3: bool = True) -> tuple:
    """Setup Info client for read-only operations."""
    config = get_config(require_credentials=require_credentials)
    # Fetch all available HIP-3 dexes dynamically
    perp_dexs = get_all_dex_names(config['api_url']) if include_hip3 else None
    info = Info(config['api_url'], skip_ws=skip_ws, perp_dexs=perp_dexs)
    return info, config


def setup_exchange(skip_ws: bool = True, include_hip3: bool = True) -> tuple:
    """Setup Exchange client for trading operations."""
    config = get_config()
    # Create wallet from private key
    wallet = Account.from_key(config['secret_key'])
    # Fetch all available HIP-3 dexes dynamically
    perp_dexs = get_all_dex_names(config['api_url']) if include_hip3 else None
    # Exchange uses the real API URL (not proxy) so signing uses the correct chain domain.
    # The SDK checks base_url == MAINNET_API_URL to determine mainnet vs testnet signing.
    exchange = Exchange(wallet, config['base_api_url'], account_address=config['account_address'], perp_dexs=perp_dexs)
    # Info client uses proxy URL for cached reads
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
        # Get main perps state
        user_state = info.user_state(config['account_address'])

        # Also get xyz (HIP-3) state
        xyz_state = info.user_state(config['account_address'], dex='xyz')

        # Account balances
        margin_summary = user_state.get('marginSummary', {})
        account_value = float(margin_summary.get('accountValue', 0))
        total_margin = float(margin_summary.get('totalMarginUsed', 0))
        total_pnl = float(margin_summary.get('totalRawUsd', 0))
        withdrawable = float(user_state.get('withdrawable', 0))

        print(f"\n{Colors.BOLD}Account Summary:{Colors.END}")
        print(f"  Account Value:  {format_price(account_value)}")
        print(f"  Margin Used:    {format_price(total_margin)}")
        print(f"  Withdrawable:   {format_price(withdrawable)}")

        # Positions (combine main + xyz HIP-3)
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

                # Get mark price
                mark_px = entry_px  # Fallback
                if 'markPx' in p:
                    mark_px = float(p['markPx'])

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
                max_lev = _get_max_leverage(info, coin)
                max_str = f" / max {max_lev}x" if max_lev else ""
                print(f"  Leverage:       {lev_val}x ({lev_type}{max_str})")
            if liq_px:
                print(f"  Liquidation:    {format_price(liq_px)}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching positions: {e}{Colors.END}")


def cmd_price(args):
    """Get current price for an asset."""
    info, config = setup_info()
    coins = args.coins if args.coins else ['BTC', 'ETH', 'SOL']

    try:
        # Cache mids per dex to avoid repeated API calls
        mids_cache = {}

        def get_price(coin):
            """Get price for a coin, handling HIP-3 dex prefix."""
            if ':' in coin:
                # HIP-3 asset like xyz:META or vntl:ANTHROPIC
                dex = coin.split(':')[0]
                if dex not in mids_cache:
                    mids_cache[dex] = info.all_mids(dex=dex)
                return mids_cache[dex].get(coin)
            else:
                # Native perp
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
        # Get meta and asset contexts
        meta = info.meta_and_asset_ctxs()
        universe = meta[0]['universe']
        asset_ctxs = meta[1]

        # Build name to index map
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

                # Signal interpretation
                if funding < -0.0001:
                    signal = f"{Colors.GREEN}Shorts paying (bullish){Colors.END}"
                elif funding > 0.0005:
                    signal = f"{Colors.RED}Longs crowded (bearish){Colors.END}"
                else:
                    signal = f"{Colors.YELLOW}Neutral{Colors.END}"

                print(f"  {coin:<12} {funding_pct:>11.4f}% {apr:>11.1f}% {signal}")
            else:
                # Try HIP-3 perps - fetch dex list dynamically from API
                try:
                    all_dexes = info.perp_dexs()
                    hip3_dexes = [d.get('name') for d in all_dexes if d is not None and d.get('name')]
                except:
                    # Fallback to known dexes
                    hip3_dexes = ['xyz', 'vntl', 'flx', 'hyna', 'km', 'abcd', 'cash']
                found = False

                # Check if coin already has a dex prefix
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
                    except:
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

        # Mid price
        if bids and asks:
            mid = (float(bids[0]['px']) + float(asks[0]['px'])) / 2
            spread = float(asks[0]['px']) - float(bids[0]['px'])
            spread_pct = (spread / mid) * 100
            print(f"\n  Mid: {format_price(mid)} | Spread: {format_price(spread)} ({spread_pct:.3f}%)")

    except Exception as e:
        print(f"{Colors.RED}Error fetching order book: {e}{Colors.END}")


def cmd_orders(args):
    """List open orders."""
    info, config = setup_info(require_credentials=True)

    try:
        open_orders = info.open_orders(config['account_address'])

        print(f"\n{Colors.BOLD}Open Orders:{Colors.END}")

        if not open_orders:
            print(f"  {Colors.DIM}No open orders{Colors.END}")
            return

        print(f"  {'OID':<12} {'Asset':<12} {'Side':<6} {'Size':>12} {'Price':>12} {'Type':<10}")
        print("  " + "-" * 70)

        for order in open_orders:
            oid = order.get('oid', 'N/A')
            coin = order.get('coin', 'N/A')
            side = "BUY" if order.get('side') == 'B' else "SELL"
            side_color = Colors.GREEN if side == "BUY" else Colors.RED
            sz = order.get('sz', '0')
            px = float(order.get('limitPx', 0))
            order_type = order.get('orderType', 'limit')

            print(f"  {oid:<12} {coin:<12} {side_color}{side:<6}{Colors.END} {sz:>12} {format_price(px):>12} {order_type:<10}")

    except Exception as e:
        print(f"{Colors.RED}Error fetching orders: {e}{Colors.END}")


# ============================================================================
# TRADING COMMANDS
# ============================================================================

def _set_leverage(exchange, coin, leverage, is_cross=True):
    """Set leverage for an asset before trading."""
    margin_type = "cross" if is_cross else "isolated"
    try:
        result = exchange.update_leverage(leverage, coin, is_cross)
        if result.get('status') == 'ok':
            print(f"  Leverage set: {leverage}x ({margin_type})")
        else:
            print(f"{Colors.RED}Failed to set leverage: {result}{Colors.END}")
            return False
    except Exception as e:
        print(f"{Colors.RED}Error setting leverage: {e}{Colors.END}")
        return False
    return True


def _get_max_leverage(info, coin):
    """Get max leverage for an asset from metadata."""
    try:
        # Check native perps
        meta = info.meta()
        for asset in meta.get('universe', []):
            if asset['name'] == coin:
                return asset.get('maxLeverage')
        # Check HIP-3 dexes
        if ':' in coin:
            dex = coin.split(':')[0]
            meta = info.meta(dex=dex)
            for asset in meta.get('universe', []):
                if asset['name'] == coin:
                    return asset.get('maxLeverage')
    except Exception:
        pass
    return None


def cmd_leverage(args):
    """Set leverage for an asset."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    leverage = args.leverage
    is_cross = not args.isolated

    max_lev = _get_max_leverage(info, coin)
    margin_type = "cross" if is_cross else "isolated"
    max_str = f" (max: {max_lev}x)" if max_lev else ""

    print(f"\n{Colors.BOLD}Setting {coin} leverage: {leverage}x ({margin_type}){max_str}{Colors.END}")

    if max_lev and leverage > max_lev:
        print(f"{Colors.RED}Error: {leverage}x exceeds max leverage of {max_lev}x for {coin}{Colors.END}")
        return

    try:
        result = exchange.update_leverage(leverage, coin, is_cross)
        if result.get('status') == 'ok':
            print(f"{Colors.GREEN}Leverage updated!{Colors.END}")
            print(f"  {coin}: {leverage}x {margin_type}")
        else:
            print(f"{Colors.RED}Failed: {result}{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")


def cmd_buy(args):
    """Market buy."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size

    print(f"\n{Colors.BOLD}Market Buy: {size} {coin}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        # Set leverage if specified
        if args.leverage:
            if not _set_leverage(exchange, coin, args.leverage, not getattr(args, 'isolated', False)):
                return

        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            print(f"Current price: {format_price(current_price)}")
            print(f"Estimated cost: {format_price(current_price * size)}")

        # Execute market buy
        result = exchange.market_open(coin, True, size, None, 0.01)  # 1% slippage

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
        # Set leverage if specified
        if args.leverage:
            if not _set_leverage(exchange, coin, args.leverage, not getattr(args, 'isolated', False)):
                return

        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            print(f"Current price: {format_price(current_price)}")

        # Execute market sell
        result = exchange.market_open(coin, False, size, None, 0.01)  # 1% slippage

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
        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from limit)")

        # Place limit order
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
        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from limit)")

        # Place limit order
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
    """Place a stop-loss trigger order. Closes position at market when trigger price is hit."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    trigger_price = args.trigger_price

    print(f"\n{Colors.BOLD}Stop-Loss: {size} {coin} @ trigger {format_price(trigger_price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((trigger_price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from trigger)")

        # Determine direction: if trigger is below current price, it's a sell stop (closing a long)
        # If trigger is above current price, it's a buy stop (closing a short)
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
    """Place a take-profit trigger order. Closes position at market when trigger price is hit."""
    exchange, info, config = setup_exchange()
    coin = args.coin
    size = args.size
    trigger_price = args.trigger_price

    print(f"\n{Colors.BOLD}Take-Profit: {size} {coin} @ trigger {format_price(trigger_price)}{Colors.END}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")

    try:
        # Get current price for reference
        all_mids = info.all_mids()
        if coin in all_mids:
            current_price = float(all_mids[coin])
            diff_pct = ((trigger_price - current_price) / current_price) * 100
            print(f"Current price: {format_price(current_price)} ({diff_pct:+.2f}% from trigger)")

        # For take-profit: if trigger is above current price, it's a sell (closing a long)
        # If trigger is below current price, it's a buy (closing a short)
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
        # Check current position - check both main perps and HIP-3 dexes
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

        # Close position
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

    # Need to find the coin for this order
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

        result = exchange.cancel(coin, int(oid))

        if result.get('status') == 'ok':
            print(f"{Colors.GREEN}Order canceled!{Colors.END}")
        else:
            print(f"{Colors.RED}Cancel failed: {result}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error canceling order: {e}{Colors.END}")


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
                result = exchange.cancel(coin, int(oid))
                if result.get('status') == 'ok':
                    print(f"  {Colors.GREEN}Canceled {coin} order {oid}{Colors.END}")
                else:
                    print(f"  {Colors.RED}Failed to cancel {coin} order {oid}{Colors.END}")
            except Exception as e:
                print(f"  {Colors.RED}Error canceling {coin} order {oid}: {e}{Colors.END}")

        print(f"\n{Colors.GREEN}Done!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error canceling orders: {e}{Colors.END}")


def cmd_analyze(args):
    """Comprehensive market analysis with raw data for AI agent processing."""
    info, config = setup_info(require_credentials=False)

    # Assets to analyze
    default_assets = ['BTC', 'ETH', 'SOL', 'DOGE', 'HYPE']
    xyz_assets = ['xyz:TSLA', 'xyz:NVDA', 'xyz:AAPL']
    coins = args.coins if args.coins else default_assets

    print(f"\n{Colors.BOLD}{Colors.CYAN}COMPREHENSIVE MARKET ANALYSIS{Colors.END}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    if config['is_testnet']:
        print(f"{Colors.YELLOW}[TESTNET]{Colors.END}")
    print("=" * 80)

    try:
        # 1. Account State (if credentials configured)
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
            print(f"Add HL_ACCOUNT_ADDRESS and HL_SECRET_KEY to .env to see positions")

        # 2. All Prices
        print(f"\n{Colors.BOLD}=== CURRENT PRICES ==={Colors.END}")
        all_mids = info.all_mids()
        for coin in coins:
            if coin in all_mids:
                print(f"{coin}: ${float(all_mids[coin]):,.2f}")

        # 3. Funding Rates & Market Context
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

        # 4. HIP-3 Equity Perps
        print(f"\n{Colors.BOLD}=== HIP-3 EQUITY PERPS (trade.xyz) ==={Colors.END}")
        import requests
        for xyz_coin in xyz_assets:
            try:
                # Get funding
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

                        # Get price from L2 book
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

        # 5. Order Book Depth (for major assets)
        print(f"\n{Colors.BOLD}=== ORDER BOOK SUMMARY ==={Colors.END}")
        for coin in ['BTC', 'ETH', 'SOL']:
            if coin in coins or True:  # Always show major assets
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

                        # Sum depth
                        bid_depth = sum(float(b['sz']) for b in bids[:10])
                        ask_depth = sum(float(a['sz']) for a in asks[:10])
                        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0

                        print(f"{coin}: Spread {spread_bps:.1f}bps | Bid depth: {bid_depth:.2f} | Ask depth: {ask_depth:.2f} | Imbalance: {imbalance:+.2%}")
                except:
                    pass

        # 6. Recent Price Changes (from candles if available)
        print(f"\n{Colors.BOLD}=== NOTES FOR ANALYSIS ==={Colors.END}")
        print("""
Key signals to consider:
- Negative funding = shorts paying longs = potential squeeze opportunity (contrarian long)
- Positive funding > 0.01%/hr = longs crowded = potential long squeeze (caution)
- Order book imbalance > ±20% = directional pressure
- Open interest spike = new positions being built

For full technical analysis (RSI, SMA, ATH distance):
  python market_analyzer.py --skip-sentiment

For sentiment analysis (slower, uses Grok):
  python market_analyzer.py
""")

    except Exception as e:
        print(f"{Colors.RED}Error during analysis: {e}{Colors.END}")
        import traceback
        traceback.print_exc()


def cmd_raw(args):
    """Dump raw JSON data for specified asset - for AI processing."""
    info, config = setup_info()
    coin = args.coin

    print(f"\n{Colors.BOLD}Raw Data Dump: {coin}{Colors.END}")
    print("=" * 60)

    try:
        # Price
        all_mids = info.all_mids()
        if coin in all_mids:
            print(f"\n--- Price ---")
            print(f"mid_price: {all_mids[coin]}")

        # Meta and context
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

        # Order book
        print(f"\n--- L2 Book (Top 5) ---")
        book = info.l2_snapshot(coin)
        print(json.dumps({
            'bids': book.get('levels', [[]])[0][:5],
            'asks': book.get('levels', [[], []])[1][:5]
        }, indent=2))

        # Recent trades
        print(f"\n--- Recent Trades (Last 10) ---")
        # Note: SDK might not have this, using requests
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

            if volume >= min_volume:
                assets.append({
                    'name': name,
                    'price': mark_px,
                    'funding_hr': funding * 100,
                    'funding_apr': funding * 24 * 365 * 100,
                    'oi': oi,
                    'volume': volume
                })

        print(f"\nTotal perps: {len(universe)} | With sufficient volume: {len(assets)}")

        # Sort by funding rate (most negative first)
        assets_by_funding = sorted(assets, key=lambda x: x['funding_apr'])

        print(f"\n{Colors.BOLD}{Colors.GREEN}TOP {top_n} NEGATIVE FUNDING (shorts paying longs - LONG opportunities):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'Funding/hr':>12} {'APR':>10} {'Open Interest':>15} {'24h Volume':>15}")
        print("-" * 80)

        for a in assets_by_funding[:top_n]:
            funding_color = Colors.GREEN if a['funding_apr'] < -50 else Colors.YELLOW if a['funding_apr'] < 0 else Colors.END
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {funding_color}{a['funding_hr']:>11.4f}%{Colors.END} {a['funding_apr']:>9.1f}% ${a['oi']:>13,.0f} ${a['volume']:>13,.0f}")

        print(f"\n{Colors.BOLD}{Colors.RED}TOP {top_n} POSITIVE FUNDING (longs paying shorts - SHORT opportunities or avoid):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'Funding/hr':>12} {'APR':>10} {'Open Interest':>15} {'24h Volume':>15}")
        print("-" * 80)

        for a in assets_by_funding[-top_n:][::-1]:
            funding_color = Colors.RED if a['funding_apr'] > 50 else Colors.YELLOW if a['funding_apr'] > 0 else Colors.END
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {funding_color}{a['funding_hr']:>11.4f}%{Colors.END} {a['funding_apr']:>9.1f}% ${a['oi']:>13,.0f} ${a['volume']:>13,.0f}")

        # High volume movers
        assets_by_volume = sorted(assets, key=lambda x: x['volume'], reverse=True)[:10]
        print(f"\n{Colors.BOLD}{Colors.BLUE}TOP 10 BY VOLUME (most liquid):{Colors.END}")
        print(f"{'Asset':<12} {'Price':>12} {'Funding APR':>12} {'24h Volume':>15}")
        print("-" * 55)
        for a in assets_by_volume:
            funding_color = Colors.GREEN if a['funding_apr'] < -10 else Colors.RED if a['funding_apr'] > 10 else Colors.YELLOW
            print(f"{a['name']:<12} ${a['price']:>10,.2f} {funding_color}{a['funding_apr']:>11.1f}%{Colors.END} ${a['volume']:>13,.0f}")

        # HIP-3 Equity Perps (trade.xyz)
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}HIP-3 PERPS (trade.xyz - equities, commodities, forex):{Colors.END}")
        print(f"{'Asset':<14} {'Price':>12} {'Funding/hr':>12} {'APR':>10}")
        print("-" * 50)

        import requests as req

        # Fetch all HIP-3 assets dynamically
        try:
            meta = info.meta(dex='xyz')
            universe = meta.get('universe', [])
            hip3_assets = [a.get('name', '') for a in universe if a.get('name')]
        except:
            # Fallback to known assets
            hip3_assets = [
                'xyz:TSLA', 'xyz:NVDA', 'xyz:AAPL', 'xyz:GOOGL', 'xyz:AMZN',
                'xyz:META', 'xyz:MSFT', 'xyz:HOOD', 'xyz:PLTR', 'xyz:MSTR',
                'xyz:AMD', 'xyz:NFLX', 'xyz:COIN', 'xyz:XYZ100',
                'xyz:GOLD', 'xyz:SILVER', 'xyz:COPPER', 'xyz:NATGAS',
            ]

        hip3_data = []
        for coin in hip3_assets:
            try:
                # Get funding
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

                        # Get price from L2 book
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
            except Exception as e:
                pass  # Skip failed assets

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
    """Get detailed data for HIP-3 perps (trade.xyz assets - equities, commodities, forex)."""
    info, config = setup_info()
    import requests as req

    # If no specific asset, fetch all available from API
    if not args.coin:
        try:
            # Fetch all HIP-3 assets dynamically from xyz dex
            meta = info.meta(dex='xyz')
            universe = meta.get('universe', [])
            assets = [a.get('name', '') for a in universe]
            # Filter out empty and sort
            assets = sorted([a for a in assets if a])
        except Exception as e:
            print(f"{Colors.YELLOW}Warning: Could not fetch HIP-3 assets dynamically, using fallback list{Colors.END}")
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

            # Get L2 Book (price + liquidity)
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

                    # Calculate depth
                    bid_depth = sum(float(b['sz']) * float(b['px']) for b in levels[0][:5])
                    ask_depth = sum(float(a['sz']) * float(a['px']) for a in levels[1][:5])

                    print(f"  Price:       ${mid:,.2f}")
                    print(f"  Bid:         ${best_bid:,.2f}")
                    print(f"  Ask:         ${best_ask:,.2f}")
                    print(f"  Spread:      {spread_bps:.1f} bps (${spread:.2f})")
                    print(f"  Bid Depth:   ${bid_depth:,.0f} (top 5 levels)")
                    print(f"  Ask Depth:   ${ask_depth:,.0f} (top 5 levels)")

            # Get Funding Rate
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

            # Get Meta info (if available)
            meta_resp = req.post(
                config['api_url'] + "/info",
                json={"type": "perpsAtTime", "req": {"user": config['account_address'], "time": 0}},
                timeout=10
            )

        except Exception as e:
            print(f"  {Colors.RED}Error: {e}{Colors.END}")


def cmd_sentiment(args):
    """Get sentiment analysis for an asset using Grok API."""
    coin = args.coin

    grok_api_key = os.getenv('XAI_API_KEY')
    if not grok_api_key:
        print(f"{Colors.RED}Error: XAI_API_KEY not set in .env{Colors.END}")
        print("Add your Grok API key to use sentiment analysis")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}SENTIMENT ANALYSIS: {coin}{Colors.END}")
    print("=" * 60)

    try:
        import requests as req

        # Web search
        print(f"\n{Colors.BOLD}Web Search (News & Analysis):{Colors.END}")
        web_query = f"What is the current market sentiment and recent news for {coin} cryptocurrency? Focus on price action, major developments, and whether traders are bullish or bearish. Be concise."

        response = req.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {grok_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-4-1-fast",
                "tools": [{"type": "web_search"}],
                "input": [{"role": "user", "content": web_query}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            for item in data.get('output', []):
                if item.get('type') == 'message':
                    for content in item.get('content', []):
                        if content.get('type') in ('text', 'output_text'):
                            text = content.get('text', '')[:800]
                            print(f"{Colors.DIM}{text}{Colors.END}")
        else:
            print(f"{Colors.RED}Web search error: {response.status_code}{Colors.END}")

        # X/Twitter search
        print(f"\n{Colors.BOLD}X/Twitter Sentiment:{Colors.END}")
        x_query = f"What is the sentiment on X/Twitter about ${coin} in the last 24-48 hours? Are traders bullish or bearish? What are the key opinions? Be concise."

        response = req.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {grok_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-4-1-fast",
                "tools": [{"type": "x_search"}],
                "input": [{"role": "user", "content": x_query}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            for item in data.get('output', []):
                if item.get('type') == 'message':
                    for content in item.get('content', []):
                        if content.get('type') in ('text', 'output_text'):
                            text = content.get('text', '')[:800]
                            print(f"{Colors.DIM}{text}{Colors.END}")
        else:
            print(f"{Colors.RED}X search error: {response.status_code}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")


def cmd_unlocks(args):
    """Check token unlock schedules using Grok search."""
    import requests as req

    grok_api_key = os.getenv('XAI_API_KEY')
    if not grok_api_key:
        print(f"{Colors.RED}Error: XAI_API_KEY not set in .env{Colors.END}")
        return

    # If no coin specified, check current positions
    if not args.coins:
        info, config = setup_info(require_credentials=True)
        try:
            user_state = info.user_state(config['account_address'])
            positions = user_state.get('assetPositions', [])
            coins = []
            for pos in positions:
                position = pos.get('position', {})
                if float(position.get('szi', 0)) != 0:
                    coin = position.get('coin', '')
                    # Skip HIP-3 perps (equities don't have token unlocks)
                    if ':' not in coin:
                        coins.append(coin)
            if not coins:
                print("No native token positions found.")
                return
        except Exception as e:
            print(f"{Colors.RED}Error getting positions: {e}{Colors.END}")
            return
    else:
        coins = args.coins

    print(f"\n{Colors.BOLD}{Colors.CYAN}TOKEN UNLOCK CHECK{Colors.END}")
    print("=" * 70)

    for coin in coins:
        print(f"\n{Colors.BOLD}{coin}:{Colors.END}")

        try:
            # Search for unlock info
            query = f"What are the upcoming token unlocks or vesting events for {coin} cryptocurrency in the next 30 days? Include dates, amounts, and percentage of supply if available. Be specific and concise. If no unlocks found, say so."

            response = req.post(
                "https://api.x.ai/v1/responses",
                headers={
                    "Authorization": f"Bearer {grok_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-4-1-fast",
                    "tools": [{"type": "web_search"}],
                    "input": [{"role": "user", "content": query}]
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                for item in data.get('output', []):
                    if item.get('type') == 'message':
                        for content in item.get('content', []):
                            if content.get('type') in ('text', 'output_text'):
                                text = content.get('text', '')[:600]
                                print(f"{Colors.DIM}{text}{Colors.END}")
            else:
                print(f"{Colors.RED}Search error: {response.status_code}{Colors.END}")

        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")

    print()


def cmd_devcheck(args):
    """Check for developer sentiment, complaints, and exodus signals."""
    import requests as req

    coin = args.coin

    grok_api_key = os.getenv('XAI_API_KEY')
    if not grok_api_key:
        print(f"{Colors.RED}Error: XAI_API_KEY not set in .env{Colors.END}")
        return

    print(f"\n{Colors.BOLD}{Colors.CYAN}DEVELOPER CHECK: {coin}{Colors.END}")
    print("=" * 70)

    try:
        # Search for developer issues/complaints
        print(f"\n{Colors.BOLD}Developer Sentiment & Issues:{Colors.END}")
        dev_query = f"""Search for developer complaints, issues, or concerns about {coin} blockchain/protocol:
1. Are developers leaving or switching to other chains?
2. Any complaints about costs, centralization, or technical issues?
3. Any apps or projects that abandoned {coin} for competitors?
4. What are devs saying in forums, Discord, or X?
Be specific with examples and sources."""

        response = req.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {grok_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-4-1-fast",
                "tools": [{"type": "web_search"}],
                "input": [{"role": "user", "content": dev_query}]
            },
            timeout=45
        )

        if response.status_code == 200:
            data = response.json()
            for item in data.get('output', []):
                if item.get('type') == 'message':
                    for content in item.get('content', []):
                        if content.get('type') in ('text', 'output_text'):
                            text = content.get('text', '')[:1200]
                            print(f"{Colors.DIM}{text}{Colors.END}")
        else:
            print(f"{Colors.RED}Search error: {response.status_code}{Colors.END}")

        # X/Twitter dev sentiment
        print(f"\n{Colors.BOLD}X/Twitter Dev Chatter:{Colors.END}")
        x_query = f"What are developers saying about {coin} on X/Twitter? Look for: complaints, frustrations, projects leaving, technical issues, cost concerns. Not price speculation - developer experience only."

        response = req.post(
            "https://api.x.ai/v1/responses",
            headers={
                "Authorization": f"Bearer {grok_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-4-1-fast",
                "tools": [{"type": "x_search"}],
                "input": [{"role": "user", "content": x_query}]
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            for item in data.get('output', []):
                if item.get('type') == 'message':
                    for content in item.get('content', []):
                        if content.get('type') in ('text', 'output_text'):
                            text = content.get('text', '')[:800]
                            print(f"{Colors.DIM}{text}{Colors.END}")
        else:
            print(f"{Colors.RED}X search error: {response.status_code}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")

    print()


def cmd_polymarket(args):
    """Get Polymarket prediction market data for trading signals."""
    import httpx
    import json

    category = args.category.lower() if args.category else 'crypto'

    print(f"\n{Colors.BOLD}{Colors.CYAN}POLYMARKET PREDICTIONS: {category.upper()}{Colors.END}")
    print("=" * 70)

    try:
        # Define event slugs by category
        event_slugs = {
            'crypto': [
                'what-price-will-bitcoin-hit-in-january-2026',
                'what-price-will-ethereum-hit-in-january-2026',
            ],
            'btc': ['what-price-will-bitcoin-hit-in-january-2026'],
            'eth': ['what-price-will-ethereum-hit-in-january-2026'],
            'fed': [],  # Will search for Fed-related
            'macro': [],  # Will search for macro events
        }

        slugs = event_slugs.get(category, event_slugs['crypto'])

        if slugs:
            for slug in slugs:
                url = f'https://gamma-api.polymarket.com/events?slug={slug}'
                r = httpx.get(url, timeout=15)
                if r.status_code == 200 and r.json():
                    event = r.json()[0]
                    title = event.get('title', 'Unknown')
                    volume = float(event.get('volume', 0) or 0)

                    print(f"\n{Colors.BOLD}{title}{Colors.END}")
                    print(f"Total Volume: ${volume:,.0f}")
                    print()

                    markets = event.get('markets', [])
                    # Sort by volume
                    markets.sort(key=lambda x: float(x.get('volume', 0) or 0), reverse=True)

                    for m in markets[:15]:
                        question = m.get('question', '')
                        prices = m.get('outcomePrices', '[]')
                        try:
                            p = json.loads(prices) if isinstance(prices, str) else prices
                            yes_prob = float(p[0]) * 100 if p and len(p) > 0 else 0
                        except:
                            yes_prob = 0
                        vol = float(m.get('volume', 0) or 0)

                        # Color code by probability
                        if yes_prob > 70:
                            prob_color = Colors.GREEN
                        elif yes_prob < 30:
                            prob_color = Colors.RED
                        else:
                            prob_color = Colors.YELLOW

                        # Shorten question
                        q_short = question.replace('Will Bitcoin ', 'BTC ').replace('Will Ethereum ', 'ETH ')
                        q_short = q_short.replace('in January?', 'Jan').replace(' in January', ' Jan')

                        print(f"  {q_short}: {prob_color}{yes_prob:5.1f}%{Colors.END} (${vol:,.0f})")

        # Also fetch trending/high volume markets
        if category in ['trending', 'all', 'macro']:
            print(f"\n{Colors.BOLD}High Volume Markets:{Colors.END}")
            url = 'https://gamma-api.polymarket.com/events?limit=20&active=true&closed=false'
            r = httpx.get(url, timeout=15)
            if r.status_code == 200:
                events = r.json()
                # Sort by volume
                events.sort(key=lambda x: float(x.get('volume', 0) or 0), reverse=True)

                for e in events[:10]:
                    title = e.get('title', '')[:60]
                    vol = float(e.get('volume', 0) or 0)
                    if vol > 100000:
                        print(f"  {title}: ${vol:,.0f}")

        # Summary for trading
        print(f"\n{Colors.BOLD}Trading Signal Summary:{Colors.END}")

        if category in ['crypto', 'btc']:
            # Fetch BTC data and summarize
            url = 'https://gamma-api.polymarket.com/events?slug=what-price-will-bitcoin-hit-in-january-2026'
            r = httpx.get(url, timeout=15)
            if r.status_code == 200 and r.json():
                markets = r.json()[0].get('markets', [])

                # Find key levels
                upside_probs = {}
                downside_probs = {}

                for m in markets:
                    q = m.get('question', '').lower()
                    prices = m.get('outcomePrices', '[]')
                    try:
                        p = json.loads(prices) if isinstance(prices, str) else prices
                        prob = float(p[0]) * 100 if p else 0
                    except:
                        prob = 0

                    if 'reach' in q:
                        # Extract price level
                        for word in q.split():
                            if word.startswith('$'):
                                try:
                                    level = int(word.replace('$', '').replace(',', ''))
                                    upside_probs[level] = prob
                                except:
                                    pass
                    elif 'dip' in q:
                        for word in q.split():
                            if word.startswith('$'):
                                try:
                                    level = int(word.replace('$', '').replace(',', ''))
                                    downside_probs[level] = prob
                                except:
                                    pass

                if upside_probs:
                    print(f"\n  BTC Upside Odds (Jan):")
                    for level in sorted(upside_probs.keys()):
                        prob = upside_probs[level]
                        color = Colors.GREEN if prob > 20 else Colors.YELLOW if prob > 5 else Colors.RED
                        print(f"    ${level:,}: {color}{prob:.1f}%{Colors.END}")

                if downside_probs:
                    print(f"\n  BTC Downside Risk (Jan):")
                    for level in sorted(downside_probs.keys(), reverse=True):
                        prob = downside_probs[level]
                        color = Colors.RED if prob > 20 else Colors.YELLOW if prob > 5 else Colors.GREEN
                        print(f"    ${level:,}: {color}{prob:.1f}%{Colors.END}")

        print()

    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.END}")


def cmd_dexes(args):
    """List all HIP-3 dexes and their assets (fetched dynamically from API)."""
    # Get base info client
    base_info, config = setup_info(require_credentials=False, include_hip3=False)

    print(f"\n{Colors.BOLD}{Colors.CYAN}HIP-3 DEXES{Colors.END}")
    print("=" * 80)

    try:
        # Fetch all dexes from API
        all_dexes = base_info.perp_dexs()

        for dex_info in all_dexes:
            if dex_info is None:
                # Native perps (BTC, ETH, SOL, etc.)
                continue

            dex_name = dex_info.get('name', 'unknown')
            full_name = dex_info.get('fullName', dex_name)

            # Get assets from meta
            try:
                meta = base_info.meta(dex=dex_name)
                universe = meta.get('universe', [])
                assets = sorted([a.get('name', '').replace(f'{dex_name}:', '') for a in universe if a.get('name')])
                leverages = [a.get('maxLeverage', 0) for a in universe]
            except:
                # Fallback to assetToStreamingOiCap from dex info
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
    from datetime import datetime

    info, config = setup_info(require_credentials=True)

    print(f"\n{Colors.BOLD}{Colors.CYAN}TRADE HISTORY{Colors.END}")
    print("=" * 80)

    try:
        fills = info.user_fills(config['account_address'])

        if not fills:
            print("No trades found.")
            return

        # Limit results
        limit = args.limit if hasattr(args, 'limit') and args.limit else 20
        recent = fills[-limit:]

        print(f"{'Time':<18} {'Side':<6} {'Asset':<14} {'Size':>12} {'Price':>14} {'Value':>12}")
        print("-" * 80)

        for fill in reversed(recent):  # Most recent first
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
        description='Hyperliquid Trading Toolkit',
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
    leverage_parser = subparsers.add_parser('leverage', help='Set leverage for an asset')
    leverage_parser.add_argument('coin', help='Asset to set leverage for')
    leverage_parser.add_argument('leverage', type=int, help='Leverage multiplier (e.g., 5 for 5x)')
    leverage_parser.add_argument('--isolated', action='store_true', help='Use isolated margin (default: cross)')

    buy_parser = subparsers.add_parser('buy', help='Market buy')
    buy_parser.add_argument('coin', help='Asset to buy')
    buy_parser.add_argument('size', type=float, help='Size to buy')
    buy_parser.add_argument('--leverage', type=int, help='Set leverage before order (e.g., 5 for 5x)')
    buy_parser.add_argument('--isolated', action='store_true', help='Use isolated margin (default: cross)')

    sell_parser = subparsers.add_parser('sell', help='Market sell')
    sell_parser.add_argument('coin', help='Asset to sell')
    sell_parser.add_argument('size', type=float, help='Size to sell')
    sell_parser.add_argument('--leverage', type=int, help='Set leverage before order (e.g., 5 for 5x)')
    sell_parser.add_argument('--isolated', action='store_true', help='Use isolated margin (default: cross)')

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
    sl_parser.add_argument('trigger_price', type=float, help='Trigger price (market order fires when hit)')
    sl_parser.add_argument('--buy', action='store_true', help='Force buy side (for closing shorts)')

    tp_parser = subparsers.add_parser('take-profit', help='Place take-profit trigger order')
    tp_parser.add_argument('coin', help='Asset')
    tp_parser.add_argument('size', type=float, help='Size to close')
    tp_parser.add_argument('trigger_price', type=float, help='Trigger price (market order fires when hit)')
    tp_parser.add_argument('--buy', action='store_true', help='Force buy side (for closing shorts)')

    close_parser = subparsers.add_parser('close', help='Close position')
    close_parser.add_argument('coin', help='Asset to close')

    cancel_parser = subparsers.add_parser('cancel', help='Cancel order')
    cancel_parser.add_argument('oid', help='Order ID to cancel')

    subparsers.add_parser('cancel-all', help='Cancel all open orders')

    # Analysis commands
    analyze_parser = subparsers.add_parser('analyze', help='Comprehensive analysis with raw data')
    analyze_parser.add_argument('coins', nargs='*', help='Assets to analyze (default: BTC ETH SOL DOGE HYPE)')

    raw_parser = subparsers.add_parser('raw', help='Dump raw JSON data for an asset')
    raw_parser.add_argument('coin', help='Asset to dump data for')

    scan_parser = subparsers.add_parser('scan', help='Scan ALL assets for funding opportunities')
    scan_parser.add_argument('--min-volume', type=float, default=100000, help='Minimum 24h volume filter (default: 100000)')
    scan_parser.add_argument('--top', type=int, default=20, help='Number of top results to show (default: 20)')

    sentiment_parser = subparsers.add_parser('sentiment', help='Get Grok sentiment analysis for an asset')
    sentiment_parser.add_argument('coin', help='Asset to analyze sentiment for')

    hip3_parser = subparsers.add_parser('hip3', help='Get HIP-3 equity perp data (trade.xyz)')
    hip3_parser.add_argument('coin', nargs='?', help='HIP-3 asset (e.g., META, TSLA) - leave empty for all')

    polymarket_parser = subparsers.add_parser('polymarket', help='Get Polymarket prediction market data')
    polymarket_parser.add_argument('category', nargs='?', default='crypto',
                                   help='Category: crypto, btc, eth, trending, macro (default: crypto)')

    subparsers.add_parser('dexes', help='List all HIP-3 dexes and their assets')

    history_parser = subparsers.add_parser('history', help='Show trade history from API')
    history_parser.add_argument('--limit', type=int, default=20, help='Number of trades to show (default: 20)')

    unlocks_parser = subparsers.add_parser('unlocks', help='Check token unlock schedules')
    unlocks_parser.add_argument('coins', nargs='*', help='Tokens to check (default: current positions)')

    devcheck_parser = subparsers.add_parser('devcheck', help='Check developer sentiment and exodus signals')
    devcheck_parser.add_argument('coin', help='Protocol to check developer sentiment for')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Route to command handlers
    commands = {
        'status': cmd_status,
        'positions': cmd_positions,
        'orders': cmd_orders,
        'price': cmd_price,
        'funding': cmd_funding,
        'book': cmd_book,
        'leverage': cmd_leverage,
        'buy': cmd_buy,
        'sell': cmd_sell,
        'limit-buy': cmd_limit_buy,
        'limit-sell': cmd_limit_sell,
        'stop-loss': cmd_stop_loss,
        'take-profit': cmd_take_profit,
        'close': cmd_close,
        'cancel': cmd_cancel,
        'cancel-all': cmd_cancel_all,
        'analyze': cmd_analyze,
        'raw': cmd_raw,
        'scan': cmd_scan,
        'sentiment': cmd_sentiment,
        'hip3': cmd_hip3,
        'polymarket': cmd_polymarket,
        'dexes': cmd_dexes,
        'history': cmd_history,
        'unlocks': cmd_unlocks,
        'devcheck': cmd_devcheck,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
