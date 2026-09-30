import { afterEach, expect, it, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import axios from 'axios';
import PatientForm from './PatientForm';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it('shows every field supplied by the model schema', async () => {
  vi.spyOn(axios, 'get').mockImplementation(async (url) => {
    if (String(url).endsWith('/schema')) {
      return { data: { schema: {
        Age: { type: 'int64', default: 58, unit: 'years' },
        BUN: { type: 'int64', default: 16, unit: 'mg/dL' },
      } } } as any;
    }
    return { data: { samples: [] } } as any;
  });

  render(<PatientForm />);

  expect(await screen.findByLabelText('BUN')).toBeTruthy();
  expect(screen.getByLabelText('Age')).toBeTruthy();
});
