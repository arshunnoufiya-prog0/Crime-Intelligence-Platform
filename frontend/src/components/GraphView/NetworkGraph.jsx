import { useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useGraphData } from './useGraphData';
import '../../styles/intel.css';
import './NetworkGraph.css';

const COLORS = [
  '#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7',
  '#00B894', '#E17055', '#0984E3', '#FDCB6E',
  '#E84393', '#00CEC9',
];

/**
 * §14.2 change 6 — dashed edges for SAME_NAME_AS with a legend entry
 * "possible identity match — not confirmed".
 * §14.2 change 7 — approximation label when the backend says centrality was
 * sampled (graph.approximate_centrality, §13.1).
 */
export default function NetworkGraph({ firId = '' }) {
  const { graph, loading, error, refetch } = useGraphData(firId);
  const graphRef = useRef(null);

  const handleNodeClick = useCallback((node) => {
    if (node._label === 'FIR' || node.fir_id || node.fir_key) {
      const id = node.fir_id || (node.fir_key || '').split('@')[0];
      if (id) refetch(id);
    }
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 800);
      graphRef.current.zoom(2, 600);
    }
  }, [refetch]);

  const nodeColor = (node) => {
    const c = node.community || 0;
    return COLORS[c % COLORS.length];
  };

  const nodeCanvasObject = (node, ctx) => {
    const label = node.label || node.id || '?';
    const size = Math.max(3, (node.degree || 0.1) * 30) + 4;
    const color = nodeColor(node);

    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    if (node._label === 'FIR') {
      ctx.strokeStyle = '#1f2937';
      ctx.lineWidth = 2;
    } else {
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 0.5;
    }
    ctx.stroke();

    ctx.font = '10px Sans-serif';
    ctx.fillStyle = '#333';
    ctx.fillText(label, node.x + size + 2, node.y + 4);
  };

  if (loading) {
    return (
      <div className="graph-box">
        <h3 className="graph-title">🔗 Criminal Network</h3>
        <div className="graph-status">Loading network graph...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="graph-box">
        <h3 className="graph-title">🔗 Criminal Network</h3>
        <div className="graph-status error">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="graph-box">
      <h3 className="graph-title">🔗 Criminal Network</h3>
      <div className="graph-legend">
        <span className="legend-item"><span className="legend-line legend-solid" /> confirmed (from FIR records)</span>
        <span className="legend-item"><span className="legend-line legend-dashed" /> possible identity match — not confirmed</span>
        {graph?.approximate_centrality && (
          <span className="legend-item legend-approx">centrality approximate (sampled over large subgraph)</span>
        )}
      </div>
      <ForceGraph2D
        ref={graphRef}
        graphData={graph}
        nodeCanvasObject={nodeCanvasObject}
        nodeColor={nodeColor}
        linkDirectionalArrowLength={0}
        linkWidth={(link) => link.type === 'SIMILAR_PATTERN' ? 2 : 1}
        linkLineDash={(link) => (link.type === 'SAME_NAME_AS' ? [4, 3] : null)}
        linkColor={(link) => (link.type === 'SAME_NAME_AS' ? '#b45309' : (link.type === 'SIMILAR_PATTERN' ? '#e74c3c' : '#999'))}
        linkLabel={(link) => (link.type === 'SAME_NAME_AS' ? 'possible identity match — not confirmed' : link.type)}
        onNodeClick={handleNodeClick}
        width={780}
        height={450}
        cooldown={1500}
      />
    </div>
  );
}
