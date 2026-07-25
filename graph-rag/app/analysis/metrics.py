"""Centrality + community detection. Runs ONLY inside a thread pool —
never on the FastAPI event loop. Output is force-graph-ready:
{nodes:[{id,label,...metrics,community}], links:[{source,target,type}]}.
"""
from __future__ import annotations

import networkx as nx


def compute_metrics(G: nx.Graph) -> dict:
    return {
        "degree_centrality": nx.degree_centrality(G),
        "betweenness_centrality": nx.betweenness_centrality(G, k=min(len(G), 100)) if len(G) > 1 else {},
        "eigenvector_centrality": _safe_eigenvector(G),
        "communities": _safe_communities(G),
    }


def _safe_eigenvector(G: nx.Graph) -> dict:
    if len(G) == 0:
        return {}
    try:
        return nx.eigenvector_centrality(G, max_iter=500)
    except Exception:
        # PowerIteration convergence may fail on disconnected/degenerate graphs
        try:
            return nx.eigenvector_centrality_numpy(G)
        except Exception:
            return {n: 0.0 for n in G.nodes()}


def _safe_communities(G: nx.Graph):
    if len(G) == 0:
        return []
    try:
        return [list(c) for c in nx.algorithms.community.louvain_communities(G, seed=42)]
    except Exception:
        # Louvain may raise on tiny or disconnected graphs in some versions
        return [list(G.nodes())]


def to_force_graph(G: nx.Graph, metrics: dict) -> dict:
    communities = metrics["communities"]
    node_to_comm: dict[str, int] = {}
    for idx, members in enumerate(communities):
        for m in members:
            node_to_comm[m] = idx
    nodes: list[dict] = []
    for nid, data in G.nodes(data=True):
        label = data.get("_label")
        community = node_to_comm.get(nid, -1)
        nodes.append({
            "id": nid,
            "label": label,
            "properties": {k: v for k, v in data.items() if not k.startswith("_")},
            "degree": metrics["degree_centrality"].get(nid, 0.0),
            "betweenness": metrics["betweenness_centrality"].get(nid, 0.0),
            "eigenvector": metrics["eigenvector_centrality"].get(nid, 0.0),
            "community": community,
        })
    links: list[dict] = []
    for s, t, data in G.edges(data=True):
        links.append({"source": s, "target": t, "type": data.get("type", "RELATED")})
    return {"nodes": nodes, "links": links}
