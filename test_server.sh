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

echo -e "\n=== Set Light ON + Blue ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"set_light","arguments":{"on":true,"color":"blue","brightness":80}}}' \
  | python3 -m json.tool

echo -e "\n=== Get Light Status ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_light_status","arguments":{}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Color Yellow ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"set_color","arguments":{"color":"yellow"}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Brightness 50% ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"set_brightness","arguments":{"level":50}}}' \
  | python3 -m json.tool

echo -e "\n=== Blink Red 5s (fast 100ms) ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"blink","arguments":{"color":"red","duration":5,"interval":100}}}' \
  | python3 -m json.tool

sleep 6

echo -e "\n=== Pulse Purple 10s ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":8,"method":"tools/call","params":{"name":"pulse","arguments":{"color":"purple","duration":10}}}' \
  | python3 -m json.tool

sleep 3

echo -e "\n=== Stop Effect ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":9,"method":"tools/call","params":{"name":"stop_effect","arguments":{}}}' \
  | python3 -m json.tool

echo -e "\n=== Temp Color (green 3s) ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":10,"method":"tools/call","params":{"name":"temp_color","arguments":{"color":"green","duration":3}}}' \
  | python3 -m json.tool

sleep 4

echo -e "\n=== Get Status (should revert) ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":11,"method":"tools/call","params":{"name":"get_light_status","arguments":{}}}' \
  | python3 -m json.tool

echo -e "\n=== Set Light OFF ==="
curl -s -X POST "$BASE_URL/mcp" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":12,"method":"tools/call","params":{"name":"set_light","arguments":{"on":false}}}' \
  | python3 -m json.tool

echo -e "\n=== Done ==="
