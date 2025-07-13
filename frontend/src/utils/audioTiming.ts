/**
 * Audio timing utilities for precise chord and note playback
 */

export interface TimingConfig {
  clipDuration: number
  sampleDuration: number
  notes: string[]
  startTime: number
}

/**
 * Calculate precise timing for chord/note playback with no gaps
 */
export function calculateChordTiming(config: TimingConfig) {
  const { clipDuration, sampleDuration, notes, startTime } = config
  
  // Calculate how many complete chord positions fit in the clip
  const totalPositions = Math.floor(clipDuration / sampleDuration)
  
  // Create timing schedule for each position
  const schedule: Array<{
    startTime: number
    duration: number
    noteIndex: number
    note: string
  }> = []
  
  for (let i = 0; i < totalPositions; i++) {
    const positionStartTime = startTime + (i * sampleDuration)
    const noteIndex = i % notes.length
    const note = notes[noteIndex]
    
    schedule.push({
      startTime: positionStartTime,
      duration: sampleDuration,
      noteIndex,
      note
    })
  }
  
  return schedule
}

/**
 * Calculate the current playing position within a clip
 */
export function getCurrentPlayingPosition(
  currentTime: number,
  clipStartTime: number,
  sampleDuration: number
): {
  positionIndex: number
  timeIntoPosition: number
  remainingTime: number
} {
  const timeIntoClip = currentTime - clipStartTime
  const positionIndex = Math.floor(timeIntoClip / sampleDuration)
  const timeIntoPosition = timeIntoClip % sampleDuration
  const remainingTime = sampleDuration - timeIntoPosition
  
  return {
    positionIndex,
    timeIntoPosition,
    remainingTime
  }
}

/**
 * Validate that timing configuration will result in seamless playback
 */
export function validateTimingConfig(config: TimingConfig): {
  isValid: boolean
  warnings: string[]
  totalChords: number
  actualDuration: number
} {
  const warnings: string[] = []
  const totalChords = Math.floor(config.clipDuration / config.sampleDuration)
  const actualDuration = totalChords * config.sampleDuration
  
  // Check for timing issues
  if (actualDuration < config.clipDuration) {
    const gap = config.clipDuration - actualDuration
    warnings.push(`There will be a ${gap.toFixed(2)}s gap at the end of the clip`)
  }
  
  if (config.sampleDuration <= 0) {
    warnings.push('Sample duration must be greater than 0')
  }
  
  if (config.notes.length === 0) {
    warnings.push('No notes provided for playback')
  }
  
  if (totalChords === 0) {
    warnings.push('Clip duration is too short for any chord playback')
  }
  
  const isValid = warnings.length === 0 || 
    (warnings.length === 1 && warnings[0].includes('gap at the end'))
  
  return {
    isValid,
    warnings,
    totalChords,
    actualDuration
  }
}

/**
 * Create a schedule for seamless chord looping within a clip
 */
export function createSeamlessSchedule(config: TimingConfig) {
  const validation = validateTimingConfig(config)
  
  if (!validation.isValid) {
    console.warn('Timing configuration issues:', validation.warnings)
  }
  
  const schedule = calculateChordTiming(config)
  
  return {
    schedule,
    validation,
    totalChords: validation.totalChords,
    actualDuration: validation.actualDuration
  }
}
