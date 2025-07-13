<template>
  <div id="app" class="app-container">
    <WelcomeDialog />
    <AppHeader />
    <main class="main-content">
      <div class="workspace">
        <div class="left-panel">
          <TrackControls />
        </div>
        <div class="center-panel">
          <PlaybackControls />
          <TimelineEditor />
        </div>
        <div class="right-panel">
          <RightPanelToggle />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAudioStore } from './stores/audioStore'
import * as Tone from 'tone'
import AppHeader from './components/AppHeader.vue'
import TrackControls from './components/TrackControls.vue'
import PlaybackControls from './components/PlaybackControls.vue'
import TimelineEditor from './components/TimelineEditor.vue'
import RightPanelToggle from './components/RightPanelToggle.vue'
import WelcomeDialog from './components/WelcomeDialog.vue'

const audioStore = useAudioStore()

onMounted(() => {
  // Remove automatic initialization - let the welcome dialog handle it
  // audioStore.forceInitialize()
  
  // Create global diagnostic function
  ;(window as any).audioTest = async function() {
    console.log('🔍 === AUDIO DIAGNOSTIC ===')
    
    // Audio store state
    console.log('📊 === AUDIO STORE STATE ===')
    console.log('- isInitialized:', audioStore.isInitialized)
    console.log('- masterVolume:', audioStore.masterVolume)
    console.log('- tracks:', audioStore.songStructure.tracks.length)
    
    // Check Tone.js
    console.log('🎵 === TONE.JS STATE ===')
    console.log('- Tone available:', typeof Tone !== 'undefined')
    console.log('- Context state:', Tone.context.state)
    
    // Initialize audio if needed
    console.log('🔧 === FIXING AUDIO ===')
    if (Tone.context.state !== 'running') {
      console.log('🔧 Starting Tone context...')
      await Tone.start()
      console.log('✅ Tone context started')
    }
    
    if (!audioStore.isInitialized) {
      console.log('🔧 Initializing audio...')
      try {
        await audioStore.initializeAudio()
        console.log('✅ Audio initialized')
      } catch (error) {
        console.log('🔧 Trying force initialize...')
        await audioStore.forceInitialize()
        console.log('✅ Audio force initialized')
      }
    }
    
    // Create test content
    console.log('🛠️ === CREATING TEST ===')
    audioStore.songStructure.tracks = []
    
    const trackId = audioStore.addTrack('Test Synth', 'synth-pad')
    const clip = {
      startTime: 0,
      duration: 6,
      type: 'synth' as const,
      instrument: 'synth-pad',
      notes: ['C4', 'E4', 'G4'],
      sampleDuration: 2,
      volume: 0.8,
      effects: { reverb: 0, delay: 0, distortion: 0 }
    }
    
    audioStore.addClip(trackId, clip)
    console.log('✅ Test track created!')
    
    // Test basic sound
    console.log('🧪 Testing basic sound...')
    const testOsc = new Tone.Oscillator(440, "sine").toDestination()
    testOsc.start()
    setTimeout(() => {
      testOsc.stop()
      testOsc.dispose()
      console.log('✅ Basic test completed (you should have heard a beep)')
    }, 500)
    
    console.log('🎮 Click PLAY button to test full system!')
    console.log('📝 Expected: C4 (2s) → E4 (2s) → G4 (2s)')
    
    // Test instrument directly
    console.log('🧪 Testing instrument creation...')
    try {
      const directSynth = new Tone.PolySynth(Tone.Synth, {
        oscillator: { type: "sine" },
        envelope: { attack: 0.8, decay: 0.5, sustain: 0.8, release: 2 }
      }).toDestination()
      
      setTimeout(() => {
        try {
          console.log('🎹 Testing direct synth note...')
          directSynth.triggerAttackRelease('C4', '4n')
        } catch (directError) {
          console.error('❌ Direct synth failed:', directError)
        }
      }, 2000)
    } catch (synthError) {
      console.error('❌ Failed to create direct synth:', synthError)
    }
  }
  
  console.log('🔧 Audio diagnostic function loaded! Type: audioTest()')
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--background);
}

.main-content {
  flex: 1;
  overflow: hidden;
}

.workspace {
  display: grid;
  grid-template-columns: 300px 1fr 450px;
  height: 100%;
  gap: 1px;
  background: var(--border);
}

.left-panel,
.center-panel,
.right-panel {
  background: var(--background);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.left-panel {
  border-right: 1px solid var(--border);
}

.right-panel {
  border-left: 1px solid var(--border);
}

@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 280px 1fr 370px;
  }
}

@media (max-width: 768px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }
  
  .left-panel,
  .right-panel {
    border: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>
