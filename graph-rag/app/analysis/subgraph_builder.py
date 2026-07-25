"""Build a networkx.Graph from Neo4j graphstore rows. The caller passes the
{nodes, edges} dict from neo4j_client.get_subgraph_rows().
"""
from __future__ import annotations

import networkx as nx


def build_networkx_graph(rows: dict) -> nx.Graph:
    """rows: {"nodes": [{label, properties}], "edges": [{source, target, type}]}."""
    G = nx.Graph()
    nodes = rows.get("nodes") or []
    for n in nodes:
        props = n.get("properties", {}) or {}
        nid = props.get("fir_key") or props.get("person_key") or props.get("name") or props.get("number") \
            or props.get("plate") or props.get("account_id") or props.get("label") or f"node-{len(G)}"
        attrs = dict(props)
        attrs["_label"] = n.get("label")
        attrs["_id"] = nid
        G.add_node(nid, **attrs)
    edges = rows.get("edges") or []
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s and t:
            G.add_edge(s, t, type=e.get("type"))
    return G
