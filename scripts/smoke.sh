#!/usr/bin/env bash
# Smoke a running xtav2 HTTP endpoint (Production-Path Parity).
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8080}"
echo "Smoke against ${BASE_URL}"

python - <<PY
import json, sys, urllib.request
base = "${BASE_URL}".rstrip("/")

def get(path: str) -> dict:
    with urllib.request.urlopen(f"{base}{path}", timeout=10) as resp:
        body = resp.read().decode()
        print(path, body)
        return json.loads(body)

live = get("/health/live")
assert live.get("status") == "ok", live

db = get("/health/db")
assert db.get("status") == "ok", db

flags = get("/health/flags")
assert "FEATURE_MANUAL_ENTRY" in (flags.get("flags") or {}), flags

ollama = get("/health/ollama")
assert "configured_model" in ollama, ollama
assert "available_models" in ollama, ollama
print("Smoke OK")
PY
