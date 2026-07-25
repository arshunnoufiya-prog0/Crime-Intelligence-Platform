import { useRef, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useGraphData } from './useGraphData';
import './NetworkGraph.css';

const COLORS = [
  '#FF6B6B', '#4ECDC4', '#FFD93D', '#6C5CE7',
  '#00B894', '#E17055', '#0984E3', '#FDCB6E',
  '#E84393', '#00CEC9',
];

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
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 0.5;
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
      <ForceGraph2D
        ref={graphRef}
        graphData={graph}
        nodeCanvasObject={nodeCanvasObject}
        nodeColor={nodeColor}
        linkDirectionalArrowLength={0}
        linkWidth={(link) => link.type === 'SIMILAR_PATTERN' ? 2 : 1}
        linkColor={(link) => link.type === 'SIMILAR_PATTERN' ? '#e74c3c' : '#999'}
        linkLabel={(link) => link.type}
        onNodeClick={handleNodeClick}
        width={780}
        height={450}
        cooldown={1500}
      />
    </div>
  );
}