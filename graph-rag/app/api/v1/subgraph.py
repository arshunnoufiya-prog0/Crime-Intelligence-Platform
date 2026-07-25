"""Subgraph endpoint — returns force-graph-ready JSON with centrality + community."""
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ....config import get_settings
from ....core.exceptions import GraphRagError, new_request_id
from ....graphstore.neo4j_client import neo4j_client
from ....analysis.subgraph_builder import build_networkx_graph
from ....analysis.metrics import compute_metrics, to_force_graph

router = APIRouter(tags=["subgraph"])


async def _auth(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail={"error": "invalid api key", "code": "unauthorized"})


@router.get("/subgraph/{fir_id}")
async def get_subgraph(
    fir_id: str,
    max_hops: int = Query(default=2, ge=1, le=3),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    _auth=Depends(_auth),
):
    rid = new_request_id()
    settings = get_settings()

    try:
        # Resolve fir_id -> fir_key (may be ambiguous across stations)
        from ....cypher.validator import resolve_fir_key
        try:
            fir_key = await resolve_fir_key(fir_id)
        except GraphRagError as exc:
            if exc.code == "ambiguous_fir_id":
                raise HTTPException(
                    status_code=400,
                    detail={"error": "ambiguous_fir_id", "message": exc.message, "request_id": rid},
                )
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": exc.message, "request_id": rid},
            )

        # Bounded traversal
        rows = await neo4j_client.get_subgraph_rows(fir_key, max_hops=min(max_hops, settings.subgraph_max_hops))

        if not rows.get("nodes"):
            return {"nodes": [], "links": [], "error": None, "request_id": rid}

        G = build_networkx_graph(rows)
        if G.number_of_nodes() > settings.subgraph_max_nodes:
            # trim by degree centrality (keep highest-degree nodes)
            deg = dict(G.degree())
            keep = sorted(deg.keys(), key=lambda n: deg[n], reverse=True)[: settings.subgraph_max_nodes]
            G = G.subgraph(keep).copy()

        metrics = compute_metrics(G)
        fg = to_force_graph(G, metrics)
        return {**fg, "error": None, "request_id": rid}

    except GraphRagError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": exc.code, "message": exc.message, "request_id": rid},
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(exc), "request_id": rid},
        )