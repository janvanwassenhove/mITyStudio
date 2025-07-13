<template>
  <div class="json-panel">
    <div class="json-header">
      <h3>{{ $t('song.title') }}</h3>
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
      <div class="song-info">
        <div class="album-cover">
          <img 
            :src="(audioStore.songStructure as any).albumCover || '/music-note.svg'" 
            :alt="audioStore.songStructure.name"
            class="cover-image"
            @error="handleImageError"
          />
          <div class="cover-overlay">
            <div class="cover-actions">
              <button class="cover-action-btn" @click="generateCover" :title="$t('song.generateCover')" :disabled="isGeneratingCover">
                <Sparkles class="icon" />
              </button>
              <button class="cover-action-btn" @click="uploadCover" :title="$t('song.uploadCover')">
                <Upload class="icon" />
              </button>
            </div>
          </div>
        </div>
        
        <div class="song-details">
          <h2 class="song-name">{{ audioStore.songStructure.name }}</h2>
          <p class="artist-name">{{ (audioStore.songStructure as any).artist || 'Unknown Artist' }}</p>
          
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
        </div>
      </div>
      
      <div class="lyrics-section">
        <div class="section-header" @click="toggleLyricsExpanded">
          <h4>Lyrics</h4>
          <button class="collapse-btn" :class="{ 'expanded': isLyricsExpanded }">
            <ChevronDown class="icon" />
          </button>
        </div>
        
        <div v-if="isLyricsExpanded" class="lyrics-editor-container">
          <textarea
            v-model="lyricsContent"
            class="lyrics-editor"
            @input="handleLyricsChange"
            @blur="updateLyricsInJSON"
            spellcheck="true"
            :placeholder="$t('song.lyricsPlaceholder')"
            ref="lyricsEditor"
          ></textarea>
          
          <div class="lyrics-info">
            <span class="info-text">{{ getLyricsStats() }}</span>
          </div>
        </div>
      </div>
      
      <div class="json-structure-section">
        <div class="section-header" @click="toggleJSONExpanded">
          <h4>JSON Structure</h4>
          <button class="collapse-btn" :class="{ 'expanded': isJSONExpanded }">
            <ChevronDown class="icon" />
          </button>
        </div>
        
        <div v-if="isJSONExpanded" class="json-editor-container">
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
  Download,
  ChevronDown,
  Sparkles,
  Upload
} from 'lucide-vue-next'

const audioStore = useAudioStore()
const jsonEditor = ref<HTMLTextAreaElement>()
const lyricsEditor = ref<HTMLTextAreaElement>()

const jsonContent = ref('')
const jsonError = ref('')
const isEditing = ref(false)
const isJSONExpanded = ref(false)
const isLyricsExpanded = ref(false)
const lyricsContent = ref('')
const isGeneratingCover = ref(false)

// Watch for changes in song structure and update JSON content
watch(() => audioStore.songStructure, (newStructure) => {
  if (!isEditing.value) {
    jsonContent.value = JSON.stringify(newStructure, null, 2)
  }
  // Update lyrics content when song structure changes
  const lyrics = (newStructure as any).lyrics || ''
  if (lyricsContent.value !== lyrics) {
    lyricsContent.value = lyrics
  }
}, { deep: true, immediate: true })

const handleJSONChange = () => {
  isEditing.value = true
  jsonError.value = ''
}

const toggleJSONExpanded = () => {
  isJSONExpanded.value = !isJSONExpanded.value
}

const toggleLyricsExpanded = () => {
  isLyricsExpanded.value = !isLyricsExpanded.value
}

const handleLyricsChange = () => {
  // Optional: You can add real-time validation or other logic here
}

const updateLyricsInJSON = () => {
  try {
    const updatedStructure = {
      ...audioStore.songStructure,
      lyrics: lyricsContent.value
    }
    audioStore.loadSongStructure(updatedStructure)
    console.log('Lyrics updated in song structure')
  } catch (error) {
    console.error('Failed to update lyrics:', error)
  }
}

const getLyricsStats = () => {
  const text = lyricsContent.value
  if (!text) return 'No lyrics'
  
  const lines = text.split('\n').filter(line => line.trim().length > 0)
  const words = text.split(/\s+/).filter(word => word.length > 0)
  const characters = text.length
  
  return `${lines.length} lines, ${words.length} words, ${characters} characters`
}

const handleImageError = (event: Event) => {
  const img = event.target as HTMLImageElement
  img.src = '/music-note.svg'
}

const uploadCover = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'image/*'
  input.onchange = (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const imageUrl = e.target?.result as string
        updateAlbumCover(imageUrl)
      }
      reader.readAsDataURL(file)
    }
  }
  input.click()
}

const generateCover = async () => {
  if (isGeneratingCover.value) return
  
  isGeneratingCover.value = true
  
  try {
    const prompt = createCoverPrompt()
    const response = await fetch('/api/ai/generate-image', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt,
        size: '512x512',
        style: 'album_cover'
      })
    })
    
    if (!response.ok) {
      throw new Error('Failed to generate cover image')
    }
    
    const data = await response.json()
    if (data.imageUrl) {
      updateAlbumCover(data.imageUrl)
    } else {
      throw new Error('No image URL received')
    }
  } catch (error) {
    console.error('Error generating cover:', error)
    // You could show a toast notification here
    alert('Failed to generate cover image. Please try again or upload an image instead.')
  } finally {
    isGeneratingCover.value = false
  }
}

const createCoverPrompt = () => {
  const songName = audioStore.songStructure.name
  const artist = (audioStore.songStructure as any).artist || 'Unknown Artist'
  const key = audioStore.songStructure.key
  const tempo = audioStore.songStructure.tempo
  const lyrics = (audioStore.songStructure as any).lyrics || ''
  
  // Extract genre/mood from lyrics or use default
  const genre = extractGenreFromLyrics(lyrics) || 'modern'
  
  return `Create an album cover for a song called "${songName}" by ${artist}. 
    The song is in the key of ${key} with a tempo of ${tempo} BPM. 
    Style: ${genre} music album cover, professional, artistic, high quality, 
    suitable for digital music platforms. No text overlays.`
}

const extractGenreFromLyrics = (lyrics: string): string | null => {
  const lyricsLower = lyrics.toLowerCase()
  
  // Simple genre detection based on common words/themes
  if (lyricsLower.includes('rock') || lyricsLower.includes('guitar') || lyricsLower.includes('metal')) {
    return 'rock'
  } else if (lyricsLower.includes('love') || lyricsLower.includes('heart') || lyricsLower.includes('romance')) {
    return 'romantic'
  } else if (lyricsLower.includes('dance') || lyricsLower.includes('party') || lyricsLower.includes('beat')) {
    return 'electronic dance'
  } else if (lyricsLower.includes('country') || lyricsLower.includes('home') || lyricsLower.includes('family')) {
    return 'country'
  } else if (lyricsLower.includes('jazz') || lyricsLower.includes('smooth') || lyricsLower.includes('swing')) {
    return 'jazz'
  }
  
  return null
}

const updateAlbumCover = (imageUrl: string) => {
  const updatedStructure = {
    ...audioStore.songStructure,
    albumCover: imageUrl,
    artist: (audioStore.songStructure as any).artist || 'Unknown Artist'
  }
  audioStore.loadSongStructure(updatedStructure)
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
  padding: 1rem;
}

.song-info {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  padding: 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.album-cover {
  position: relative;
  width: 120px;
  height: 120px;
  flex-shrink: 0;
  border-radius: 8px;
  overflow: hidden;
  background: var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
}

.cover-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform var(--transition-normal);
}

.cover-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-normal);
}

.cover-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  justify-content: center;
}

.cover-action-btn {
  background: rgba(255, 255, 255, 0.9);
  border: none;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  color: var(--text);
  backdrop-filter: blur(4px);
}

.cover-action-btn:hover:not(:disabled) {
  background: white;
  transform: scale(1.1);
}

.cover-action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.cover-action-btn:disabled .icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.album-cover:hover .cover-overlay {
  opacity: 1;
}

.album-cover:hover .cover-image {
  transform: scale(1.05);
}

.song-details {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.song-name {
  margin: 0 0 0.25rem 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text);
  line-height: 1.2;
}

.artist-name {
  margin: 0 0 1rem 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.json-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.25rem 0;
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
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-top: 0.5rem;
  overflow: hidden;
}

.json-structure-section {
  margin-bottom: 1rem;
}

.lyrics-section {
  margin-bottom: 1rem;
}

.lyrics-editor-container {
  position: relative;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: 6px;
  margin-top: 0.5rem;
  overflow: hidden;
}

.lyrics-editor {
  min-height: 150px;
  max-height: 300px;
  padding: 1rem;
  background: var(--background);
  border: none;
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  font-size: 0.875rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  overflow-y: auto;
}

.lyrics-editor::placeholder {
  color: var(--text-secondary);
  font-style: italic;
}

.lyrics-info {
  padding: 0.5rem 1rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.lyrics-info .info-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.section-header:hover {
  background: var(--border);
}

.section-header h4 {
  margin: 0;
  font-size: 0.875rem;
  color: var(--text);
  font-weight: 600;
}

.collapse-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  transition: all var(--transition-normal);
}

.collapse-btn:hover {
  background: var(--border);
  color: var(--text);
}

.collapse-btn.expanded {
  transform: rotate(180deg);
}

.json-editor {
  flex: 1;
  min-height: 200px;
  max-height: 400px;
  padding: 1rem;
  background: var(--background);
  border: none;
  color: var(--text);
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8125rem;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  white-space: pre;
  overflow-wrap: normal;
  overflow: auto;
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
  .song-info {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  
  .album-cover {
    width: 100px;
    height: 100px;
  }
  
  .song-details {
    align-items: center;
    width: 100%;
  }
  
  .json-stats {
    grid-template-columns: 1fr;
    gap: 0.5rem;
    width: 100%;
  }
  
  .lyrics-editor {
    font-size: 0.8125rem;
    min-height: 120px;
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
