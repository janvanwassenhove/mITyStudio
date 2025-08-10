<template>
  <div v-if="show" class="modal-overlay" @click="closeDialog">
    <div class="modal-content export-dialog" @click.stop>
      <div class="modal-header">
        <h3>{{ $t('exportSong.title') }}</h3>
        <button @click="closeDialog" class="btn btn-ghost close-btn">
          <X class="icon" />
        </button>
      </div>
      
      <div class="modal-body">
        <!-- Song Name -->
        <div class="form-group">
          <label for="songName">{{ $t('exportSong.songName') }}</label>
          <input 
            id="songName"
            v-model="songName" 
            type="text" 
            class="input"
            :placeholder="$t('exportSong.songNamePlaceholder')"
          />
        </div>

        <!-- Export Format -->
        <div class="form-group">
          <label for="exportFormat">{{ $t('exportSong.format') }}</label>
          <select id="exportFormat" v-model="selectedFormat" class="input select">
            <option value="wav">WAV</option>
            <option value="mp3">MP3</option>
            <option value="ogg">OGG</option>
          </select>
        </div>

        <!-- Export Quality -->
        <div class="form-group">
          <label for="exportQuality">{{ $t('exportSong.quality') }}</label>
          <select id="exportQuality" v-model="selectedQuality" class="input select">
            <option value="high">{{ $t('exportSong.qualityHigh') }}</option>
            <option value="medium">{{ $t('exportSong.qualityMedium') }}</option>
            <option value="low">{{ $t('exportSong.qualityLow') }}</option>
          </select>
        </div>

        <!-- Export Folder -->
        <div class="form-group">
          <label for="exportFolder">{{ $t('exportSong.exportFolder') }}</label>
          <div class="folder-input-group">
            <input 
              id="exportFolder"
              v-model="exportFolder" 
              type="text" 
              class="input"
              :placeholder="$t('exportSong.exportFolderPlaceholder')"
              readonly
            />
            <button @click="selectExportFolder" class="btn btn-ghost folder-btn">
              <FolderOpen class="icon" />
              {{ $t('exportSong.browse') }}
            </button>
          </div>
          <p class="help-text">{{ $t('exportSong.exportFolderHelp') }}</p>
        </div>

        <!-- Export Options -->
        <div class="form-group">
          <label class="checkbox-label">
            <input 
              v-model="includeProject" 
              type="checkbox" 
              class="checkbox"
            />
            {{ $t('exportSong.includeProject') }}
          </label>
          <p class="help-text">{{ $t('exportSong.includeProjectHelp') }}</p>
        </div>
      </div>
      
      <div class="modal-footer">
        <button @click="closeDialog" class="btn btn-ghost">
          {{ $t('common.cancel') }}
        </button>
        <button 
          @click="exportSong" 
          class="btn btn-primary" 
          :disabled="isExporting || !songName.trim()"
        >
          <Download v-if="!isExporting" class="icon" />
          <div v-else class="spinner"></div>
          {{ isExporting ? $t('exportSong.exporting') : $t('exportSong.export') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, FolderOpen, Download } from 'lucide-vue-next'
import { useAudioStore } from '../stores/audioStore'

interface Props {
  show: boolean
}

interface ExportSettings {
  exportFormat: string
  exportQuality: string
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const audioStore = useAudioStore()

// Form state
const songName = ref('')
const selectedFormat = ref('wav')
const selectedQuality = ref('high')
const exportFolder = ref('')
const includeProject = ref(true)
const isExporting = ref(false)

// Load settings from localStorage or default to settings panel values
const loadExportSettings = (): ExportSettings => {
  try {
    const settings = localStorage.getItem('mity-studio-settings')
    if (settings) {
      const parsed = JSON.parse(settings)
      return {
        exportFormat: parsed.exportFormat || 'wav',
        exportQuality: parsed.exportQuality || 'high'
      }
    }
  } catch (error) {
    console.warn('Failed to load export settings:', error)
  }
  
  return {
    exportFormat: 'wav',
    exportQuality: 'high'
  }
}

// Initialize form values
const initializeForm = () => {
  // Set song name from current song structure
  songName.value = audioStore.songStructure.name || 'Untitled Song'
  
  // Load export settings from settings panel
  const settings = loadExportSettings()
  selectedFormat.value = settings.exportFormat
  selectedQuality.value = settings.exportQuality
  
  // Set default export folder (Downloads for web, user selection for desktop)
  exportFolder.value = t('exportSong.defaultFolder')
}

// Watch for dialog opening
watch(() => props.show, (newShow) => {
  if (newShow) {
    initializeForm()
  }
})

const selectExportFolder = async () => {
  try {
    // For web apps, we can't actually browse folders
    // In a real desktop app, this would open a folder picker
    if ('showDirectoryPicker' in window) {
      // Use File System Access API if available (Chrome 86+)
      const dirHandle = await (window as any).showDirectoryPicker()
      exportFolder.value = dirHandle.name
    } else {
      // Fallback: show info about browser limitation
      alert(t('exportSong.browserLimitation'))
    }
  } catch (error) {
    console.log('Folder selection cancelled or failed:', error)
  }
}

const exportSong = async () => {
  if (!songName.value.trim()) {
    alert(t('exportSong.nameRequired'))
    return
  }

  isExporting.value = true

  try {
    // Prepare export data
    const exportData = {
      song_structure: audioStore.songStructure,
      format: selectedFormat.value,
      quality: selectedQuality.value,
      include_project: includeProject.value,
      filename: songName.value.trim()
    }

    console.log('🎵 Exporting song with data:', exportData)

    // Call backend to generate the song
    const response = await fetch('/api/audio/export-song', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(exportData)
    })

    if (!response.ok) {
      const errorData = await response.json()
      throw new Error(errorData.error || 'Export failed')
    }

    const result = await response.json()
    
    console.log('✅ Export completed:', result)

    // Download the generated file
    if (result.download_url) {
      // Create download link
      const a = document.createElement('a')
      a.href = result.download_url
      a.download = `${songName.value}.${selectedFormat.value}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }

    // Also save project if requested
    if (includeProject.value && result.project_file) {
      const projectBlob = new Blob([JSON.stringify(result.project_file, null, 2)], { 
        type: 'application/json' 
      })
      const projectUrl = URL.createObjectURL(projectBlob)
      const projectLink = document.createElement('a')
      projectLink.href = projectUrl
      projectLink.download = `${songName.value}-project.json`
      document.body.appendChild(projectLink)
      projectLink.click()
      document.body.removeChild(projectLink)
      URL.revokeObjectURL(projectUrl)
    }

    alert(t('exportSong.success', { name: songName.value, format: selectedFormat.value.toUpperCase() }))
    closeDialog()

  } catch (error) {
    console.error('❌ Export failed:', error)
    const errorMessage = error instanceof Error ? error.message : 'Unknown error'
    alert(t('exportSong.error', { error: errorMessage }))
  } finally {
    isExporting.value = false
  }
}

const closeDialog = () => {
  emit('close')
}

onMounted(() => {
  if (props.show) {
    initializeForm()
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--surface);
  border-radius: 12px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.2);
  max-width: 500px;
  width: 90%;
  max-height: 90vh;
  overflow: hidden;
  border: 1px solid var(--border);
}

.export-dialog {
  max-width: 600px;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--background);
}

.modal-header h3 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.close-btn {
  padding: 0.5rem;
  border-radius: 6px;
}

.modal-body {
  padding: 1.5rem;
  max-height: 60vh;
  overflow-y: auto;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-primary);
}

.input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: all var(--transition-normal);
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.select {
  cursor: pointer;
}

.folder-input-group {
  display: flex;
  gap: 0.5rem;
}

.folder-input-group .input {
  flex: 1;
}

.folder-btn {
  padding: 0.75rem 1rem;
  white-space: nowrap;
  border: 1px solid var(--border);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: normal;
}

.checkbox {
  width: auto;
  margin: 0;
}

.help-text {
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.4;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  background: var(--background);
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-normal);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border-color: var(--border);
}

.btn-ghost:hover:not(:disabled) {
  background: var(--background-hover);
  color: var(--text-primary);
}

.btn-primary {
  background: var(--primary);
  color: white;
  box-shadow: 0 2px 4px rgba(99, 102, 241, 0.2);
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-dark);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(99, 102, 241, 0.3);
}

.icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid transparent;
  border-top: 2px solid currentColor;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* Dark theme adjustments */
.theme-dark .modal-overlay {
  background: rgba(0, 0, 0, 0.7);
}

.theme-dark .modal-content {
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4);
}
</style>
