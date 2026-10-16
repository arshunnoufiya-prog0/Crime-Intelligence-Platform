"""Row → force-graph serializers (spec §12.5 graph event, §14.2 changes 6–7).

Flat rows only (§13 invariant). The SAME_NAME_AS type is preserved on links
so the frontend renders dashed "possible identity match — not confirmed"
edges, and the `approximate` flag rides along for the §14.2 change 7 label.
"""
from __future__ import annotations


def rows_to_force_graph(rows: list[dict], *, src_key: str, dst_key: str,
                        src_label_key: str | None = None,
                        dst_label_key: str | None = None,
                        type_key: str = "rel_type",
                        weight_key: str | None = None) -> dict:
    nodes: dict[str, dict] = {}
    links: list[dict] = []
    for row in rows:
        src, dst = row.get(src_key), row.get(dst_key)
        if not src or not dst:
            continue
        if src not in nodes:
            nodes[src] = {"id": src, "label": (row.get(src_label_key) if src_label_key else src) or src}
        if dst not in nodes:
            nodes[dst] = {"id": dst, "label": (row.get(dst_label_key) if dst_label_key else dst) or dst}
        link = {"source": src, "target": dst, "type": row.get(type_key) or "RELATED"}
        if weight_key and row.get(weight_key) is not None:
            link["weight"] = row[weight_key]
        if row.get("source_fir_id"):
            link["source_fir_id"] = row["source_fir_id"]
        links.append(link)
    return {"nodes": list(nodes.values()), "links": links}


def apply_metrics(graph: dict, metrics: dict, approximate: bool) -> dict:
    """Attach degree/betweenness/eigenvector/community to nodes and flag
    approximation at the top level (§13.1/§14.2 change 7)."""
    community_of: dict[str, int] = {}
    for idx, members in enumerate(metrics.get("communities", [])):
        for member in members:
            community_of[member] = idx
    degree = metrics.get("degree_centrality", {})
    betweenness = metrics.get("betweenness_centrality", {})
    eigen = metrics.get("eigenvector_centrality", {})
    for node in graph.get("nodes", []):
        node_id = node["id"]
        node["degree"] = round(degree.get(node_id, 0.0), 4)
        node["betweenness"] = round(betweenness.get(node_id, 0.0), 4)
        node["eigenvector"] = round(eigen.get(node_id, 0.0), 4)
        node["community"] = community_of.get(node_id, -1)
    graph["approximate_centrality"] = approximate
    return graph
