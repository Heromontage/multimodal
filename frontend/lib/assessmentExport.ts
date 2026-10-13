import JSZip from 'jszip';
import type {Field, Results, Schema, Target, Values} from './types';

type Cell = string | number;
type Sheet = {name: string; rows: Cell[][]};
type Assessment = {schema: Schema; inputs: Values; results: Results};
const targets: Target[] = ['CAD', 'LAD', 'LCX', 'RCA'];

function displayValue(field: Field, raw: Values[string] | undefined): Cell {
  if(raw === null || raw === undefined) return 'Unknown / missing';
  const binary = field.kind === 'category' && field.options?.length === 2 &&
    field.options.every(option => ['N', 'Y', 0, 1].includes(option));
  if(binary) return raw === 1 || raw === 'Y' ? 'Yes' : 'No';
  if(raw === 'Fmale') return 'Female';
  if(raw === 'Y') return 'Yes';
  if(raw === 'N') return 'No';
  return raw;
}

export function assessmentJson({schema, inputs, results}: Assessment) {
  return {
    inputs: schema.fields.map(field => ({name: field.label, value: displayValue(field, inputs[field.name])})),
    outputs: targets.map(name => ({name, percentage: (results.predictions[name].probability * 100).toFixed(1) + '%'})),
  };
}

export function assessmentSheets(assessment: Assessment): Sheet[] {
  const data = assessmentJson(assessment);
  return [
    {name: 'Inputs', rows: [['Input', 'Value'], ...data.inputs.map(({name, value}) => [name, value])]},
    {name: 'Outputs', rows: [['Output', 'Percentage'], ...data.outputs.map(({name, percentage}) => [name, percentage])]},
  ];
}

const csvCell = (item: Cell): string => {
  const text = String(item);
  const safe = /^[=+@\-]/.test(text) && typeof item === 'string' ? "'" + text : text;
  return /[",\r\n]/.test(safe) ? '"' + safe.replaceAll('"', '""') + '"' : safe;
};

export function assessmentCsv(assessment: Assessment): string {
  const data = assessmentJson(assessment);
  const rows: Cell[][] = [
    ['Type', 'Name', 'Value'],
    ...data.inputs.map(({name, value}) => ['Input', name, value]),
    ...data.outputs.map(({name, percentage}) => ['Output', name, percentage]),
  ];
  return '\uFEFF' + rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

const xml = (item: string): string => item.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
  .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;');
const column = (index: number): string => {
  let name = '';
  for (let n = index + 1; n > 0; n = Math.floor((n - 1) / 26)) name = String.fromCharCode(65 + (n - 1) % 26) + name;
  return name;
};
const xlsxCell = (item: Cell, row: number, col: number): string => {
  const address = column(col) + row;
  const style = row === 1 ? ' s="1"' : '';
  if (typeof item === 'number' && Number.isFinite(item)) return `<c r="${address}"${style}><v>${item}</v></c>`;
  if (typeof item === 'boolean') return `<c r="${address}"${style} t="b"><v>${item ? 1 : 0}</v></c>`;
  return `<c r="${address}"${style} t="inlineStr"><is><t xml:space="preserve">${xml(String(item ?? ''))}</t></is></c>`;
};
const sheetXml = (sheet: Sheet): string => {
  const width = Math.max(...sheet.rows.map(row => row.length));
  const rows = sheet.rows.map((items, index) =>
    `<row r="${index + 1}">${items.map((item, col) => xlsxCell(item, index + 1, col)).join('')}</row>`).join('');
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<dimension ref="A1:${column(width - 1)}${sheet.rows.length}"/>
<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>${Array.from({length: width}, (_, index) => `<col min="${index + 1}" max="${index + 1}" width="${index === 0 ? 38 : 22}" customWidth="1"/>`).join('')}</cols>
<sheetData>${rows}</sheetData>
<autoFilter ref="A1:${column(width - 1)}${sheet.rows.length}"/>
</worksheet>`;
};

export async function assessmentXlsx(assessment: Assessment): Promise<Uint8Array> {
  const sheets = assessmentSheets(assessment);
  const zip = new JSZip();
  zip.file('[Content_Types].xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
${sheets.map((_, index) => `<Override PartName="/xl/worksheets/sheet${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}
</Types>`);
  zip.file('_rels/.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>`);
  zip.file('xl/workbook.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>${sheets.map((sheet, index) => `<sheet name="${xml(sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join('')}</sheets>
</workbook>`);
  zip.file('xl/_rels/workbook.xml.rels', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
${sheets.map((_, index) => `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`).join('')}
<Relationship Id="rId${sheets.length + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>`);
  zip.file('xl/styles.xml', `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2"><font><sz val="11"/><name val="Arial"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Arial"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF237C77"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>`);
  sheets.forEach((sheet, index) => zip.file(`xl/worksheets/sheet${index + 1}.xml`, sheetXml(sheet)));
  return zip.generateAsync({type: 'uint8array', compression: 'DEFLATE'});
}
