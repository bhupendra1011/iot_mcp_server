import os
import json
import asyncio
import uuid
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

load_dotenv()

app = FastAPI(title="IoT Smart Light MCP Server")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEVICE_IP = os.getenv("DEVICE_IP", "192.168.1.100")
DEVICE_PORT = os.getenv("DEVICE_PORT", "80")
DEVICE_TIMEOUT = int(os.getenv("DEVICE_TIMEOUT", "10"))
DEVICE_BASE_URL = f"http://{DEVICE_IP}:{DEVICE_PORT}"
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

# ─── Color Mapping ─────────────────────────────────────────
COLOR_MAP = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "white": "#FFFFFF",
    "warm_white": "#FFD700",
    "warm white": "#FFD700",
    "orange": "#FFA500",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "off": "#000000",
}


def resolve_color(color_input: str) -> str:
    """Convert color name to hex, or validate hex input."""
    color_lower = color_input.lower().strip()
    if color_lower in COLOR_MAP:
        return COLOR_MAP[color_lower]
    if color_lower.startswith("#") and len(color_lower) == 7:
        return color_lower.upper()
    return "#FFFFFF"


# ─── Mock State (for development without hardware) ─────────
mock_state = {"on": False, "color": "#FFFFFF", "brightness": 100}


# ─── Device Communication ──────────────────────────────────
async def device_request(method: str, path: str, body: dict = None) -> dict:
    """Send HTTP request to ESP8266 device, or use mock if MOCK_MODE is enabled."""
    if MOCK_MODE:
        if path == "/light" and method == "POST" and body:
            mock_state.update(body)
            return {"success": True, "state": dict(mock_state)}
        elif path == "/status" and method == "GET":
            return {
                **mock_state,
                "device": "MOCK-NodeMCU-SmartLight",
                "uptime_seconds": 0,
                "wifi_rssi": 0,
                "ip": "127.0.0.1",
            }
        elif path == "/display" and method == "POST":
            return {"success": True}
        elif path == "/health" and method == "GET":
            return {"status": "ok", "device": "MOCK-NodeMCU-SmartLight", "uptime_seconds": 0}
        return {"success": True}

    async with httpx.AsyncClient(timeout=DEVICE_TIMEOUT) as client:
        url = f"{DEVICE_BASE_URL}{path}"
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


# ─── Tool Handlers ─────────────────────────────────────────
async def handle_set_light(args: dict) -> str:
    body = {"on": args["on"]}
    if "color" in args:
        body["color"] = resolve_color(args["color"])
    if "brightness" in args:
        body["brightness"] = max(0, min(100, args["brightness"]))
    result = await device_request("POST", "/light", body)
    state = result.get("state", {})
    if state.get("on"):
        return (
            f"Light is ON. Color: {state.get('color', 'unknown')}, "
            f"Brightness: {state.get('brightness', 'unknown')}%"
        )
    else:
        return "Light is OFF."


async def handle_get_light_status(args: dict) -> str:
    result = await device_request("GET", "/status")
    on_status = "ON" if result.get("on") else "OFF"
    return (
        f"Light Status: {on_status}\n"
        f"Color: {result.get('color', 'unknown')}\n"
        f"Brightness: {result.get('brightness', 'unknown')}%\n"
        f"Device: {result.get('device', 'unknown')}\n"
        f"Uptime: {result.get('uptime_seconds', 0)}s"
    )


async def handle_set_color(args: dict) -> str:
    hex_color = resolve_color(args["color"])
    await device_request("POST", "/light", {"color": hex_color})
    return f"Color changed to {args['color']} ({hex_color})."


async def handle_set_brightness(args: dict) -> str:
    level = max(0, min(100, args["level"]))
    await device_request("POST", "/light", {"brightness": level})
    return f"Brightness set to {level}%."


async def handle_display_text(args: dict) -> str:
    body = {"text": args["text"]}
    if "line" in args:
        body["line"] = args["line"]
    await device_request("POST", "/display", body)
    return f"Displayed '{args['text']}' on OLED screen."


TOOL_HANDLERS = {
    "set_light": handle_set_light,
    "get_light_status": handle_get_light_status,
    "set_color": handle_set_color,
    "set_brightness": handle_set_brightness,
    "display_text": handle_display_text,
}

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
                    "description": (
                        "Color name (red, blue, green, yellow, cyan, magenta, white, "
                        "warm_white, orange, purple, pink) or hex code (#FF0000)"
                    ),
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
            "and brightness. Use this when the user asks about the current light state."
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
                    "description": (
                        "Color name (red, blue, green, yellow, cyan, magenta, white, "
                        "warm_white, orange, purple, pink) or hex code (#FF0000)"
                    ),
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
        "name": "display_text",
        "description": (
            "Show text on the OLED display attached to the smart light device. "
            "Use this to display messages or status info."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to display on the OLED screen",
                },
                "line": {
                    "type": "integer",
                    "description": "Line number (1-4) to display on",
                    "minimum": 1,
                    "maximum": 4,
                },
            },
            "required": ["text"],
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
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "iot-light-controller",
                    "version": "1.0.0",
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


# ─── HTTP Transport ────────────────────────────────────────
@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """HTTP transport — single JSON-RPC request/response."""
    body = await request.json()
    response = await handle_mcp_request(body)
    return response


# ─── SSE Transport ─────────────────────────────────────────
sse_connections: dict[str, asyncio.Queue] = {}


@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE transport — persistent connection with session-based messaging."""
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    sse_connections[session_id] = queue

    async def event_generator():
        # Send the message endpoint as the first event
        yield {
            "event": "endpoint",
            "data": f"/sse/message?sessionId={session_id}",
        }
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {"event": "message", "data": json.dumps(data)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "keepalive"}
        except asyncio.CancelledError:
            pass
        finally:
            sse_connections.pop(session_id, None)

    return EventSourceResponse(event_generator())


@app.post("/sse/message")
async def sse_message(request: Request):
    """Receive a JSON-RPC request for an active SSE session."""
    session_id = request.query_params.get("sessionId")
    if not session_id or session_id not in sse_connections:
        return {"error": "Invalid or expired session"}

    body = await request.json()
    response = await handle_mcp_request(body)
    queue = sse_connections[session_id]
    await queue.put(response)
    return {"status": "ok"}


# ─── Health & Device Status ────────────────────────────────
@app.get("/health")
async def health():
    """Server health check."""
    return {
        "status": "ok",
        "server": "iot-light-controller",
        "version": "1.0.0",
        "mock_mode": MOCK_MODE,
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
    print(f"Mock mode: {MOCK_MODE}")
    print(f"Device URL: {DEVICE_BASE_URL}")
    uvicorn.run(app, host="0.0.0.0", port=port)
