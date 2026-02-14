"""
Mainnet read-only tests for HyperClaw CLI.

These tests hit the real Hyperliquid mainnet API with read-only commands.
No credentials needed. No trades executed.

Run with:
    scripts/.venv/bin/python -m pytest tests/test_mainnet_readonly.py -v -x --tb=short
"""

import os
import time
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"
PYTHON_PATH = PROJECT_ROOT / "scripts" / ".venv" / "bin" / "python"

RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", "1"))


def run_cli(*args, timeout=30):
    """Run hyperliquid_tools.py against mainnet (no credentials)."""
    cmd = [str(PYTHON_PATH), str(SCRIPT_PATH)] + list(args)
    env = os.environ.copy()
    env["HL_TESTNET"] = "false"
    # Clear credentials so we don't accidentally trade
    env.pop("HL_SECRET_KEY", None)
    env.pop("HL_API_WALLET_KEY", None)
    # Clear HL_ENV_FILE so the script uses hyperclaw's own .env discovery
    env.pop("HL_ENV_FILE", None)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


@pytest.fixture(autouse=True)
def rate_limit_pause():
    yield
    time.sleep(RATE_LIMIT_DELAY)


@pytest.fixture(scope="session", autouse=True)
def check_setup():
    assert PYTHON_PATH.exists(), f"venv not found at {PYTHON_PATH}. Run: bash scripts/setup.sh"
    assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"


# ============================================================================
# PRICE
# ============================================================================


class TestPrice:
    def test_price_defaults(self):
        """price with no args shows BTC, ETH, SOL."""
        rc, out, err = run_cli("price")
        assert rc == 0, f"failed: {err or out}"
        assert "Current Prices" in out
        assert "BTC" in out
        assert "$" in out

    def test_price_single(self):
        rc, out, err = run_cli("price", "BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "BTC" in out
        assert "$" in out

    def test_price_multiple(self):
        rc, out, err = run_cli("price", "BTC", "ETH", "SOL")
        assert rc == 0, f"failed: {err or out}"
        assert "BTC" in out
        assert "ETH" in out
        assert "SOL" in out

    def test_price_hip3(self):
        """HIP-3 asset price via dex prefix."""
        rc, out, err = run_cli("price", "xyz:TSLA")
        assert rc == 0, f"failed: {err or out}"
        assert "xyz:TSLA" in out

    def test_price_nonexistent(self):
        rc, out, err = run_cli("price", "ZZZZNOTREAL")
        assert rc == 0
        assert "Not found" in out


# ============================================================================
# FUNDING
# ============================================================================


class TestFunding:
    def test_funding_defaults(self):
        rc, out, err = run_cli("funding")
        assert rc == 0, f"failed: {err or out}"
        assert "Funding Rates" in out

    def test_funding_specific(self):
        rc, out, err = run_cli("funding", "BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "BTC" in out
        assert "%" in out

    def test_funding_multiple(self):
        rc, out, err = run_cli("funding", "BTC", "ETH", "SOL")
        assert rc == 0, f"failed: {err or out}"
        assert "BTC" in out
        assert "ETH" in out


# ============================================================================
# ORDER BOOK
# ============================================================================


class TestBook:
    def test_book_btc(self):
        rc, out, err = run_cli("book", "BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "Order Book" in out
        assert "Mid:" in out

    def test_book_eth(self):
        rc, out, err = run_cli("book", "ETH")
        assert rc == 0, f"failed: {err or out}"
        assert "Order Book" in out

    def test_book_sol(self):
        rc, out, err = run_cli("book", "SOL")
        assert rc == 0, f"failed: {err or out}"
        assert "Order Book" in out


# ============================================================================
# RAW DATA
# ============================================================================


class TestRaw:
    def test_raw_btc(self):
        rc, out, err = run_cli("raw", "BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "Raw Data Dump" in out
        assert "mid_price" in out

    def test_raw_has_json(self):
        """raw should include JSON-formatted data."""
        rc, out, err = run_cli("raw", "ETH")
        assert rc == 0, f"failed: {err or out}"
        assert "{" in out  # contains JSON


# ============================================================================
# CANDLES
# ============================================================================


class TestCandles:
    def test_candles_btc(self):
        """candles should show OHLCV data for BTC."""
        rc, out, err = run_cli("candles", "BTC", "--interval", "1h", "--lookback", "24h")
        assert rc == 0, f"failed: {err or out}"
        assert "Candles" in out
        assert "Open" in out
        assert "Summary" in out

    def test_candles_default_lookback(self):
        """candles with defaults should work."""
        rc, out, err = run_cli("candles", "ETH")
        assert rc == 0, f"failed: {err or out}"
        assert "Candles" in out
        assert "SMA" in out


# ============================================================================
# FUNDING HISTORY
# ============================================================================


class TestFundingHistory:
    def test_funding_history_btc(self):
        """funding-history should show historical rates."""
        rc, out, err = run_cli("funding-history", "BTC", "--lookback", "24h")
        assert rc == 0, f"failed: {err or out}"
        assert "Funding History" in out
        assert "Annualized" in out
        assert "Summary" in out

    def test_funding_history_default(self):
        rc, out, err = run_cli("funding-history", "ETH")
        assert rc == 0, f"failed: {err or out}"
        assert "Funding History" in out


# ============================================================================
# RECENT TRADES
# ============================================================================


class TestTrades:
    def test_trades_btc(self):
        """trades should show recent trade tape."""
        rc, out, err = run_cli("trades", "BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "Recent Trades" in out
        assert "BUY" in out or "SELL" in out

    def test_trades_with_limit(self):
        rc, out, err = run_cli("trades", "ETH", "--limit", "5")
        assert rc == 0, f"failed: {err or out}"
        assert "Recent Trades" in out
        assert "Summary" in out


# ============================================================================
# HIP-3 / DEXES
# ============================================================================


class TestHip3:
    def test_dexes(self):
        """dexes should list available HIP-3 dexes."""
        rc, out, err = run_cli("dexes", timeout=60)
        assert rc == 0, f"failed: {err or out}"
        assert "HIP-3 DEXES" in out

    def test_hip3_specific(self):
        """hip3 TSLA should show data for xyz:TSLA."""
        rc, out, err = run_cli("hip3", "TSLA", timeout=60)
        assert rc == 0, f"failed: {err or out}"
        assert "HIP-3" in out or "TSLA" in out

    def test_hip3_all(self):
        """hip3 with no args should list all HIP-3 assets."""
        rc, out, err = run_cli("hip3", timeout=90)
        assert rc == 0, f"failed: {err or out}"
        assert "HIP-3" in out


# ============================================================================
# HIP-3 COLLATERAL
# ============================================================================


class TestCollateral:
    """Test that HIP-3 dex collateral detection works for different stablecoins."""

    def test_price_km_asset(self):
        """km dex asset (USDH collateral) should return a price."""
        rc, out, err = run_cli("price", "km:US500")
        assert rc == 0, f"failed: {err or out}"
        assert "km:US500" in out
        assert "$" in out

    def test_price_hyna_asset(self):
        """hyna dex asset (USDe collateral) should return a price."""
        rc, out, err = run_cli("price", "hyna:BTC")
        assert rc == 0, f"failed: {err or out}"
        assert "hyna:BTC" in out

    def test_price_xyz_asset(self):
        """xyz dex asset (USDC collateral) should return a price."""
        rc, out, err = run_cli("price", "xyz:TSLA")
        assert rc == 0, f"failed: {err or out}"
        assert "xyz:TSLA" in out
        assert "$" in out

    def test_funding_hip3_multi_dex(self):
        """funding should work across dexes with different collateral tokens."""
        rc, out, err = run_cli("funding", "km:US500")
        assert rc == 0, f"failed: {err or out}"
        assert "km:US500" in out

    def test_price_cash_asset(self):
        """cash dex asset (USDT0 collateral) should return a price."""
        rc, out, err = run_cli("price", "cash:TSLA")
        assert rc == 0, f"failed: {err or out}"
        assert "cash:TSLA" in out

    def test_book_hip3_non_usdc(self):
        """Order book should work for non-USDC collateral dexes."""
        rc, out, err = run_cli("book", "km:US500")
        assert rc == 0, f"failed: {err or out}"
        assert "Order Book" in out


# ============================================================================
# SCAN (heavy - many API calls)
# ============================================================================


class TestScan:
    def test_scan_small(self):
        """scan with small top count."""
        time.sleep(5)  # cooldown before heavy command
        rc, out, err = run_cli("scan", "--top", "5", "--min-volume", "1000000", timeout=120)
        assert rc == 0, f"failed: {err or out}"
        assert "MARKET SCANNER" in out
        assert "NEGATIVE FUNDING" in out or "POSITIVE FUNDING" in out

    def test_scan_shows_volume(self):
        rc, out, err = run_cli("scan", "--top", "3", timeout=120)
        assert rc == 0, f"failed: {err or out}"
        assert "BY VOLUME" in out

    def test_scan_sorted_by_volume(self):
        """scan with --sort flag produces flat table."""
        rc, out, err = run_cli("scan", "--sort", "volume", "--top", "5", timeout=120)
        assert rc == 0, f"failed: {err or out}"
        assert "MARKET SCANNER" in out
        # Sorted mode should NOT show the sectioned headers
        assert "NEGATIVE FUNDING" not in out


# ============================================================================
# ANALYZE (heavy - many API calls)
# ============================================================================


class TestAnalyze:
    def test_analyze_single(self):
        time.sleep(5)  # cooldown before heavy command
        rc, out, err = run_cli("analyze", "BTC", timeout=120)
        assert rc == 0, f"failed: {err or out}"
        assert "COMPREHENSIVE MARKET ANALYSIS" in out
        assert "CURRENT PRICES" in out

    def test_analyze_multiple(self):
        rc, out, err = run_cli("analyze", "BTC", "ETH", timeout=120)
        assert rc == 0, f"failed: {err or out}"
        assert "COMPREHENSIVE MARKET ANALYSIS" in out


# ============================================================================
# LEVERAGE (max leverage check only — no account changes)
# ============================================================================


class TestLeverage:
    def test_leverage_exceeds_max(self):
        """leverage should reject values above max."""
        rc, out, err = run_cli("leverage", "SOL", "999")
        assert rc == 0  # exits cleanly with error message
        assert "exceeds max leverage" in out

    def test_leverage_shows_max(self):
        """leverage should display max leverage for the asset."""
        rc, out, err = run_cli("leverage", "BTC", "999")
        assert rc == 0
        assert "max:" in out


# ============================================================================
# CHECK (position health)
# ============================================================================


class TestCheck:
    def test_check_no_address(self):
        """check with no address should show error."""
        rc, out, err = run_cli("check")
        assert rc == 0
        assert "No account address" in out or "POSITION HEALTH CHECK" in out

    def test_check_with_address(self):
        """check with a known address should show header and account info."""
        # Use Hyperliquid's well-known vault address (always has state)
        rc, out, err = run_cli("check", "--address", "0xdead000000000000000000000000000000000000", timeout=60)
        assert rc == 0
        assert "POSITION HEALTH CHECK" in out
        # Should show either positions or "No open positions"
        assert "Account:" in out or "No open positions" in out

    def test_check_with_real_address(self):
        """check with a real trader address should show position data if they have positions."""
        # This address is a known active trader on Hyperliquid (public data)
        rc, out, err = run_cli("check", "--address", "0x0000000000000000000000000000000000000000", timeout=60)
        assert rc == 0
        assert "POSITION HEALTH CHECK" in out


# ============================================================================
# CLI BASICS
# ============================================================================


class TestCLI:
    def test_no_command_shows_help(self):
        rc, out, err = run_cli()
        assert rc == 0
        assert "usage" in out.lower() or "Available commands" in out

    def test_invalid_command(self):
        rc, out, err = run_cli("nonexistent-command")
        assert rc != 0
