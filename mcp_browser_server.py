from fastapi import FastAPI, Request
from pydantic import BaseModel
from playwright.async_api import async_playwright
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import time
import asyncio

app = FastAPI()
browser_instance = None
page = None

# ------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------
# Async Browser Setup
# ------------------------------------------------------------
async def ensure_browser():
    """Launch Playwright Chromium asynchronously and reuse it."""
    global browser_instance, page
    if browser_instance is None:
        pw = await async_playwright().start()
        browser_instance = await pw.chromium.launch(headless=True)
        page = await browser_instance.new_page()
        print("🟢 Async browser launched")
    return page


# ------------------------------------------------------------
# JSON-RPC Dispatcher for LM Studio MCP
# ------------------------------------------------------------
@app.post("/")
async def mcp_router(request: Request):
    """Handles MCP JSON-RPC methods like initialize, tools/list, tools/call."""
    try:
        body = await request.json()
        print("🔹 LM Studio body:", json.dumps(body, indent=2))
    except Exception:
        body = {}
        print("⚠️ Could not parse body; returning default handshake.")
        return JSONResponse(content={"error": "invalid JSON"})

    method = body.get("method")
    req_id = body.get("id", 0)
    params = body.get("params", {})
    protocol_version = params.get("protocolVersion", "2025-06-18")

    # ---- initialize ----
    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {
                    "tools": {"supported": True},
                    "browsing": {"supported": True},
                    "experimental": {},
                },
                "serverInfo": {
                    "name": "mcp-browser",
                    "version": "0.2.0",
                    "description": "Async Playwright MCP browser agent",
                },
            },
        }
        print("✅ Responding to initialize:", json.dumps(response, indent=2))
        return JSONResponse(content=response)

    # ---- tools/list ----
    elif method == "tools/list":
        tools = [
            {
                "name": "open_url",
                "description": "Open a URL in the browser",
                "inputSchema": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
            {
                "name": "click",
                "description": "Click an element by CSS selector",
                "inputSchema": {
                    "type": "object",
                    "properties": {"selector": {"type": "string"}},
                    "required": ["selector"],
                },
            },
            {
                "name": "fill_form",
                "description": "Fill a form field",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["selector", "text"],
                },
            },
            {
                "name": "get_text",
                "description": "Retrieve the first 1000 characters of the page text",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools}}
        print("✅ Responding to tools/list with", len(tools), "tools.")
        return JSONResponse(content=response)

    # ---- tools/call ----
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        print(f"🧩 Tool call requested: {name} with args {args}")

        try:
            p = await ensure_browser()
            result = {}

            if name == "open_url":
                await p.goto(args["url"])
                result = {"title": await p.title(), "url": args["url"]}

            elif name == "click":
                await p.click(args["selector"])
                result = {"status": "clicked", "selector": args["selector"]}

            elif name == "fill_form":
                await p.fill(args["selector"], args["text"])
                result = {
                    "status": "filled",
                    "selector": args["selector"],
                    "text": args["text"],
                }

            elif name == "get_text":
                text = await p.inner_text("body")
                result = {"text": text[:1000]}

            else:
                raise ValueError(f"Unknown tool: {name}")

            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }

            print(f"✅ Tool {name} executed successfully.")
            return JSONResponse(content=response)

        except Exception as e:
            print(f"❌ Tool execution failed: {e}")
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }
            return JSONResponse(content=response)

    # ---- notifications/initialized ----
    elif method == "notifications/initialized":
        print("✅ Acknowledged notifications/initialized")
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": req_id, "result": {"ack": True}}
        )

    # ---- notifications/cancelled ----
    elif method == "notifications/cancelled":
        print("ℹ️ Operation cancelled:", params)
        return JSONResponse(
            content={"jsonrpc": "2.0", "id": req_id, "result": {"ack": True}}
        )

    # ---- Unknown methods ----
    else:
        response = {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
        }
        print(f"⚠️ Unknown method: {method}")
        return JSONResponse(content=response)


# ------------------------------------------------------------
# Optional SSE Stream
# ------------------------------------------------------------
@app.get("/")
def sse_stream():
    def stream():
        yield f"data: {json.dumps({'event': 'ready', 'message': 'MCP Browser connected'})}\n\n"
        while True:
            time.sleep(10)
            yield f"data: {json.dumps({'event': 'heartbeat', 'timestamp': time.time()})}\n\n"

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)


# ------------------------------------------------------------
# Shutdown Hook
# ------------------------------------------------------------
@app.on_event("shutdown")
async def shutdown_event():
    global browser_instance
    if browser_instance:
        print("🟥 Closing browser instance...")
        await browser_instance.close()
        browser_instance = None


# ------------------------------------------------------------
# Run command
# ------------------------------------------------------------
# python -m uvicorn mcp_browser_server:app --host 127.0.0.1 --port 3333
# ------------------------------------------------------------
