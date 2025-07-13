<template>
  <div v-if="isOpen" class="diagnostics-overlay" @click="close">
    <div class="diagnostics-dialog" @click.stop>
      <div class="dialog-header">
        <h3>
          <Stethoscope class="header-icon" />
          Audio Diagnostics
        </h3>
        <button @click="close" class="close-btn">
          <X class="icon" />
        </button>
      </div>

      <div class="dialog-content">
        <!-- Overall Status -->
        <div class="status-section">
          <div class="status-card" :class="overallStatus">
            <div class="status-header">
              <component :is="overallStatusIcon" class="status-icon" />
              <h4>System Status</h4>
            </div>
            <p class="status-message">{{ overallStatusMessage }}</p>
          </div>
        </div>

        <!-- Control Panel -->
        <div class="control-panel">
          <div class="control-group">
            <button 
              @click="startDiagnostics" 
              :disabled="isRunning"
              class="btn btn-primary"
            >
              <Play v-if="!isRunning" class="icon" />
              <Loader v-else class="icon spinning" />
              {{ isRunning ? 'Running...' : 'Start Diagnostics' }}
            </button>
            
            <button 
              @click="stopDiagnostics" 
              :disabled="!isRunning"
              class="btn btn-secondary"
            >
              <Square class="icon" />
              Stop
            </button>
            
            <button 
              @click="clearResults" 
              :disabled="isRunning"
              class="btn btn-ghost"
            >
              <RotateCcw class="icon" />
              Clear
            </button>
          </div>
          
          <div class="progress-section" v-if="isRunning">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${progress}%` }"></div>
            </div>
            <p class="progress-text">
              {{ currentTest }} ({{ testIndex + 1 }}/{{ totalTests }})
            </p>
          </div>
        </div>

        <!-- Test Options -->
        <div class="test-options">
          <h4>Test Options</h4>
          <div class="option-group">
            <label class="checkbox-label">
              <input type="checkbox" v-model="testOptions.testSamples" />
              Test Sample Loading
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="testOptions.testPlayback" />
              Test Audio Playback
            </label>
            <label class="checkbox-label">
              <input type="checkbox" v-model="testOptions.testChords" />
              Test Chord Samples
            </label>
          </div>
        </div>

        <!-- Results Section -->
        <div class="results-section" v-if="diagnosticsResults.length > 0">
          <div class="results-header">
            <h4>Test Results</h4>
            <div class="results-summary">
              <span class="success-count">✅ {{ successCount }}</span>
              <span class="warning-count">⚠️ {{ warningCount }}</span>
              <span class="error-count">❌ {{ errorCount }}</span>
            </div>
          </div>

          <div class="results-list">
            <div 
              v-for="result in diagnosticsResults" 
              :key="result.id"
              class="result-item"
              :class="result.status"
            >
              <div class="result-header" @click="result.expanded = !result.expanded">
                <div class="result-info">
                  <component :is="getStatusIcon(result.status)" class="result-icon" />
                  <span class="result-title">{{ result.instrument }}</span>
                  <span class="result-category">{{ result.category }}</span>
                </div>
                <div class="result-summary">
                  <span class="result-time">{{ result.testTime }}ms</span>
                  <ChevronDown 
                    class="expand-icon" 
                    :class="{ expanded: result.expanded }"
                  />
                </div>
              </div>

              <div v-if="result.expanded" class="result-details">
                <div class="test-details">
                  <div v-for="test in result.tests" :key="test.name" class="test-result">
                    <component :is="getStatusIcon(test.status)" class="test-icon" />
                    <span class="test-name">{{ test.name }}</span>
                    <span class="test-message">{{ test.message }}</span>
                    <span v-if="test.duration" class="test-duration">{{ test.duration }}ms</span>
                  </div>
                </div>
                
                <div v-if="result.samples && result.samples.length > 0" class="samples-section">
                  <h5>Sample Tests ({{ result.samples.length }} samples)</h5>
                  <div class="samples-grid">
                    <div 
                      v-for="sample in result.samples.slice(0, 20)" 
                      :key="sample.name"
                      class="sample-item"
                      :class="sample.status"
                      :title="sample.message"
                    >
                      <span class="sample-name">{{ sample.name }}</span>
                      <component :is="getStatusIcon(sample.status)" class="sample-icon" />
                    </div>
                    <div v-if="result.samples.length > 20" class="sample-more">
                      +{{ result.samples.length - 20 }} more...
                    </div>
                  </div>
                </div>

                <div v-if="result.error" class="error-details">
                  <h5>Error Details</h5>
                  <pre class="error-message">{{ result.error }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Export Results -->
        <div v-if="diagnosticsResults.length > 0" class="export-section">
          <button @click="exportResults" class="btn btn-ghost">
            <Download class="icon" />
            Export Results
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { 
  X, Stethoscope, Play, Square, RotateCcw, Loader, 
  ChevronDown, CheckCircle, AlertTriangle, XCircle, 
  Download 
} from 'lucide-vue-next'
import { getAllSampleInstruments } from '../utils/api'
import * as Tone from 'tone'

// Props
defineProps<{
  isOpen: boolean
}>()

// Emits
const emit = defineEmits<{
  close: []
}>()

// State
const isRunning = ref(false)
const currentTest = ref('')
const testIndex = ref(0)
const totalTests = ref(0)
const progress = ref(0)
const diagnosticsResults = ref<DiagnosticResult[]>([])

// Test options
const testOptions = ref({
  testSamples: true,
  testPlayback: true,
  testChords: true
})

interface TestResult {
  name: string
  status: 'success' | 'warning' | 'error'
  message: string
  duration?: number
  data?: any
}

interface SampleResult {
  name: string
  status: 'success' | 'warning' | 'error'
  message: string
  path: string
}

interface DiagnosticResult {
  id: string
  instrument: string
  category: string
  status: 'success' | 'warning' | 'error'
  testTime: number
  tests: TestResult[]
  samples: SampleResult[]
  error?: string
  expanded: boolean
}

// Computed
const overallStatus = computed(() => {
  if (diagnosticsResults.value.length === 0) return 'pending'
  
  const hasErrors = diagnosticsResults.value.some(r => r.status === 'error')
  const hasWarnings = diagnosticsResults.value.some(r => r.status === 'warning')
  
  if (hasErrors) return 'error'
  if (hasWarnings) return 'warning'
  return 'success'
})

const overallStatusIcon = computed(() => {
  switch (overallStatus.value) {
    case 'success': return CheckCircle
    case 'warning': return AlertTriangle
    case 'error': return XCircle
    default: return Stethoscope
  }
})

const overallStatusMessage = computed(() => {
  const total = diagnosticsResults.value.length
  if (total === 0) return 'Ready to run diagnostics'
  
  const success = successCount.value
  const warnings = warningCount.value
  const errors = errorCount.value
  
  return `${total} instruments tested: ${success} working, ${warnings} with warnings, ${errors} failed`
})

const successCount = computed(() => 
  diagnosticsResults.value.filter(r => r.status === 'success').length
)

const warningCount = computed(() => 
  diagnosticsResults.value.filter(r => r.status === 'warning').length
)

const errorCount = computed(() => 
  diagnosticsResults.value.filter(r => r.status === 'error').length
)

// Methods
const close = () => {
  emit('close')
}

const getStatusIcon = (status: string) => {
  switch (status) {
    case 'success': return CheckCircle
    case 'warning': return AlertTriangle
    case 'error': return XCircle
    default: return CheckCircle
  }
}

const startDiagnostics = async () => {
  if (isRunning.value) return
  
  isRunning.value = true
  diagnosticsResults.value = []
  testIndex.value = 0
  progress.value = 0
  
  try {
    // Get all available instruments
    currentTest.value = 'Loading instrument list...'
    const instrumentData = await getAllSampleInstruments()
    
    const instrumentsToTest: Array<{ category: string; instrument: string }> = []
    
    // Flatten instrument data into testable array
    for (const category in instrumentData.categories) {
      const instruments = instrumentData.categories[category]
      for (const instrumentObj of instruments) {
        // Extract the actual instrument name from the object
        const instrumentName = instrumentObj.name || instrumentObj
        instrumentsToTest.push({ category, instrument: instrumentName })
      }
    }
    
    totalTests.value = instrumentsToTest.length
    
    // Test each instrument
    for (let i = 0; i < instrumentsToTest.length && isRunning.value; i++) {
      const { category, instrument } = instrumentsToTest[i]
      testIndex.value = i
      currentTest.value = `Testing ${instrument} (${category})`
      progress.value = Math.round((i / totalTests.value) * 100)
      
      const result = await testInstrument(category, instrument)
      diagnosticsResults.value.push(result)
      
      // Small delay to allow UI updates
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    
  } catch (error) {
    console.error('Diagnostics failed:', error)
  } finally {
    isRunning.value = false
    currentTest.value = ''
    progress.value = 100
  }
}

const stopDiagnostics = () => {
  isRunning.value = false
}

const clearResults = () => {
  diagnosticsResults.value = []
  progress.value = 0
  testIndex.value = 0
  totalTests.value = 0
}

const testInstrument = async (category: string, instrument: string): Promise<DiagnosticResult> => {
  const startTime = Date.now()
  const tests: TestResult[] = []
  const samples: SampleResult[] = []
  let overallStatus: 'success' | 'warning' | 'error' = 'success'
  let errorMessage = ''
  
  try {
    console.log(`Starting diagnostics for ${category}/${instrument}`)
    console.log(`Test options:`, testOptions.value)
    
    // Test 1: Check if instrument directory exists
    if (testOptions.value.testSamples) {
      console.log(`Running directory test for ${instrument}`)
      const directoryTest = await testInstrumentDirectory(category, instrument)
      tests.push(directoryTest)
      console.log(`Directory test result for ${instrument}:`, directoryTest.status)
      if (directoryTest.status === 'error') {
        overallStatus = 'error'
        console.log(`${instrument} failed directory test, stopping here`)
      }
    } else {
      console.log(`Skipping directory test for ${instrument} (testSamples disabled)`)
    }
    
    // Test 2: Test sample loading
    if (testOptions.value.testChords && overallStatus !== 'error') {
      console.log(`Running sample loading test for ${instrument}`)
      const sampleTest = await testSampleLoading(category, instrument)
      tests.push(sampleTest)
      console.log(`Sample test result for ${instrument}:`, sampleTest.status, `(${sampleTest.data?.samples?.length || 0} samples)`)
      if (sampleTest.data?.samples) {
        samples.push(...sampleTest.data.samples)
      }
      if (sampleTest.status === 'error') {
        overallStatus = 'error'
        console.log(`${instrument} failed sample loading test`)
      } else if (sampleTest.status === 'warning' && overallStatus === 'success') {
        overallStatus = 'warning'
      }
    } else {
      console.log(`Skipping sample loading test for ${instrument}: testChords=${testOptions.value.testChords}, overallStatus=${overallStatus}`)
    }
    
    // Test 3: Test audio playback (only if samples loaded successfully)
    if (testOptions.value.testPlayback && overallStatus !== 'error' && samples.length > 0) {
      console.log(`Running playback test for ${instrument} with ${samples.length} samples`)
      const playbackTest = await testAudioPlayback(category, instrument, samples[0])
      tests.push(playbackTest)
      console.log(`Playback test result for ${instrument}:`, playbackTest.status)
      if (playbackTest.status === 'error') {
        overallStatus = 'error'
      } else if (playbackTest.status === 'warning' && overallStatus === 'success') {
        overallStatus = 'warning'
      }
    } else {
      console.log(`Skipping playback test for ${instrument}: testPlayback=${testOptions.value.testPlayback}, overallStatus=${overallStatus}, samples=${samples.length}`)
    }
    
  } catch (error) {
    console.error(`Error testing ${instrument}:`, error)
    overallStatus = 'error'
    errorMessage = error instanceof Error ? error.message : 'Unknown error'
    tests.push({
      name: 'General Test',
      status: 'error',
      message: errorMessage
    })
  }
  
  const testTime = Date.now() - startTime
  console.log(`Completed diagnostics for ${instrument}: ${overallStatus} in ${testTime}ms with ${tests.length} tests`)
  
  return {
    id: `${category}_${instrument}`,
    instrument,
    category,
    status: overallStatus,
    testTime,
    tests,
    samples,
    error: errorMessage || undefined,
    expanded: false
  }
}

const testInstrumentDirectory = async (category: string, instrument: string): Promise<TestResult> => {
  const startTime = Date.now()
  
  try {
    // URL encode the instrument name to handle spaces and special characters
    const encodedInstrument = encodeURIComponent(instrument)
    
    // Test both simplified and duration-based structures like the audio store does
    const testPaths = [
      // Simplified structure
      `instruments/${category}/${encodedInstrument}/mp3/C_major.mp3`,
      `instruments/${category}/${encodedInstrument}/wav/C_major.wav`,
      // Duration-based structure
      `instruments/${category}/${encodedInstrument}/1.0s/mp3/C_major.mp3`,
      `instruments/${category}/${encodedInstrument}/1.0s/wav/C_major.wav`,
      `instruments/${category}/${encodedInstrument}/2.0s/mp3/C_major.mp3`,
      `instruments/${category}/${encodedInstrument}/2.0s/wav/C_major.wav`,
    ]
    
    let pathExists = false
    let foundPath = ''
    for (const path of testPaths) {
      try {
        const response = await fetch(path, { method: 'HEAD' })
        if (response.ok) {
          pathExists = true
          foundPath = path
          break
        }
      } catch (e) {
        // Continue trying other paths
      }
    }
    
    const duration = Date.now() - startTime
    
    if (pathExists) {
      return {
        name: 'Directory Check',
        status: 'success',
        message: `Instrument directory found (${foundPath})`,
        duration
      }
    } else {
      return {
        name: 'Directory Check',
        status: 'error',
        message: 'Instrument directory not found or inaccessible',
        duration
      }
    }
  } catch (error) {
    return {
      name: 'Directory Check',
      status: 'error',
      message: `Directory check failed: ${error}`,
      duration: Date.now() - startTime
    }
  }
}

const testSampleLoading = async (category: string, instrument: string): Promise<TestResult> => {
  const startTime = Date.now()
  const sampleResults: SampleResult[] = []
  
  try {
    // URL encode the instrument name to handle spaces and special characters
    const encodedInstrument = encodeURIComponent(instrument)
    
    // Test common chord samples using the same path logic as the audio store
    const testChords = ['C_major', 'D_major', 'E_major', 'F_major', 'G_major', 'A_major', 'B_major']
    const formats = [
      { ext: 'mp3', folder: 'mp3' },
      { ext: 'wav', folder: 'wav' }
    ]
    const structures = [
      '', // Simplified structure
      '1.0s/', // Duration-based structure
      '2.0s/' // Longer duration structure
    ]
    
    let loadedCount = 0
    
    for (const chord of testChords) {
      let loaded = false
      
      for (const structure of structures) {
        for (const format of formats) {
          const path = `instruments/${category}/${encodedInstrument}/${structure}${format.folder}/${chord}.${format.ext}`
          
          try {
            const response = await fetch(path, { method: 'HEAD' })
            if (response.ok) {
              // Additional validation: check if it's a valid audio file by checking content type
              const contentType = response.headers.get('content-type') || ''
              const isValidAudio = contentType.includes('audio') || 
                                   contentType.includes('mpeg') || 
                                   contentType.includes('wav') ||
                                   path.endsWith('.mp3') || 
                                   path.endsWith('.wav')
              
              if (isValidAudio) {
                sampleResults.push({
                  name: chord,
                  status: 'success',
                  message: 'Sample found and validated',
                  path
                })
                loaded = true
                loadedCount++
                break
              } else {
                sampleResults.push({
                  name: chord,
                  status: 'warning',
                  message: `File found but invalid content type: ${contentType}`,
                  path
                })
              }
            }
          } catch (e) {
            // Continue trying other paths
          }
        }
        if (loaded) break
      }
      
      if (!loaded) {
        sampleResults.push({
          name: chord,
          status: 'error',
          message: 'Sample not found',
          path: `instruments/${category}/${encodedInstrument}/*/[mp3|wav]/${chord}.[mp3|wav]`
        })
      }
    }
    
    const duration = Date.now() - startTime
    const successRate = loadedCount / testChords.length
    
    if (successRate >= 0.8) {
      return {
        name: 'Sample Loading',
        status: 'success',
        message: `${loadedCount}/${testChords.length} samples loaded successfully`,
        duration,
        data: { samples: sampleResults }
      }
    } else if (successRate >= 0.5) {
      return {
        name: 'Sample Loading',
        status: 'warning',
        message: `Only ${loadedCount}/${testChords.length} samples loaded`,
        duration,
        data: { samples: sampleResults }
      }
    } else {
      return {
        name: 'Sample Loading',
        status: 'error',
        message: `Failed to load most samples (${loadedCount}/${testChords.length})`,
        duration,
        data: { samples: sampleResults }
      }
    }
    
  } catch (error) {
    return {
      name: 'Sample Loading',
      status: 'error',
      message: `Sample loading test failed: ${error}`,
      duration: Date.now() - startTime
    }
  }
}

const testAudioPlayback = async (_category: string, _instrument: string, sample: SampleResult): Promise<TestResult> => {
  const startTime = Date.now()
  
  try {
    // Ensure Tone.js context is started
    if (Tone.context.state !== 'running') {
      try {
        await Tone.start()
      } catch (error) {
        return {
          name: 'Audio Playback',
          status: 'error',
          message: `Failed to start audio context: ${error}`,
          duration: Date.now() - startTime
        }
      }
    }
    
    // Create a test player with better error handling
    let player: Tone.Player | null = null
    
    try {
      player = new Tone.Player({
        url: sample.path,
        autostart: false,
        volume: -30 // Very quiet for testing
      })
      
      // Wait for the sample to load with timeout
      const loadPromise = new Promise<void>((resolve, reject) => {
        player!.load(sample.path).then(() => {
          if (player!.loaded) {
            resolve()
          } else {
            reject(new Error('Player failed to load'))
          }
        }).catch(reject)
      })
      
      const timeoutPromise = new Promise<void>((_, reject) => {
        setTimeout(() => reject(new Error('Load timeout')), 5000)
      })
      
      await Promise.race([loadPromise, timeoutPromise])
      
      // Connect to output but keep volume very low
      player.toDestination()
      
      // Quick playback test (very short)
      player.start()
      await new Promise(resolve => setTimeout(resolve, 50)) // Play for 50ms
      player.stop()
      
      return {
        name: 'Audio Playback',
        status: 'success',
        message: 'Audio playback test successful',
        duration: Date.now() - startTime
      }
      
    } finally {
      // Cleanup - ensure player is disposed
      if (player) {
        try {
          player.dispose()
        } catch (e) {
          console.warn('Error disposing player:', e)
        }
      }
    }
    
  } catch (error) {
    return {
      name: 'Audio Playback',
      status: 'error',
      message: `Playback test failed: ${error instanceof Error ? error.message : error}`,
      duration: Date.now() - startTime
    }
  }
}

const exportResults = () => {
  const exportData = {
    timestamp: new Date().toISOString(),
    summary: {
      total: diagnosticsResults.value.length,
      success: successCount.value,
      warnings: warningCount.value,
      errors: errorCount.value
    },
    testOptions: testOptions.value,
    results: diagnosticsResults.value.map(result => ({
      ...result,
      expanded: undefined // Remove UI state
    }))
  }
  
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `mity-studio-diagnostics-${new Date().toISOString().split('T')[0]}.json`
  a.click()
  URL.revokeObjectURL(url)
}

// Initialize
onMounted(() => {
  // Component ready
})
</script>

<style scoped>
.diagnostics-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.diagnostics-dialog {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: 90%;
  max-width: 900px;
  max-height: 90%;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--background);
  border-radius: 12px 12px 0 0;
}

.dialog-header h3 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  color: var(--text);
}

.header-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: var(--surface);
  color: var(--text);
}

.dialog-content {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.status-section {
  margin-bottom: 1.5rem;
}

.status-card {
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.status-card.success {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
}

.status-card.warning {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.3);
}

.status-card.error {
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.3);
}

.status-card.pending {
  background: var(--surface);
  border-color: var(--border);
}

.status-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.status-icon {
  width: 1.25rem;
  height: 1.25rem;
}

.status-header h4 {
  margin: 0;
}

.status-message {
  margin: 0;
  color: var(--text-secondary);
}

.control-panel {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--surface);
  border-radius: 8px;
}

.control-group {
  display: flex;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  transition: all 0.2s ease;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--primary) 80%, black 20%);
}

.btn-secondary {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--background);
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid transparent;
}

.btn-ghost:hover:not(:disabled) {
  background: var(--surface);
  border-color: var(--border);
}

.icon {
  width: 1rem;
  height: 1rem;
}

.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.progress-section {
  margin-top: 1rem;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--surface);
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: var(--primary);
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin: 0;
}

.test-options {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: var(--surface);
  border-radius: 8px;
}

.test-options h4 {
  margin: 0 0 0.75rem 0;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.checkbox-label input[type="checkbox"] {
  margin: 0;
}

.results-section {
  margin-bottom: 1.5rem;
}

.results-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}

.results-header h4 {
  margin: 0;
}

.results-summary {
  display: flex;
  gap: 1rem;
  font-size: 0.875rem;
}

.success-count {
  color: #22c55e;
}

.warning-count {
  color: #f59e0b;
}

.error-count {
  color: #ef4444;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.result-item {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
}

.result-item.success {
  border-left: 4px solid #22c55e;
}

.result-item.warning {
  border-left: 4px solid #f59e0b;
}

.result-item.error {
  border-left: 4px solid #ef4444;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--surface);
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.result-header:hover {
  background: var(--background);
}

.result-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.result-icon {
  width: 1rem;
  height: 1rem;
}

.result-title {
  font-weight: 500;
}

.result-category {
  font-size: 0.875rem;
  color: var(--text-secondary);
  background: var(--background);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.result-summary {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.result-time {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.expand-icon {
  width: 1rem;
  height: 1rem;
  transition: transform 0.2s ease;
}

.expand-icon.expanded {
  transform: rotate(180deg);
}

.result-details {
  padding: 1rem;
  background: var(--background);
  border-top: 1px solid var(--border);
}

.test-details {
  margin-bottom: 1rem;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  font-size: 0.875rem;
}

.test-icon {
  width: 0.875rem;
  height: 0.875rem;
}

.test-name {
  font-weight: 500;
  min-width: 120px;
}

.test-message {
  flex: 1;
  color: var(--text-secondary);
}

.test-duration {
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.samples-section h5 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
}

.samples-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.5rem;
}

.sample-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem;
  background: var(--surface);
  border-radius: 4px;
  font-size: 0.75rem;
  border: 1px solid transparent;
}

.sample-item.success {
  border-color: rgba(34, 197, 94, 0.3);
  background: rgba(34, 197, 94, 0.05);
}

.sample-item.error {
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.05);
}

.sample-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sample-icon {
  width: 0.75rem;
  height: 0.75rem;
}

.sample-more {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem;
  background: var(--surface);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.error-details h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  color: #ef4444;
}

.error-message {
  background: var(--surface);
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  overflow-x: auto;
}

.export-section {
  text-align: center;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
}
</style>
