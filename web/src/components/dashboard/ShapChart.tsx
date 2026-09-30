import React from 'react';
import { useCardioStore } from '../../store/useCardioStore';

const ShapChart: React.FC<{ vessel: string }> = ({ vessel }) => {
  const { explanation } = useCardioStore();

  const targetExplanation = explanation ? explanation[vessel] : null;
  const contributions = targetExplanation?.contributions || [];

  // Compute maximum SHAP magnitude for relative bar scaling
  const maxMagnitude = contributions.length > 0
    ? Math.max(...contributions.map((c: any) => Math.abs(c.shap)), 0.01)
    : 1;

  // Clean feature prefix like "num__", "remainder__"
  const cleanFeatureName = (name: string) => {
    return name.replace(/^(num__|cat__|remainder__)/, '');
  };

  return (
    <div className="bg-white rounded-xl shadow-md p-5 border border-slate-100">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold text-slate-800">
          {vessel} Feature Attribution (SHAP)
        </h3>
        {targetExplanation?.base_value !== undefined && (
          <span className="text-[11px] text-slate-500 bg-slate-50 px-2 py-0.5 rounded border border-slate-200">
            Baseline: {targetExplanation.base_value.toFixed(2)}
          </span>
        )}
      </div>

      {contributions.length > 0 ? (
        <div className="space-y-3">
          <div className="flex items-center justify-between text-[11px] text-slate-400 border-b pb-1 font-medium">
            <span>Clinical Feature</span>
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1 text-red-600">
                <span className="w-2 h-2 rounded-full bg-red-500 inline-block"></span> +Risk
              </span>
              <span className="flex items-center gap-1 text-blue-600">
                <span className="w-2 h-2 rounded-full bg-blue-500 inline-block"></span> -Risk
              </span>
              <span className="w-14 text-right">SHAP Impact</span>
            </div>
          </div>

          <div className="space-y-2.5">
            {contributions.map((contrib: any, index: number) => {
              const isPositive = contrib.shap >= 0;
              const barWidthPercent = Math.min(100, Math.max(8, (Math.abs(contrib.shap) / maxMagnitude) * 100));

              return (
                <div key={index} className="flex items-center justify-between text-xs gap-3">
                  <div className="w-36 truncate font-medium text-slate-700" title={cleanFeatureName(contrib.feature)}>
                    {cleanFeatureName(contrib.feature)}
                    {contrib.value !== undefined && contrib.value !== null && (
                      <span className="text-[10px] text-slate-400 font-normal ml-1">
                        ({typeof contrib.value === 'number' ? contrib.value.toFixed(1) : contrib.value})
                      </span>
                    )}
                  </div>

                  <div className="flex-1 bg-slate-100 rounded-full h-2.5 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isPositive ? 'bg-red-500' : 'bg-blue-500'
                      }`}
                      style={{ width: `${barWidthPercent}%` }}
                    ></div>
                  </div>

                  <div className={`w-14 text-right font-mono text-[11px] font-semibold ${
                    isPositive ? 'text-red-600' : 'text-blue-600'
                  }`}>
                    {isPositive ? '+' : ''}{contrib.shap.toFixed(3)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="py-6 text-center text-slate-400 text-xs">
          No explanation data available for {vessel} yet. Run a prediction to see feature attributions.
        </div>
      )}
    </div>
  );
};

export default ShapChart;