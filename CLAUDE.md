# Project Rules

## Security

- NEVER read, cat, or display the contents of `.env` files — they contain private keys and secrets
- NEVER log, print, or echo environment variables that contain keys, secrets, or addresses
- When helping with `.env` configuration, only reference `.env.example` for the format

## Project Structure

- `scripts/hyperliquid_tools.py` — main CLI tool
- `scripts/server.py` — caching proxy server (port 18731)
- `scripts/setup.sh` — venv setup script
- `scripts/requirements.txt` — Python dependencies
- `SKILL.md` — agent-facing skill documentation
- `tests/` — pytest test suite

## Running Commands

- Always use the venv Python: `scripts/.venv/bin/python`
- For mainnet with proxy: `HL_PROXY_URL=http://localhost:18731 HL_TESTNET=false scripts/.venv/bin/python scripts/hyperliquid_tools.py <command>`
