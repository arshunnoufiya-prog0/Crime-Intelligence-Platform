import CrimeMap from '../components/CrimeMap';
import { mockHotspots } from '../data/mockData';

export default function CrimeMapPage() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">🗺️ Crime Hotspot Map</h2>
      <CrimeMap hotspots={mockHotspots} />
    </div>
  );
}
