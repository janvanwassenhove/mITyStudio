<template>
  <div v-if="show" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>
          <Music :size="20" class="header-icon" />
          {{ $t('generateSong.title') }}
        </h2>
        <button @click="$emit('close')" class="close-btn">
          <X :size="20" />
        </button>
      </div>
      
      <div class="modal-body">
        <div class="form-group">
          <label for="songIdea" class="section-label">
            <PenTool :size="16" class="section-icon" />
            {{ $t('generateSong.songIdea') }}
          </label>
          <textarea
            id="songIdea"
            v-model="songIdea"
            :placeholder="$t('generateSong.songIdeaPlaceholder')"
            class="input textarea"
            rows="3"
          ></textarea>
        </div>
        
        <div class="form-group">
          <label class="section-label">
            <Mic :size="16" class="section-icon" />
            {{ $t('generateSong.lyricsOptions') }}
          </label>
          
          <!-- Instrumental Toggle - Always Visible -->
          <div class="instrumental-toggle">
            <div class="toggle-container">
              <input
                type="checkbox"
                v-model="isInstrumental"
                class="toggle-checkbox"
                id="instrumental-toggle"
              />
              <label for="instrumental-toggle" class="toggle-switch">
                <span class="toggle-slider"></span>
              </label>
              <label for="instrumental-toggle" class="toggle-text">
                {{ $t('generateSong.instrumental') }} ({{ $t('generateSong.noLyrics') }})
              </label>
            </div>
          </div>
          
          <!-- Lyrics Tabs - Hidden when Instrumental is selected -->
          <div v-if="!isInstrumental" class="lyrics-section">
            <div class="lyrics-tabs">
              <button 
                type="button"
                class="lyrics-tab"
                :class="{ active: lyricsOption === 'automatically' }"
                @click="lyricsOption = 'automatically'"
              >
                {{ $t('generateSong.auto') }}
              </button>
              <button 
                type="button"
                class="lyrics-tab"
                :class="{ active: lyricsOption === 'own' }"
                @click="lyricsOption = 'own'"
              >
                {{ $t('generateSong.writeLyrics') }}
              </button>
            </div>
            
            <div v-if="lyricsOption === 'own'" class="lyrics-content">
              <textarea
                v-model="customLyrics"
                :placeholder="$t('generateSong.addYourOwnLyrics')"
                class="lyrics-textarea"
                rows="8"
              ></textarea>
            </div>
          </div>
        </div>
        
        <div class="form-group">
          <label for="musicalStyle" class="section-label">
            <Palette :size="16" class="section-icon" />
            {{ $t('generateSong.musicalStyle') }} ({{ $t('common.optional') }})
          </label>
          <div class="styles-grid">
            <button 
              v-for="style in allStyles" 
              :key="style.value"
              type="button"
              class="style-tag"
              :class="{ selected: selectedStyles.includes(style.value), custom: style.isCustom }"
              @click="toggleStyle(style.value)"
            >
              <component :is="style.icon" :size="14" v-if="style.icon" />
              {{ style.label }}
            </button>
          </div>
          <div class="custom-style-input">
            <input
              v-model="customStyle"
              type="text"
              :placeholder="$t('generateSong.customStyle')"
              class="input"
              @keyup.enter="addCustomStyle"
            />
            <button 
              type="button" 
              class="add-style-btn"
              @click="addCustomStyle"
              :disabled="!customStyle.trim()"
            >
              {{ $t('generateSong.addCustomStyle') }}
            </button>
          </div>
        </div>
        
        <div class="form-group">
          <div class="collapsible-header" @click="showAdvanced = !showAdvanced">
            <span class="advanced-title">
              <Settings :size="16" class="section-icon" />
              {{ $t('generateSong.advancedOptions') }}
            </span>
            <ChevronDown 
              :size="16" 
              class="chevron" 
              :class="{ 'rotate-180': showAdvanced }"
            />
          </div>
          <div v-if="showAdvanced" class="advanced-options">
            <div class="form-group">
              <label for="duration" class="section-label">
                <Clock :size="14" class="section-icon" />
                {{ $t('generateSong.duration') }} ({{ $t('common.optional') }})
              </label>
              <select v-model="duration" id="duration" class="input select">
                <option value="">{{ $t('generateSong.selectDuration') }}</option>
                <option value="short">{{ $t('generateSong.shortSong') }} (2-3 {{ $t('common.minutes') }})</option>
                <option value="medium">{{ $t('generateSong.mediumSong') }} (3-4 {{ $t('common.minutes') }})</option>
                <option value="long">{{ $t('generateSong.longSong') }} (4-6 {{ $t('common.minutes') }})</option>
              </select>
            </div>
            
            <div class="form-group">
              <label for="songKey" class="section-label">
                <Music2 :size="14" class="section-icon" />
                {{ $t('generateSong.key') }} ({{ $t('common.optional') }})
              </label>
              <select v-model="songKey" id="songKey" class="input select">
                <option value="">{{ $t('generateSong.selectKey') }}</option>
                <option value="C">C Major</option>
                <option value="Cm">C Minor</option>
                <option value="G">G Major</option>
                <option value="Gm">G Minor</option>
                <option value="D">D Major</option>
                <option value="Dm">D Minor</option>
                <option value="A">A Major</option>
                <option value="Am">A Minor</option>
                <option value="E">E Major</option>
                <option value="Em">E Minor</option>
                <option value="B">B Major</option>
                <option value="Bm">B Minor</option>
                <option value="F#">F# Major</option>
                <option value="F#m">F# Minor</option>
                <option value="F">F Major</option>
                <option value="Fm">F Minor</option>
                <option value="Bb">Bb Major</option>
                <option value="Bbm">Bb Minor</option>
                <option value="Eb">Eb Major</option>
                <option value="Ebm">Eb Minor</option>
                <option value="Ab">Ab Major</option>
                <option value="Abm">Ab Minor</option>
                <option value="Db">Db Major</option>
                <option value="Dbm">Db Minor</option>
              </select>
            </div>
            
            <div class="form-group">
              <label class="section-label">
                <Bot :size="14" class="section-icon" />
                {{ $t('generateSong.aiProvider') }} & {{ $t('generateSong.model') }}
              </label>
              
              <!-- Provider and Model Selection Row -->
              <div class="provider-model-row">
                <select v-model="selectedProvider" class="provider-select">
                  <option v-for="provider in providers" :key="provider" :value="provider">
                    {{ provider }}
                  </option>
                </select>
                <select v-model="selectedModel" class="model-select">
                  <option v-for="model in availableModels" :key="model" :value="model">
                    {{ model }}
                  </option>
                </select>
                <button class="get-api-key-btn" @click="openApiKeyLink" :title="$t('generateSong.getApiKey')">
                  <Key :size="16" />
                </button>
              </div>
              
              <!-- API Key Status -->
              <div class="api-key-status-container">
                <span class="api-key-status" :class="{ set: apiKeySet, checking: isCheckingApiKey }">
                  <span v-if="isCheckingApiKey">
                    <span class="api-key-spinner">⟳</span>
                    <span class="api-key-label">{{ apiKeyLabel }}</span>
                    <span class="api-key-checking">Checking...</span>
                  </span>
                  <span v-else-if="apiKeySet">
                    <span class="api-key-check">✔</span>
                    <span class="api-key-label">{{ apiKeyLabel }}</span>
                    <span class="api-key-set">Set via environment variable</span>
                  </span>
                  <span v-else>
                    <span class="api-key-label">{{ apiKeyLabel }}</span>
                    <span class="api-key-not-set">Not set</span>
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="modal-footer">
        <button @click="$emit('close')" class="btn btn-ghost">
          {{ $t('common.cancel') }}
        </button>
        <button @click="generateSong" class="btn btn-primary" :disabled="isGenerating">
          <Loader2 v-if="isGenerating" :size="16" class="animate-spin" />
          <Music v-else :size="16" />
          {{ isGenerating ? $t('generateSong.generating') : $t('generateSong.generate') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, Music, Loader2, ChevronDown, Mic, Radio, Guitar, Piano, Drum, Zap, Disc, Heart, Volume2, Headphones, Star, Key, PenTool, Palette, Settings, Clock, Music2, Bot } from 'lucide-vue-next'
import { useAIStore } from '../stores/aiStore'
import { checkApiKeyStatus } from '../utils/api'

interface Props {
  show: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const aiStore = useAIStore()

const songIdea = ref('')
const lyricsOption = ref('automatically')
const customLyrics = ref('')
const isInstrumental = ref(false)
const selectedStyles = ref<string[]>([])
const customStyle = ref('')
const isGenerating = ref(false)
const showAdvanced = ref(false)
const duration = ref('')
const songKey = ref('')

// API key status checking
const apiKeySet = ref(false)
const isCheckingApiKey = ref(false)

// Providers and models - sync with AI store
const providers = ['Anthropic', 'OpenAI', 'Google', 'Mistral', 'xAI']

// Model display names mapping
const modelDisplayNames: Record<string, string> = {
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku',
  'claude-3-opus-20240229': 'Claude 3 Opus',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'gpt-4-turbo': 'GPT-4 Turbo',
  'gemini-1.5-pro-latest': 'Gemini 1.5 Pro',
  'gemini-1.5-flash-latest': 'Gemini 1.5 Flash',
  'mistral-large-latest': 'Mistral Large',
  'mistral-small-latest': 'Mistral Small',
  'grok-beta': 'Grok Beta'
}

// Reverse mapping for setting store values
const modelStoreValues: Record<string, string> = Object.fromEntries(
  Object.entries(modelDisplayNames).map(([store, display]) => [display, store])
)

// Get models for each provider using store values
const getModelsForProvider = (provider: string): string[] => {
  const storeProvider = provider.toLowerCase()
  const storeProviders = aiStore.providers || []
  const providerData = storeProviders.find(p => p.id === storeProvider)
  return providerData?.models || []
}

// Use AI store for provider/model selection
const selectedProvider = computed({
  get: () => {
    // Convert lowercase store value to proper display name
    const provider = aiStore.selectedProvider
    const providerMap: Record<string, string> = {
      'anthropic': 'Anthropic',
      'openai': 'OpenAI',
      'google': 'Google',
      'mistral': 'Mistral',
      'xai': 'xAI'
    }
    return providerMap[provider] || provider
  },
  set: (value) => {
    aiStore.setProvider(value.toLowerCase())
  }
})

const selectedModel = computed({
  get: () => {
    // Convert store value to display name
    const storeValue = aiStore.selectedModel
    const displayValue = modelDisplayNames[storeValue] || storeValue
    return displayValue
  },
  set: (displayValue) => {
    // Convert display name to store value
    const storeValue = modelStoreValues[displayValue] || displayValue
    aiStore.setModel(storeValue)
  }
})

// Get available models for currently selected provider
const availableModels = computed(() => {
  const models = getModelsForProvider(selectedProvider.value)
  return models.map(model => modelDisplayNames[model] || model)
})

// API key checking functionality
const apiKeyLabel = computed(() => `${selectedProvider.value} API Key:`)

const apiKeyLink = computed(() => {
  if (selectedProvider.value === 'Anthropic') {
    return 'https://console.anthropic.com/account/keys'
  } else if (selectedProvider.value === 'OpenAI') {
    return 'https://platform.openai.com/api-keys'
  } else if (selectedProvider.value === 'Google') {
    return 'https://aistudio.google.com/app/apikey'
  } else if (selectedProvider.value === 'Mistral') {
    return 'https://console.mistral.ai/api-keys'
  } else if (selectedProvider.value === 'xAI') {
    return 'https://console.x.ai/api-keys'
  }
  return '#'
})

const openApiKeyLink = () => {
  window.open(apiKeyLink.value, '_blank')
}

const checkApiKeyStatusForProvider = async (provider: string) => {
  isCheckingApiKey.value = true
  try {
    const data = await checkApiKeyStatus(provider.toLowerCase())
    apiKeySet.value = data.api_key_set
  } catch (error) {
    console.error('Error checking API key status:', error)
    apiKeySet.value = false
  } finally {
    isCheckingApiKey.value = false
  }
}

// Watch for provider changes to re-check API key status
watch(() => selectedProvider.value, (newProvider) => {
  checkApiKeyStatusForProvider(newProvider)
}, { immediate: true })

// Available musical styles
const musicalStyles = [
  { value: 'pop', label: 'Pop', icon: Star },
  { value: 'rock', label: 'Rock', icon: Guitar },
  { value: 'hip-hop', label: 'Hip-Hop', icon: Mic },
  { value: 'r&b', label: 'R&B', icon: Heart },
  { value: 'country', label: 'Country', icon: Guitar },
  { value: 'folk', label: 'Folk', icon: Guitar },
  { value: 'blues', label: 'Blues', icon: Guitar },
  { value: 'jazz', label: 'Jazz', icon: Piano },
  { value: 'classical', label: 'Classical', icon: Piano },
  { value: 'electronic', label: 'Electronic', icon: Zap },
  { value: 'edm', label: 'EDM', icon: Zap },
  { value: 'house', label: 'House', icon: Disc },
  { value: 'techno', label: 'Techno', icon: Disc },
  { value: 'trance', label: 'Trance', icon: Radio },
  { value: 'afroswing', label: 'Afroswing', icon: Music },
  { value: 'dancehall', label: 'Dancehall', icon: Volume2 },
  { value: 'reggae', label: 'Reggae', icon: Music },
  { value: 'soul', label: 'Soul', icon: Heart },
  { value: 'funk', label: 'Funk', icon: Music },
  { value: 'disco', label: 'Disco', icon: Disc },
  { value: 'punk', label: 'Punk', icon: Guitar },
  { value: 'metal', label: 'Metal', icon: Guitar },
  { value: 'alternative', label: 'Alternative', icon: Guitar },
  { value: 'indie', label: 'Indie', icon: Headphones },
  { value: 'grunge', label: 'Grunge', icon: Guitar },
  { value: 'progressive', label: 'Progressive', icon: Music },
  { value: 'fusion', label: 'Fusion', icon: Music },
  { value: 'experimental', label: 'Experimental', icon: Music },
  { value: 'minimalist', label: 'Minimalist', icon: Music },
  { value: 'cinematic', label: 'Cinematic', icon: Music },
  { value: 'opera', label: 'Opera', icon: Music },
  { value: 'musical-theatre', label: 'Musical Theatre', icon: Music },
  { value: 'trap', label: 'Trap', icon: Drum },
  { value: 'lo-fi', label: 'Lo-Fi', icon: Headphones },
  { value: 'synthwave', label: 'Synthwave', icon: Zap },
  { value: 'vaporwave', label: 'Vaporwave', icon: Headphones },
  { value: 'celtic', label: 'Celtic', icon: Music },
  { value: 'latin', label: 'Latin', icon: Music },
  { value: 'orchestral', label: 'Orchestral', icon: Piano }
]

// Combine predefined styles with custom styles
const allStyles = computed(() => {
  const predefinedStyles = musicalStyles.map(style => ({
    value: style.value,
    label: style.label,
    icon: style.icon,
    isCustom: false
  }))
  
  const customStyles = selectedStyles.value
    .filter(style => !musicalStyles.some(ms => ms.value === style))
    .map(style => ({
      value: style,
      label: style,
      icon: Music, // Default icon for custom styles
      isCustom: true
    }))
  
  return [...predefinedStyles, ...customStyles]
})

const handleOverlayClick = () => {
  emit('close')
}

const toggleStyle = (style: string) => {
  const index = selectedStyles.value.indexOf(style)
  if (index > -1) {
    selectedStyles.value.splice(index, 1)
  } else {
    selectedStyles.value.push(style)
  }
}

const addCustomStyle = () => {
  if (customStyle.value.trim() && !selectedStyles.value.includes(customStyle.value.trim())) {
    selectedStyles.value.push(customStyle.value.trim())
    customStyle.value = ''
  }
}

const generateSong = async () => {
  if (!songIdea.value.trim()) {
    alert(t('generateSong.pleaseEnterIdea'))
    return
  }
  
  isGenerating.value = true
  
  try {
    // AI provider and model are already set through computed properties
    const prompt = buildSongPrompt()
    
    const response = await aiStore.sendMessage(prompt)
    
    console.log('Generated Song Structure:', response)
    
    // Here you would parse the response and update the audio store
    // For now, just show the response
    alert(t('generateSong.success'))
    
  } catch (error) {
    console.error('Error generating song:', error)
    alert(t('generateSong.error'))
  } finally {
    isGenerating.value = false
    emit('close')
  }
}

const buildSongPrompt = (): string => {
  let prompt = `Create a song structure based on this idea: "${songIdea.value}"`
  
  if (selectedStyles.value.length > 0) {
    prompt += ` in ${selectedStyles.value.join(', ')} style${selectedStyles.value.length > 1 ? 's' : ''}`
  }
  
  if (duration.value) {
    const durationMap = {
      'short': '2-3 minutes',
      'medium': '3-4 minutes', 
      'long': '4-6 minutes'
    }
    prompt += ` with a ${durationMap[duration.value as keyof typeof durationMap]} duration`
  }
  
  if (songKey.value) {
    prompt += ` in the key of ${songKey.value}`
  }
  
  if (isInstrumental.value) {
    prompt += '. This should be an instrumental piece with no lyrics.'
  } else {
    switch (lyricsOption.value) {
      case 'automatically':
        prompt += '. Generate catchy, appropriate lyrics that fit the theme and style.'
        break
      case 'own':
        if (customLyrics.value.trim()) {
          prompt += `. Use these custom lyrics: "${customLyrics.value}"`
        } else {
          prompt += '. Create the song structure but leave space for custom lyrics to be added later.'
        }
        break
    }
  }
  
  prompt += `
  
Please provide a complete song structure in JSON format with the following structure:
{
  "name": "Song Title",
  "tempo": 120,
  "timeSignature": [4, 4],
  "key": "${songKey.value || 'C'}",
  "sections": [
    {
      "id": "intro",
      "name": "Intro",
      "type": "intro",
      "duration": 8,
      "chords": ["C", "Am", "F", "G"],
      "lyrics": "Optional lyrics here",
      "instruments": ["piano", "strings"]
    }
  ],
  "structure": ["intro", "verse1", "chorus", "verse2", "chorus", "bridge", "chorus", "outro"]
}

Make sure to include appropriate chords, suggested instruments, and if lyrics are requested, include them for each section.`
  
  return prompt
}
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
  max-width: 600px;
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

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: var(--text-primary);
}

.section-label {
  display: flex !important;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem !important;
  font-weight: 600 !important;
  color: var(--text-primary) !important;
  font-size: 0.95rem;
}

.section-icon {
  color: var(--primary);
  flex-shrink: 0;
}

.header-icon {
  color: var(--primary);
  margin-right: 0.5rem;
}

.advanced-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.input {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  transition: all var(--transition-normal);
  font-family: inherit;
}

.input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-alpha);
}

.textarea {
  resize: vertical;
  min-height: 80px;
}

.select {
  cursor: pointer;
}

.styles-section {
  margin-bottom: 1rem;
}

.styles-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
  max-height: 200px;
  overflow-y: auto;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-elevated);
}

.style-tag {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 0.4rem 0.8rem;
  border-radius: 16px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all var(--transition-normal);
  user-select: none;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  white-space: nowrap;
  font-weight: 500;
}

.style-tag:hover {
  border-color: var(--primary);
  background: var(--surface-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.style-tag.selected {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 12px var(--primary-alpha);
}

.style-tag.selected:hover {
  background: var(--primary-hover);
}

.style-tag.custom {
  background: var(--surface-elevated);
  border-style: dashed;
}

.style-tag.custom.selected {
  background: var(--primary);
  border-style: solid;
}

.lyrics-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.lyrics-tab {
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  flex: 1;
}

.lyrics-tab:hover {
  background: var(--surface-hover);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.lyrics-tab.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px var(--primary-alpha);
}

.lyrics-content {
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-top: 0.5rem;
}

.lyrics-textarea {
  width: 100%;
  min-height: 150px;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 0.875rem;
  line-height: 1.6;
  resize: vertical;
  transition: all var(--transition-normal);
  font-family: inherit;
}

.lyrics-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-alpha);
}

.lyrics-textarea::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.instrumental-toggle {
  margin-bottom: 1rem;
  padding: 1rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.toggle-container {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.toggle-checkbox {
  display: none;
}

.toggle-switch {
  position: relative;
  width: 50px;
  height: 26px;
  display: inline-block;
  cursor: pointer;
  flex-shrink: 0;
}

.toggle-slider {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--surface);
  border: 2px solid var(--border);
  border-radius: 13px;
  transition: all 0.3s ease;
  cursor: pointer;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  height: 18px;
  width: 18px;
  left: 2px;
  bottom: 2px;
  background: var(--text-secondary);
  border-radius: 50%;
  transition: all 0.3s ease;
}

.toggle-checkbox:checked + .toggle-switch .toggle-slider {
  background: var(--primary);
  border-color: var(--primary);
}

.toggle-checkbox:checked + .toggle-switch .toggle-slider::before {
  transform: translateX(24px);
  background: white;
}

.toggle-switch:hover .toggle-slider {
  border-color: var(--border-hover);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.toggle-text {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-primary);
  cursor: pointer;
  user-select: none;
  flex: 1;
}

.lyrics-section {
  animation: slideDown 0.3s ease-out;
}

.custom-style-input {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.custom-style-input .input {
  flex: 1;
}

.add-style-btn {
  background: var(--primary);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  transition: background-color var(--transition-normal);
}

.add-style-btn:hover {
  background: var(--primary-hover);
}

.collapsible-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 0.75rem 0;
  font-weight: 500;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}

.chevron {
  transition: transform var(--transition-normal);
}

.rotate-180 {
  transform: rotate(180deg);
}

.advanced-options {
  padding-top: 1rem;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.api-key-status-container {
  margin-top: 0.5rem;
}

.provider-model-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.provider-select,
.model-select {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  color: var(--text-primary);
  cursor: pointer;
  transition: all var(--transition-normal);
  font-family: inherit;
  min-width: 120px;
}

.provider-select:focus,
.model-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px var(--primary-alpha);
}

.provider-select:hover,
.model-select:hover {
  border-color: var(--border-hover);
  background: var(--surface-hover);
}

.provider-select {
  flex: 1;
}

.model-select {
  flex: 1.5;
}

.get-api-key-btn {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-normal);
  flex-shrink: 0;
  min-width: 40px;
  border-radius: 6px;
}

.get-api-key-btn:hover {
  color: var(--primary-hover);
  background: var(--primary-alpha);
}

.api-key-status {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
}

.api-key-status.set {
  background: rgba(34, 197, 94, 0.1);
  border-color: rgba(34, 197, 94, 0.3);
  color: rgb(34, 197, 94);
}

.api-key-status.checking {
  background: rgba(59, 130, 246, 0.1);
  border-color: rgba(59, 130, 246, 0.3);
  color: rgb(59, 130, 246);
}

.api-key-spinner {
  animation: spin 1s linear infinite;
  display: inline-block;
}

.api-key-check {
  color: rgb(34, 197, 94);
  font-weight: bold;
}

.api-key-label {
  font-weight: 500;
  color: var(--text-secondary);
}

.api-key-set {
  color: rgb(34, 197, 94);
  font-weight: 500;
}

.api-key-checking {
  color: rgb(59, 130, 246);
  font-style: italic;
}

.api-key-not-set {
  color: rgb(239, 68, 68);
  font-weight: 500;
}

.radio-group {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.radio-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 6px;
  transition: background-color var(--transition-normal);
}

.radio-option:hover {
  background: var(--surface-hover);
}

.radio-option input[type="radio"] {
  margin: 0;
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.radio-option span {
  font-size: 0.875rem;
  color: var(--text-primary);
}

.modal-footer {
  padding: 1.5rem;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  background: var(--surface-elevated);
}

.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  display: flex;
  align-items: center;
  gap: 0.5rem;
  text-decoration: none;
  font-family: inherit;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: var(--text-secondary);
  border: 2px solid var(--border);
}

.btn-ghost:hover:not(:disabled) {
  background: var(--surface-hover);
  color: var(--text-primary);
  border-color: var(--border-hover);
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px var(--primary-alpha);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (max-width: 768px) {
  .modal-content {
    width: 95%;
    margin: 1rem;
  }
  
  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }
  
  .provider-model-row {
    flex-direction: column;
  }
  
  .provider-select,
  .model-select {
    width: 100%;
    min-width: unset;
  }
  
  .radio-group {
    gap: 0.5rem;
  }
  
  .lyrics-tabs {
    flex-direction: row;
    gap: 0.25rem;
  }
  
  .lyrics-tab {
    padding: 0.6rem 1rem;
    font-size: 0.8rem;
  }
  
  .lyrics-content {
    padding: 0.75rem;
  }
  
  .lyrics-textarea {
    padding: 0.75rem;
    min-height: 120px;
  }
  
  .instrumental-toggle {
    padding: 0.75rem;
    margin-bottom: 0.75rem;
  }
  
  .toggle-container {
    gap: 0.75rem;
  }
  
  .toggle-switch {
    width: 44px;
    height: 24px;
  }
  
  .toggle-slider::before {
    height: 16px;
    width: 16px;
  }
  
  .toggle-checkbox:checked + .toggle-switch .toggle-slider::before {
    transform: translateX(20px);
  }
  
  .toggle-text {
    font-size: 0.8rem;
  }
  
  .modal-footer {
    flex-direction: column;
  }
  
  .btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
