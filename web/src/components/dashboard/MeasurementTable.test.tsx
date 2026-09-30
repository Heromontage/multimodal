import { afterEach, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import MeasurementTable from './MeasurementTable';
import { useCardioStore } from '../../store/useCardioStore';

afterEach(() => cleanup());

it('shows the selected model contribution beside a measured value', () => {
  useCardioStore.setState({
    measurements: [{ feature: 'BP', value: 150, unit: 'mmHg', ref_range: [90, 120], status: 'high' }],
    explanation: { CAD: { base_value: 0, contributions: [{ feature: 'num__BP', value: 150, shap: 0.25 }] } },
  });

  render(<MeasurementTable vessel="CAD" />);

  expect(screen.getByText('Contribution')).toBeTruthy();
  expect(screen.getByText('+0.250')).toBeTruthy();
});
