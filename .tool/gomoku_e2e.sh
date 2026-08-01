#!/usr/bin/env bash
set -e
cd /d/code/a_js/proj/rt/backend
PYTHONPATH=src uv run uvicorn rt_backend.main:app --port 8095 --log-level warning &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 50); do curl -s http://127.0.0.1:8095/health >/dev/null 2>&1 && break; sleep 0.25; done
curl -s http://127.0.0.1:8095/health && echo " <- health ok"
PYTHONPATH=src uv run python - <<'PY'
import json, urllib.request, urllib.error
B = [[0]*15 for _ in range(15)]
for c in (5,6,7): B[7][c] = 1
def call(s):
    body = json.dumps({"board": B, "to_move": 1, "top_k": 1, "strength": s}).encode()
    req = urllib.request.Request("http://127.0.0.1:8095/api/gomoku/next-move",
                                 data=body, headers={"Content-Type":"application/json"})
    try:
        j = json.load(urllib.request.urlopen(req, timeout=10))
        b = j["best"]
        return f'best=({b["row"]},{b["col"]}) score={b["score"]} blocks={b["blocks"]} {j["elapsed_ms"]}ms'
    except urllib.error.HTTPError as e:
        return f'HTTP {e.code}: {e.read().decode()[:80]}'
for s in (1,2,3):
    print(f'strength={s}:', call(s))
print('strength=9:', call(9))
PY
echo done
