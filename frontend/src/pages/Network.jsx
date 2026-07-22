import { mockNetworkGraph } from '../data/mockData';

export default function Network() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">🔗 Criminal Network Analysis</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Graph Placeholder */}
        <div className="lg:col-span-2 bg-white rounded-lg border border-gray-200 p-4">
          <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
            <div className="text-center text-gray-500">
              <p className="text-lg mb-2">🔗 Network Graph</p>
              <p className="text-sm">react-force-graph integration coming soon</p>
            </div>
          </div>
        </div>

        {/* Nodes List */}
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-bold mb-4">Nodes ({mockNetworkGraph.nodes.length})</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {mockNetworkGraph.nodes.map(node => (
              <div key={node.id} className="bg-gray-50 p-2 rounded text-sm">
                <p className="font-semibold">{node.label}</p>
                <p className="text-xs text-gray-600">Type: {node.type}</p>
                <p className="text-xs text-gray-600">Centrality: {(node.centrality * 100).toFixed(0)}%</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
