#!/usr/bin/env python3
"""Step 19 gate — E2E: login → query → stream (spec §15 Step 19).

Requires the full stack UP (Django :8000 + RAG :9000 + llama services).
Stdlib-only so it runs anywhere. If the stack is not reachable the test
fails LOUD with the exact BLOCKED line — it never pretends to pass.

Run:  python3 tests/test_e2e_query.py
Env:  E2E_BASE_URL (default http://localhost:8000), E2E_EMAIL, E2E_PASSWORD
"""
from __future__ import annotations

import http.client
import json
import os
import sys
from urllib.parse import urlparse

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
EMAIL = os.environ.get("E2E_EMAIL", "analyst@crime.local")
PASSWORD = os.environ.get("E2E_PASSWORD", "Admin@1234")
QUESTION = "Chain snatching linked to two-wheelers in Jayanagar since January 2024."


def _post(conn, path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    conn.request("POST", path, body=json.dumps(payload), headers=headers)
    resp = conn.getresponse()
    return resp.status, resp.read().decode("utf-8", "replace")


def test_login_query_stream():
    parsed = urlparse(BASE_URL)
    conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=300)
    try:
        status, body = _post(conn, "/api/accounts/login/", {"email": EMAIL, "password": PASSWORD})
        assert status == 200, f"login failed: {status} {body[:200]}"
        tokens = json.loads(body)
        access = tokens["access"]
        assert tokens["user"]["role"], "login must return the server-assigned role"

        status, _ = _post(
            conn, "/api/intel/query/",
            {"question": QUESTION, "history": []},
            token=access,
        )
        assert status == 200, f"query failed: {status}"

        conn.request(
            "POST", "/api/intel/query/",
            body=json.dumps({"question": QUESTION, "history": []}),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {access}"},
        )
        resp = conn.getresponse()
        assert resp.status == 200, f"stream failed: {resp.status}"
        assert "text/event-stream" in resp.getheader("Content-Type", ""), "must be SSE"

        events: dict[str, list] = {}
        event = None
        buffer = ""
        while True:
            chunk = resp.read(2048)
            if not chunk:
                break
            buffer += chunk.decode("utf-8", "replace")
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                data_lines = []
                for line in frame.split("\n"):
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_lines.append(line[5:].strip())
                if not data_lines:
                    continue
                try:
                    data = json.loads("\n".join(data_lines))
                except json.JSONDecodeError:
                    continue
                events.setdefault(event, []).append(data)

        assert "token" in events, "no answer tokens in the stream (§12.5)"
        assert "done" in events, "stream did not finish with done (§12.5)"
        assert "meta" in events, "meta event missing (§12.5)"
        meta = events["meta"][-1]
        assert meta.get("prompt_tokens", 0) > 0, "assembled token count must be > 0 (§12.4)"
        answer = "".join(e.get("t", "") for e in events.get("token", []))
        reasoning = "".join(e.get("t", "") for e in events.get("reasoning", []))
        for frag in (reasoning[i:i + 4] for i in range(0, max(len(reasoning) - 3, 0))):
            assert frag not in answer, "reasoning byte leaked into the answer channel (§1.3)"
        if reasoning:
            assert meta.get("reasoning_tokens", 0) > 0, "reasoning tokens reported in meta (§12.5)"
        print(f"  [OK] token events: {len(events['token'])} | citations: {len(events.get('citations', []))} | "
              f"warnings: {len(events.get('warning', []))} | intent: {meta.get('intent')}")
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        test_login_query_stream()
    except (ConnectionRefusedError, OSError) as exc:
        print(f"BLOCKED: Step 19 — stack not reachable at {BASE_URL} ({exc.__class__.__name__}). "
              "Start the stack, then re-run (§15 Step 19 gate).")
        sys.exit(1)
    print("PASS — E2E login → query → stream verified (§15 Step 19).")
