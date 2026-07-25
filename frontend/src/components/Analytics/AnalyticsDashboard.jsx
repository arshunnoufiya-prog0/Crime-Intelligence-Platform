import { useState, useEffect } from 'react';
import Plot from 'react-plotly.js';
import axios from 'axios';
import './AnalyticsDashboard.css';

export default function AnalyticsDashboard() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    axios.get('/api/firs/stats/', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((res) => setStats(res.data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="analytics-status">Loading analytics...</div>;
  if (error) return <div className="analytics-status" style={{ color: '#e53e3e' }}>Error: {error}</div>;

  const byStatus = stats?.by_status || {};
  const byCategory = stats?.by_category || {};
  const byCrime = stats?.by_crime_head || {};
  const byMonth = stats?.by_month || {};

  const statusLabels = Object.keys(byStatus);
  const statusValues = Object.values(byStatus);
  const categoryLabels = Object.keys(byCategory);
  const categoryValues = Object.values(byCategory);
  const crimeLabels = Object.keys(byCrime);
  const crimeValues = Object.values(byCrime);
  const monthLabels = Object.keys(byMonth).sort();

  return (
    <div className="analytics-box">
      <h3 className="analytics-title">📊 Crime Statistics</h3>
      <div className="analytics-grid">
        <Plot
          data={[{
            type: 'bar',
            x: crimeLabels,
            y: crimeValues,
            marker: { color: '#3B82F6' },
          }]}
          layout={{
            title: 'Crimes by Type',
            height: 300,
            margin: { l: 50, r: 10, t: 40, b: 80 },
          }}
          config={{ responsive: true }}
          style={{ width: '100%' }}
        />
        <Plot
          data={[{
            type: 'pie',
            labels: statusLabels,
            values: statusValues,
            marker: { colors: ['#10B981', '#F59E0B', '#EF4444'] },
          }]}
          layout={{
            title: 'Case Status',
            height: 300,
            margin: { l: 10, r: 10, t: 40, b: 10 },
          }}
          config={{ responsive: true }}
          style={{ width: '100%' }}
        />
        <Plot
          data={[{
            type: 'pie',
            labels: categoryLabels,
            values: categoryValues,
            marker: { colors: ['#8B5CF6', '#EC4899'] },
          }]}
          layout={{
            title: 'Case Category',
            height: 300,
            margin: { l: 10, r: 10, t: 40, b: 10 },
          }}
          config={{ responsive: true }}
          style={{ width: '100%' }}
        />
        <Plot
          data={[{
            type: 'scatter',
            mode: 'lines+markers',
            x: monthLabels,
            y: monthLabels.map((l) => byMonth[l] || 0),
            marker: { color: '#F59E0B' },
          }]}
          layout={{
            title: 'FIRs by Month',
            height: 300,
            margin: { l: 50, r: 10, t: 40, b: 80 },
          }}
          config={{ responsive: true }}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  );
}