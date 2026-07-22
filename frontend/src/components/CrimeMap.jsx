
export default function CrimeMap({ hotspots = [] }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">🗺️ Crime Hotspots</h3>
      <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center border-2 border-dashed border-gray-300">
        <div className="text-center text-gray-500">
          <p className="text-lg mb-2">🗺️ Map Loading...</p>
          <p className="text-sm">Leaflet integration coming soon</p>
          <p className="text-xs mt-2 text-gray-400">Total hotspots: {hotspots.length}</p>
        </div>
      </div>

      {/* Hotspots List */}
      <div className="mt-4">
        <p className="font-semibold text-sm mb-2">Detected Hotspots:</p>
        <div className="space-y-2">
          {hotspots.map((spot, idx) => (
            <div key={idx} className="bg-gray-50 p-2 rounded text-sm">
              <p className="font-medium">{spot.location}</p>
              <p className="text-xs text-gray-600">Crime Type: {spot.crimeType} | Count: {spot.count}</p>
              <p className="text-xs text-gray-500">Coordinates: {spot.lat}, {spot.lng}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
