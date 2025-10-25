<template>
  <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>
          <ImageIcon :size="20" class="header-icon" />
          {{ $t('albumCover.title') }}
        </h2>
        <button @click="$emit('close')" class="close-btn">
          <X :size="20" />
        </button>
      </div>
      
      <div class="modal-body">
        <div class="form-group">
          <label for="albumDescription" class="section-label">
            <PenTool :size="16" class="section-icon" />
            {{ $t('albumCover.description') }}
          </label>
          <textarea
            id="albumDescription"
            v-model="description"
            :placeholder="$t('albumCover.descriptionPlaceholder')"
            class="input textarea"
            rows="3"
            :disabled="isGenerating"
          ></textarea>
          <p class="help-text">
            {{ $t('albumCover.helpText') }}
          </p>
        </div>

        <div class="form-group">
          <label class="section-label">
            <Palette :size="16" class="section-icon" />
            {{ $t('albumCover.style') }}
          </label>
          <select v-model="selectedStyle" class="input select" :disabled="isGenerating">
            <option value="">{{ $t('albumCover.selectStyle') }}</option>
            <option value="synthwave">{{ $t('albumCover.styles.synthwave') }}</option>
            <option value="minimalist">{{ $t('albumCover.styles.minimalist') }}</option>
            <option value="abstract">{{ $t('albumCover.styles.abstract') }}</option>
            <option value="vintage">{{ $t('albumCover.styles.vintage') }}</option>
            <option value="modern">{{ $t('albumCover.styles.modern') }}</option>
            <option value="artistic">{{ $t('albumCover.styles.artistic') }}</option>
            <option value="photographic">{{ $t('albumCover.styles.photographic') }}</option>
            <option value="illustration">{{ $t('albumCover.styles.illustration') }}</option>
          </select>
        </div>

        <!-- Preview current cover if exists -->
        <div v-if="currentCover" class="current-cover-preview">
          <label class="section-label">
            <ImageIcon :size="16" class="section-icon" />
            {{ $t('albumCover.currentCover') }}
          </label>
          <div class="cover-preview">
            <img :src="currentCover" alt="Current album cover" class="cover-image" />
          </div>
        </div>

        <!-- Progress section -->
        <div v-if="isGenerating" class="progress-section">
          <div class="progress-header">
            <Loader2 :size="16" class="animate-spin" />
            <span>{{ $t('albumCover.generating') }}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: progress + '%' }"></div>
          </div>
          <p class="progress-text">{{ currentStep }}</p>
        </div>
      </div>
      
      <div class="modal-footer">
        <button @click="$emit('close')" class="btn btn-secondary" :disabled="isGenerating">
          {{ $t('common.cancel') }}
        </button>
        <button @click="uploadFromFile" class="btn btn-secondary" :disabled="isGenerating">
          <Upload :size="16" />
          {{ $t('albumCover.uploadImage') }}
        </button>
        <button 
          @click="generateCover" 
          class="btn btn-primary" 
          :disabled="!description.trim() || isGenerating"
        >
          <Loader2 v-if="isGenerating" :size="16" class="animate-spin" />
          <ImageIcon v-else :size="16" />
          {{ isGenerating ? $t('albumCover.generating') : $t('albumCover.generate') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, ImageIcon as ImageIcon, Loader2, PenTool, Palette, Upload } from 'lucide-vue-next'
import { useAudioStore } from '../stores/audioStore'

interface Props {
  show: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  close: []
  coverGenerated: [imageUrl: string]
}>()

const { t } = useI18n()
const audioStore = useAudioStore()

const description = ref('')
const selectedStyle = ref('')
const isGenerating = ref(false)
const progress = ref(0)
const currentStep = ref('')

const currentCover = computed(() => {
  return (audioStore.songStructure as any)?.albumCover
})

const handleOverlayClick = (e: MouseEvent) => {
  if (e.target === e.currentTarget && !isGenerating.value) {
    emit('close')
  }
}

const generateAutoPrompt = () => {
  const structure = audioStore.songStructure as any
  const songName = structure?.title || 'Untitled Song'
  const artist = structure?.artist || 'Unknown Artist'
  const genre = structure?.genre || 'music'
  
  return `Create an album cover for a song called "${songName}" by ${artist}. 
    Genre: ${genre}. 
    Style: ${selectedStyle.value || 'professional'} music album cover, professional, artistic, high quality, 
    vibrant colors, suitable for music streaming platforms.`
}

const simulateProgress = () => {
  progress.value = 0
  currentStep.value = t('albumCover.steps.preparing')
  
  const steps = [
    { progress: 20, step: t('albumCover.steps.analyzing') },
    { progress: 40, step: t('albumCover.steps.designing') },
    { progress: 60, step: t('albumCover.steps.rendering') },
    { progress: 80, step: t('albumCover.steps.optimizing') },
    { progress: 95, step: t('albumCover.steps.finishing') }
  ]

  let stepIndex = 0
  const interval = setInterval(() => {
    if (stepIndex < steps.length && isGenerating.value) {
      progress.value = steps[stepIndex].progress
      currentStep.value = steps[stepIndex].step
      stepIndex++
    } else {
      clearInterval(interval)
      if (isGenerating.value) {
        progress.value = 100
        currentStep.value = t('albumCover.steps.complete')
      }
    }
  }, 800)

  return interval
}

const generateCover = async () => {
  if (!description.value.trim() || isGenerating.value) return
  
  isGenerating.value = true
  const progressInterval = simulateProgress()
  
  try {
    const fullPrompt = description.value.trim() + 
      (selectedStyle.value ? ` in ${selectedStyle.value} style` : '') +
      '. Professional album cover, high quality, vibrant colors, suitable for music streaming platforms.'
    
    const response = await fetch('/api/ai/generate/image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: fullPrompt })
    })
    
    const data = await response.json()
    
    if (data.success && data.image_url) {
      // Update the song structure with the new album cover
      const updatedStructure = {
        ...audioStore.songStructure,
        albumCover: data.image_url
      }
      audioStore.loadSongStructure(updatedStructure)
      emit('coverGenerated', data.image_url)
      
      // Small delay to show completion
      setTimeout(() => {
        emit('close')
      }, 1000)
    } else {
      throw new Error(data.error || 'Failed to generate image')
    }
  } catch (error) {
    console.error('Failed to generate album cover:', error)
    alert(t('albumCover.generateError'))
  } finally {
    clearInterval(progressInterval)
    isGenerating.value = false
    progress.value = 0
    currentStep.value = ''
  }
}

const uploadFromFile = () => {
  if (isGenerating.value) return
  
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  
  input.onchange = (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const imageUrl = e.target?.result as string
        const updatedStructure = {
          ...audioStore.songStructure,
          albumCover: imageUrl
        }
        audioStore.loadSongStructure(updatedStructure)
        emit('coverGenerated', imageUrl)
        emit('close')
      }
      reader.readAsDataURL(file)
    }
  }
  
  input.click()
}

// Auto-generate description based on song details
onMounted(() => {
  if (!description.value) {
    const structure = audioStore.songStructure as any
    if (structure?.title) {
      description.value = generateAutoPrompt()
    }
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
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--surface);
  border-radius: 12px;
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.2);
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  padding: 1.5rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--surface-elevated);
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.header-icon {
  color: var(--accent);
}

.close-btn {
  background: none;
  border: none;
  padding: 0.5rem;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-normal);
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.modal-body {
  padding: 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.form-group {
  margin-bottom: 1.5rem;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 0.95rem;
}

.section-icon {
  color: var(--accent);
}

.input {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.95rem;
  transition: all var(--transition-normal);
  box-sizing: border-box;
}

.input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.textarea {
  resize: vertical;
  min-height: 80px;
  font-family: inherit;
}

.select {
  cursor: pointer;
}

.help-text {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: 0.5rem;
  margin-bottom: 0;
}

.current-cover-preview {
  margin-bottom: 1.5rem;
}

.cover-preview {
  margin-top: 0.5rem;
  display: flex;
  justify-content: center;
}

.cover-image {
  width: 120px;
  height: 120px;
  object-fit: cover;
  border-radius: 8px;
  border: 2px solid var(--border);
}

.progress-section {
  padding: 1rem;
  background: var(--surface-elevated);
  border-radius: 8px;
  margin-top: 1rem;
}

.progress-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
  font-weight: 500;
  color: var(--text-primary);
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-light));
  border-radius: 3px;
  transition: width 0.3s ease;
}

.progress-text {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin: 0;
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 0.75rem;
  justify-content: flex-end;
  background: var(--surface-elevated);
}

.btn {
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  transition: all var(--transition-normal);
  min-width: fit-content;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--accent);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-dark);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.btn-secondary {
  background: var(--surface-hover);
  color: var(--text-primary);
  border: 2px solid var(--border);
}

.btn-secondary:hover:not(:disabled) {
  background: var(--surface-elevated);
  border-color: var(--accent);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .modal-content {
    width: 95%;
    max-height: 95vh;
  }
  
  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }
  
  .modal-footer {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .btn {
    justify-content: center;
  }
}
</style>