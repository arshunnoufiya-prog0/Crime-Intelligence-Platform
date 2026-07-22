import StatCard from '../components/StatCard';
import AnalyticsChart from '../components/AnalyticsChart';
import CrimeTrendChart from '../components/CrimeTrendChart';
import CrimeMap from '../components/CrimeMap';
import { mockCrimeTrends, mockHotspots } from '../data/mockData';

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard title="Active Cases" value="342" icon="📋" bgColor="bg-blue-600" />
        <StatCard title="Suspects" value="1,245" icon="👤" bgColor="bg-red-600" />
        <StatCard title="Arrests" value="567" icon="🚨" bgColor="bg-orange-600" />
        <StatCard title="Solved Cases" value="903" icon="✅" bgColor="bg-green-600" />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Analytics */}
        <div className="lg:col-span-2 space-y-6">
          <AnalyticsChart />
          <CrimeTrendChart trendData={mockCrimeTrends} />
        </div>

        {/* Right: Map */}
        <div>
          <CrimeMap hotspots={mockHotspots} />
        </div>
      </div>
    </div>
  );
}
