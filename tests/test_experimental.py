"""
Experimental tests for HyperClaw CLI.

Tests for non-strict-list assets, low-liquidity pairs, and other experimental
features. These hit real mainnet APIs but are READ-ONLY (no trades).

WARNING: Don't run these frequently — some assets have low liquidity and
thin order books. Hammering their endpoints is unnecessary.

Run with:
    scripts/.venv/bin/python -m pytest tests/test_experimental.py -v -x --tb=short

These are excluded from the default test suite. Run explicitly when needed.
"""

import os
import time
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"
PYTHON_PATH = PROJECT_ROOT / "scripts" / ".venv" / "bin" / "python"

RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", "2"))


def run_cli(*args, timeout=30):
    """Run hyperliquid_tools.py against mainnet (no credentials)."""
    cmd = [str(PYTHON_PATH), str(SCRIPT_PATH)] + list(args)
    env = os.environ.copy()
    env["HL_TESTNET"] = "false"
    env.pop("HL_SECRET_KEY", None)
    env.pop("HL_API_WALLET_KEY", None)
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
# USDXL (Last USD) — not on strict list, low liquidity
# ============================================================================


class TestUSDXL:
    """USDXL swap support. Not on Hyperliquid's strict list, thin order book."""

    def test_swap_help_shows_usdxl(self):
        """swap --help should list USDXL as an option."""
        rc, out, err = run_cli("swap", "--help")
        assert rc == 0
        assert "USDXL" in out

    def test_usdxl_spot_price(self):
        """USDXL/USDC spot pair should return a price near $1."""
        rc, out, err = run_cli("price", "@152")
        assert rc == 0, f"failed: {err or out}"
        assert "$" in out

    def test_usdxl_book(self):
        """USDXL/USDC order book should have at least some levels."""
        rc, out, err = run_cli("book", "@152")
        assert rc == 0, f"failed: {err or out}"
        assert "Order Book" in out
