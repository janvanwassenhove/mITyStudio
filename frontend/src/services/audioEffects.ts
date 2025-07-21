/**
 * Audio effects service for managing Tone.js effects chains
 */
import * as Tone from 'tone'

export interface EffectSettings {
  reverb: number
  delay: number
  distortion: number
}

export interface AudioEffectsChain {
  reverb: Tone.Reverb
  delay: Tone.PingPongDelay
  distortion: Tone.Distortion
  output: Tone.Gain
  dispose: () => void
  updateSettings: (settings: EffectSettings) => void
  connectInput: (source: any) => void
}

/**
 * Create an audio effects chain for a track or clip
 */
export function createEffectsChain(settings: EffectSettings = { reverb: 0, delay: 0, distortion: 0 }): AudioEffectsChain {
  // Create effects
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

  // Create output gain node
  const output = new Tone.Gain(1)

  // Chain effects: input -> distortion -> delay -> reverb -> output
  distortion.chain(delay, reverb, output)

  // Update effect settings
  const updateSettings = (newSettings: EffectSettings) => {
    // Update reverb
    reverb.wet.value = Math.max(0, Math.min(1, newSettings.reverb))
    
    // Update delay
    delay.wet.value = Math.max(0, Math.min(1, newSettings.delay))
    
    // Update distortion
    distortion.wet.value = Math.max(0, Math.min(1, newSettings.distortion))
    
    console.log('🎛️ Updated effects:', {
      reverb: reverb.wet.value,
      delay: delay.wet.value,
      distortion: distortion.wet.value
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
      
      // Connect to effects chain input (distortion)
      source.connect(distortion)
      
      console.log('🔗 Connected source to effects chain input')
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
      output.dispose()
    } catch (error) {
      console.warn('Error disposing effects chain:', error)
    }
  }

  return {
    reverb,
    delay,
    distortion,
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
    
    // Connect to effects chain
    source.connect(effectsChain.distortion)
    
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
    distortion: Math.min(1, trackSettings.distortion + clipSettings.distortion)
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
  clipSettings: EffectSettings = { reverb: 0, delay: 0, distortion: 0 }
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
    
    // Connect to clip effects chain
    source.connect(clipEffectsChain.distortion)
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
