
export default function AnalyticsChart() {
  const stats = [
    { label: "Total Cases", value: "1,245", color: "blue" },
    { label: "Active Investigations", value: "342", color: "orange" },
    { label: "Solved Cases", value: "903", color: "green" },
    { label: "Suspects Arrested", value: "567", color: "red" }
  ];

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="font-bold text-lg mb-4">📊 Crime Statistics</h3>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, idx) => (
          <div key={idx} className={`bg-${stat.color}-50 p-4 rounded-lg border border-${stat.color}-200`}>
            <p className="text-xs font-medium text-gray-600">{stat.label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-2">{stat.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
