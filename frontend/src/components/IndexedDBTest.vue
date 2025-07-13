<template>
  <div class="indexeddb-test">
    <h2>IndexedDB Sample Storage Test</h2>
    
    <div class="test-section">
      <h3>Upload Samples</h3>
      <input 
        ref="fileInput"
        type="file" 
        accept="audio/*" 
        multiple 
        @change="handleFileUpload"
      />
      <button @click="uploadSamples" :disabled="isLoading">
        {{ isLoading ? `Uploading... ${Math.round(loadingProgress)}%` : 'Upload & Store in IndexedDB' }}
      </button>
    </div>

    <div class="test-section">
      <h3>Sample Library ({{ totalSamples }} samples)</h3>
      <div class="controls">
        <button @click="refreshFromStorage">Refresh from Storage</button>
        <button @click="showStorageInfo">Show Storage Info</button>
        <button @click="clearAllSamples" class="danger">Clear All</button>
      </div>
      
      <div v-if="storageInfo" class="storage-info">
        <h4>Storage Information</h4>
        <p><strong>IndexedDB:</strong> {{ storageInfo.indexedDB.count }} files, {{ formatFileSize(storageInfo.indexedDB.estimatedSize) }}</p>
        <p><strong>LocalStorage:</strong> {{ storageInfo.localStorage.samples }} samples metadata, {{ formatFileSize(storageInfo.localStorage.metadataSize) }}</p>
        <p><strong>Total:</strong> {{ storageInfo.total.samples }} samples, {{ formatFileSize(storageInfo.total.estimatedSize) }}</p>
      </div>
      
      <div v-if="localSamples.length > 0" class="samples-list">
        <div 
          v-for="sample in localSamples" 
          :key="sample.id"
          class="sample-item"
        >
          <div class="sample-info">
            <h4>{{ sample.name }}</h4>
            <p>{{ sample.category }} | {{ formatFileSize(sample.size) }} | {{ formatDuration(sample.duration) }}</p>
            <p>File ID: {{ sample.fileId }}</p>
            <p>Has URL: {{ sample.url ? 'Yes' : 'No' }}</p>
            <p>Has File: {{ sample.file ? 'Yes' : 'No' }}</p>
          </div>
          <div class="sample-controls">
            <button v-if="!sample.file" @click="restoreFile(sample.id)" class="restore">
              Restore File
            </button>
            <button @click="removeSample(sample.id)" class="danger">Remove</button>
          </div>
          <audio v-if="sample.url" :src="sample.url" controls></audio>
        </div>
      </div>
    </div>

    <div class="test-section">
      <h3>Test Results</h3>
      <div class="results">
        <div v-for="result in testResults" :key="result.id" :class="result.type">
          <span class="timestamp">{{ result.timestamp }}</span>
          {{ result.message }}
        </div>
      </div>
      <button @click="clearResults">Clear Results</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSampleStore } from '../stores/sampleStore'

const sampleStore = useSampleStore()
const fileInput = ref<HTMLInputElement>()
const storageInfo = ref<any>(null)
const testResults = ref<Array<{id: number, type: 'success' | 'error' | 'info', message: string, timestamp: string}>>([])

// Destructure store properties
const { 
  localSamples, 
  isLoading, 
  loadingProgress, 
  totalSamples,
  loadSamples,
  removeSample: storeRemoveSample,
  clearAllSamples: storeClearAllSamples,
  formatFileSize,
  formatDuration,
  getStorageInfo,
  restoreSampleFile
} = sampleStore

const addResult = (type: 'success' | 'error' | 'info', message: string) => {
  testResults.value.unshift({
    id: Date.now(),
    type,
    message,
    timestamp: new Date().toLocaleTimeString()
  })
}

const handleFileUpload = () => {
  // File selection handled by input
}

const uploadSamples = async () => {
  if (!fileInput.value?.files?.length) {
    addResult('error', 'Please select audio files first')
    return
  }

  try {
    const files = fileInput.value.files
    addResult('info', `Starting upload of ${files.length} files to IndexedDB...`)
    
    const newSamples = await loadSamples(files)
    addResult('success', `Successfully uploaded and stored ${newSamples?.length || 0} samples in IndexedDB`)
    
    // Update storage info
    await showStorageInfo()
    
  } catch (error) {
    addResult('error', `Upload failed: ${error}`)
  }
}

const refreshFromStorage = async () => {
  try {
    addResult('info', 'Refreshing samples from storage...')
    // The store automatically loads from storage on init, but we can trigger a reload
    window.location.reload()
  } catch (error) {
    addResult('error', `Failed to refresh from storage: ${error}`)
  }
}

const showStorageInfo = async () => {
  try {
    storageInfo.value = await getStorageInfo()
    if (storageInfo.value) {
      addResult('success', 'Storage information updated')
    } else {
      addResult('error', 'Failed to get storage information')
    }
  } catch (error) {
    addResult('error', `Failed to get storage info: ${error}`)
  }
}

const clearAllSamples = async () => {
  try {
    await storeClearAllSamples()
    storageInfo.value = null
    addResult('success', 'All samples cleared from IndexedDB and localStorage')
  } catch (error) {
    addResult('error', `Failed to clear samples: ${error}`)
  }
}

const removeSample = async (sampleId: string) => {
  try {
    await storeRemoveSample(sampleId)
    addResult('success', 'Sample removed from IndexedDB')
    await showStorageInfo()
  } catch (error) {
    addResult('error', `Failed to remove sample: ${error}`)
  }
}

const restoreFile = async (sampleId: string) => {
  try {
    const file = await restoreSampleFile(sampleId)
    if (file) {
      addResult('success', `File restored: ${file.name}`)
    } else {
      addResult('error', 'Failed to restore file')
    }
  } catch (error) {
    addResult('error', `Failed to restore file: ${error}`)
  }
}

const clearResults = () => {
  testResults.value = []
}

onMounted(async () => {
  addResult('info', 'IndexedDB Sample Storage Test initialized')
  
  // Show initial storage info
  await showStorageInfo()
  
  // Check if there are existing samples
  if (localSamples.length > 0) {
    addResult('success', `Found ${localSamples.length} existing samples in store`)
  }
})
</script>

<style scoped>
.indexeddb-test {
  max-width: 1000px;
  margin: 0 auto;
  padding: 20px;
}

.test-section {
  margin: 20px 0;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #f9f9f9;
}

.test-section h3 {
  margin-top: 0;
  color: #333;
}

.controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.controls button {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  background: #007bff;
  color: white;
}

.controls button:hover {
  background: #0056b3;
}

.controls button.danger {
  background: #dc3545;
}

.controls button.danger:hover {
  background: #c82333;
}

.controls button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.storage-info {
  margin: 15px 0;
  padding: 10px;
  background: #e9ecef;
  border-radius: 4px;
}

.storage-info h4 {
  margin: 0 0 10px 0;
}

.storage-info p {
  margin: 5px 0;
  font-family: monospace;
}

.samples-list {
  margin-top: 15px;
}

.sample-item {
  margin: 10px 0;
  padding: 15px;
  border: 1px solid #ccc;
  border-radius: 4px;
  background: white;
}

.sample-info h4 {
  margin: 0 0 5px 0;
  color: #333;
}

.sample-info p {
  margin: 2px 0;
  font-size: 0.9em;
  color: #666;
}

.sample-controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
}

.sample-controls button {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9em;
}

.sample-controls button.restore {
  background: #28a745;
  color: white;
}

.sample-controls button.restore:hover {
  background: #218838;
}

.sample-controls button.danger {
  background: #dc3545;
  color: white;
}

.sample-controls button.danger:hover {
  background: #c82333;
}

.results {
  max-height: 300px;
  overflow-y: auto;
  margin-bottom: 10px;
}

.results div {
  margin: 5px 0;
  padding: 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.9em;
}

.timestamp {
  color: #666;
  margin-right: 10px;
}

.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.info {
  background: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}

input[type="file"] {
  margin: 10px 0;
  padding: 5px;
}

audio {
  width: 100%;
  margin-top: 10px;
}
</style>
