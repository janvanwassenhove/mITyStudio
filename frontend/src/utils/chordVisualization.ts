/**
 * Utility functions for chord and clip visualization
 */

export interface ChordInfo {
  root: string
  type: string
  displayName: string
  color: string
}

/**
 * Extract chord information from a sample URL
 */
export function extractChordFromSampleUrl(sampleUrl: string): ChordInfo | null {
  if (!sampleUrl) return null
  
  // Extract filename from URL: /instruments/strings/piano/2_0s/wav/C_major.wav -> C_major.wav
  const filename = sampleUrl.split('/').pop()
  if (!filename) return null
  
  // Remove extension: C_major.wav -> C_major
  const nameWithoutExt = filename.replace(/\.(wav|mp3|ogg)$/i, '')
  
  // Split by underscore: C_major -> [C, major]
  const parts = nameWithoutExt.split('_')
  if (parts.length !== 2) return null
  
  const [root, type] = parts
  
  return {
    root,
    type,
    displayName: formatChordDisplay(root, type),
    color: getChordColor(root, type)
  }
}

/**
 * Format chord for display (e.g., "C_major" -> "C", "F#_min7" -> "F#m7")
 */
export function formatChordDisplay(root: string, type: string): string {
  const typeMap: Record<string, string> = {
    'major': '',
    'minor': 'm',
    'dom7': '7',
    'maj7': 'maj7',
    'min7': 'm7',
    'augmented': '+',
    'diminished': '°',
    'sus2': 'sus2',
    'sus4': 'sus4'
  }
  
  const displayRoot = root.replace('#', '♯').replace('b', '♭')
  const displayType = typeMap[type] || type
  
  return displayRoot + displayType
}

/**
 * Get color for chord based on root and type
 */
export function getChordColor(root: string, type: string): string {
  // Color scheme based on chord root (circle of fifths)
  const rootColors: Record<string, string> = {
    'C': '#FF6B6B',   // Red
    'G': '#4ECDC4',   // Teal
    'D': '#45B7D1',   // Blue
    'A': '#96CEB4',   // Green
    'E': '#FFEAA7',   // Yellow
    'B': '#DDA0DD',   // Plum
    'F#': '#FFB347',  // Orange
    'C#': '#87CEEB',  // Sky Blue
    'F': '#98D8C8',   // Mint
    'Bb': '#F7DC6F',  // Light Yellow
    'Eb': '#BB8FCE',  // Light Purple
    'Ab': '#F8C471'   // Peach
  }
  
  // Get base color from root note
  let baseColor = rootColors[root] || rootColors['C']
  
  // Modify color based on chord type
  if (type === 'minor' || type === 'min7') {
    // Darker shade for minor chords
    baseColor = adjustBrightness(baseColor, -20)
  } else if (type === 'dom7' || type === 'maj7') {
    // Slightly more saturated for 7th chords
    baseColor = adjustSaturation(baseColor, 10)
  } else if (type === 'diminished') {
    // Much darker for diminished
    baseColor = adjustBrightness(baseColor, -40)
  } else if (type === 'augmented') {
    // Brighter for augmented
    baseColor = adjustBrightness(baseColor, 20)
  }
  
  return baseColor
}

/**
 * Adjust brightness of hex color
 */
function adjustBrightness(hex: string, percent: number): string {
  const num = parseInt(hex.replace('#', ''), 16)
  const amt = Math.round(2.55 * percent)
  const R = (num >> 16) + amt
  const G = (num >> 8 & 0x00FF) + amt
  const B = (num & 0x0000FF) + amt
  
  return '#' + (0x1000000 + (R < 255 ? R < 1 ? 0 : R : 255) * 0x10000 +
    (G < 255 ? G < 1 ? 0 : G : 255) * 0x100 +
    (B < 255 ? B < 1 ? 0 : B : 255)).toString(16).slice(1)
}

/**
 * Adjust saturation of hex color
 */
function adjustSaturation(hex: string, _percent: number): string {
  // Simple saturation adjustment (this is a simplified version)
  return hex // For now, return original color
}

/**
 * Get instrument icon/color for track visualization
 */
export function getInstrumentColor(instrument: string): string {
  const instrumentColors: Record<string, string> = {
    'piano': '#8B4513',           // Brown
    'electric-piano': '#4682B4',  // Steel Blue
    'guitar': '#228B22',          // Forest Green
    'synth': '#9932CC',           // Dark Orchid
    'synth-lead': '#FF4500',      // Orange Red
    'synth-pad': '#6495ED',       // Cornflower Blue
    'bass': '#800080',            // Purple
    'drums': '#A52A2A'            // Brown
  }
  
  return instrumentColors[instrument] || '#808080'
}

/**
 * Calculate bar position for timeline visualization
 */
export function calculateBarPosition(timeInSeconds: number, tempo: number, beatWidth: number): number {
  // Convert seconds to beats (assuming 4/4 time signature)
  const beatsPerSecond = tempo / 60
  const beats = timeInSeconds * beatsPerSecond
  return beats * beatWidth
}

/**
 * Get bar number from time position
 */
export function getBarNumber(timeInSeconds: number, tempo: number): number {
  const beatsPerSecond = tempo / 60
  const beats = timeInSeconds * beatsPerSecond
  return Math.floor(beats / 4) + 1
}

/**
 * Get beat within bar from time position
 */
export function getBeatInBar(timeInSeconds: number, tempo: number): number {
  const beatsPerSecond = tempo / 60
  const beats = timeInSeconds * beatsPerSecond
  return (beats % 4) + 1
}
