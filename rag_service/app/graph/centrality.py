"""NetworkX centrality over pulled subgraphs (spec §13.1).

Rules (§13.1):
  * degree_centrality — always;
  * betweenness_centrality — exact ONLY when n <= 2000, otherwise the
    k-sample approximation with k = min(500, n), and the result is labeled
    approximate in the response (§14.2 change 7 renders that label);
  * eigenvector_centrality_numpy — wrapped for non-convergence, falling
    back to degree;
  * louvain_communities for clustering.

Never run centrality over the whole graph on the request path — callers pull
a bounded subgraph via a template first and hand it here (routes wrap the
sync compute in asyncio.to_thread; this module stays pure/sync for testing).
"""
from __future__ import annotations

import networkx as nx

BETWEENNESS_EXACT_MAX = 2000
APPROX_SAMPLE = 500


def compute_metrics(G: nx.Graph) -> tuple[dict, bool]:
    """Returns (metrics, approximate) — approximate=True when betweenness
    used sampling (§13.1)."""
    n = G.number_of_nodes()
    approximate = False
    degree = nx.degree_centrality(G)
    if n <= BETWEENNESS_EXACT_MAX:
        betweenness = nx.betweenness_centrality(G) if n > 1 else {}
    else:
        betweenness = nx.betweenness_centrality(G, k=min(APPROX_SAMPLE, n))
        approximate = True
    eigenvector = _safe_eigenvector(G, degree)
    communities = _safe_communities(G)
    metrics = {
        "degree_centrality": degree,
        "betweenness_centrality": betweenness,
        "eigenvector_centrality": eigenvector,
        "communities": communities,
    }
    return metrics, approximate


def _safe_eigenvector(G: nx.Graph, degree: dict) -> dict:
    if G.number_of_nodes() == 0:
        return {}
    try:
        return nx.eigenvector_centrality_numpy(G)
    except Exception:
        try:
            return nx.eigenvector_centrality(G, max_iter=500)
        except Exception:
            return {node: degree.get(node, 0.0) for node in G.nodes()}


def _safe_communities(G: nx.Graph) -> list[list[str]]:
    if G.number_of_nodes() == 0:
        return []
    try:
        return [sorted(c) for c in nx.algorithms.community.louvain_communities(G, seed=42)]
    except Exception:
        return [sorted(G.nodes())]
