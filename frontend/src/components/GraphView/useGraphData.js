import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

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
      const resp = await axios.get(`/api/llm/graph/subgraph/${id}/`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const data = resp.data;
      if (data.error) {
        setError(data.error);
        return;
      }
      setGraph({
        nodes: (data.nodes || []).map((n) => ({
          id: n.id,
          label: (n.properties && (n.properties.name || n.properties.fir_id || n.properties.label)) || n.id,
          ...n.properties,
          degree: n.degree || 0,
          betweenness: n.betweenness || 0,
          eigenvector: n.eigenvector || 0,
          community: n.community || 0,
          _label: n.label,
        })),
        links: (data.links || []).map((l) => ({
          source: l.source,
          target: l.target,
          type: l.type || 'RELATED',
        })),
      });
    } catch (err) {
      setError(err.message || err.response?.data?.error || 'Failed to fetch graph');
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