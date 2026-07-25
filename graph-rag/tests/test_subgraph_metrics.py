"""Test NetworkX subgraph metrics produce expected fields."""
import networkx as nx

from app.analysis.subgraph_builder import build_networkx_graph
from app.analysis.metrics import compute_metrics, to_force_graph


def test_metrics_on_small_graph():
    G = nx.Graph()
    G.add_node("a", fir_key="a@ps1")
    G.add_node("b", fir_key="b@ps1")
    G.add_node("c", fir_key="c@ps1")
    G.add_edge("a", "b", type="SIMILAR_PATTERN")
    G.add_edge("b", "c", type="INVOLVES_ACCUSED")

    metrics = compute_metrics(G)
    assert "degree_centrality" in metrics
    assert "betweenness_centrality" in metrics
    assert "eigenvector_centrality" in metrics
    assert "communities" in metrics
    assert isinstance(metrics["communities"], list)

    fg = to_force_graph(G, metrics)
    assert "nodes" in fg and "links" in fg
    for n in fg["nodes"]:
        assert "degree" in n and "betweenness" in n and "eigenvector" in n and "community" in n