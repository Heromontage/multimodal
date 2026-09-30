import React from 'react';
import { useCardioStore } from '../../store/useCardioStore';

const MeasurementTable: React.FC<{ vessel: string }> = ({ vessel }) => {
  const { measurements, explanation } = useCardioStore();
  const contributions = new Map(
    (explanation?.[vessel]?.contributions || []).map((item: { feature: string; shap: number }) =>
      [item.feature.replace(/^(num__|cat__|remainder__)/, ''), item.shap]
    )
  );

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-bold mb-4">
        Measurement Table for {vessel}
      </h2>
      {measurements && measurements.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="sticky top-0 bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Feature
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Value
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reference Range
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Contribution
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {measurements.map((measurement, index) => (
                <tr key={index} className={`hover:bg-gray-50 ${index % 2 === 1 ? 'bg-gray-50' : ''}`}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {measurement.feature}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {measurement.value.toFixed(1)} {measurement.unit}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    [{measurement.ref_range[0]} - {measurement.ref_range[1]}] {measurement.unit}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span className={`px-2 py-1 text-xs rounded-full
                      ${measurement.status === 'high' ? 'bg-red-100 text-red-800' :
                        measurement.status === 'low' ? 'bg-blue-100 text-blue-800' :
                        'bg-green-100 text-green-800'}`}>
                      {measurement.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-mono">
                    {contributions.has(measurement.feature)
                      ? `${(contributions.get(measurement.feature) as number) >= 0 ? '+' : ''}${(contributions.get(measurement.feature) as number).toFixed(3)}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-500 text-center py-8">No measurement data available</p>
      )}
    </div>
  );
};

export default MeasurementTable;
