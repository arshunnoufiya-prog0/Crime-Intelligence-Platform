import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

/**
 * §14.2 change 8 — dead endpoint removal: the old /api/llm/graph/subgraph/
 * route died with the LightRAG migration; this now calls the intel route.
 */
function useGraphData(firId) {
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchGraph = useCallback(async (id) => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('access_token');
      const resp = await axios.get(`/api/intel/graph/subgraph/${id}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = resp.data?.ok === true ? resp.data.data : resp.data;
      if (data && data.error) {
        setError(data.error);
        return;
      }
      setGraph({
        approximate_centrality: Boolean(data?.approximate_centrality),
        nodes: (data?.nodes || []).map((n) => ({
          id: n.id,
          label: (n.properties && (n.properties.name || n.properties.fir_id)) || n.label || n.id,
          ...n.properties,
          degree: n.degree || 0,
          betweenness: n.betweenness || 0,
          eigenvector: n.eigenvector || 0,
          community: n.community || 0,
          _label: n._label || n.label,
        })),
        links: (data?.links || []).map((l) => ({
          source: l.source,
          target: l.target,
          type: l.type || 'RELATED',
        })),
      });
    } catch (err) {
      setError(err.message || err.response?.data?.error?.message || 'Failed to fetch graph');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchGraph(firId);
  }, [firId, fetchGraph]);

  return { graph, loading, error, refetch: fetchGraph };
}

export default useGraphData;
export { useGraphData };
