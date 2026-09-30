import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useCardioStore } from '../../store/useCardioStore';

type FeatureInfo = { type: string; default: number; unit?: string };
type FeatureSchema = Record<string, FeatureInfo>;
type Sample = { name: string; features: Record<string, number> };

const API_BASE = import.meta.env.VITE_API_URL || '/api';
const BASIC_FIELDS = ['Age', 'Sex', 'BP', 'PR', 'DM', 'HTN', 'Typical Chest Pain', 'FBS'];

const PatientForm: React.FC = () => {
  const { setPrediction, setExplanation, setMeasurements, setSelectedVessel } = useCardioStore();
  const [schema, setSchema] = useState<FeatureSchema>({});
  const [formData, setFormData] = useState<Record<string, number>>({});
  const [samples, setSamples] = useState<Sample[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([axios.get(`${API_BASE}/schema`), axios.get(`${API_BASE}/samples`)])
      .then(([schemaResponse, samplesResponse]) => {
        if (!active) return;
        const nextSchema = schemaResponse.data.schema as FeatureSchema;
        setSchema(nextSchema);
        setFormData(Object.fromEntries(
          Object.entries(nextSchema).map(([name, info]) => [name, info.default ?? 0])
        ));
        setSamples(samplesResponse.data.samples || []);
      })
      .catch(() => { if (active) setError('Could not load the clinical feature schema. Check the API connection.'); });
    return () => { active = false; };
  }, []);

  const runPrediction = async (features: Record<string, number>) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.post(`${API_BASE}/predict`, { features });
      setPrediction(response.data.predictions);
      setExplanation(response.data.explanations);
      setMeasurements(response.data.measurements);
      setSelectedVessel('CAD');
    } catch (failure: any) {
      const detail = failure.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'Prediction failed. Check the API connection and input values.');
    } finally {
      setLoading(false);
    }
  };

  const selectSample = (sample: Sample) => {
    const next = { ...Object.fromEntries(Object.entries(schema).map(([name, info]) => [name, info.default ?? 0])), ...sample.features };
    setFormData(next);
    void runPrediction(next);
  };

  const renderField = (name: string) => {
    const info = schema[name];
    if (!info) return null;
    const id = `feature-${name.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`;
    return (
      <div key={name}>
        <label htmlFor={id} className="block text-xs font-semibold text-slate-700 mb-1">
          {name}{info.unit ? ` (${info.unit})` : ''}
        </label>
        {name === 'Sex' ? (
          <select id={id} aria-label={name} value={formData[name] ?? 0}
            onChange={(event) => setFormData({ ...formData, [name]: Number(event.target.value) })}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg">
            <option value={0}>Female</option>
            <option value={1}>Male</option>
          </select>
        ) : (
          <input id={id} aria-label={name} type="number" step="any" required
            value={formData[name] ?? ''}
            onChange={(event) => setFormData({ ...formData, [name]: event.target.value === '' ? NaN : Number(event.target.value) })}
            className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500" />
        )}
      </div>
    );
  };

  const otherFields = Object.keys(schema).filter((name) => !BASIC_FIELDS.includes(name));

  return (
    <div className="bg-white rounded-xl shadow-md p-6 border border-slate-100">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <h2 className="text-xl font-bold">Patient Clinical Profile</h2>
        <div className="flex flex-wrap gap-1.5">
          {samples.map((sample) => (
            <button key={sample.name} type="button" onClick={() => selectSample(sample)}
              className="px-2.5 py-1 text-xs bg-slate-100 hover:bg-blue-50 rounded border border-slate-200">
              {sample.name}
            </button>
          ))}
        </div>
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void runPrediction(formData); }}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {BASIC_FIELDS.map(renderField)}
        </div>
        {otherFields.length > 0 && (
          <details className="mt-5 border-t pt-4">
            <summary className="cursor-pointer font-semibold text-sm text-blue-700">
              Additional clinical inputs ({otherFields.length})
            </summary>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4 max-h-96 overflow-y-auto pr-2">
              {otherFields.map(renderField)}
            </div>
          </details>
        )}
        <div className="flex justify-end pt-5">
          <button type="submit" disabled={loading || Object.keys(schema).length === 0}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium text-sm rounded-lg disabled:opacity-50">
            {loading ? 'Analyzing Risk...' : 'Run AI Risk Assessment'}
          </button>
        </div>
        {error && <p role="alert" className="mt-3 p-3 bg-red-50 text-red-700 text-sm rounded-lg">{error}</p>}
      </form>
    </div>
  );
};

export default PatientForm;
