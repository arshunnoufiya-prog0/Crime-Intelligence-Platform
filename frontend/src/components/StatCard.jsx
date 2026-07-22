
export default function StatCard({ title, value, icon, bgColor }) {
  return (
    <div className={`${bgColor} rounded-lg p-6 shadow-md text-white`}>
      <div className="flex justify-between items-center">
        <div>
          <p className="text-sm font-medium opacity-90">{title}</p>
          <h3 className="text-3xl font-bold mt-2">{value}</h3>
        </div>
        <div className="text-4xl opacity-50">{icon}</div>
      </div>
    </div>
  );
}
