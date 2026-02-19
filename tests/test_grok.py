"""
Tests for Grok-powered commands: ask, search, sentiment.

These hit the real xAI (Grok) API. Requires XAI_API_KEY in .env.
Excluded from default test suite — run explicitly:

    scripts/.venv/bin/python -m pytest tests/test_grok.py -v -x --tb=short

Tests verify:
- The `ask` command works with both tools in a single call
- The `search` command works (web + X, web-only, X-only)
- The `sentiment` command returns structured output
- The shared _grok_call helper handles errors gracefully
"""

import os
import time
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"
PYTHON_PATH = PROJECT_ROOT / "scripts" / ".venv" / "bin" / "python"

RATE_LIMIT_DELAY = int(os.environ.get("RATE_LIMIT_DELAY", "3"))


def run_cli(*args, timeout=90):
    """Run hyperliquid_tools.py with Grok commands."""
    cmd = [str(PYTHON_PATH), str(SCRIPT_PATH)] + list(args)
    env = os.environ.copy()
    env["HL_TESTNET"] = "false"
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


class TestAskCommand:
    """Tests for the new `ask` command (both tools in one call)."""

    def test_ask_basic(self):
        """ask returns a response using auto-selected tools."""
        rc, out, err = run_cli("ask", "What is the current price of Bitcoin?")
        assert rc == 0
        assert "ASK GROK:" in out
        # Should contain some price-related content
        assert len(out) > 100

    def test_ask_web_only(self):
        """ask --web restricts to web search only."""
        rc, out, err = run_cli("ask", "--web", "What is Ethereum?")
        assert rc == 0
        assert "ASK GROK:" in out

    def test_ask_x_only(self):
        """ask --x restricts to X/Twitter search only."""
        rc, out, err = run_cli("ask", "--x", "What are traders saying about BTC?")
        assert rc == 0
        assert "ASK GROK:" in out

    def test_ask_risk_check_clean(self):
        """ask can do a risk assessment and return clean results."""
        rc, out, err = run_cli(
            "ask",
            "Is BTC (Bitcoin) being delisted from any exchange, undergoing "
            "a token swap, been hacked, or facing regulatory action? Be concise."
        )
        assert rc == 0
        # Bitcoin shouldn't have any of these issues
        assert "ASK GROK:" in out
        out_lower = out.lower()
        # Should indicate no issues (exact wording varies)
        assert any(word in out_lower for word in ["no", "not", "none"])


class TestSearchCommand:
    """Tests for the refactored search command."""

    def test_search_both(self):
        """search queries both web and X."""
        rc, out, err = run_cli("search", "Hyperliquid DEX latest news")
        assert rc == 0
        assert "SEARCH:" in out
        assert "Web:" in out

    def test_search_web_only(self):
        """search --web skips X/Twitter."""
        rc, out, err = run_cli("search", "--web", "Solana ecosystem")
        assert rc == 0
        assert "Web:" in out
        assert "X/Twitter:" not in out

    def test_search_x_only(self):
        """search --x skips web search."""
        rc, out, err = run_cli("search", "--x", "crypto market sentiment")
        assert rc == 0
        assert "X/Twitter:" in out
        assert "Web:" not in out


class TestSentimentCommand:
    """Tests for the refactored sentiment command."""

    def test_sentiment_native(self):
        """sentiment works for a native perp asset."""
        rc, out, err = run_cli("sentiment", "BTC")
        assert rc == 0
        assert "SENTIMENT ANALYSIS:" in out
        assert "Web Search" in out
        assert "X/Twitter" in out

    def test_sentiment_hip3(self):
        """sentiment works for a HIP-3 asset."""
        rc, out, err = run_cli("sentiment", "xyz:SNDK")
        assert rc == 0
        assert "SENTIMENT ANALYSIS:" in out


class TestGrokCallHelper:
    """Tests that verify the _grok_call shared helper behavior via CLI."""

    def test_ask_returns_content(self):
        """Verify ask actually returns meaningful content, not empty."""
        rc, out, err = run_cli("ask", "What day of the week is it today?")
        assert rc == 0
        # Strip ANSI and headers, check there's real content
        import re
        clean = re.sub(r'\033\[[0-9;]*m', '', out)
        # Remove the header lines
        lines = [l for l in clean.split('\n') if l.strip() and 'ASK GROK' not in l and '===' not in l]
        assert len(lines) > 0, "Expected meaningful content in response"
