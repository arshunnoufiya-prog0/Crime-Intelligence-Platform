import CrimeTrendChart from '../components/CrimeTrendChart';
import AnalyticsChart from '../components/AnalyticsChart';
import { mockCrimeTrends } from '../data/mockData';

export default function Analytics() {
  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">📈 Analytics & Reports</h2>
      <AnalyticsChart />
      <CrimeTrendChart trendData={mockCrimeTrends} />
    </div>
  );
}
