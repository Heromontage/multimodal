const GREEN = '#10b981';
const YELLOW = '#f59e0b';
const RED = '#ef4444';

function mix(start: string, end: string, fraction: number): string {
  const left = [1, 3, 5].map((offset) => parseInt(start.slice(offset, offset + 2), 16));
  const right = [1, 3, 5].map((offset) => parseInt(end.slice(offset, offset + 2), 16));
  return `#${left.map((value, index) => Math.round(value + (right[index] - value) * fraction)
    .toString(16).padStart(2, '0')).join('')}`;
}

export function riskColor(probability: number): string {
  const value = Math.min(1, Math.max(0, probability));
  return value <= 0.5 ? mix(GREEN, YELLOW, value * 2) : mix(YELLOW, RED, (value - 0.5) * 2);
}
