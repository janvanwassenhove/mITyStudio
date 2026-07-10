// Track-type color roles — the single source of truth.
// styles.css mirrors these as --track-* custom properties for CSS-only use.
export const TRACK_COLORS: Record<string, string> = {
  drums: '#e6a23c',
  bass: '#f2555a',
  guitar: '#f78fb3',
  keys: '#4f9cf9',
  synth: '#9d6ff2',
  strings: '#3ecf8e',
  brass: '#e0c341',
  sample: '#41c9e0',
  lead_vocal: '#ff7eb6',
  backing_vocal: '#c792ea',
  fx: '#8d96a8',
}

export function trackColor(trackType: string): string {
  return TRACK_COLORS[trackType] ?? TRACK_COLORS.fx
}

// readable abbreviations so track types aren't distinguished by color alone
export const TYPE_ABBR: Record<string, string> = {
  drums: 'DR', bass: 'BA', guitar: 'GT', keys: 'KY', synth: 'SY',
  strings: 'ST', brass: 'BR', sample: 'SMP', lead_vocal: 'VOX',
  backing_vocal: 'BVX', fx: 'FX',
}
