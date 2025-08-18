/**
 * Audio effects service for managing Tone.js effects chains
 */
import * as Tone from 'tone'

export interface EffectSettings {
  reverb: number
  delay: number
  distortion: number
  // Extended vocal effects
  pitchShift: number    // -12 to +12 semitones (0 = no shift)
  chorus: number        // 0 to 1 (chorus/doubling effect)
  filter: number        // 0 to 1 (low-pass filter amount)
  bitcrush: number      // 0 to 1 (bit crushing/lo-fi effect)
}

export interface AudioEffectsChain {
  reverb: Tone.Reverb
  delay: Tone.PingPongDelay
  distortion: Tone.Distortion
  // Extended vocal effects
  pitchShift: Tone.PitchShift
  chorus: Tone.Chorus
  filter: Tone.Filter
  bitCrusher: Tone.BitCrusher
  // Bitcrush wet/dry controls
  bitCrushWet: Tone.Gain
  bitCrushDry: Tone.Gain
  bitCrushInput: Tone.Gain
  bitCrushOutput: Tone.Gain
  output: Tone.Gain
  dispose: () => void
  updateSettings: (settings: EffectSettings) => void
  connectInput: (source: any) => void
}

// Helper to create default effect settings
const createDefaultEffectSettings = (): EffectSettings => ({
  reverb: 0,
  delay: 0,
  distortion: 0,
  pitchShift: 0,
  chorus: 0,
  filter: 0,
  bitcrush: 0
})

/**
 * Create an audio effects chain for a track or clip
 */
export function createEffectsChain(settings: EffectSettings = createDefaultEffectSettings()): AudioEffectsChain {
  // Create basic effects
  const reverb = new Tone.Reverb({
    decay: 2.5,
    preDelay: 0.01,
    wet: settings.reverb
  })

  const delay = new Tone.PingPongDelay({
    delayTime: "8n",
    feedback: 0.3,
    wet: settings.delay
  })

  const distortion = new Tone.Distortion({
    distortion: 0.8,
    wet: settings.distortion
  })

  // Create extended vocal effects
  const pitchShift = new Tone.PitchShift({
    pitch: settings.pitchShift * 100, // Convert semitones to cents (1 semitone = 100 cents)
    windowSize: 0.1, // Larger window for better pitch tracking with vocals
    delayTime: 0, // No additional delay
    feedback: 0 // No feedback to avoid artifacts
  })

  const chorus = new Tone.Chorus({
    frequency: 1.5,
    delayTime: 3.5,
    depth: 0.9, // Increased depth for more noticeable effect
    wet: settings.chorus
  })

  const filter = new Tone.Filter({
    frequency: 2000 - (settings.filter * 1800), // 2000Hz down to 200Hz
    type: "lowpass",
    rolloff: -24, // Steeper rolloff for more dramatic effect
    Q: 2 // Higher Q for more resonance
  })

  const bitCrusher = new Tone.BitCrusher({
    bits: Math.max(1, 16 - (settings.bitcrush * 15)) // 16 bits down to 1 bit
  })
  
  // Create wet/dry control for bitcrusher (since it doesn't have built-in wet control)
  const bitCrushWet = new Tone.Gain(Math.max(0, Math.min(1, settings.bitcrush)))
  const bitCrushDry = new Tone.Gain(Math.max(0, Math.min(1, 1 - settings.bitcrush)))
  
  // Create crossfade setup for bitcrusher
  const bitCrushInput = new Tone.Gain(1)
  const bitCrushOutput = new Tone.Gain(1)
  
  // Route bitcrusher wet/dry
  bitCrushInput.connect(bitCrusher)
  bitCrusher.connect(bitCrushWet)
  bitCrushInput.connect(bitCrushDry)
  bitCrushWet.connect(bitCrushOutput)
  bitCrushDry.connect(bitCrushOutput)

  // Create output gain node
  const output = new Tone.Gain(1)

  // Chain effects: input -> pitchShift -> filter -> bitCrushInput -> (wet/dry mix) -> bitCrushOutput -> distortion -> chorus -> delay -> reverb -> output
  pitchShift.chain(filter, bitCrushInput)
  bitCrushOutput.chain(distortion, chorus, delay, reverb, output)
  
  // Ensure output is connected to destination
  output.toDestination()
  
  console.log('🔗 Effects chain created and connected:', {
    pitchShift: !!pitchShift,
    filter: !!filter,
    bitCrusher: !!bitCrusher,
    distortion: !!distortion,
    chorus: !!chorus,
    delay: !!delay,
    reverb: !!reverb,
    output: !!output,
    connectedToDestination: true
  })

  // Update effect settings
  const updateSettings = (newSettings: EffectSettings) => {
    // Update reverb
    reverb.wet.value = Math.max(0, Math.min(1, newSettings.reverb))
    
    // Update delay
    delay.wet.value = Math.max(0, Math.min(1, newSettings.delay))
    
    // Update distortion
    distortion.wet.value = Math.max(0, Math.min(1, newSettings.distortion))
    
    // Update pitch shift (convert semitones to cents)
    const pitchCents = Math.max(-1200, Math.min(1200, newSettings.pitchShift * 100))
    pitchShift.pitch = pitchCents
    
    console.log(`🎛️ Pitch Shift Update:`, {
      semitones: newSettings.pitchShift,
      cents: pitchCents,
      applied: pitchShift.pitch,
      windowSize: pitchShift.windowSize,
      effectActive: pitchCents !== 0
    })
    
    // Update chorus
    chorus.wet.value = Math.max(0, Math.min(1, newSettings.chorus))
    
    // Update filter
    filter.frequency.value = 2000 - (Math.max(0, Math.min(1, newSettings.filter)) * 1800)
    
    // Update bit crusher (wet/dry mix control)
    const bitCrushWetAmount = Math.max(0, Math.min(1, newSettings.bitcrush))
    const bitCrushDryAmount = Math.max(0, Math.min(1, 1 - newSettings.bitcrush))
    bitCrushWet.gain.value = bitCrushWetAmount
    bitCrushDry.gain.value = bitCrushDryAmount
    
    // Update bit depth based on settings
    const newBitDepth = Math.max(1, 16 - (newSettings.bitcrush * 15))
    bitCrusher.bits.value = newBitDepth
    
    console.log('🎛️ Updated effects:', {
      reverb: reverb.wet.value,
      delay: delay.wet.value,
      distortion: distortion.wet.value,
      pitchShift: pitchShift.pitch,
      chorus: chorus.wet.value,
      filter: filter.frequency.value,
      bitcrush: bitCrushWet
    })
  }

  // Connect input source to effects chain
  const connectInput = (source: any) => {
    try {
      // Disconnect source from destination first if connected
      if (source.disconnect) {
        try {
          source.disconnect()
        } catch (disconnectError) {
          console.log('ℹ️ Source was not connected, proceeding to connect to effects:', disconnectError)
        }
      }
      
      // Connect to effects chain input (pitchShift is first in chain)
      source.connect(pitchShift)
      
      console.log('🔗 Connected source to effects chain input:', {
        source: source.constructor.name,
        connectedToPitchShift: true,
        pitchShiftValue: pitchShift.pitch
      })
    } catch (error) {
      console.error('Error connecting input to effects chain:', error)
    }
  }

  // Apply initial settings
  updateSettings(settings)

  // Dispose function to clean up resources
  const dispose = () => {
    try {
      reverb.dispose()
      delay.dispose()
      distortion.dispose()
      pitchShift.dispose()
      chorus.dispose()
      filter.dispose()
      bitCrusher.dispose()
      bitCrushWet.dispose()
      bitCrushDry.dispose()
      bitCrushInput.dispose()
      bitCrushOutput.dispose()
      output.dispose()
    } catch (error) {
      console.warn('Error disposing effects chain:', error)
    }
  }

  return {
    reverb,
    delay,
    distortion,
    pitchShift,
    chorus,
    filter,
    bitCrusher,
    bitCrushWet,
    bitCrushDry,
    bitCrushInput,
    bitCrushOutput,
    output,
    dispose,
    updateSettings,
    connectInput
  }
}

/**
 * Apply effects to a Tone.js instrument or player
 */
export function connectToEffectsChain(source: any, effectsChain: AudioEffectsChain): void {
  try {
    // Disconnect from destination first
    if (source.toDestination) {
      try {
        source.disconnect()
      } catch (disconnectError) {
        console.log('ℹ️ Source was not connected, proceeding to connect to effects:', disconnectError)
      }
    }
    
    // Connect to effects chain (start with pitchShift as first effect)
    source.connect(effectsChain.pitchShift)
    
    // Connect output to destination
    effectsChain.output.toDestination()
    
    console.log('🔗 Connected source to effects chain')
  } catch (error) {
    console.error('Error connecting to effects chain:', error)
  }
}

/**
 * Create a track-level effects bus
 */
export function createTrackEffectsBus(trackId: string, settings: EffectSettings): AudioEffectsChain {
  const effectsChain = createEffectsChain(settings)
  
  console.log(`🎚️ Created effects bus for track ${trackId}:`, settings)
  
  return effectsChain
}

/**
 * Create a clip-level effects chain that combines track and clip effects
 */
export function createClipEffectsChain(
  trackSettings: EffectSettings, 
  clipSettings: EffectSettings
): AudioEffectsChain {
  // Combine track and clip effects settings (clip settings add to track settings)
  const combinedSettings: EffectSettings = {
    reverb: Math.min(1, trackSettings.reverb + clipSettings.reverb),
    delay: Math.min(1, trackSettings.delay + clipSettings.delay),
    distortion: Math.min(1, trackSettings.distortion + clipSettings.distortion),
    pitchShift: Math.max(-12, Math.min(12, trackSettings.pitchShift + clipSettings.pitchShift)),
    chorus: Math.min(1, trackSettings.chorus + clipSettings.chorus),
    filter: Math.min(1, trackSettings.filter + clipSettings.filter),
    bitcrush: Math.min(1, trackSettings.bitcrush + clipSettings.bitcrush)
  }
  
  const effectsChain = createEffectsChain(combinedSettings)
  
  console.log(`🎵 Created clip effects chain with combined settings:`, {
    track: trackSettings,
    clip: clipSettings,
    combined: combinedSettings
  })
  
  return effectsChain
}

/**
 * Apply combined track and clip effects to an audio source
 */
export function applyClipEffects(
  source: any,
  trackSettings: EffectSettings,
  clipSettings: EffectSettings = createDefaultEffectSettings()
): AudioEffectsChain {
  const clipEffectsChain = createClipEffectsChain(trackSettings, clipSettings)
  
  try {
    // Disconnect source from destination first if connected
    if (source.disconnect) {
      try {
        source.disconnect()
      } catch (disconnectError) {
        console.log('ℹ️ Source was not connected, proceeding to connect to effects:', disconnectError)
      }
    }
    
    // Connect to clip effects chain (start with pitchShift as first effect)
    source.connect(clipEffectsChain.pitchShift)
    clipEffectsChain.output.toDestination()
    
    console.log('🎵 Applied combined track and clip effects')
  } catch (error) {
    console.error('Error applying clip effects:', error)
    // Fallback to direct connection
    source.toDestination()
  }
  
  return clipEffectsChain
}

/**
 * Mix dry and wet signals for subtle effect application
 */
export function applyEffectsWithMix(
  source: any, 
  effectsChain: AudioEffectsChain, 
  settings: EffectSettings
): void {
  try {
    // Create dry/wet mixer
    const dryGain = new Tone.Gain(1 - Math.max(settings.reverb, settings.delay, settings.distortion) * 0.5)
    const wetGain = new Tone.Gain(1)
    
    // Split signal
    try {
      source.disconnect()
    } catch (disconnectError) {
      console.log('ℹ️ Source was not connected, proceeding to split signal:', disconnectError)
    }
    source.fan(dryGain, effectsChain.distortion)
    
    // Mix dry and wet signals
    const mixer = new Tone.Gain(1)
    dryGain.connect(mixer)
    effectsChain.output.connect(wetGain)
    wetGain.connect(mixer)
    
    // Connect to destination
    mixer.toDestination()
    
    console.log('🎛️ Applied effects with dry/wet mixing')
  } catch (error) {
    console.error('Error applying effects with mix:', error)
    // Fallback to direct connection
    connectToEffectsChain(source, effectsChain)
  }
}
