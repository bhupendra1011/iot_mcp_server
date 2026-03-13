# IoT Smart Light MCP Server

A Python/FastAPI MCP (Model Context Protocol) server that enables AI agents to control a physical LED light (ESP8266 + WS2812B NeoPixel ring + SSD1306 OLED) via voice commands.

## Architecture

```
Agora Convo AI Agent  →  MCP Server (this)  →  ESP8266 Device
    (tool_call)          (JSON-RPC 2.0)         (HTTP REST)
```

## Tools

| Tool | Description |
|------|-------------|
| `set_light` | Turn light on/off, set color and brightness |
| `get_light_status` | Query current light state |
| `set_color` | Change light color (by name or hex) |
| `set_brightness` | Adjust brightness (0-100%) |
| `display_text` | Show text on OLED display |

## Quick Start

### 1. Setup

```bash
cp .env.example .env
# Edit .env — set DEVICE_IP to your ESP8266 IP address

pip install -r requirements.txt
```

### 2. Run

```bash
# With real hardware
python server.py

# Without hardware (mock mode)
MOCK_MODE=true python server.py
```

Server starts at `http://localhost:8000`

### 3. Test

```bash
chmod +x test_server.sh
./test_server.sh
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp` | POST | HTTP transport — JSON-RPC 2.0 |
| `/sse` | GET | SSE transport — persistent connection |
| `/sse/message` | POST | Send message to SSE session |
| `/health` | GET | Server health check |
| `/device/health` | GET | Check ESP8266 device connectivity |

## Using with Agora Convo AI

In your app's Agent Settings → LLM → MCP Servers:

- **Name**: `iot-light-controller`
- **Endpoint**: `http://localhost:8000/sse` (SSE) or `http://localhost:8000/mcp` (HTTP)
- **Transport**: SSE (recommended)
- **Enabled**: ON

## Supported Colors

red, green, blue, yellow, cyan, magenta, white, warm_white, orange, purple, pink — or any hex code (#FF0000)

## Deployment

### Render.com
```bash
# Uses render.yaml — just connect repo and set DEVICE_IP
```

### Railway
```bash
# Connect repo, set DEVICE_IP env var
```

> **Note**: For cloud deployment, the server must reach the ESP8266. Use ngrok/Cloudflare Tunnel for local devices, or set `MOCK_MODE=true` for demos without hardware.

## Development

```bash
# Run with auto-reload
uvicorn server:app --reload --port 8000

# Mock mode (no hardware needed)
MOCK_MODE=true uvicorn server:app --reload --port 8000
```
