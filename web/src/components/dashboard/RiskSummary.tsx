import React from 'react';
import { useCardioStore } from '../../store/useCardioStore';

const RiskSummary: React.FC = () => {
  const { prediction, selectedVessel, setSelectedVessel } = useCardioStore();

  const getRiskLevel = (probability: number): string => {
    if (probability >= 0.7) return 'High';
    if (probability >= 0.4) return 'Moderate';
    return 'Low';
  };

  const getRiskColor = (level: string): string => {
    switch (level) {
      case 'High': return 'bg-red-100 text-red-800';
      case 'Moderate': return 'bg-yellow-100 text-yellow-800';
      case 'Low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-bold mb-4">Risk Summary</h2>
      <div className="grid gap-4">
        {/* Overall CAD */}
        <div className="border rounded-lg p-4 bg-slate-50">
          <h3 className="font-semibold mb-2 text-slate-900">Overall CAD Risk</h3>
          {prediction && prediction.CAD ? (
            <>
              <p className="flex justify-between">
                <span>Probability:</span>
                <span className="font-medium">{(prediction.CAD.probability * 100).toFixed(1)}%</span>
              </p>
              <p className="flex justify-between mt-1">
                <span>Risk Level:</span>
                <span className={`px-2 py-1 text-xs rounded-full ${getRiskColor(getRiskLevel(prediction.CAD.probability))}`}>
                  {getRiskLevel(prediction.CAD.probability)}
                </span>
              </p>
            </>
          ) : (
            <p className="text-gray-500 text-sm">Submit patient details to view CAD risk score</p>
          )}
        </div>

        {/* Vessel Risks */}
        <div className="grid gap-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Coronary Vessels (Click to inspect)</p>
          {['LAD', 'LCX', 'RCA'].map(vessel => {
            const vesselData = prediction ? prediction[vessel] : null;
            const isSelected = selectedVessel === vessel;
            return (
              <div
                key={vessel}
                onClick={() => setSelectedVessel(isSelected ? null : vessel)}
                className={`border rounded-lg p-4 cursor-pointer transition-all ${
                  isSelected ? 'border-blue-500 ring-2 ring-blue-200 bg-blue-50/30' : 'hover:border-gray-400'
                }`}
              >
                <div className="flex justify-between items-center mb-1">
                  <h3 className="font-semibold">{vessel}</h3>
                  {isSelected && <span className="text-xs text-blue-600 font-medium">Selected in 3D</span>}
                </div>
                {vesselData ? (
                  <>
                    <p className="flex justify-between text-sm">
                      <span>Stenosis Probability:</span>
                      <span className="font-medium">{(vesselData.probability * 100).toFixed(1)}%</span>
                    </p>
                    <p className="flex justify-between mt-1 text-sm">
                      <span>Status:</span>
                      <span className={`px-2 py-0.5 text-xs rounded-full ${getRiskColor(getRiskLevel(vesselData.probability))}`}>
                        {getRiskLevel(vesselData.probability)}
                      </span>
                    </p>
                  </>
                ) : (
                  <p className="text-gray-400 text-xs italic">
                    {prediction ? 'Model pending training for this vessel' : 'Awaiting patient analysis'}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default RiskSummary;