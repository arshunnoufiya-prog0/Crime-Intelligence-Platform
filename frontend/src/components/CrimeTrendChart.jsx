
export default function CrimeTrendChart({ trendData = [] }) {
  if (trendData.length === 0) {
    return <div className="text-gray-500 p-4">No data available</div>;
  }

  const crimeTypes = Object.keys(trendData[0]).filter(k => k !== 'month');

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">📈 Crime Trends (Last 5 Months)</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-gray-300">
              <th className="text-left py-2 px-2 font-semibold">Month</th>
              {crimeTypes.map(type => (
                <th key={type} className="text-center py-2 px-2 font-semibold capitalize">{type}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trendData.map((row, idx) => (
              <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-50' : 'bg-white'}>
                <td className="py-2 px-2 font-medium">{row.month}</td>
                {crimeTypes.map(type => (
                  <td key={type} className="text-center py-2 px-2">
                    <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full text-xs font-semibold">
                      {row[type]}
                    </span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
