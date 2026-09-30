import { expect, it } from 'vitest';
import { riskColor } from './colorScale';

it('maps vessel probability continuously through green, yellow, and red', () => {
  expect(riskColor(0)).toBe('#10b981');
  expect(riskColor(0.5)).toBe('#f59e0b');
  expect(riskColor(1)).toBe('#ef4444');
  expect(riskColor(0.25)).not.toBe(riskColor(0));
  expect(riskColor(0.25)).not.toBe(riskColor(0.5));
});
