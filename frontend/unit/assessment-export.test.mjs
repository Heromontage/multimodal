import test from 'node:test';
import assert from 'node:assert/strict';
import JSZip from 'jszip';
import * as exportModule from '../lib/assessmentExport.ts';
const {assessmentSheets, assessmentCsv, assessmentXlsx} = exportModule;

const targets = ['CAD', 'LAD', 'LCX', 'RCA'];
const prediction = target => ({
  model: 'mixed_nb', auc: 0.83, threshold: 0.4, calibrated: target !== 'LCX',
  selected_features: ['Age'], probability: target === 'LAD' ? 0.71 : 0.3,
  positive: target === 'LAD', prior_log_odds: -0.2,
  features: [{name: 'Age', label: 'Age, years', value: 58, used: true, contribution: 0.24}],
});
const schema = {
  fields: [
    {name: 'Age', label: 'Age, years', group: 'Profile', kind: 'number',
      options: null, default: 50, unit: 'years', min: 18, max: 100,
      constant: false, used_by: targets},
    {name: 'Obesity', label: 'Obesity', group: 'Profile', kind: 'category',
      options: [0, 1], default: 0, unit: '', min: null, max: null,
      constant: false, used_by: targets},
  ],
  groups: ['Profile'],
  targets: Object.fromEntries(targets.map(target => [target, {
    model: 'mixed_nb', auc: 0.83, threshold: 0.4,
    calibrated: target !== 'LCX', selected_features: ['Age'],
  }])),
  patient_count: 303, validation: 'nested CV', selection_note: 'exploratory',
};
const results = {
  predictions: Object.fromEntries(targets.map(target => [target, prediction(target)])),
  warnings: ['Do not export this warning'], explanation: 'Do not export this explanation',
};
const input = {schema, inputs: {Age: 58, Obesity: 1}, results};

test('CSV has only readable input values and four output percentages', () => {
  const csv = assessmentCsv(input);
  assert.match(csv, /Input,"Age, years",58/);
  assert.match(csv, /Input,Obesity,Yes/);
  assert.match(csv, /Output,LAD,71\.0%/);
  assert.equal(csv.trim().split('\r\n').length, 7);
  assert.doesNotMatch(csv, /warning|explanation|threshold|model|evidence/i);
});

test('JSON contains only the input values and four output percentages', () => {
  const data = exportModule.assessmentJson(input);
  assert.deepEqual(Object.keys(data), ['inputs', 'outputs']);
  assert.deepEqual(data.inputs, [
    {name: 'Age, years', value: 58},
    {name: 'Obesity', value: 'Yes'},
  ]);
  assert.equal(data.outputs.length, 4);
  assert.deepEqual(data.outputs[1], {name: 'LAD', percentage: '71.0%'});
});

test('Excel has only Inputs and Outputs sheets', async () => {
  const sheets = assessmentSheets(input);
  assert.deepEqual(sheets.map(sheet => sheet.name), ['Inputs', 'Outputs']);
  assert.deepEqual(sheets[0].rows, [
    ['Input', 'Value'], ['Age, years', 58], ['Obesity', 'Yes'],
  ]);
  assert.deepEqual(sheets[1].rows[2], ['LAD', '71.0%']);
  const zip = await JSZip.loadAsync(await assessmentXlsx(input));
  const workbook = await zip.file('xl/workbook.xml').async('string');
  assert.doesNotMatch(workbook, /Evidence|Overview|Warnings/);
  assert.match(workbook, /name="Outputs"/);
});
