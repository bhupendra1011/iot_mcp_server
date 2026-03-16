import os
import json
import asyncio
import uuid
import logging
import time
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

load_dotenv()

# ─── Logging Setup ────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("iot-mcp")

app = FastAPI(title="IoT Smart Light MCP Server")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE_IP = os.getenv("DEVICE_IP", "192.168.1.50")  # static IP of ESP8266/NodeMCU
DEVICE_PORT = os.getenv("DEVICE_PORT", "80")
DEVICE_TIMEOUT = int(os.getenv("DEVICE_TIMEOUT", "10"))
DEVICE_BASE_URL = f"http://{DEVICE_IP}:{DEVICE_PORT}"

logger.info(f"[STARTUP] DEVICE_IP={DEVICE_IP} DEVICE_PORT={DEVICE_PORT} DEVICE_TIMEOUT={DEVICE_TIMEOUT}s")
logger.info(f"[STARTUP] DEVICE_BASE_URL={DEVICE_BASE_URL}")

# ─── Valid Colors (must match Arduino's parseColor) ───────
VALID_COLORS = [
    "red", "green", "blue", "yellow", "orange", "purple", "violet",
    "cyan", "magenta", "pink", "white", "warm_white", "cool_white",
    "gold", "silver", "lime", "teal", "indigo", "coral", "off",
]


def resolve_color(color_input: str) -> str:
    """Validate color name or hex code. Arduino accepts names directly."""
    color_lower = color_input.lower().strip()
    if color_lower in VALID_COLORS:
        return color_lower
    # Arduino also accepts hex codes like #FF5500
    if color_lower.startswith("#") and len(color_lower) == 7:
        return color_lower
    return "white"


# ─── Device Communication ──────────────────────────────────
async def device_request(method: str, path: str, body: dict = None) -> dict:
    """Send HTTP request to ESP8266 device at DEVICE_IP."""
    url = f"{DEVICE_BASE_URL}{path}"
    logger.info(f"[DEVICE] {method} {url} body={body}")
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=DEVICE_TIMEOUT) as client:
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=body)
            elapsed = (time.time() - start) * 1000
            logger.info(f"[DEVICE] Response {resp.status_code} in {elapsed:.0f}ms")
            resp.raise_for_status()
            data = resp.json()
            logger.debug(f"[DEVICE] Response body: {json.dumps(data)[:500]}")
            return data
    except httpx.ConnectError as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"[DEVICE] CONNECT FAILED to {url} after {elapsed:.0f}ms: {e}")
        raise
    except httpx.TimeoutException as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"[DEVICE] TIMEOUT to {url} after {elapsed:.0f}ms (limit={DEVICE_TIMEOUT}s): {e}")
        raise
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        logger.error(f"[DEVICE] ERROR {url} after {elapsed:.0f}ms: {type(e).__name__}: {e}")
        raise


# ─── Tool Handlers ─────────────────────────────────────────
async def handle_set_light(args: dict) -> str:
    """Turn light on/off with optional color and brightness."""
    body: dict = {}
    if "on" in args:
        body["on"] = args["on"]
    if "color" in args:
        body["color"] = resolve_color(args["color"])
    if "brightness" in args:
        body["brightness"] = max(0, min(100, args["brightness"]))
    result = await device_request("POST", "/light", body)
    state = result.get("state", {})
    if state.get("on"):
        return (
            f"Light is ON. Color: {state.get('color', 'unknown')}, "
            f"Brightness: {state.get('brightness', 'unknown')}%, "
            f"Effect: {state.get('effect', 'none')}"
        )
    return "Light is OFF."


async def handle_get_light_status(args: dict) -> str:
    """Get current light state from device."""
    result = await device_request("GET", "/status")
    on_status = "ON" if result.get("on") else "OFF"
    effect = result.get("effect", {})
    effect_str = effect.get("type", "none") if isinstance(effect, dict) else str(effect)
    return (
        f"Light Status: {on_status}\n"
        f"Color: {result.get('color', 'unknown')}\n"
        f"Brightness: {result.get('brightness', 'unknown')}%\n"
        f"RGB: R={result.get('rgb', {}).get('r', 0)}, "
        f"G={result.get('rgb', {}).get('g', 0)}, "
        f"B={result.get('rgb', {}).get('b', 0)}\n"
        f"Effect: {effect_str}\n"
        f"Device: {result.get('device', 'unknown')}\n"
        f"IP: {result.get('ip', 'unknown')}\n"
        f"Uptime: {result.get('uptime_seconds', 0)}s"
    )


async def handle_set_color(args: dict) -> str:
    """Change color without changing on/off state."""
    color = resolve_color(args["color"])
    result = await device_request("POST", "/light", {"color": color})
    state = result.get("state", {})
    return f"Color changed to {state.get('color', color)}."


async def handle_set_brightness(args: dict) -> str:
    """Adjust brightness level."""
    level = max(0, min(100, args["level"]))
    await device_request("POST", "/light", {"brightness": level})
    return f"Brightness set to {level}%."


async def handle_blink(args: dict) -> str:
    """Blink the light with optional color, duration, and interval."""
    body: dict = {}
    if "color" in args:
        body["color"] = resolve_color(args["color"])
    body["blink"] = args.get("duration", 5)
    if "interval" in args:
        body["interval"] = args["interval"]
    result = await device_request("POST", "/light", body)
    state = result.get("state", {})
    return f"Blinking {state.get('color', 'current')} for {body['blink']}s (interval: {body.get('interval', 300)}ms)."


async def handle_pulse(args: dict) -> str:
    """Pulse/fade effect on the light."""
    body: dict = {}
    if "color" in args:
        body["color"] = resolve_color(args["color"])
    body["pulse"] = args.get("duration", 10)
    result = await device_request("POST", "/light", body)
    state = result.get("state", {})
    return f"Pulsing {state.get('color', 'current')} for {body['pulse']}s."


async def handle_temp_color(args: dict) -> str:
    """Show a color temporarily, then revert to previous state."""
    body: dict = {
        "color": resolve_color(args["color"]),
        "duration": args.get("duration", 3),
    }
    result = await device_request("POST", "/light", body)
    return f"Showing {body['color']} for {body['duration']}s, then reverting."


async def handle_stop_effect(args: dict) -> str:
    """Stop any active effect (blink, pulse)."""
    await device_request("POST", "/light", {"effect": "stop"})
    return "Effect stopped."


TOOL_HANDLERS = {
    "set_light": handle_set_light,
    "get_light_status": handle_get_light_status,
    "set_color": handle_set_color,
    "set_brightness": handle_set_brightness,
    "blink": handle_blink,
    "pulse": handle_pulse,
    "temp_color": handle_temp_color,
    "stop_effect": handle_stop_effect,
}

# ─── Available colors description ─────────────────────────
_COLORS_DESC = (
    "Color name (red, green, blue, yellow, orange, purple, violet, cyan, magenta, "
    "pink, white, warm_white, cool_white, gold, silver, lime, teal, indigo, coral) "
    "or hex code (#FF5500)"
)

# ─── MCP Tools Schema ─────────────────────────────────────
TOOLS_SCHEMA = [
    {
        "name": "set_light",
        "description": (
            "Turn the smart light on or off, and optionally set its color and brightness. "
            "Use this when the user asks to turn on/off the light or change its color."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "on": {
                    "type": "boolean",
                    "description": "true to turn on, false to turn off",
                },
                "color": {
                    "type": "string",
                    "description": _COLORS_DESC,
                },
                "brightness": {
                    "type": "integer",
                    "description": "Brightness level 0-100",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["on"],
        },
    },
    {
        "name": "get_light_status",
        "description": (
            "Get the current state of the smart light including on/off status, color, "
            "brightness, RGB values, active effects, and device info."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "set_color",
        "description": (
            "Change the light color without changing on/off state. "
            "Use this when the user only wants to change the color."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "description": _COLORS_DESC,
                },
            },
            "required": ["color"],
        },
    },
    {
        "name": "set_brightness",
        "description": (
            "Adjust the light brightness. "
            "Use this when the user asks to make the light brighter or dimmer."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "description": "Brightness level from 0 (off) to 100 (maximum)",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
            "required": ["level"],
        },
    },
    {
        "name": "blink",
        "description": (
            "Make the light blink with optional color, duration, and speed. "
            "Use this for alerts, notifications, or attention-getting effects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "description": _COLORS_DESC,
                },
                "duration": {
                    "type": "integer",
                    "description": "How long to blink in seconds (0 = forever)",
                    "minimum": 0,
                },
                "interval": {
                    "type": "integer",
                    "description": "Blink interval in milliseconds (default 300)",
                    "minimum": 50,
                },
            },
        },
    },
    {
        "name": "pulse",
        "description": (
            "Make the light pulse (fade in/out) with optional color and duration. "
            "Use this for a smooth breathing effect."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "description": _COLORS_DESC,
                },
                "duration": {
                    "type": "integer",
                    "description": "How long to pulse in seconds (0 = forever)",
                    "minimum": 0,
                },
            },
        },
    },
    {
        "name": "temp_color",
        "description": (
            "Temporarily show a color for a few seconds, then revert to the previous state. "
            "Use this for brief visual indicators (e.g., flash red for error, green for success)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "color": {
                    "type": "string",
                    "description": _COLORS_DESC,
                },
                "duration": {
                    "type": "integer",
                    "description": "How long to show the color in seconds (default 3)",
                    "minimum": 1,
                },
            },
            "required": ["color"],
        },
    },
    {
        "name": "stop_effect",
        "description": "Stop any active effect (blink, pulse). The light stays on with its current color.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


# ─── MCP Protocol Handler ─────────────────────────────────
async def handle_mcp_request(request_data: dict) -> dict:
    """Process MCP JSON-RPC 2.0 request."""
    method = request_data.get("method", "")
    req_id = request_data.get("id")
    params = request_data.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {
                    "tools": {"listChanged": False},
                },
                "serverInfo": {
                    "name": "iot-light-controller",
                    "version": "2.0.0",
                },
            },
        }

    elif method == "notifications/initialized":
        # Client acknowledgment — no response needed for notifications
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": TOOLS_SCHEMA},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(tool_name)

        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}",
                },
            }

        try:
            result_text = await handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": result_text}],
                },
            }
        except httpx.ConnectError:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Error: Cannot reach the smart light device. "
                                "It may be offline or disconnected."
                            ),
                        }
                    ],
                    "isError": True,
                },
            }
        except httpx.TimeoutException:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Error: The smart light device did not respond in time. "
                                "It may be busy or unreachable."
                            ),
                        }
                    ],
                    "isError": True,
                },
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error controlling light: {str(e)}",
                        }
                    ],
                    "isError": True,
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }


# ─── Friendly tool descriptions for progress messages ──────
TOOL_PROGRESS_MSG = {
    "set_light": "Sending on/off command to the smart light...",
    "get_light_status": "Querying device status...",
    "set_color": "Changing light color...",
    "set_brightness": "Adjusting brightness...",
    "blink": "Starting blink effect...",
    "pulse": "Starting pulse effect...",
    "temp_color": "Showing temporary color...",
    "stop_effect": "Stopping active effect...",
}


def _sse_event(data: dict, event: str = "message") -> str:
    """Format a single SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ─── Streamable HTTP Transport ─────────────────────────────
sessions: dict[str, bool] = {}


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Streamable HTTP transport — streams progress for tool calls."""
    start = time.time()
    accept = request.headers.get("accept", "")
    body = await request.json()
    method = body.get("method", "")
    req_id = body.get("id")
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"[MCP] POST /mcp method={method} id={req_id} from={client_ip}")
    logger.debug(f"[MCP] Headers: accept={accept}")
    if method == "tools/call":
        params = body.get("params", {})
        logger.info(f"[MCP] Tool call: {params.get('name')} args={params.get('arguments')}")

    # Assign or reuse session
    session_id = request.headers.get("mcp-session-id") or str(uuid.uuid4())
    sessions[session_id] = True

    if method == "initialize":
        resp = await handle_mcp_request(body)
        elapsed = (time.time() - start) * 1000
        logger.info(f"[MCP] initialize done in {elapsed:.0f}ms session={session_id}")
        response = JSONResponse(content=resp)
        response.headers["Mcp-Session-Id"] = session_id
        return response

    # For tool calls with streaming accepted, send progress + result via SSE
    if "text/event-stream" in accept and method == "tools/call":
        async def stream_tool():
            params = body.get("params", {})
            tool_name = params.get("name", "")
            args = params.get("arguments", {})

            progress_msg = TOOL_PROGRESS_MSG.get(tool_name, f"Running {tool_name}...")
            color_info = args.get("color", "")
            if color_info:
                progress_msg = progress_msg.replace("...", f" ({color_info})...")

            progress_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/message",
                "params": {
                    "level": "info",
                    "data": progress_msg,
                },
            }
            yield _sse_event(progress_notification)

            result = await handle_mcp_request(body)
            elapsed = (time.time() - start) * 1000
            is_err = result.get("result", {}).get("isError", False)
            logger.info(f"[MCP] tools/call done in {elapsed:.0f}ms error={is_err}")
            logger.debug(f"[MCP] Result: {json.dumps(result)[:500]}")
            yield _sse_event(result)

        response = StreamingResponse(
            stream_tool(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Mcp-Session-Id": session_id,
            },
        )
        return response

    # Non-streaming: return plain JSON
    resp = await handle_mcp_request(body)
    elapsed = (time.time() - start) * 1000
    logger.info(f"[MCP] {method} done in {elapsed:.0f}ms (non-streaming)")
    response = JSONResponse(content=resp)
    response.headers["Mcp-Session-Id"] = session_id
    return response


@app.get("/mcp")
async def mcp_sse_stream(request: Request):
    """GET /mcp — open an SSE stream for server-initiated messages (optional)."""
    session_id = request.headers.get("mcp-session-id") or str(uuid.uuid4())

    async def keep_alive():
        try:
            while True:
                if await request.is_disconnected():
                    break
                yield _sse_event({"type": "ping"}, event="ping")
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        keep_alive(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Mcp-Session-Id": session_id,
        },
    )


@app.delete("/mcp")
async def mcp_close_session(request: Request):
    """DELETE /mcp — close a session."""
    session_id = request.headers.get("mcp-session-id")
    if session_id:
        sessions.pop(session_id, None)
    return JSONResponse(content={"status": "closed"}, status_code=200)


# ─── Health & Device Status ────────────────────────────────
@app.get("/health")
async def health():
    """Server health check."""
    return {
        "status": "ok",
        "server": "iot-light-controller",
        "version": "2.0.0",
    }


@app.get("/device/health")
async def device_health():
    """Check if the ESP8266 device is reachable."""
    try:
        result = await device_request("GET", "/health")
        return {"status": "ok", "device": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ─── Run ───────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"Starting IoT Smart Light MCP Server on port {port}")
    print(f"Device URL: {DEVICE_BASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=port)
