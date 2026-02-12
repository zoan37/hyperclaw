# HyperClaw

An [AgentSkills](https://agentskills.io)-compatible skill for trading perpetual futures on [Hyperliquid](https://hyperliquid.xyz). Works with Claude Code, OpenClaw, and any agent that supports the AgentSkills standard.

Supports 228+ native crypto perps and HIP-3 builder-deployed perps (equities like TSLA, commodities like GOLD, and more).

## Quick Start

```bash
# 1. Clone into your skills directory
git clone https://github.com/zoan37/hyperclaw.git

# 2. Run setup (creates venv, installs deps)
bash hyperclaw/scripts/setup.sh

# 3. Configure credentials
cp hyperclaw/.env.example hyperclaw/.env
# Edit .env with your Hyperliquid API key

# 4. Test
hyperclaw/scripts/.venv/bin/python hyperclaw/scripts/hl.py price BTC
```

## For AI Agents

See [SKILL.md](SKILL.md) for the full command reference and usage instructions that agents read.

## Commands

- **Account:** `status`, `positions`, `orders`, `history`
- **Market Data:** `price`, `funding`, `book`, `scan`, `analyze`, `raw`
- **HIP-3:** `hip3`, `dexes`
- **Trading:** `buy`, `sell`, `limit-buy`, `limit-sell`, `stop-loss`, `take-profit`, `close`, `cancel`, `cancel-all`

## License

MIT
