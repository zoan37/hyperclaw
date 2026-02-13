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

## Environment / .env Safety

- **This repo's `.env` contains real trading credentials with real money.** Always use it when running commands or tests here.
- **NEVER let an external `HL_ENV_FILE` leak in.** If you are working from another project (e.g. sandbox-2) that sets `HL_ENV_FILE`, make sure it does NOT propagate into hyperclaw commands or tests.
- The test suite's `run_cli()` helper explicitly clears `HL_ENV_FILE` from the subprocess environment so tests always use hyperclaw's own `.env` discovery. Do not remove that safeguard.
- When running tests manually, run them from the hyperclaw project root — not from another repo's directory — to avoid picking up the wrong `.env`.

## Running Commands

- Always use the venv Python: `scripts/.venv/bin/python`
- For mainnet with proxy: `HL_PROXY_URL=http://localhost:18731 HL_TESTNET=false scripts/.venv/bin/python scripts/hyperliquid_tools.py <command>`
