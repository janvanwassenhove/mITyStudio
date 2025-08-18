/**
 * Centralized countdown composable for recording countdown
 */
import { ref } from 'vue'
import * as Tone from 'tone'

const countdownValue = ref<number | null>(null)
const isCountdownActive = ref(false)

// Create a simple synth for countdown beeps
let countdownSynth: Tone.Synth | null = null

const initializeCountdownAudio = async () => {
  try {
    await Tone.start()
    if (!countdownSynth) {
      countdownSynth = new Tone.Synth({
        oscillator: {
          type: 'sine'
        },
        envelope: {
          attack: 0.01,
          decay: 0.1,
          sustain: 0,
          release: 0.1
        }
      }).toDestination()
    }
  } catch (error) {
    console.warn('Could not initialize countdown audio:', error)
  }
}

const playCountdownBeep = (number: number) => {
  if (!countdownSynth) return
  
  try {
    // Higher pitch for final numbers, lower for start
    const pitches = {
      4: 'C4',
      3: 'D4', 
      2: 'E4',
      1: 'G4' // Highest pitch for "1" (ready to record)
    }
    
    const pitch = pitches[number as keyof typeof pitches] || 'C4'
    countdownSynth.triggerAttackRelease(pitch, '0.2')
  } catch (error) {
    console.warn('Could not play countdown beep:', error)
  }
}

const startCountdown = async (seconds: number = 4): Promise<void> => {
  return new Promise((resolve) => {
    isCountdownActive.value = true
    countdownValue.value = seconds
    
    // Initialize audio if needed
    initializeCountdownAudio()
    
    const interval = setInterval(() => {
      if (countdownValue.value && countdownValue.value > 0) {
        // Play beep for current number
        playCountdownBeep(countdownValue.value)
        
        // Move to next number
        countdownValue.value = countdownValue.value - 1
        
        if (countdownValue.value === 0) {
          // Countdown finished
          setTimeout(() => {
            countdownValue.value = null
            isCountdownActive.value = false
            clearInterval(interval)
            resolve()
          }, 1000) // Show "0" or "GO" for 1 second
        }
      }
    }, 1000)
  })
}

export const useCountdown = () => {
  return {
    countdownValue,
    isCountdownActive,
    startCountdown,
    initializeCountdownAudio
  }
}
