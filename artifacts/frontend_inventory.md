# Frontend Inventory — Step 2 (spec §14.1)

Audited: 2026-09-23. Every file under `frontend/src/` plus build config. Everything
not touched by the eight §14.2 changes is `□`.

## Stack & build

- React **19.2.7** + Vite **8.1.1** (JS/JSX), Tailwind 3.4, axios 1.18, leaflet 1.9.4 +
  react-leaflet 5.0, plotly.js 3.7 + react-plotly.js 4.0, react-force-graph-2d **1.29.1**
- `react-router-dom` 7.18 is installed but **UNUSED** — routing is a `currentPage`
  state switch in `App.jsx`. Do not introduce react-router (change-controlled).
- **`vite.config.js` has NO dev proxy** → all `/api/*` axios calls 404 in `:5173` dev
  until a proxy is configured (Step 18 wiring note).
- `frontend/dist.zip` and part of `node_modules` are committed (repo-hygiene debt).

## Routing (App.jsx state switch)

`dashboard | chat | network | analytics | map | fir | network_live | map_live | analytics_live`
— Sidebar sets `currentPage`. Login gate is client-side only.

## Auth flow (current — fake)

- `pages/Login.jsx`: **no API call**. Any credentials "log in"; role dropdown offers
  `investigator | analyst | policymaker` (note: `policymaker` is not a backend role).
- `onLoginSuccess` sets state only — **no token is ever stored**.
- Live components read `localStorage.getItem('access_token')` and send
  `Authorization: Bearer …` — the token is never written, so live calls currently 401.

## API calls (complete list)

| # | File:line | Method+Path | Request | Response shape as consumed |
|---|---|---|---|---|
| 1 | `components/GraphView/useGraphData.js:15` | `GET /api/llm/graph/subgraph/{firId}/` | `params: {max_hops:2}` (implicit via Django), Bearer from localStorage | `{nodes:[{id,label,properties,degree,betweenness,eigenvector,community}], links:[{source,target,type}], error, request_id}` |
| 2 | `components/MapView/CrimeMap.jsx:36` | `GET /api/firs/?page_size=1000` | Bearer | `{results:[{id,fir_id,crime_head,case_status,police_station,latitude,longitude,…}]}` → markers filter `latitude && longitude`; popup shows `fir_id, crime_head, case_status, police_station` |
| 3 | `components/Analytics/AnalyticsDashboard.jsx:13` | `GET /api/firs/stats/` | Bearer | `{total, by_status, by_category, by_crime_head, by_month, by_district_category}` |

**SSE handling: NONE exists anywhere.** `hooks/useChat.js` is a `setTimeout(1500ms)`
mock that fabricates `text: "This is a mock response…"`, `citations: ["FIR/2024/001 (2024-01-15)"]`
(format does not even match the real `id_regex ^(?:\d+/\d{4})$`), `confidence: 0.85`.
No `EventSource`, no fetch-stream, no SSE parser in the entire codebase.

## Component classification

**Live-API (render real backend data):**
- `components/GraphView/NetworkGraph.jsx` — react-force-graph-2d canvas; node circle
  radius ∝ degree; community colors (10-color palette); node click: if FIR node →
  refetch subgraph for that `fir_id`, else centerAt/zoom; `linkWidth/Color` style
  `SIMILAR_PATTERN` edges red/thick; `linkLabel` = edge type; fixed 780×450.
- `components/GraphView/useGraphData.js` — fetch + shape mapping.
- `components/MapView/CrimeMap.jsx` — leaflet OSM tiles, markers + popup, FitBounds.
- `components/Analytics/AnalyticsDashboard.jsx` — plotly bars/pie/month heatmap.

**Mock-only (render `data/mockData.js`):** `pages/Dashboard.jsx` (StatCard,
AnalyticsChart, CrimeTrendChart, CrimeMap), `pages/Analytics.jsx` (AnalyticsChart,
CrimeTrendChart), `pages/CrimeMap.jsx`, `pages/Network.jsx`, `pages/FIRDetails.jsx`
(CrimeCard), `pages/Chat.jsx` (via `useChat` mock).

**Chat/AI-output rendering:** `components/ChatWindow.jsx` — MessageBubble with
`message.text` plain text, `message.citations` as `<p>📄 {cite}</p>` strings,
`message.confidence` as %. No markdown renderer. No reasoning panel, no warning
banner, no context meter.

**Dead (never imported):** `components/NetworkGraph.jsx` (superseded by GraphView/),
`components/Navbar.jsx` (Sidebar is used).

## react-force-graph data shape expected (§14.2 change 6 target)

```js
{ nodes: [{ id, label, properties: {...}, degree, betweenness, eigenvector, community, _label }],
  links: [{ source, target, type }] }
```
Node `id` = backend node id; FIR nodes carry `fir_id`/`fir_key` in properties;
`type` drives link styling. **No dashed-edge support yet** — needed for `SAME_NAME_AS`
(change 6), plus a legend entry.

## §14.2 change impact map (planned edits, everything else stays □)

| §14.2 change | Files to touch |
|---|---|
| 1. SSE event handling (`reasoning/token/citations/graph/warning/meta/done`, unknown ignored) | `hooks/useChat.js` (rewrite: real POST + SSE parser) |
| 2. Reasoning panel (collapsed, "not a finding" label) | `components/ChatWindow.jsx` + new `components/ReasoningPanel.jsx` |
| 3. Citation chips → FIR detail deep-link | `components/ChatWindow.jsx` (citations rendering) |
| 4. Warning banner (UNGROUNDED_CITATION / UNSOURCED_QUANTITY, strikethrough) | `components/ChatWindow.jsx` |
| 5. Context meter (prompt_tokens/budget from meta) | `components/ChatWindow.jsx` (small footer widget) |
| 6. Dashed `SAME_NAME_AS` edges + legend | `components/GraphView/NetworkGraph.jsx` |
| 7. Approximation label for centrality | `components/GraphView/NetworkGraph.jsx` |
| 8. Dead-endpoint removal | remove calls to endpoints that die with the LightRAG migration (`/api/llm/graph/subgraph/{fir_id}/` re-points to the new `/api/intel/graph/subgraph/…` route) |

Login and token storage are NOT on the §14.2 list — the fake login stays as-is
for now (recorded; if wiring the SSE consumer requires attaching the Bearer token,
`localStorage['access_token']` must be written by `Login.jsx` — that is change 1's
plumbing, same as token refresh is backend-only).
