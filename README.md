# MCP Browser Server

Minimal MCP JSON-RPC server that exposes Playwright browsing tools via FastAPI.

## Highlights
- Implements a compact MCP tool surface (`open_url`, `click`, `fill_form`, `get_text`).
- Reuses a single headless Chromium instance for efficiency.
- Simple JSON-RPC request/response handling.

## Tech
Python, FastAPI, Playwright

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## Run
```bash
uvicorn mcp_browser_server:app --host 0.0.0.0 --port 8000
```

## Notes
- CORS is open by default.
