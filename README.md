# MCP Browser Server

FastAPI server that exposes a minimal MCP JSON-RPC interface and drives a Playwright browser for simple browsing tools.

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

## Supported Tools
- `open_url`
- `click`
- `fill_form`
- `get_text`

## Notes
- CORS is open by default.
- The server keeps a single shared browser instance.
