"""
Mainnet trading integration tests for HyperClaw CLI.

⚠️  WARNING: These tests execute REAL TRADES on Hyperliquid mainnet with REAL MONEY.
    They use minimal position sizes to keep costs low, but they ARE spending real funds.

These tests do NOT run by default. To run them:

    HL_TRADING_TESTS=true HL_PROXY_URL=http://localhost:18731 \
        scripts/.venv/bin/python -m pytest tests/test_mainnet_trading.py -v -x --tb=short

Prerequisites:
    - Proxy server running: scripts/.venv/bin/python scripts/server.py &
    - Valid .env with credentials in project root
    - Sufficient account balance (~$500 recommended)
"""

import os
import re
import time
import subprocess
from pathlib import Path

import pytest

# Skip entire module unless explicitly enabled
if not os.environ.get("HL_TRADING_TESTS", "").lower() in ("true", "1", "yes"):
    pytest.skip(
        "Trading tests disabled. Set HL_TRADING_TESTS=true to enable.",
        allow_module_level=True,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"
PYTHON_PATH = PROJECT_ROOT / "scripts" / ".venv" / "bin" / "python"

RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", "2"))


def run_cli(*args, timeout=30):
    """Run hyperliquid_tools.py against mainnet WITH credentials."""
    cmd = [str(PYTHON_PATH), str(SCRIPT_PATH)] + list(args)
    env = os.environ.copy()
    env["HL_TESTNET"] = "false"
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


def parse_oid(output):
    """Extract OID from CLI output."""
    match = re.search(r"OID:\s*(\d+)", output)
    return int(match.group(1)) if match else None


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def rate_limit_pause():
    yield
    time.sleep(RATE_LIMIT_DELAY)


@pytest.fixture(scope="session", autouse=True)
def check_setup():
    assert PYTHON_PATH.exists(), f"venv not found at {PYTHON_PATH}. Run: bash scripts/setup.sh"
    assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"


@pytest.fixture(scope="session", autouse=True)
def cleanup_positions():
    """Safety net: close all positions and cancel all orders at end of session."""
    yield
    # Cancel all open orders
    try:
        run_cli("cancel-all", timeout=30)
    except Exception:
        pass
    time.sleep(2)
    # Close any remaining positions
    try:
        rc, out, _ = run_cli("positions", timeout=30)
        if rc == 0 and "No open positions" not in out:
            # Extract asset names from position output
            for coin in re.findall(r"^\x1b\[1m(\S+)\x1b\[0m", out, re.MULTILINE):
                try:
                    run_cli("close", coin, timeout=30)
                    time.sleep(2)
                except Exception:
                    pass
            # Also try common assets we test with
            for coin in ["SOL", "xyz:TSLA"]:
                try:
                    run_cli("close", coin, timeout=30)
                    time.sleep(2)
                except Exception:
                    pass
    except Exception:
        pass


# ============================================================================
# ACCOUNT READS (credential-required)
# ============================================================================


class TestAccountReads:
    def test_status(self):
        """status should show account summary with portfolio value."""
        rc, out, err = run_cli("status")
        assert rc == 0, f"failed: {err or out}"
        assert "ACCOUNT STATUS" in out
        assert "Account Summary" in out
        assert "Portfolio Value" in out

    def test_positions(self):
        """positions should show position details or 'No open positions'."""
        rc, out, err = run_cli("positions")
        assert rc == 0, f"failed: {err or out}"
        assert "POSITION DETAILS" in out

    def test_orders(self):
        """orders should show open orders list."""
        rc, out, err = run_cli("orders")
        assert rc == 0, f"failed: {err or out}"
        assert "Open Orders" in out

    def test_portfolio(self):
        """portfolio should show performance data."""
        rc, out, err = run_cli("portfolio")
        assert rc == 0, f"failed: {err or out}"
        assert "Portfolio Performance" in out

    def test_user_funding(self):
        """user-funding should succeed (may have no data)."""
        rc, out, err = run_cli("user-funding")
        assert rc == 0, f"failed: {err or out}"


# ============================================================================
# LEVERAGE
# ============================================================================


class TestLeverage:
    def test_set_leverage_native(self):
        """Set leverage on a native asset."""
        rc, out, err = run_cli("leverage", "SOL", "3")
        assert rc == 0, f"failed: {err or out}"
        assert "Leverage updated!" in out

    def test_set_leverage_hip3(self):
        """Set leverage on a HIP-3 asset with isolated margin."""
        rc, out, err = run_cli("leverage", "xyz:TSLA", "3", "--isolated")
        assert rc == 0, f"failed: {err or out}"
        assert "Leverage updated!" in out


# ============================================================================
# NATIVE TRADING (SOL)
# ============================================================================


class TestNativeTrading:
    oid = None  # shared between methods for limit order tracking

    def test_buy_sol(self):
        """Market buy SOL."""
        rc, out, err = run_cli("buy", "SOL", "0.2")
        assert rc == 0, f"failed: {err or out}"
        assert "Order filled!" in out
        oid = parse_oid(out)
        assert oid is not None, f"No OID in output: {out}"

    def test_positions_after_buy(self):
        """SOL should appear in positions after buy."""
        rc, out, err = run_cli("positions")
        assert rc == 0, f"failed: {err or out}"
        assert "SOL" in out
        assert "POSITION DETAILS" in out

    def test_limit_sell_sol(self):
        """Place a limit sell far above market (won't fill)."""
        # Get current price to set limit far above
        rc, out, _ = run_cli("price", "SOL")
        assert rc == 0
        price_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", out)
        assert price_match, f"Could not parse SOL price from: {out}"
        current_price = float(price_match.group(1).replace(",", ""))
        limit_price = round(current_price * 1.50, 2)  # 50% above market

        rc, out, err = run_cli("limit-sell", "SOL", "0.2", str(limit_price))
        assert rc == 0, f"failed: {err or out}"
        assert "Order placed!" in out
        TestNativeTrading.oid = parse_oid(out)
        assert TestNativeTrading.oid is not None, f"No OID in output: {out}"

    def test_orders_shows_limit(self):
        """Limit order should be visible in orders."""
        rc, out, err = run_cli("orders")
        assert rc == 0, f"failed: {err or out}"
        assert "Open Orders" in out
        assert "SOL" in out

    def test_modify_order(self):
        """Modify the limit order price."""
        assert TestNativeTrading.oid is not None, "No OID from limit-sell test"

        # Get current price to set new limit
        rc, out, _ = run_cli("price", "SOL")
        assert rc == 0
        price_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", out)
        assert price_match, f"Could not parse SOL price from: {out}"
        current_price = float(price_match.group(1).replace(",", ""))
        new_limit = round(current_price * 1.55, 2)  # 55% above market

        rc, out, err = run_cli(
            "modify-order", str(TestNativeTrading.oid), str(new_limit)
        )
        assert rc == 0, f"failed: {err or out}"
        assert "Order modified!" in out
        # Modify creates a new order — update the OID for cancel test
        new_oid = parse_oid(out)
        if new_oid is not None:
            TestNativeTrading.oid = new_oid

    def test_cancel_order(self):
        """Cancel the limit order."""
        assert TestNativeTrading.oid is not None, "No OID from limit-sell test"

        rc, out, err = run_cli("cancel", str(TestNativeTrading.oid))
        assert rc == 0, f"failed: {err or out}"
        assert "Order canceled!" in out

    def test_close_sol(self):
        """Close the SOL position."""
        rc, out, err = run_cli("close", "SOL")
        assert rc == 0, f"failed: {err or out}"
        assert "Position closed!" in out


# ============================================================================
# HIP-3 TRADING (xyz:TSLA)
# ============================================================================


class TestHip3Trading:
    def test_set_leverage_tsla(self):
        """Set leverage before trading."""
        rc, out, err = run_cli("leverage", "xyz:TSLA", "3", "--isolated")
        assert rc == 0, f"failed: {err or out}"
        assert "Leverage updated!" in out

    def test_buy_tsla(self):
        """Market buy TSLA HIP-3 perp."""
        rc, out, err = run_cli("buy", "xyz:TSLA", "1", "--leverage", "3", "--isolated")
        assert rc == 0, f"failed: {err or out}"
        assert "Order filled!" in out

    def test_close_tsla(self):
        """Close the TSLA position."""
        rc, out, err = run_cli("close", "xyz:TSLA")
        assert rc == 0, f"failed: {err or out}"
        assert "Position closed!" in out


# ============================================================================
# TRIGGER ORDERS (stop-loss / take-profit)
# ============================================================================


class TestTriggerOrders:
    sl_oid = None
    tp_oid = None

    def test_buy_for_triggers(self):
        """Buy SOL to have a position for trigger orders."""
        rc, out, err = run_cli("buy", "SOL", "0.2")
        assert rc == 0, f"failed: {err or out}"
        assert "Order filled!" in out

    def test_stop_loss(self):
        """Place stop-loss far below market."""
        rc, out, _ = run_cli("price", "SOL")
        assert rc == 0
        price_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", out)
        assert price_match, f"Could not parse SOL price from: {out}"
        current_price = float(price_match.group(1).replace(",", ""))
        sl_price = round(current_price * 0.50, 2)  # 50% below market

        rc, out, err = run_cli("stop-loss", "SOL", "0.2", str(sl_price))
        assert rc == 0, f"failed: {err or out}"
        assert "Stop-loss placed!" in out
        TestTriggerOrders.sl_oid = parse_oid(out)
        assert TestTriggerOrders.sl_oid is not None, f"No OID in output: {out}"

    def test_take_profit(self):
        """Place take-profit far above market."""
        rc, out, _ = run_cli("price", "SOL")
        assert rc == 0
        price_match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", out)
        assert price_match, f"Could not parse SOL price from: {out}"
        current_price = float(price_match.group(1).replace(",", ""))
        tp_price = round(current_price * 1.50, 2)  # 50% above market

        rc, out, err = run_cli("take-profit", "SOL", "0.2", str(tp_price))
        assert rc == 0, f"failed: {err or out}"
        assert "Take-profit placed!" in out
        TestTriggerOrders.tp_oid = parse_oid(out)
        assert TestTriggerOrders.tp_oid is not None, f"No OID in output: {out}"

    def test_cancel_all(self):
        """Cancel all open orders (including triggers)."""
        rc, out, err = run_cli("cancel-all")
        assert rc == 0, f"failed: {err or out}"
        assert "Done!" in out

    def test_close_after_triggers(self):
        """Close SOL position after trigger tests."""
        rc, out, err = run_cli("close", "SOL")
        assert rc == 0, f"failed: {err or out}"
        assert "Position closed!" in out
