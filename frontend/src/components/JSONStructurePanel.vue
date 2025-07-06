<template>
  <div class="json-panel">
    <div class="json-header">
      <h3>{{ $t('json.title') }}</h3>
      <div class="json-controls">
        <button class="btn btn-ghost" @click="formatJSON" :title="$t('json.format')">
          <Code class="icon" />
        </button>
        <button class="btn btn-ghost" @click="copyJSON" :title="$t('json.copy')">
          <Copy class="icon" />
        </button>
        <button class="btn btn-ghost" @click="pasteJSON" :title="$t('json.paste')">
          <Clipboard class="icon" />
        </button>
      </div>
    </div>
    
    <div class="json-content">
      <div class="json-stats">
        <div class="stat-item">
          <span class="stat-label">Tracks:</span>
          <span class="stat-value">{{ audioStore.songStructure.tracks.length }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Duration:</span>
          <span class="stat-value">{{ audioStore.songStructure.duration }}s</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Tempo:</span>
          <span class="stat-value">{{ audioStore.songStructure.tempo }} BPM</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Key:</span>
          <span class="stat-value">{{ audioStore.songStructure.key }}</span>
        </div>
      </div>
      
      <div class="json-editor-container">
        <textarea
          v-model="jsonContent"
          class="json-editor"
          @input="handleJSONChange"
          @blur="validateAndApplyJSON"
          spellcheck="false"
          ref="jsonEditor"
        ></textarea>
        
        <div v-if="jsonError" class="json-error">
          <AlertCircle class="error-icon" />
          <span>{{ jsonError }}</span>
        </div>
      </div>
    </div>
    
    <div class="json-footer">
      <div class="json-info">
        <span class="info-text">Last updated: {{ formatDate(audioStore.songStructure.updatedAt) }}</span>
      </div>
      
      <div class="json-actions">
        <button class="btn btn-secondary" @click="resetJSON">
          <RotateCcw class="icon" />
          Reset
        </button>
        <button class="btn btn-primary" @click="exportJSON">
          <Download class="icon" />
          Export
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { 
  Code, 
  Copy, 
  Clipboard, 
  AlertCircle, 
  RotateCcw, 
  Download 
} from 'lucide-vue-next'

const audioStore = useAudioStore()
const jsonEditor = ref<HTMLTextAreaElement>()

const jsonContent = ref('')
const jsonError = ref('')
const isEditing = ref(false)

// Watch for changes in song structure and update JSON content
watch(() => audioStore.songStructure, (newStructure) => {
  if (!isEditing.value) {
    jsonContent.value = JSON.stringify(newStructure, null, 2)
  }
}, { deep: true, immediate: true })

const handleJSONChange = () => {
  isEditing.value = true
  jsonError.value = ''
}

const validateAndApplyJSON = () => {
  isEditing.value = false
  
  try {
    const parsedJSON = JSON.parse(jsonContent.value)
    
    // Basic validation
    if (!parsedJSON.id || !parsedJSON.name || !Array.isArray(parsedJSON.tracks)) {
      throw new Error('Invalid song structure format')
    }
    
    // Apply the changes with enhanced JSON configuration support
    audioStore.loadSongStructure(parsedJSON)
    
    // Initialize track configurations for future clip creation
    audioStore.initializeTrackConfigurations()
    
    jsonError.value = ''
    console.log('JSON structure applied with track configurations initialized')
  } catch (error) {
    jsonError.value = error instanceof Error ? error.message : 'Invalid JSON format'
    // Revert to current structure
    jsonContent.value = JSON.stringify(audioStore.songStructure, null, 2)
  }
}

const formatJSON = () => {
  try {
    const parsed = JSON.parse(jsonContent.value)
    jsonContent.value = JSON.stringify(parsed, null, 2)
    jsonError.value = ''
  } catch (error) {
    jsonError.value = 'Cannot format invalid JSON'
  }
}

const copyJSON = async () => {
  try {
    await navigator.clipboard.writeText(jsonContent.value)
    // Could show a toast notification here
  } catch (error) {
    console.error('Failed to copy JSON:', error)
  }
}

const pasteJSON = async () => {
  try {
    const text = await navigator.clipboard.readText()
    jsonContent.value = text
    handleJSONChange()
  } catch (error) {
    console.error('Failed to paste JSON:', error)
  }
}

const resetJSON = () => {
  jsonContent.value = JSON.stringify(audioStore.songStructure, null, 2)
  jsonError.value = ''
  isEditing.value = false
}

const exportJSON = () => {
  const blob = new Blob([jsonContent.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${audioStore.songStructure.name}-structure.json`
  a.click()
  URL.revokeObjectURL(url)
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}
</script>

<style scoped>
.json-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.json-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface);
}

.json-header h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.json-controls {
  display: flex;
  gap: 0.5rem;
}

.json-controls .btn {
  padding: 0.5rem;
  min-width: auto;
}

.json-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.json-stats {
  padding: 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-label {
  font-size: 0.8125rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.stat-value {
  font-size: 0.8125rem;
  color: var(--text);
  font-weight: 600;
}

.json-editor-container {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
}

.json-editor {
  flex: 1;
  padding: 1rem;
  background: var(--background);
  border: none;
  color: var(--text);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  resize: none;
  outline: none;
  white-space: pre;
  overflow-wrap: normal;
  overflow-x: auto;
}

.json-editor::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.json-editor::-webkit-scrollbar-track {
  background: var(--surface);
}

.json-editor::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.json-editor::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.json-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border-top: 1px solid var(--error);
  color: var(--error);
  font-size: 0.8125rem;
}

.error-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.json-footer {
  padding: 1rem;
  border-top: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
}

.json-info {
  flex: 1;
}

.info-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.json-actions {
  display: flex;
  gap: 0.5rem;
}

.icon {
  width: 16px;
  height: 16px;
}

/* JSON Syntax Highlighting (basic) */
.json-editor {
  color: var(--text);
}

/* You could add more sophisticated syntax highlighting here */
@media (max-width: 768px) {
  .json-stats {
    grid-template-columns: 1fr;
    gap: 0.5rem;
  }
  
  .json-footer {
    flex-direction: column;
    align-items: stretch;
    gap: 0.75rem;
  }
  
  .json-actions {
    justify-content: stretch;
  }
  
  .json-actions .btn {
    flex: 1;
  }
}
</style>
