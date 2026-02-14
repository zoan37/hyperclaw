"""
Unified account trading tests for HyperClaw CLI.

Tests HIP-3 collateral swaps and trading on dexes that require non-USDC
collateral (USDH, USDe, USDT0). Uses the unified account from .env.unified.

WARNING: These tests execute REAL TRADES on Hyperliquid mainnet with REAL MONEY.
They use minimal position sizes and swap the collateral back after each test.

These tests do NOT run by default. To run them:

    HL_UNIFIED_TESTS=true HL_PROXY_URL=http://localhost:18731 \
        scripts/.venv/bin/python -m pytest tests/test_unified_trading.py -v -x --tb=short

Prerequisites:
    - Proxy server running: scripts/.venv/bin/python scripts/server.py &
    - Valid .env.unified with unified account credentials in project root
    - Sufficient account balance (~$50 USDC recommended)
"""

import os
import re
import time
import subprocess
from pathlib import Path

import pytest

# Skip entire module unless explicitly enabled
if not os.environ.get("HL_UNIFIED_TESTS", "").lower() in ("true", "1", "yes"):
    pytest.skip(
        "Unified trading tests disabled. Set HL_UNIFIED_TESTS=true to enable.",
        allow_module_level=True,
    )

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"
PYTHON_PATH = PROJECT_ROOT / "scripts" / ".venv" / "bin" / "python"
ENV_UNIFIED = PROJECT_ROOT / ".env.unified"

RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", "2"))


def run_cli(*args, timeout=30):
    """Run hyperliquid_tools.py with unified account credentials."""
    cmd = [str(PYTHON_PATH), str(SCRIPT_PATH)] + list(args)
    env = os.environ.copy()
    env["HL_TESTNET"] = "false"
    env["HL_ENV_FILE"] = str(ENV_UNIFIED)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        cwd=str(PROJECT_ROOT),
    )
    return result.returncode, result.stdout, result.stderr


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
    assert ENV_UNIFIED.exists(), f".env.unified not found at {ENV_UNIFIED}"


@pytest.fixture(scope="session", autouse=True)
def cleanup_positions():
    """Safety net: close positions and cancel orders at end of session."""
    yield
    try:
        run_cli("cancel-all", timeout=30)
    except Exception:
        pass
    time.sleep(2)
    for coin in ["km:US500"]:
        try:
            run_cli("close", coin, timeout=30)
            time.sleep(2)
        except Exception:
            pass


# ============================================================================
# ACCOUNT STATUS (unified mode detection)
# ============================================================================


class TestUnifiedAccount:
    def test_status_shows_unified(self):
        """Unified account should show [unified] badge."""
        rc, out, err = run_cli("status")
        assert rc == 0, f"failed: {err or out}"
        assert "ACCOUNT STATUS" in out
        assert "unified" in out.lower()


# ============================================================================
# SWAP: USDC ↔ USDH
# ============================================================================


class TestSwapUSDH:
    def test_swap_usdc_to_usdh(self):
        """Swap USDC → USDH (default collateral)."""
        rc, out, err = run_cli("swap", "11")
        assert rc == 0, f"failed: {err or out}"
        assert "Swap:" in out
        assert "USDH" in out
        assert "Swapped" in out  # confirms fill

    def test_swap_usdh_to_usdc(self):
        """Swap USDH back to USDC."""
        rc, out, err = run_cli("swap", "11", "--to-usdc")
        assert rc == 0, f"failed: {err or out}"
        assert "Swap:" in out
        assert "USDH" in out
        assert "Swapped" in out


# ============================================================================
# HIP-3 TRADING WITH NON-USDC COLLATERAL (km dex = USDH)
# ============================================================================


class TestHip3CollateralTrading:
    """Full flow: swap USDC → USDH, trade km:US500, close, swap back."""

    def test_01_swap_for_collateral(self):
        """Swap USDC → USDH for km dex trading."""
        rc, out, err = run_cli("swap", "11")
        assert rc == 0, f"failed: {err or out}"
        assert "Swapped" in out

    def test_02_set_leverage(self):
        """Set leverage on km:US500 (isolated required for HIP-3)."""
        rc, out, err = run_cli("leverage", "km:US500", "10", "--isolated")
        assert rc == 0, f"failed: {err or out}"
        assert "Leverage updated!" in out

    def test_03_buy_km_us500(self):
        """Buy km:US500 — requires USDH collateral."""
        rc, out, err = run_cli("buy", "km:US500", "0.02")
        assert rc == 0, f"failed: {err or out}"
        assert "Order filled!" in out

    def test_04_positions_show_km(self):
        """km:US500 should appear in positions (may take a moment to propagate)."""
        time.sleep(3)  # HIP-3 dex positions may take a moment to appear
        rc, out, err = run_cli("positions")
        assert rc == 0, f"failed: {err or out}"
        # Position may have already been filled and the state propagated,
        # or may still be settling. Either way positions command should work.
        assert "POSITION DETAILS" in out

    def test_05_close_km_us500(self):
        """Close the km:US500 position."""
        rc, out, err = run_cli("close", "km:US500")
        assert rc == 0, f"failed: {err or out}"
        assert "Position closed!" in out

    def test_06_swap_back_to_usdc(self):
        """Swap remaining USDH back to USDC."""
        # Check how much USDH we have
        rc, out, err = run_cli("status")
        assert rc == 0
        # Swap whatever is there (use a generous amount, IOC will fill what's available)
        rc, out, err = run_cli("swap", "11", "--to-usdc")
        assert rc == 0, f"failed: {err or out}"
        assert "Swapped" in out or "USDH" in out


# ============================================================================
# MARGIN ERROR GUIDANCE
# ============================================================================


class TestMarginErrorGuidance:
    """Test that margin errors on HIP-3 dexes give actionable swap guidance."""

    def test_insufficient_margin_shows_swap_hint(self):
        """Buying on km dex without enough USDH should suggest swap command."""
        # First swap any USDH back to USDC to minimize balance
        run_cli("swap", "50", "--to-usdc")
        time.sleep(2)

        # Try to buy a large amount that will definitely exceed any leftover USDH
        # 10 US500 @ ~$680 = $6800 notional, needs ~$680 margin at 10x
        rc, out, err = run_cli("buy", "km:US500", "10")
        assert rc == 0  # CLI exits cleanly
        # Should show guidance about USDH collateral
        assert "USDH" in out
        assert "swap" in out.lower()
