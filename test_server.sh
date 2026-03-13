#!/bin/bash
# Test script for IoT Smart Light MCP Server
# Usage: ./test_server.sh [base_url]

BASE_URL="${1:-http://localhost:8000}"

echo "=== Health Check ==="
curl -s "$BASE_URL/health" | python3 -m json.tool

echo -e "\n=== Device Health ==="
curl -s "$BASE_URL/device/health" | python3 -m json.tool

echo -e "\n=== MCP Initialize ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
  | python3 -m json.tool

echo -e "\n=== MCP List Tools ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 -m json.tool

echo -e "\n=== Set Light ON + Red ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"set_light","arguments":{"on":true,"color":"red","brightness":80}}}' \
  | python3 -m json.tool

echo -e "\n=== Get Light Status ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_light_status","arguments":{}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Color Blue ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"set_color","arguments":{"color":"blue"}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Brightness 50% ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"set_brightness","arguments":{"level":50}}}' \
  | python3 -m json.tool

echo -e "\n=== Display Text ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"display_text","arguments":{"text":"Hello from AI!","line":1}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Light OFF ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"set_light","arguments":{"on":false}}}' \
  | python3 -m json.tool

echo -e "\n=== Done ==="
