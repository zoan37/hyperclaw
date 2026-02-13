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
