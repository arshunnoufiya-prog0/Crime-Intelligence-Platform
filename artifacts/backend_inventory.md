# Backend Inventory — Step 2 (spec §14.1)

Audited: 2026-09-23. Every file under `backend/` excluding `backend/venv` (a committed
Windows venv, 6,704 files — repo-hygiene debt, see §4 below).

**Verdict:** a working legacy-v2 Django 4.2.13 service — pure Django (no DRF) as the
spec requires — but it must be *extended and corrected* per §14.3/§17, not rewritten.
`backend/venv/` is `□` (dead weight; do not touch on Linux).

## File-by-file state

| Path (relative to `backend/`) | State | Notes vs spec |
|---|---|---|
| `manage.py` | ▲ | works; keep |
| `config/settings.py` | ▲ | decouple-based, Postgres, CORS; add JWT/RBAC scope settings per §17; no dev default for `JWT_SECRET` → must fail hard at startup (§17) |
| `config/urls.py` | ▲ | add `api/intel/` include when `apps/intel/` lands (§14.3) |
| `config/wsgi.py` | □ | fine |
| `requirements.txt` | ▲ | **deviates from §3.1** — has cors-headers/auditlog/decouple/bcrypt; lacks `neo4j`, `gunicorn`, `python-dotenv`; repin to §3.1 + keep cors-headers (needed for :5173 dev) |
| `.env.example` | ▲ | extend to root-level `.env.example` contract (Step 3) |
| `apps/accounts/models.py` | ▲ | CustomUser: UUID pk, email login, role ∈ {SUPER_ADMIN, ANALYST, INVESTIGATOR, READ_ONLY} ✓ matches §17 roles; scope = single `district` FK — §17 requires `districts[]` **and** `stations[]` scope claims |
| `apps/accounts/utils.py` | ▲ | `generate_tokens()` — claims only `{user_id, type, exp, iat}`; §17 needs `sub, role, districts, stations, iat, exp, jti`; refresh not stored/hashed/single-use/rotated; 15 min/7 d vs §17's 30 min/12 h |
| `apps/accounts/middleware.py` | ▲ | `JWTAuthMiddleware` decodes with `algorithms=[HS256]` ✓; reject `verify_signature: False` per §17 (currently never used ✓) |
| `apps/accounts/decorators.py` | ▲ | role-hierarchy decorators OK; add per-capability checks per §17 RBAC matrix |
| `apps/accounts/views.py` | ▲ | login/refresh/me/change-pw/users CRUD; refresh flow must be rebuilt (hashed single-use rotation) |
| `apps/accounts/urls.py` | □ | keep |
| `apps/accounts/scope.py` | ■ NEW | §14.3 change 3: build scope payload from validated JWT → RAG request |
| `apps/accounts/management/commands/create_default_users.py` | ▲ | seeds 4 role users (pw `Admin@1234`); extend with district/stations scope (Step 19) |
| `apps/fir/models.py` | ▲ | Postgres `FIR` with ~40 flattened fields + District/PoliceStation/Accused. **Spec §2.1: FIR records live in Neo4j (evidentiary graph); Postgres keeps auth+audit only.** Postgres FIR model becomes a Step 6 legacy (keep read-only for now; Neo4j client arrives as `apps/fir/neo4j_client.py` ■) |
| `apps/fir/views.py` | ▲ | list/detail/CRUD/stats served from Postgres — re-point to Neo4j via Cypher (Step 17); `fir_stats` uses Postgres `.extra()` month trunc |
| `apps/fir/urls.py` | □ | keep |
| `apps/fir/management/commands/import_fir_json.py` | □ | legacy Postgres import; superseded by `rag_service/ingest/load_neo4j.py` — keep until Step 6 gate passes |
| `apps/fir/neo4j_client.py` + `queries.py` | ■ NEW | per §4: Django→Neo4j bolt for FIR CRUD (this is the ONLY AI-adjacent path Django is allowed besides proxying) |
| `apps/audit/models.py` | ▲ | `AuditEntry` + `RequestAuditMiddleware` (in-models); §14.3 change 2: add `intent, cypher_template_id, fir_ids_returned, prompt_token_count, reasoning_token_count, warnings, ttft_ms, latency_ms`; **answer stored, reasoning NEVER stored**; add `user_id` field + indexes `(user_id, ts)` and `(ts)`; append-only (no update/delete views exist ✓ keep it that way) |
| `apps/audit/middleware.py` | □ | placeholder comment file — real middleware lives in models.py |
| `apps/llm/models.py` | ▲ | `GraphQuery` (user, query, intent, fir_ids, latency_ms, confidence) + `post_save` signal that fabricates an AuditEntry — remove signal when audit fields land (double-audit) |
| `apps/llm/views.py` | ▲→retire | **Defect:** `_drive_async_sse()` collects the ENTIRE upstream SSE payload, then yields it as one chunk — not incremental streaming; §17 requires `httpx.Client.stream` generator → replaced by `apps/intel/proxy.py` ■ |
| `apps/llm/services/graph_rag_client.py` | ▲→retire | httpx AsyncClient to graph-rag :9000; replaced by `apps/intel/proxy.py` (§14.3 change 4: remove old Graph-RAG endpoints once new path verified) |
| `apps/intel/{proxy,views,urls}.py` | ■ NEW | §14.3: pass-through ALL §12.5 event types unmodified, incl. unknown |
| `backend/Dockerfile` | ■ NEW | Step 3 |
| `common/{responses,errors,pagination}.py` | ■ NEW | §4 layout (envelope lives here) |

No migrations exist anywhere (`manage.py makemigrations` runs at first deploy — fine).

## URL map (current)

```
admin/
api/accounts/login|refresh|me|change-password|users|users/{pk}
api/firs/ | stats/ | districts/ | stations/ | {pk}/ | create/ | {pk}/update/ | {pk}/delete/
api/llm/graph/query/ (POST, SSE) | graph/subgraph/{fir_id}/ | graph/history/
```

## Decisions recorded (§17 "record the decision")

- **Response envelope:** frontend has NO established envelope — it consumes raw
  payloads (`{results,…}` from `/api/firs/`, `{access,refresh,user}` from login, and
  `{nodes,links}` from subgraph). Per §17 we therefore adopt the spec default
  `{"ok": true, "data": …, "meta": …}` / `{"ok": false, "error": {code, message, details}}`
  for **new** endpoints under `api/intel/` and keep legacy raw shapes on existing
  endpoints (change-controlled); `common/responses.py` implements both helpers.
- **SSE:** Django stays synchronous; `intel/proxy.py` uses `httpx.Client.stream`
  inside a generator → `StreamingHttpResponse` with `Cache-Control: no-cache`,
  `X-Accel-Buffering: no`, gunicorn gthread (§17).
- **`apps/llm` vs `apps/intel`:** `intel/` is added alongside; `llm/` endpoints are
  removed at Step 17 gate once the new path streams (§14.3 change 4).
