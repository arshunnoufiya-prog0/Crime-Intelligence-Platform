import CrimeCard from '../components/CrimeCard';
import { mockCases } from '../data/mockData';

export default function FIRDetails() {
  return (
    <div className="p-6">
      <h2 className="text-2xl font-bold mb-4">📋 FIR Details</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {mockCases.map(caseData => (
          <CrimeCard
            key={caseData.id}
            caseId={caseData.id}
            firNumber={caseData.firNumber}
            crimeType={caseData.crimeType}
            location={caseData.location}
            date={caseData.date}
            accused={caseData.accused}
            status={caseData.status}
          />
        ))}
      </div>
    </div>
  );
}
