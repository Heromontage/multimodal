import { create } from 'zustand';

interface CardioState {
  prediction: Record<string, any> | null;
  explanation: Record<string, any> | null;
  measurements: any[] | null;
  selectedVessel: string | null;

  setPrediction: (prediction: Record<string, any> | null) => void;
  setExplanation: (explanation: Record<string, any> | null) => void;
  setMeasurements: (measurements: any[] | null) => void;
  setSelectedVessel: (vessel: string | null) => void;
}

export const useCardioStore = create<CardioState>((set) => ({
  prediction: null,
  explanation: null,
  measurements: null,
  selectedVessel: null,

  setPrediction: (prediction) => set({ prediction }),
  setExplanation: (explanation) => set({ explanation }),
  setMeasurements: (measurements) => set({ measurements }),
  setSelectedVessel: (selectedVessel) => set({ selectedVessel }),
}));