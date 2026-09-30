import React from 'react';
import './App.css';
import PatientForm from './components/form/PatientForm';
import RiskSummary from './components/dashboard/RiskSummary';
import ThreeDViewer from './components/viewer/ThreeDViewer';
import ShapChart from './components/dashboard/ShapChart';
import MeasurementTable from './components/dashboard/MeasurementTable';
import DisclaimerBanner from './components/common/DisclaimerBanner';
import { useCardioStore } from './store/useCardioStore';

function App() {
  const { prediction, selectedVessel, setSelectedVessel } = useCardioStore();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Top Navigation */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-red-600 flex items-center justify-center text-white font-bold shadow-md shadow-red-200">
              🫀
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-slate-900 tracking-tight">CardioLens</h1>
                <span className="text-[10px] font-semibold uppercase tracking-wider bg-red-100 text-red-700 px-2 py-0.5 rounded-full">
                  AI Decision Support
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Interactive 3D Cardiovascular Risk Visualization & Prediction System
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={`${import.meta.env.VITE_API_URL || '/api'}/docs`}
              target="_blank"
              rel="noreferrer"
              className="text-xs font-medium text-slate-600 hover:text-blue-600 px-3 py-1.5 rounded-lg border border-slate-200 hover:border-blue-200 bg-white transition-all shadow-sm"
            >
              API Docs
            </a>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <DisclaimerBanner />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-4">
          {/* Left Column: Form and 3D Viewer */}
          <div className="lg:col-span-6 space-y-6">
            <PatientForm />
            <ThreeDViewer selectedVessel={selectedVessel} />
          </div>

          {/* Right Column: Risk Summary, SHAP Explanations & Measurements */}
          <div className="lg:col-span-6 space-y-6">
            <RiskSummary />

            {/* Target Selector Tabs */}
            <div className="bg-white rounded-xl shadow-md p-4 border border-slate-100">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Select Target for Explanation:
                </span>
                <div className="flex gap-1.5">
                  {(['CAD', 'LAD', 'LCX', 'RCA'] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setSelectedVessel(t)}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                        selectedVessel === t
                          ? 'bg-blue-600 text-white shadow-sm'
                          : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              {selectedVessel ? (
                <div className="space-y-4">
                  <ShapChart vessel={selectedVessel} />
                  <MeasurementTable vessel={selectedVessel} />
                </div>
              ) : (
                <div className="text-center py-6 text-slate-400 text-sm">
                  Select a vessel or CAD above to inspect clinical feature contributions
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
