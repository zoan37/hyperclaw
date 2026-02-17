"""
Unit tests for stop-loss / take-profit trigger logic.

These tests are pure logic checks using mocked Info/Exchange objects.
No network calls. No real trades.
"""

from pathlib import Path
import importlib.util
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_PATH = PROJECT_ROOT / "scripts" / "hyperliquid_tools.py"

spec = importlib.util.spec_from_file_location("hyperliquid_tools", TOOLS_PATH)
tools = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(tools)


class FakeInfo:
    def __init__(self, positions_by_dex, mids_by_dex):
        self._positions_by_dex = positions_by_dex
        self._mids_by_dex = mids_by_dex
        self.mid_calls = []

    def user_state(self, _address, dex=""):
        positions = self._positions_by_dex.get(dex, [])
        return {"assetPositions": [{"position": p} for p in positions]}

    def all_mids(self, dex=""):
        self.mid_calls.append(dex)
        return self._mids_by_dex.get(dex, {})


class FakeExchange:
    def __init__(self):
        self.order_calls = []

    def order(self, coin, is_buy, size, trigger_price, order_type, reduce_only=False):
        self.order_calls.append(
            {
                "coin": coin,
                "is_buy": is_buy,
                "size": size,
                "trigger_price": trigger_price,
                "order_type": order_type,
                "reduce_only": reduce_only,
            }
        )
        return {
            "status": "ok",
            "response": {"data": {"statuses": [{"resting": {"oid": 12345}}]}},
        }


def _run_trigger(monkeypatch, command, coin, position_size, trigger_price, size, current_price, capsys):
    dex = coin.split(":", 1)[0] if ":" in coin else ""
    positions_by_dex = {dex: [{"coin": coin, "szi": str(position_size)}]}
    mids_by_dex = {dex: {coin: str(current_price)}} if current_price is not None else {dex: {}}

    exchange = FakeExchange()
    info = FakeInfo(positions_by_dex, mids_by_dex)
    config = {"account_address": "0xabc", "is_testnet": False}

    monkeypatch.setattr(tools, "setup_exchange", lambda **_kwargs: (exchange, info, config))
    monkeypatch.setattr(tools, "_invalidate_proxy_cache", lambda _cfg: None)

    args = SimpleNamespace(coin=coin, size=size, trigger_price=trigger_price, buy=False)
    if command == "sl":
        tools.cmd_stop_loss(args)
    else:
        tools.cmd_take_profit(args)

    out = capsys.readouterr().out
    return exchange, info, out


def test_stop_loss_long_closes_with_sell(monkeypatch, capsys):
    exchange, _info, _out = _run_trigger(
        monkeypatch,
        command="sl",
        coin="BTC",
        position_size=1.0,
        trigger_price=90.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 1
    call = exchange.order_calls[0]
    assert call["is_buy"] is False
    assert call["reduce_only"] is True
    assert call["order_type"]["trigger"]["tpsl"] == "sl"


def test_stop_loss_short_closes_with_buy(monkeypatch, capsys):
    exchange, _info, _out = _run_trigger(
        monkeypatch,
        command="sl",
        coin="BTC",
        position_size=-1.0,
        trigger_price=110.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 1
    assert exchange.order_calls[0]["is_buy"] is True


def test_take_profit_long_closes_with_sell(monkeypatch, capsys):
    exchange, _info, _out = _run_trigger(
        monkeypatch,
        command="tp",
        coin="BTC",
        position_size=1.0,
        trigger_price=110.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 1
    call = exchange.order_calls[0]
    assert call["is_buy"] is False
    assert call["order_type"]["trigger"]["tpsl"] == "tp"


def test_take_profit_short_closes_with_buy(monkeypatch, capsys):
    exchange, _info, _out = _run_trigger(
        monkeypatch,
        command="tp",
        coin="BTC",
        position_size=-1.0,
        trigger_price=90.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 1
    assert exchange.order_calls[0]["is_buy"] is True


def test_stop_loss_invalid_trigger_for_long_rejected(monkeypatch, capsys):
    exchange, _info, out = _run_trigger(
        monkeypatch,
        command="sl",
        coin="BTC",
        position_size=1.0,
        trigger_price=110.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 0
    assert "LONG stop-loss" in out


def test_take_profit_invalid_trigger_for_short_rejected(monkeypatch, capsys):
    exchange, _info, out = _run_trigger(
        monkeypatch,
        command="tp",
        coin="BTC",
        position_size=-1.0,
        trigger_price=110.0,
        size=0.5,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 0
    assert "SHORT take-profit" in out


def test_trigger_size_exceeding_position_rejected(monkeypatch, capsys):
    exchange, _info, out = _run_trigger(
        monkeypatch,
        command="sl",
        coin="BTC",
        position_size=0.5,
        trigger_price=90.0,
        size=1.0,
        current_price=100.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 0
    assert "exceeds open position size" in out


def test_hip3_trigger_uses_dex_price_lookup(monkeypatch, capsys):
    exchange, info, _out = _run_trigger(
        monkeypatch,
        command="sl",
        coin="km:US500",
        position_size=0.02,
        trigger_price=6800.0,
        size=0.01,
        current_price=7000.0,
        capsys=capsys,
    )
    assert len(exchange.order_calls) == 1
    assert info.mid_calls == ["km"]


def test_close_no_open_position_is_idempotent_success(monkeypatch, capsys):
    info = FakeInfo(positions_by_dex={"": []}, mids_by_dex={"": {}})
    config = {"account_address": "0xabc", "is_testnet": False}

    class NoopExchange:
        pass

    monkeypatch.setattr(tools, "setup_exchange", lambda **_kwargs: (NoopExchange(), info, config))

    args = SimpleNamespace(coin="SOL")
    rc = tools.cmd_close(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "No open position for SOL" in out
