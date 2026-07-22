
export default function CrimeCard({ caseId, firNumber, crimeType, location, date, accused, status }) {
  // eslint-disable-next-line no-unused-vars
  const _caseId = caseId;
  const statusColor = {
    "Under Investigation": "bg-yellow-100 text-yellow-800",
    "Closed": "bg-green-100 text-green-800",
    "Arrested": "bg-red-100 text-red-800"
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm hover:shadow-md transition">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h4 className="font-bold text-gray-900">{firNumber}</h4>
          <p className="text-sm text-gray-500">{date}</p>
        </div>
        <span className={`text-xs font-semibold px-2 py-1 rounded ${statusColor[status] || 'bg-gray-100'}`}>
          {status}
        </span>
      </div>
      <p className="text-sm font-medium text-gray-700 mb-2">{crimeType}</p>
      <p className="text-xs text-gray-600 mb-3">📍 {location}</p>
      <div className="border-t pt-3">
        <p className="text-xs font-semibold text-gray-700 mb-2">Accused ({accused?.length || 0})</p>
        <div className="flex flex-wrap gap-1">
          {accused?.map(acc => (
            <span key={acc.id} className="bg-red-50 text-red-700 text-xs px-2 py-1 rounded">
              {acc.name}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
