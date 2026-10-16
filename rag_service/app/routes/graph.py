"""Graph routes (§2.1 SSE graph event data, §13.1 centrality panel).

Scope injection: Django attaches `districts` / `stations` query parameters
when proxying (from the validated JWT) — the RAG service is internal-only
and never trusts browser-supplied scope (§12). Missing scope parameters mean
unscoped access, which Django never sends in production.
"""
from __future__ import annotations

import asyncio

import networkx as nx
from fastapi import APIRouter, Depends, Query

from ..config import get_settings
from ..deps import require_api_key
from ..graph import centrality, neo4j_client, serializers

router = APIRouter(prefix="/v1/graph", tags=["graph"])


def _scope_params(districts: str | None, stations: str | None) -> dict:
    return {
        "districts": [d.strip().upper() for d in districts.split(",") if d.strip()] if districts else None,
        "stations": [s.strip().upper() for s in stations.split(",") if s.strip()] if stations else None,
    }


@router.get("/subgraph/{fir_id}", dependencies=[Depends(require_api_key)])
async def subgraph(
    fir_id: str,
    districts: str | None = Query(default=None),
    stations: str | None = Query(default=None),
):
    params = _scope_params(districts, stations)
    params.update({"fir_id": fir_id, "person_name": None})
    rows = await neo4j_client.run_template("EVIDENCE_TRAIL", params)
    nodes: dict[str, dict] = {}
    links: list[dict] = []
    for row in rows:
        fir_node = f"fir:{row.get('fir_key') or row.get('fir_id')}"
        nodes.setdefault(fir_node, {
            "id": fir_node,
            "label": f"FIR {row.get('fir_id')}",
            "properties": {"fir_id": row.get("fir_id"), "station": row.get("station_name"),
                            "crime_head": row.get("crime_head")},
            "_label": "FIR",
        })
        if row.get("evidence_ref"):
            kind = (row.get("evidence_kind") or "EVIDENCE").lower()
            ev_node = f"{kind}:{row['evidence_ref']}"
            nodes.setdefault(ev_node, {
                "id": ev_node, "label": str(row["evidence_ref"]),
                "properties": {"kind": row.get("evidence_kind")},
                "_label": row.get("evidence_kind") or "EVIDENCE",
            })
            links.append({"source": fir_node, "target": ev_node, "type": "HAS_EVIDENCE"})
    return {"nodes": list(nodes.values()), "links": links, "error": None}


@router.get("/network/{person_name}", dependencies=[Depends(require_api_key)])
async def network(
    person_name: str,
    districts: str | None = Query(default=None),
    stations: str | None = Query(default=None),
):
    settings = get_settings()
    params = _scope_params(districts, stations)
    params["person_name"] = person_name.strip().upper()
    rows = await neo4j_client.run_template("PERSON_NETWORK", params)
    graph = serializers.rows_to_force_graph(
        rows, src_key="src", dst_key="dst",
        src_label_key="src_name", dst_label_key="dst_name",
        type_key="rel_type", weight_key="weight",
    )
    if graph["nodes"]:
        G = nx.Graph()
        G.add_nodes_from(n["id"] for n in graph["nodes"])
        G.add_edges_from((l["source"], l["target"]) for l in graph["links"])
        metrics, approximate = await asyncio.wait_for(
            asyncio.to_thread(centrality.compute_metrics, G),
            timeout=settings.lightrag_timeout_s,
        )
        graph = serializers.apply_metrics(graph, metrics, approximate)
    return graph
