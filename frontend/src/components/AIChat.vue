/**
 * AI Chat Component
 * 
 * Provides an intelligent chat interface for music composition assistance.
 * Features real-time AI responses, contextual suggestions, and integration
 * with the main audio production workflow.
 */
<template>
  <div class="ai-chat">
    <div class="chat-header">
      <div class="header-title">
        <Bot class="header-icon" />
        <h3>AI Assistant</h3>
        <span class="status-indicator" :class="{ 'online': isOnline }"></span>
      </div>
      
      <button 
        class="btn btn-ghost btn-sm"
        @click="clearChat"
        :disabled="messages.length === 0"
      >
        <Trash2 class="icon" />
        Clear
      </button>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="messages.length === 0" class="welcome-message">
        <div class="welcome-icon">
          <Bot class="icon" />
        </div>
        <h4>Welcome to mITyStudio AI!</h4>
        <p>I'm here to help you create amazing music. Ask me about:</p>
        <ul class="help-list">
          <li>🎵 Music composition and arrangement</li>
          <li>🎛️ Audio production techniques</li>
          <li>🎹 Instrument suggestions and tips</li>
          <li>🎚️ Mixing and effects guidance</li>
          <li>🎼 Music theory and chord progressions</li>
        </ul>
        <div class="quick-actions">
          <button 
            v-for="suggestion in quickSuggestions"
            :key="suggestion"
            class="suggestion-btn"
            @click="sendMessage(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
      </div>
      
      <div 
        v-for="message in messages" 
        :key="message.id"
        class="message"
        :class="{ 'user': message.type === 'user', 'ai': message.type === 'ai' }"
      >
        <div class="message-avatar">
          <User v-if="message.type === 'user'" class="avatar-icon" />
          <Bot v-else class="avatar-icon" />
        </div>
        
        <div class="message-content">
          <div class="message-text" v-html="formatMessage(message.content)"></div>
          
          <!-- Sample Controls - Enhanced UI for samples mentioned in AI responses -->
          <div v-if="extractedSamples(message.content).length > 0" class="sample-controls">
            <h5 class="sample-controls-title">
              <Music class="icon" />
              Referenced Samples
            </h5>
            <div class="sample-list">
              <div 
                v-for="sample in extractedSamples(message.content)" 
                :key="sample.id"
                class="sample-item"
              >
                <div class="sample-waveform" v-if="sample.waveform">
                  <canvas 
                    :ref="el => sampleWaveformCanvases[sample.id] = el as HTMLCanvasElement"
                    class="waveform-canvas"
                    :width="80"
                    :height="32"
                  ></canvas>
                </div>
                
                <div class="sample-info">
                  <div class="sample-name">{{ sample.name }}</div>
                  <div class="sample-meta">
                    <span class="duration">{{ formatDuration(sample.duration) }}</span>
                    <span v-if="sample.bpm" class="bpm">{{ sample.bpm }} BPM</span>
                    <span class="category">{{ sample.category }}</span>
                  </div>
                </div>
                
                <div class="sample-actions">
                  <button 
                    class="sample-action-btn play-btn"
                    @click="toggleSamplePlayback(sample)"
                    :disabled="playingSampleId && playingSampleId !== sample.id"
                  >
                    <Play v-if="playingSampleId !== sample.id" class="icon" />
                    <Pause v-else class="icon" />
                  </button>
                  
                  <button 
                    class="sample-action-btn add-btn"
                    @click="addSampleToTrack(sample)"
                    title="Add to new track"
                  >
                    <Plus class="icon" />
                  </button>
                </div>
              </div>
            </div>
          </div>
          
          <div class="message-time">{{ formatTime(message.timestamp) }}</div>
          
          <div v-if="message.actions" class="message-actions">
            <button 
              v-for="action in message.actions"
              :key="action.label"
              class="action-btn"
              @click="executeAction(action)"
            >
              <component :is="action.icon" class="icon" />
              {{ action.label }}
            </button>
          </div>
        </div>
      </div>
      
      <div v-if="isTyping" class="message ai typing">
        <div class="message-avatar">
          <Bot class="avatar-icon" />
        </div>
        <div class="message-content">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>

    <!-- Model Selection Bar (moved below messages, above input) -->
    <div class="model-selection-bar">
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
      <div class="model-select-row">
        <select v-model="selectedProvider" class="model-select">
          <option v-for="provider in providers" :key="provider" :value="provider">{{ provider }}</option>
        </select>
        <select v-model="selectedModel" class="model-select">
          <option v-for="model in availableModels" :key="model" :value="model">{{ model }}</option>
        </select>
        <button class="get-api-key-btn" @click="openApiKeyLink" :title="'Get API key'">
          <Key class="icon" />
        </button>
      </div>
    </div>
    
    <div class="chat-input">
      <div class="input-wrapper">
        <textarea
          v-model="currentMessage"
          @keydown="handleKeyDown"
          @input="adjustTextareaHeight"
          ref="messageInput"
          :placeholder="isListening ? 'Listening... Speak now!' : 'Ask me anything about music production...'"
          class="message-textarea"
          :class="{ 'listening': isListening }"
          rows="1"
          :disabled="isTyping"
        ></textarea>
        
        <div v-if="isListening" class="voice-indicator">
          <div class="voice-wave">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span class="voice-text">
            Listening... 
            <span class="voice-lang">
              {{ supportedLanguages.find(l => l.code === currentLanguage)?.flag }}
              {{ supportedLanguages.find(l => l.code === currentLanguage)?.name }}
            </span>
          </span>
        </div>
        
        <button 
          class="send-btn"
          @click="sendCurrentMessage"
          :disabled="!currentMessage.trim() || isTyping"
        >
          <Send class="icon" />
        </button>
      </div>
      
      <div class="input-actions">
        <button 
          class="action-btn-small"
          @click="attachFile"
          :class="{ 'uploading': isUploading }"
          :title="isUploading ? 'Uploading scores...' : 'Attach musical scores or tablatures'"
          :disabled="isUploading"
        >
          <Paperclip class="icon" :class="{ 'spinning': isUploading }" />
        </button>
        
        <div class="voice-input-group">
          <select 
            v-model="currentLanguage" 
            @change="setLanguage(currentLanguage)"
            class="language-select"
            :disabled="isListening"
            title="Select voice input language (Ctrl+L to cycle)"
          >
            <option 
              v-for="lang in supportedLanguages" 
              :key="lang.code" 
              :value="lang.code"
            >
              {{ lang.flag }} {{ lang.name }}
            </option>
          </select>
          
          <button 
            class="action-btn-small detect-btn"
            @click="detectLanguage"
            :disabled="isListening || isDetectingLanguage"
            title="Auto-detect language"
          >
            <span v-if="isDetectingLanguage" class="detect-spinner">⟳</span>
            <Settings v-else class="icon detect-icon" />
          </button>
          
          <button 
            class="action-btn-small mic-btn"
            @click="toggleVoiceInput"
            :class="{ 'active': isListening, 'recording': isListening }"
            :disabled="!speechSupported"
            :title="speechSupported ? (isListening ? 'Stop voice input (Ctrl+;)' : 'Voice input (Ctrl+;)') : 'Voice input not supported in this browser'"
          >
            <Mic class="icon" />
          </button>
        </div>
        
        <button 
          class="action-btn-small"
          @click="showSuggestions = !showSuggestions"
          :class="{ 'active': showSuggestions }"
          title="Quick suggestions"
        >
          <Lightbulb class="icon" />
        </button>
      </div>
      
      <div v-if="showSuggestions" class="suggestions-panel">
        <h5>Quick Suggestions:</h5>
        <div class="suggestions-grid">
          <button 
            v-for="suggestion in contextualSuggestions"
            :key="suggestion"
            class="suggestion-btn"
            @click="sendMessage(suggestion)"
          >
            {{ suggestion }}
          </button>
        </div>
      </div>
      
      <!-- Uploaded Scores Display -->
      <div v-if="uploadedScores.length > 0" class="uploaded-scores">
        <h5>📜 Uploaded Musical Scores</h5>
        <div class="score-items">
          <div 
            v-for="score in uploadedScores" 
            :key="score.file_id" 
            class="score-item"
            :class="{ 'error': score.status === 'error', 'success': score.status === 'success' }"
          >
            <div class="score-info">
              <span class="score-name">{{ score.filename }}</span>
              <span class="score-category">{{ score.category }}</span>
              <span class="score-status" :class="score.status">
                {{ score.status === 'success' ? '✓' : score.status === 'error' ? '✗' : '⏳' }}
              </span>
            </div>
            <div v-if="score.analysis && score.status === 'success'" class="score-details">
              <span v-if="score.analysis.estimated_key" class="detail">Key: {{ score.analysis.estimated_key }}</span>
              <span v-if="score.analysis.estimated_tempo" class="detail">{{ score.analysis.estimated_tempo }} BPM</span>
              <span v-if="score.analysis.difficulty_level" class="detail">{{ score.analysis.difficulty_level }}</span>
            </div>
            <button 
              class="remove-score-btn"
              @click="removeUploadedScore(score.file_id)"
              title="Remove score"
            >
              ×
            </button>
          </div>
        </div>
        <div class="scores-help">
          <small>The AI assistant will consider these scores in its responses</small>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { useAIStore } from '../stores/aiStore'
import { useSampleStore } from '../stores/sampleStore'
import { checkApiKeyStatus as apiCheckApiKeyStatus, getAllSampleInstruments } from '../utils/api'
import { ScoreService, type ScoreFile } from '../services/scoreService'
import { 
  Bot, User, Trash2, Send, Paperclip, Mic, Lightbulb, Key,
  Music, Play, Plus, Download, Upload, Settings, Volume2, Mic2, Pause, Square
} from 'lucide-vue-next'

interface ChatAction {
  label: string
  icon: any
  action: string
  params?: any
  data?: any
}

const audioStore = useAudioStore()
const aiStore = useAIStore()
const sampleStore = useSampleStore()

// State - Use AI store messages instead of local state
const currentMessage = ref('')
const isListening = ref(false)
const showSuggestions = ref(false)
const messagesContainer = ref<HTMLElement>()
const messageInput = ref<HTMLTextAreaElement>()
const currentLyricsJSON = ref<any>(null) // Store current lyrics JSON for Apply button

// Voice recognition state
const recognition = ref<any>(null) // Using any to avoid TypeScript issues with SpeechRecognition
const speechSupported = ref(false)
const currentLanguage = ref('en-US')
const supportedLanguages = ref([
  { code: 'en-US', name: 'English', flag: '🇺🇸' },
  { code: 'nl-NL', name: 'Dutch', flag: '🇳🇱' },
  { code: 'fr-FR', name: 'French', flag: '🇫🇷' },
  { code: 'de-DE', name: 'German', flag: '🇩🇪' },
  { code: 'it-IT', name: 'Italian', flag: '🇮🇹' }
])
const isDetectingLanguage = ref(false)
const detectedLanguage = ref('')

// Sample playback state
const playingSampleId = ref<string | null>(null)
const currentAudio = ref<HTMLAudioElement | null>(null)
const sampleWaveformCanvases = ref<Record<string, HTMLCanvasElement>>({})
const samplePlayProgress = ref<Record<string, number>>({})

// File upload state
const fileInput = ref<HTMLInputElement>()
const uploadedScores = ref<ScoreFile[]>([])
const isUploading = ref(false)

// Computed properties from AI store
const messages = computed(() => aiStore.messages.map(msg => ({
  id: msg.id,
  type: msg.role === 'user' ? 'user' : 'ai',
  content: msg.content,
  timestamp: msg.timestamp,
  actions: msg.actions
})))

const isTyping = computed(() => aiStore.isGenerating)
const isOnline = ref(true)

// Quick suggestions
const quickSuggestions = [
  "Help me create a chord progression",
  "What's a good drum pattern for house music?",
  "How do I make my bass sound fuller?",
  "Suggest some effects for vocals",
  "Generate full song lyrics with syllables and phonemes"
]

// Contextual suggestions based on current project
const contextualSuggestions = computed(() => {
  const suggestions = [...quickSuggestions]
  
  if (audioStore.songStructure.tracks.length > 0) {
    suggestions.push("How can I improve my current arrangement?")
    suggestions.push("What instruments should I add next?")
  }
  
  if (audioStore.songStructure.tempo) {
    suggestions.push(`Suggest a melody for ${audioStore.songStructure.tempo} BPM`)
  }
  
  return suggestions
})

// Providers and models - sync with AI store
const providers = ['Anthropic', 'OpenAI', 'Google', 'Mistral', 'xAI']

// Map store values to display names
const modelDisplayNames: Record<string, string> = {
  // Anthropic
  'claude-4-sonnet': 'Claude 4 Sonnet',
  'claude-3-7-sonnet': 'Claude 3.7 Sonnet',
  'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet (Oct 2024)',
  'claude-3-5-sonnet-20240620': 'Claude 3.5 Sonnet (Jun 2024)',
  'claude-3-5-haiku-20241022': 'Claude 3.5 Haiku (Oct 2024)',
  'claude-3-opus-20240229': 'Claude 3 Opus',
  'claude-3-sonnet-20240229': 'Claude 3 Sonnet',
  'claude-3-haiku-20240307': 'Claude 3 Haiku',
  'claude-2.1': 'Claude 2.1',
  'claude-2.0': 'Claude 2.0',
  'claude-instant-1.2': 'Claude Instant 1.2',
  // OpenAI - GPT-5 Family (Latest)
  'gpt-5': 'GPT-5 ⭐',
  'gpt-5-2025-08-07': 'GPT-5 (Aug 2025)',
  'gpt-5-chat-latest': 'GPT-5 Chat Latest',
  'gpt-5-mini': 'GPT-5 Mini',
  'gpt-5-mini-2025-08-07': 'GPT-5 Mini (Aug 2025)',
  'gpt-5-nano': 'GPT-5 Nano',
  'gpt-5-nano-2025-08-07': 'GPT-5 Nano (Aug 2025)',
  // OpenAI - o1 Family (Reasoning)
  'o1-pro': 'OpenAI o1-pro 🧠',
  'o1-pro-2025-03-19': 'OpenAI o1-pro (Mar 2025)',
  'o1': 'OpenAI o1',
  'o1-2024-12-17': 'OpenAI o1 (Dec 2024)',
  'o1-mini': 'OpenAI o1-mini',
  'o1-mini-2024-09-12': 'OpenAI o1-mini (Sep 2024)',
  // OpenAI - GPT-4.1 Family
  'gpt-4.1': 'GPT-4.1',
  'gpt-4.1-2025-04-14': 'GPT-4.1 (Apr 2025)',
  'gpt-4.1-mini': 'GPT-4.1 Mini',
  'gpt-4.1-mini-2025-04-14': 'GPT-4.1 Mini (Apr 2025)',
  'gpt-4.1-nano': 'GPT-4.1 Nano',
  'gpt-4.1-nano-2025-04-14': 'GPT-4.1 Nano (Apr 2025)',
  // OpenAI - GPT-4o Family
  'chatgpt-4o-latest': 'ChatGPT-4o Latest',
  'gpt-4o': 'GPT-4o',
  'gpt-4o-2024-11-20': 'GPT-4o (Nov 2024)',
  'gpt-4o-2024-08-06': 'GPT-4o (Aug 2024)',
  'gpt-4o-2024-05-13': 'GPT-4o (May 2024)',
  'gpt-4o-mini': 'GPT-4o Mini',
  'gpt-4o-mini-2024-07-18': 'GPT-4o Mini (Jul 2024)',
  // OpenAI - GPT-4 Family
  'gpt-4-turbo': 'GPT-4 Turbo',
  'gpt-4-turbo-2024-04-09': 'GPT-4 Turbo (Apr 2024)',
  'gpt-4-turbo-preview': 'GPT-4 Turbo Preview',
  'gpt-4-0125-preview': 'GPT-4 (Jan 2024)',
  'gpt-4-1106-preview': 'GPT-4 (Nov 2023)',
  'gpt-4': 'GPT-4',
  'gpt-4-0613': 'GPT-4 (Jun 2023)',
  // OpenAI - GPT-3.5 Family
  'gpt-3.5-turbo': 'GPT-3.5 Turbo',
  'gpt-3.5-turbo-0125': 'GPT-3.5 Turbo (Jan 2024)',
  'gpt-3.5-turbo-1106': 'GPT-3.5 Turbo (Nov 2023)',
  'gpt-3.5-turbo-16k': 'GPT-3.5 Turbo 16K',
  'gpt-3.5-turbo-instruct': 'GPT-3.5 Turbo Instruct',
  // Google
  'gemini-1.5-pro': 'Gemini 1.5 Pro',
  'gemini-1.5-pro-latest': 'Gemini 1.5 Pro (Latest)',
  'gemini-1.5-flash': 'Gemini 1.5 Flash',
  'gemini-1.5-flash-latest': 'Gemini 1.5 Flash (Latest)',
  'gemini-1.0-pro': 'Gemini 1.0 Pro',
  'gemini-1.0-pro-latest': 'Gemini 1.0 Pro (Latest)',
  'gemini-1.0-pro-vision': 'Gemini 1.0 Pro Vision',
  'gemini-pro': 'Gemini Pro',
  'gemini-pro-vision': 'Gemini Pro Vision',
  // Mistral
  'mistral-large-latest': 'Mistral Large (Latest)',
  'mistral-large-2407': 'Mistral Large (Jul 2024)',
  'mistral-large-2402': 'Mistral Large (Feb 2024)',
  'mistral-medium-latest': 'Mistral Medium (Latest)',
  'mistral-medium-2312': 'Mistral Medium (Dec 2023)',
  'mistral-small-latest': 'Mistral Small (Latest)',
  'mistral-small-2402': 'Mistral Small (Feb 2024)',
  'mistral-small-2312': 'Mistral Small (Dec 2023)',
  'mistral-tiny': 'Mistral Tiny',
  'mistral-7b-instruct': 'Mistral 7B Instruct',
  'mixtral-8x7b-instruct': 'Mixtral 8x7B Instruct',
  'mixtral-8x22b-instruct': 'Mixtral 8x22B Instruct',
  'open-mistral-7b': 'Open Mistral 7B',
  'open-mistral-8x7b': 'Open Mistral 8x7B',
  'open-mistral-8x22b': 'Open Mistral 8x22B',
  'open-mixtral-8x7b': 'Open Mixtral 8x7B',
  'open-mixtral-8x22b': 'Open Mixtral 8x22B',
  // xAI
  'grok-beta': 'Grok Beta',
  'grok-2-1212': 'Grok 2 (Dec 2024)',
  'grok-2-latest': 'Grok 2 (Latest)',
  'grok-2-public': 'Grok 2 (Public)',
  'grok-2-mini': 'Grok 2 Mini',
  'grok-vision-beta': 'Grok Vision Beta',
  'grok-1': 'Grok 1',
  'grok-1.5': 'Grok 1.5'
}

// Reverse mapping for display names to store values
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
    // Map store values to exact display names used in modelsByProvider
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

const availableModels = computed(() => {
  // Get store models for the selected provider and convert to display names
  const storeModels = getModelsForProvider(selectedProvider.value)
  const displayModels = storeModels.map(model => modelDisplayNames[model] || model)
  return displayModels
})

// Dynamically detect if API key is set for the selected provider
const apiKeySet = ref(false)
const isCheckingApiKey = ref(false)

// Function to check API key status from backend
const checkApiKeyStatus = async (provider: string) => {
  isCheckingApiKey.value = true
  try {
    const data = await apiCheckApiKeyStatus(provider)
    apiKeySet.value = data.api_key_set
  } catch (error) {
    console.error('Error checking API key status:', error)
    apiKeySet.value = false
  } finally {
    isCheckingApiKey.value = false
  }
}

// Watch for provider changes to re-check API key status
watch(() => aiStore.selectedProvider, (newProvider) => {
  checkApiKeyStatus(newProvider)
}, { immediate: true })

// Watch for available models changes to ensure model is selected
watch(() => availableModels.value, (newModels) => {
  // If models are available but no model is selected, select the first one
  if (newModels.length > 0 && !selectedModel.value) {
    selectedModel.value = newModels[0]
  }
  // If the currently selected model is not in the available models, select the first one
  else if (newModels.length > 0 && !newModels.includes(selectedModel.value)) {
    selectedModel.value = newModels[0]
  }
}, { immediate: true })

const apiKeyLabel = computed(() => `${aiStore.selectedProvider} API Key:`)

const apiKeyLink = computed(() => {
  if (aiStore.selectedProvider === 'anthropic') {
    return 'https://console.anthropic.com/account/keys'
  } else if (aiStore.selectedProvider === 'openai') {
    return 'https://platform.openai.com/api-keys'
  } else if (aiStore.selectedProvider === 'google') {
    return 'https://aistudio.google.com/app/apikey'
  } else if (aiStore.selectedProvider === 'mistral') {
    return 'https://console.mistral.ai/api-keys'
  } else if (aiStore.selectedProvider === 'xai') {
    return 'https://console.x.ai/api-keys'
  }
  return '#'
})

function openApiKeyLink() {
  window.open(apiKeyLink.value, '_blank')
}

// Add global toggle function for JSON blocks
const toggleJsonBlock = (elementId: string) => {
  const content = document.getElementById(elementId)
  const toggle = document.getElementById(`toggle-${elementId}`)
  
  if (content && toggle) {
    if (content.style.display === 'none') {
      content.style.display = 'block'
      toggle.textContent = '‹'
    } else {
      content.style.display = 'none'
      toggle.textContent = '›'
    }
  }
}

// Global JSON action handlers
const applySongStructureFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const songStructure = JSON.parse(jsonContent)
    applySongStructureChanges(songStructure)
  } catch (error) {
    console.error('Error applying song structure from JSON:', error)
    sendMessage('❌ Error applying song structure. Please check the JSON format.')
  }
}

const addTrackFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const trackData = JSON.parse(jsonContent)
    
    const trackId = audioStore.addTrack(trackData.name || `${trackData.instrument} Track`, trackData.instrument)
    if (trackId) {
      if (trackData.volume !== undefined || trackData.pan !== undefined || trackData.effects) {
        audioStore.updateTrack(trackId, {
          volume: trackData.volume || 0.8,
          pan: trackData.pan || 0,
          effects: trackData.effects || { reverb: 0, delay: 0, distortion: 0 }
        })
      }
      
      if (trackData.clips && Array.isArray(trackData.clips)) {
        for (const clip of trackData.clips) {
          audioStore.addClip(trackId, { ...clip, trackId: trackId })
        }
      }
      
      sendMessage(`✅ Added ${trackData.name || trackData.instrument} track with ${trackData.clips?.length || 0} clips!`)
    }
  } catch (error) {
    console.error('Error adding track from JSON:', error)
    sendMessage('❌ Error adding track. Please check the JSON format.')
  }
}

const addChordProgressionFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const chordData = JSON.parse(jsonContent)
    
    // Use dynamic instrument selection from AI suggestion or fallback to chord-capable instrument
    const suggestedInstrument = chordData.instrument || 'piano'
    const instrument = getAvailableInstrument(suggestedInstrument, 'piano')
    const trackName = chordData.name || 'Chord Progression'
    const trackId = audioStore.addTrack(trackName, instrument)
    
    if (trackId) {
      // Get instrument type for proper clip creation
      const { type: clipType } = getInstrumentTypeAndCategory(instrument)
      
      let chords: any[] = chordData.chords || chordData.pattern || []
      
      for (let i = 0; i < chords.length; i++) {
        const chord = chords[i]
        const duration = chord.duration || 4
        const startTime = chord.time || (i * duration)
        
        audioStore.addClip(trackId, {
          startTime: startTime,
          duration: duration,
          type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
          instrument: instrument,
          notes: [chord.chord || chord.name || 'C4'],
          volume: chordData.volume || 0.7,
          effects: chordData.effects || { reverb: 0.2, delay: 0, distortion: 0 }
        })
      }
      
      sendMessage(`🎹 Added chord progression with ${chords.length} chords using ${instrument}!`)
    }
  } catch (error) {
    console.error('Error adding chord progression from JSON:', error)
    sendMessage('❌ Error adding chord progression. Please check the JSON format.')
  }
}

const addDrumPatternFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const drumData = JSON.parse(jsonContent)
    
    // Use dynamic instrument selection for drums
    const instrument = getAvailableInstrument('drums', 'drums')
    const trackName = drumData.name || 'Drum Pattern'
    const trackId = audioStore.addTrack(trackName, instrument)
    
    if (trackId) {
      // Get instrument type for proper clip creation
      const { type: clipType } = getInstrumentTypeAndCategory(instrument)
      
      const barsCount = drumData.bars || 4
      const barDuration = drumData.barDuration || 4
      
      for (let bar = 0; bar < barsCount; bar++) {
        audioStore.addClip(trackId, {
          startTime: bar * barDuration,
          duration: barDuration,
          type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
          instrument: instrument,
          notes: ['C2'],
          volume: drumData.volume || 0.8,
          effects: drumData.effects || { reverb: 0.1, delay: 0, distortion: 0 }
        })
      }
      
      sendMessage(`🥁 Added drum pattern with ${barsCount} bars using ${instrument}!`)
    }
  } catch (error) {
    console.error('Error adding drum pattern from JSON:', error)
    sendMessage('❌ Error adding drum pattern. Please check the JSON format.')
  }
}

const addBassLineFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const bassData = JSON.parse(jsonContent)
    
    // Use dynamic instrument selection for bass
    const instrument = getAvailableInstrument('bass', 'bass')
    const trackName = bassData.name || 'Bass Line'
    const trackId = audioStore.addTrack(trackName, instrument)
    
    if (trackId) {
      // Get instrument type for proper clip creation
      const { type: clipType } = getInstrumentTypeAndCategory(instrument)
      
      const notes = bassData.notes || bassData.pattern || []
      const duration = bassData.duration || 16
      
      audioStore.addClip(trackId, {
        startTime: 0,
        duration: duration,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        notes: notes.length > 0 ? notes : ['C2'],
        volume: bassData.volume || 0.8,
        effects: bassData.effects || { reverb: 0, delay: 0, distortion: 0.1 }
      })
      
      sendMessage(`🎸 Added bass line using ${instrument}!`)
    }
  } catch (error) {
    console.error('Error adding bass line from JSON:', error)
    sendMessage('❌ Error adding bass line. Please check the JSON format.')
  }
}

const addMelodyFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const melodyData = JSON.parse(jsonContent)
    
    // Use dynamic instrument selection from AI suggestion or fallback to synth
    const suggestedInstrument = melodyData.instrument || 'synth'
    const instrument = getAvailableInstrument(suggestedInstrument, 'synth')
    const trackName = melodyData.name || 'Melody'
    const trackId = audioStore.addTrack(trackName, instrument)
    
    if (trackId) {
      // Get instrument type for proper clip creation
      const { type: clipType } = getInstrumentTypeAndCategory(instrument)
      
      const notes = melodyData.notes || melodyData.pattern || []
      const duration = melodyData.duration || 16
      
      audioStore.addClip(trackId, {
        startTime: 0,
        duration: duration,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        notes: notes.length > 0 ? notes : ['C4'],
        volume: melodyData.volume || 0.7,
        effects: melodyData.effects || { reverb: 0.3, delay: 0.1, distortion: 0 }
      })
      
      sendMessage(`🎼 Added melody track with ${getInstrumentIcon(instrument)} ${instrument} sound!`)
    }
  } catch (error) {
    console.error('Error adding melody from JSON:', error)
    sendMessage('❌ Error adding melody. Please check the JSON format.')
  }
}

const addLyricsFromJSONAction = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const lyricsData = JSON.parse(jsonContent)
    
    // Set currentLyricsJSON so we can use the merged addVocalTrackAction logic
    currentLyricsJSON.value = lyricsData
    
    // Call the merged action that creates vocal track AND applies to song structure
    addVocalTrackAction()
  } catch (error) {
    console.error('Error adding lyrics from JSON:', error)
    sendMessage('❌ Error adding lyrics. Please check the JSON format.')
  }
}

// Enhanced action functions for lyrics
const addVocalTrackFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const lyricsData = JSON.parse(jsonContent)
    
    console.log('Adding vocal track from JSON:', lyricsData)
    
    // Create or find vocals track
    let vocalsTrack = audioStore.songStructure.tracks.find(t => t.instrument === 'vocals')
    let trackId = vocalsTrack?.id

    if (!trackId) {
      // Create new vocals track
      trackId = audioStore.addTrack('Lyrics & Vocals', 'vocals')
      if (trackId) {
        audioStore.updateTrack(trackId, {
          volume: 0.8,
          pan: 0,
          effects: { 
            reverb: 0, 
            delay: 0, 
            distortion: 0, 
            pitchShift: 0, 
            chorus: 0, 
            filter: 0, 
            bitcrush: 0 
          }
        })
      }
    }

    if (trackId) {
      // Handle different JSON structures
      if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
        // Complete track with clips
        for (const clip of lyricsData.clips) {
          audioStore.addClip(trackId, {
            ...clip,
            trackId: trackId
          })
        }
        sendMessage(`🎤 Added vocal track with ${lyricsData.clips.length} clips! Ready to record your vocals.`)
      } else if (lyricsData.voices || lyricsData.type === 'lyrics') {
        // Single clip
        audioStore.addClip(trackId, {
          ...lyricsData,
          trackId: trackId
        })
        const voiceCount = lyricsData.voices?.length || 1
        sendMessage(`🎤 Added vocal track with ${voiceCount} voice part(s)! Your melody awaits lyrics.`)
      }
    }
  } catch (error) {
    console.error('Error adding vocal track from JSON:', error)
    sendMessage('❌ Error adding vocal track. Please check the JSON format.')
  }
}

const addLyricsToSongStructure = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const lyricsData = JSON.parse(jsonContent)
    
    console.log('Adding lyrics to song structure:', lyricsData)
    
    // Extract lyrics text from the JSON structure
    let extractedLyricsText = ''
    
    // Handle different structures
    if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
      for (const clip of lyricsData.clips) {
        if (clip.voices) {
          for (const voice of clip.voices) {
            if (voice.lyrics) {
              for (const lyric of voice.lyrics) {
                if (lyric.text) {
                  extractedLyricsText += lyric.text + ' '
                }
              }
              extractedLyricsText += '\n'
            }
          }
        }
      }
    } else if (lyricsData.voices) {
      for (const voice of lyricsData.voices) {
        if (voice.lyrics) {
          for (const lyric of voice.lyrics) {
            if (lyric.text) {
              extractedLyricsText += lyric.text + ' '
            }
          }
          extractedLyricsText += '\n'
        }
      }
    }
    
    // Update song structure with lyrics
    if (extractedLyricsText.trim()) {
      const currentLyrics = audioStore.songStructure.lyrics || ''
      const updatedLyrics = currentLyrics ? currentLyrics + '\n\n' + extractedLyricsText.trim() : extractedLyricsText.trim()
      
      audioStore.loadSongStructure({
        ...audioStore.songStructure,
        lyrics: updatedLyrics,
        updatedAt: new Date().toISOString()
      })
      
      const lyricsWordCount = extractedLyricsText.trim().split(/\s+/).length
      sendMessage(`📝 Added ${lyricsWordCount} words to the lyrics section! Check the Song tab to see your lyrics.`)
    } else {
      sendMessage('❌ No lyrics text found in the JSON structure.')
    }
    
  } catch (error) {
    console.error('Error adding lyrics to song structure:', error)
    sendMessage('❌ Error adding lyrics to song structure. Please check the JSON format.')
  }
}

const applyEffectsFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const effectsData = JSON.parse(jsonContent)
    
    if (effectsData.track_id && effectsData.effects) {
      audioStore.updateTrack(effectsData.track_id, { effects: effectsData.effects })
      sendMessage(`🎛️ Applied effects to track ${effectsData.track_id}!`)
    } else if (effectsData.effects && audioStore.songStructure.tracks.length > 0) {
      const lastTrack = audioStore.songStructure.tracks[audioStore.songStructure.tracks.length - 1]
      audioStore.updateTrack(lastTrack.id, { effects: effectsData.effects })
      sendMessage(`🎛️ Applied effects configuration to ${lastTrack.name}!`)
    }
  } catch (error) {
    console.error('Error applying effects from JSON:', error)
    sendMessage('❌ Error applying effects. Please check the JSON format.')
  }
}

const applyMixFromJSON = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const mixData = JSON.parse(jsonContent)
    
    if (mixData.tracks && Array.isArray(mixData.tracks)) {
      for (const trackMix of mixData.tracks) {
        if (trackMix.id && (trackMix.volume !== undefined || trackMix.pan !== undefined)) {
          const updateData: any = {}
          if (trackMix.volume !== undefined) updateData.volume = trackMix.volume
          if (trackMix.pan !== undefined) updateData.pan = trackMix.pan
          if (trackMix.effects) updateData.effects = trackMix.effects
          
          audioStore.updateTrack(trackMix.id, updateData)
        }
      }
      sendMessage(`🎚️ Applied mix settings to ${mixData.tracks.length} tracks!`)
    } else if (mixData.volume !== undefined || mixData.pan !== undefined) {
      const lastTrack = audioStore.songStructure.tracks[audioStore.songStructure.tracks.length - 1]
      if (lastTrack) {
        const updateData: any = {}
        if (mixData.volume !== undefined) updateData.volume = mixData.volume
        if (mixData.pan !== undefined) updateData.pan = mixData.pan
        if (mixData.effects) updateData.effects = mixData.effects
        
        audioStore.updateTrack(lastTrack.id, updateData)
        sendMessage(`🎚️ Applied mix settings to ${lastTrack.name}!`)
      }
    }
  } catch (error) {
    console.error('Error applying mix from JSON:', error)
    sendMessage('❌ Error applying mix settings. Please check the JSON format.')
  }
}

// Add vocal track action from footer buttons
const addVocalTrackAction = () => {
  if (!currentLyricsJSON.value) {
    aiStore.addMessage({
      role: 'assistant',
      content: '❌ No lyrics to apply. Please generate lyrics first.',
      id: Date.now().toString()
    })
    return
  }
  
  try {
    const jsonData = currentLyricsJSON.value
    
    // Create a new vocal track using the proper addTrack method
    const trackId = audioStore.addTrack('Vocals', 'vocals', undefined, 'vocal')
    
    if (!trackId) {
      throw new Error('Failed to create vocal track')
    }
    
    // Process lyrics data and create clips
    if (jsonData.clips && Array.isArray(jsonData.clips)) {
      // Handle multiple clips structure
      jsonData.clips.forEach((clipData: any, index: number) => {
        // Ensure proper lyric structure for Master Lyrics display
        const processedVoices = clipData.voices?.map((voice: any) => ({
          ...voice,
          lyrics: voice.lyrics?.map((lyric: any, lyricIndex: number) => ({
            text: lyric.text || '',
            notes: lyric.notes || [],
            start: lyric.start !== undefined ? lyric.start : lyricIndex * 2, // Default 2-second intervals
            duration: lyric.duration || lyric.durations?.reduce((a: number, b: number) => a + b, 0) || 2,
            syllables: lyric.syllables || [],
            phonemes: lyric.phonemes || []
          })) || []
        })) || []
        
        const clip = {
          startTime: clipData.startTime !== undefined ? clipData.startTime : index * 8,
          duration: clipData.duration || 8,
          type: 'lyrics' as const,
          instrument: 'vocals',
          volume: 0.8,
          effects: {
            reverb: 0.3,
            delay: 0.2,
            distortion: 0,
            pitchShift: 0,
            chorus: 0.1,
            filter: 0,
            bitcrush: 0
          },
          voices: processedVoices,
          lyrics: processedVoices[0]?.lyrics || [] // Also set direct lyrics for compatibility
        }
        
        console.log(`Adding clip ${index}:`, clip)
        const clipId = audioStore.addClip(trackId, clip)
        console.log('Clip added with ID:', clipId)
      })
    } else if (jsonData.voices) {
      // Single clip structure
      const processedVoices = jsonData.voices.map((voice: any) => ({
        ...voice,
        lyrics: voice.lyrics?.map((lyric: any, lyricIndex: number) => ({
          text: lyric.text || '',
          notes: lyric.notes || [],
          start: lyric.start !== undefined ? lyric.start : lyricIndex * 2,
          duration: lyric.duration || lyric.durations?.reduce((a: number, b: number) => a + b, 0) || 2,
          syllables: lyric.syllables || [],
          phonemes: lyric.phonemes || []
        })) || []
      }))
      
      const clip = {
        startTime: 0,
        duration: 8,
        type: 'lyrics' as const,
        instrument: 'vocals', 
        volume: 0.8,
        effects: {
          reverb: 0.3,
          delay: 0.2,
          distortion: 0,
          pitchShift: 0,
          chorus: 0.1,
          filter: 0,
          bitcrush: 0
        },
        voices: processedVoices,
        lyrics: processedVoices[0]?.lyrics || []
      }
      
      console.log('Adding single clip:', clip)
      const clipId = audioStore.addClip(trackId, clip)
      console.log('Single clip added with ID:', clipId)
    }
    
    // Step 2: Apply to song structure as well
    try {
      // Extract clean lyrics text for Song tab integration
      const lyricsLines = []
      
      // Handle different structures
      if (jsonData.clips && Array.isArray(jsonData.clips)) {
        for (const clip of jsonData.clips) {
          if (clip.voices) {
            for (const voice of clip.voices) {
              if (voice.lyrics) {
                for (const lyric of voice.lyrics) {
                  if (lyric.text && lyric.text.trim()) {
                    lyricsLines.push(lyric.text.trim())
                  }
                }
              }
            }
          }
        }
      } else if (jsonData.voices) {
        for (const voice of jsonData.voices) {
          if (voice.lyrics) {
            for (const lyric of voice.lyrics) {
              if (lyric.text && lyric.text.trim()) {
                lyricsLines.push(lyric.text.trim())
              }
            }
          }
        }
      }
      
      // Format as structured lyrics (one line per lyric)
      const extractedLyricsText = lyricsLines.join('\n')
      
      // Update song structure with lyrics
      if (extractedLyricsText.trim()) {
        const currentLyrics = audioStore.songStructure.lyrics || ''
        const updatedLyrics = currentLyrics ? currentLyrics + '\n\n' + extractedLyricsText.trim() : extractedLyricsText.trim()
        
        audioStore.loadSongStructure({
          ...audioStore.songStructure,
          lyrics: updatedLyrics,
          updatedAt: new Date().toISOString()
        })
        console.log('Song structure updated with lyrics')
      }
    } catch (structureError) {
      console.warn('Could not update song structure:', structureError)
      // Don't fail the whole operation if structure update fails
    }
    
    // Show success notification
    sendMessage('✅ Vocal track successfully added and integrated! 🎤\n\n📝 **Lyrics are now available in:**\n• **Master Lyrics** - Timeline view for karaoke-style singing\n• **Song Tab** - Lyrics section in your project structure\n• **Timeline Editor** - Visual lyrics display\n\n🎵 Your song is ready for vocal performance and mixing!')
    
    // Clear current lyrics
    currentLyricsJSON.value = null
    
    console.log('Added vocal track with ID:', trackId)
  } catch (error) {
    console.error('Error adding vocal track:', error)
    sendMessage('❌ Error adding vocal track. Please try again.')
  }
}

// Apply current lyrics from the chat
const applyCurrentLyrics = () => {
  if (!currentLyricsJSON.value) {
    sendMessage('❌ No lyrics to apply. Please generate lyrics first.')
    return
  }
  
  try {
    console.log('Applying current lyrics:', currentLyricsJSON.value)
    
    // Step 1: Extract lyrics text for Song tab
    let extractedLyricsText = ''
    const lyricsData = currentLyricsJSON.value
    
    // Handle different structures
    if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
      for (const clip of lyricsData.clips) {
        if (clip.voices) {
          for (const voice of clip.voices) {
            if (voice.lyrics) {
              for (const lyric of voice.lyrics) {
                if (lyric.text) {
                  extractedLyricsText += lyric.text + ' '
                }
              }
              extractedLyricsText += '\n'
            }
          }
        }
      }
    } else if (lyricsData.voices) {
      for (const voice of lyricsData.voices) {
        if (voice.lyrics) {
          for (const lyric of voice.lyrics) {
            if (lyric.text) {
              extractedLyricsText += lyric.text + ' '
            }
          }
          extractedLyricsText += '\n'
        }
      }
    }
    
    // Step 2: Create or find vocals track
    let vocalsTrack = audioStore.songStructure.tracks.find(t => t.instrument === 'vocals')
    let trackId = vocalsTrack?.id

    if (!trackId) {
      // Create new vocals track
      trackId = audioStore.addTrack('Lyrics & Vocals', 'vocals')
      if (trackId) {
        audioStore.updateTrack(trackId, {
          volume: 0.8,
          pan: 0,
          effects: { 
            reverb: 0, 
            delay: 0, 
            distortion: 0, 
            pitchShift: 0, 
            chorus: 0, 
            filter: 0, 
            bitcrush: 0 
          }
        })
      }
    }

    // Step 3: Add clips to vocal track
    if (trackId) {
      if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
        // Complete track with clips
        for (const clip of lyricsData.clips) {
          audioStore.addClip(trackId, {
            ...clip,
            trackId: trackId
          })
        }
      } else if (lyricsData.voices || lyricsData.type === 'lyrics') {
        // Single clip
        audioStore.addClip(trackId, {
          ...lyricsData,
          trackId: trackId
        })
      }
    }
    
    // Step 4: Update song structure with lyrics text
    if (extractedLyricsText.trim()) {
      const currentLyrics = audioStore.songStructure.lyrics || ''
      const updatedLyrics = currentLyrics ? currentLyrics + '\n\n' + extractedLyricsText.trim() : extractedLyricsText.trim()
      
      audioStore.loadSongStructure({
        ...audioStore.songStructure,
        lyrics: updatedLyrics,
        updatedAt: new Date().toISOString()
      })
    }
    
    const lyricsWordCount = extractedLyricsText.trim().split(/\s+/).length
    const voiceCount = lyricsData.voices?.length || (lyricsData.clips?.reduce((acc: number, clip: any) => acc + (clip.voices?.length || 0), 0)) || 1
    
    sendMessage(`🎵 Successfully applied lyrics to song! Added ${lyricsWordCount} words with ${voiceCount} voice part(s). Check the Song tab and timeline.`)
    
    // Clear the current lyrics JSON after applying
    currentLyricsJSON.value = null
    
  } catch (error) {
    console.error('Error applying current lyrics:', error)
    sendMessage('❌ Error applying lyrics to song. Please try again.')
  }
}

// Unified function to apply lyrics to song (both structure and vocal track)
const applyLyricsToSong = (encodedJSON: string) => {
  try {
    const jsonContent = decodeURIComponent(encodedJSON)
    const lyricsData = JSON.parse(jsonContent)
    
    console.log('Applying lyrics to song:', lyricsData)
    
    // Step 1: Add lyrics to song structure
    let extractedLyricsText = ''
    
    // Handle different structures
    if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
      for (const clip of lyricsData.clips) {
        if (clip.voices) {
          for (const voice of clip.voices) {
            if (voice.lyrics) {
              for (const lyric of voice.lyrics) {
                if (lyric.text) {
                  extractedLyricsText += lyric.text + ' '
                }
              }
              extractedLyricsText += '\n'
            }
          }
        }
      }
    } else if (lyricsData.voices) {
      for (const voice of lyricsData.voices) {
        if (voice.lyrics) {
          for (const lyric of voice.lyrics) {
            if (lyric.text) {
              extractedLyricsText += lyric.text + ' '
            }
          }
          extractedLyricsText += '\n'
        }
      }
    }
    
    // Step 2: Create or find vocals track
    let vocalsTrack = audioStore.songStructure.tracks.find(t => t.instrument === 'vocals')
    let trackId = vocalsTrack?.id

    if (!trackId) {
      // Create new vocals track
      trackId = audioStore.addTrack('Lyrics & Vocals', 'vocals')
      if (trackId) {
        audioStore.updateTrack(trackId, {
          volume: 0.8,
          pan: 0,
          effects: { 
            reverb: 0, 
            delay: 0, 
            distortion: 0, 
            pitchShift: 0, 
            chorus: 0, 
            filter: 0, 
            bitcrush: 0 
          }
        })
      }
    }

    // Step 3: Add clips to vocal track
    if (trackId) {
      if (lyricsData.clips && Array.isArray(lyricsData.clips)) {
        // Complete track with clips
        for (const clip of lyricsData.clips) {
          audioStore.addClip(trackId, {
            ...clip,
            trackId: trackId
          })
        }
      } else if (lyricsData.voices || lyricsData.type === 'lyrics') {
        // Single clip
        audioStore.addClip(trackId, {
          ...lyricsData,
          trackId: trackId
        })
      }
    }
    
    // Step 4: Update song structure with lyrics text
    if (extractedLyricsText.trim()) {
      const currentLyrics = audioStore.songStructure.lyrics || ''
      const updatedLyrics = currentLyrics ? currentLyrics + '\n\n' + extractedLyricsText.trim() : extractedLyricsText.trim()
      
      audioStore.loadSongStructure({
        ...audioStore.songStructure,
        lyrics: updatedLyrics,
        updatedAt: new Date().toISOString()
      })
    }
    
    const lyricsWordCount = extractedLyricsText.trim().split(/\s+/).length
    const voiceCount = lyricsData.voices?.length || (lyricsData.clips?.reduce((acc: number, clip: any) => acc + (clip.voices?.length || 0), 0)) || 1
    
    sendMessage(`🎵 Successfully applied lyrics to song! Added ${lyricsWordCount} words with ${voiceCount} voice part(s). Check the Song tab and timeline.`)
    
  } catch (error) {
    console.error('Error applying lyrics to song:', error)
    sendMessage('❌ Error applying lyrics to song. Please check the JSON format.')
  }
}

// New lyrics action functions
const addVocalTrackFromLyrics = (encodedJsonContent: string) => {
  try {
    const jsonData = JSON.parse(decodeURIComponent(encodedJsonContent))
    
    // Create a new vocal track with the lyrics
    const vocalTrack = {
      id: `vocal-${Date.now()}`,
      name: 'Vocals',
      instrument: 'vocals',
      type: 'vocal',
      category: 'vocals',
      volume: 0.8,
      pan: 0,
      muted: false,
      solo: false,
      clips: []
    }
    
    // Process lyrics data and create clips
    if (jsonData.clips && Array.isArray(jsonData.clips)) {
      vocalTrack.clips = jsonData.clips.map((clip: any, index: number) => ({
        ...clip,
        id: `vocal-clip-${Date.now()}-${index}`,
        trackId: vocalTrack.id,
        type: 'lyrics'
      }))
    } else if (jsonData.voices) {
      // Single clip structure
      vocalTrack.clips = [{
        id: `vocal-clip-${Date.now()}`,
        trackId: vocalTrack.id,
        startTime: 0,
        duration: 8, // Default duration
        type: 'lyrics',
        voices: jsonData.voices,
        lyrics: jsonData.lyrics || []
      }]
    }
    
    // Add track to the audio store
    audioStore.addTrack(vocalTrack)
    
    // Show success notification
    aiStore.addMessage({
      role: 'assistant',
      content: '✅ Vocal track added successfully! You can now see it in the Song tab with the generated lyrics.',
      id: Date.now().toString()
    })
    
    console.log('Added vocal track:', vocalTrack)
  } catch (error) {
    console.error('Error adding vocal track:', error)
    aiStore.addMessage({
      role: 'assistant', 
      content: '❌ Error adding vocal track. Please try again.',
      id: Date.now().toString()
    })
  }
}

const applyToSong = (encodedJsonContent: string) => {
  try {
    const jsonData = JSON.parse(decodeURIComponent(encodedJsonContent))
    
    // Update the song structure with lyrics information
    if (audioStore.songStructure) {
      // Add lyrics to the song structure
      audioStore.songStructure.lyrics = jsonData
      
      // Also create a vocal track if one doesn't exist
      const existingVocalTrack = audioStore.tracks.find(track => track.instrument === 'vocals')
      if (!existingVocalTrack) {
        addVocalTrackFromLyrics(encodedJsonContent)
      } else {
        // Update existing vocal track with new lyrics
        existingVocalTrack.clips = []
        
        if (jsonData.clips && Array.isArray(jsonData.clips)) {
          existingVocalTrack.clips = jsonData.clips.map((clip: any, index: number) => ({
            ...clip,
            id: `vocal-clip-${Date.now()}-${index}`,
            trackId: existingVocalTrack.id,
            type: 'lyrics'
          }))
        } else if (jsonData.voices) {
          existingVocalTrack.clips = [{
            id: `vocal-clip-${Date.now()}`,
            trackId: existingVocalTrack.id,
            startTime: 0,
            duration: 8,
            type: 'lyrics',
            voices: jsonData.voices,
            lyrics: jsonData.lyrics || []
          }]
        }
        
        aiStore.addMessage({
          role: 'assistant',
          content: '✅ Lyrics applied to song structure and existing vocal track updated!',
          id: Date.now().toString()
        })
      }
    } else {
      // Create new song structure with lyrics
      audioStore.songStructure = {
        title: 'New Song',
        artist: 'Artist',
        key: 'C',
        timeSignature: '4/4',
        tempo: 120,
        lyrics: jsonData
      }
      
      // Also add vocal track
      addVocalTrackFromLyrics(encodedJsonContent)
    }
    
    console.log('Applied lyrics to song:', audioStore.songStructure)
  } catch (error) {
    console.error('Error applying lyrics to song:', error)
    aiStore.addMessage({
      role: 'assistant',
      content: '❌ Error applying lyrics to song. Please try again.',
      id: Date.now().toString()
    })
  }
}

// Watch uploadedScores for debugging
watch(uploadedScores, (newScores) => {
  console.log('[AIChat] uploadedScores changed:', {
    count: newScores.length,
    scores: newScores.map(s => ({
      file_id: s.file_id,
      filename: s.filename,
      status: s.status,
      category: s.category
    }))
  })
}, { deep: true, immediate: true })

onMounted(() => {
  // Focus the input
  messageInput.value?.focus()
  
  console.log('[AIChat] Component mounted, checking initial scores state:', {
    uploadedScores: uploadedScores.value,
    length: uploadedScores.value.length
  })
  
  // Make toggle function globally available for onclick handlers
  ;(window as any).toggleJsonBlock = toggleJsonBlock
  
  // Make JSON action functions globally available
  ;(window as any).applySongStructureFromJSON = applySongStructureFromJSON
  ;(window as any).addTrackFromJSON = addTrackFromJSON
  ;(window as any).addChordProgressionFromJSON = addChordProgressionFromJSON
  ;(window as any).addDrumPatternFromJSON = addDrumPatternFromJSON
  ;(window as any).addBassLineFromJSON = addBassLineFromJSON
  ;(window as any).addMelodyFromJSON = addMelodyFromJSON
  ;(window as any).addLyricsFromJSONAction = addLyricsFromJSONAction
  ;(window as any).addVocalTrackFromJSON = addVocalTrackFromJSON
  ;(window as any).addLyricsToSongStructure = addLyricsToSongStructure
  ;(window as any).applyLyricsToSong = applyLyricsToSong
  ;(window as any).applyEffectsFromJSON = applyEffectsFromJSON
  ;(window as any).applyMixFromJSON = applyMixFromJSON
  
  // New lyrics action functions
  ;(window as any).addVocalTrackFromLyrics = addVocalTrackFromLyrics
  ;(window as any).applyToSong = applyToSong
  
  // Load available instruments on component mount
  loadAvailableInstruments()
  
  // Initialize speech recognition
  initializeSpeechRecognition()
  
  // Auto-detect language based on browser settings
  if (speechSupported.value) {
    const browserLang = navigator.language || (navigator as any).languages?.[0] || 'en-US'
    
    // Find best matching language (inline for now)
    let detectedLang = supportedLanguages.value.find(lang => lang.code === browserLang)
    if (!detectedLang) {
      const langCode = browserLang.split('-')[0]
      detectedLang = supportedLanguages.value.find(lang => lang.code.startsWith(langCode))
    }
    
    if (detectedLang) {
      currentLanguage.value = detectedLang.code
      console.log(`Auto-selected language: ${detectedLang.name} based on browser locale`)
    }
  }
})

// Available instruments management
const availableInstruments = ref<any>({
  categories: {},
  instrumentMap: new Map<string, string>() // AI name -> actual instrument name
})

const loadAvailableInstruments = async () => {
  try {
    const response = await getAllSampleInstruments()
    availableInstruments.value = response
    
    // Create mapping from AI-suggested names to actual instrument names
    const instrumentMap = new Map<string, string>()
    
    // Add direct mappings for common AI suggestions
    for (const category in response.categories) {
      const instruments = response.categories[category]
      for (const instrument of instruments) {
        const name = instrument.name || instrument
        const displayName = instrument.display_name || name
        
        // Map common AI suggestions to actual instruments
        instrumentMap.set(name.toLowerCase(), name)
        instrumentMap.set(displayName.toLowerCase(), name)
        
        // Special mappings for common AI terms
        if (name.toLowerCase().includes('piano')) {
          instrumentMap.set('piano', name)
          instrumentMap.set('acoustic piano', name)
        }
        if (name.toLowerCase().includes('electric') && name.toLowerCase().includes('piano')) {
          instrumentMap.set('electric piano', name)
          instrumentMap.set('electric-piano', name)
          instrumentMap.set('e-piano', name)
        }
        if (name.toLowerCase().includes('guitar')) {
          instrumentMap.set('guitar', name)
          if (name.toLowerCase().includes('acoustic')) {
            instrumentMap.set('acoustic guitar', name)
            instrumentMap.set('acoustic-guitar', name)
          }
          if (name.toLowerCase().includes('electric')) {
            instrumentMap.set('electric guitar', name)
            instrumentMap.set('electric-guitar', name)
          }
        }
        if (name.toLowerCase().includes('bass')) {
          instrumentMap.set('bass', name)
          instrumentMap.set('electric bass', name)
          instrumentMap.set('acoustic bass', name)
          instrumentMap.set('sub bass', name)
        }
        if (name.toLowerCase().includes('drum')) {
          instrumentMap.set('drums', name)
          instrumentMap.set('percussion', name)
        }
        if (name.toLowerCase().includes('string')) {
          instrumentMap.set('strings', name)
          instrumentMap.set('violin', name)
          instrumentMap.set('orchestra', name)
        }
        if (name.toLowerCase().includes('brass')) {
          instrumentMap.set('brass', name)
          instrumentMap.set('trumpet', name)
          instrumentMap.set('horn', name)
        }
        if (name.toLowerCase().includes('woodwind') || name.toLowerCase().includes('flute') || name.toLowerCase().includes('sax')) {
          instrumentMap.set('woodwinds', name)
          instrumentMap.set('flute', name)
          instrumentMap.set('saxophone', name)
          instrumentMap.set('sax', name)
        }
        if (name.toLowerCase().includes('vocal')) {
          instrumentMap.set('vocals', name)
          instrumentMap.set('voice', name)
          instrumentMap.set('singing', name)
        }
        if (name.toLowerCase().includes('synth')) {
          instrumentMap.set('synth', name)
          instrumentMap.set('synthesizer', name)
          if (name.toLowerCase().includes('lead')) {
            instrumentMap.set('synth lead', name)
            instrumentMap.set('synth-lead', name)
            instrumentMap.set('lead synth', name)
          }
          if (name.toLowerCase().includes('pad')) {
            instrumentMap.set('synth pad', name)
            instrumentMap.set('synth-pad', name)
            instrumentMap.set('pad', name)
          }
        }
      }
    }
    
    availableInstruments.value.instrumentMap = instrumentMap
    console.log('Available instruments loaded:', response)
    console.log('Instrument mapping created:', instrumentMap)
  } catch (error) {
    console.error('Failed to load available instruments:', error)
    // Use fallback mapping with comprehensive instrument support
    availableInstruments.value.instrumentMap = new Map([
      ['piano', 'piano'],
      ['acoustic piano', 'piano'],
      ['electric piano', 'electric-piano'],
      ['electric-piano', 'electric-piano'],
      ['e-piano', 'electric-piano'],
      ['guitar', 'guitar'],
      ['acoustic guitar', 'acoustic-guitar'],
      ['acoustic-guitar', 'acoustic-guitar'],
      ['electric guitar', 'electric-guitar'],
      ['electric-guitar', 'electric-guitar'],
      ['bass', 'bass'],
      ['electric bass', 'bass'],
      ['acoustic bass', 'bass'],
      ['sub bass', 'bass'],
      ['drums', 'drums'],
      ['percussion', 'drums'],
      ['strings', 'strings'],
      ['violin', 'strings'],
      ['orchestra', 'strings'],
      ['brass', 'brass'],
      ['trumpet', 'brass'],
      ['horn', 'brass'],
      ['woodwinds', 'woodwinds'],
      ['flute', 'woodwinds'],
      ['saxophone', 'woodwinds'],
      ['sax', 'woodwinds'],
      ['vocals', 'vocals'],
      ['voice', 'vocals'],
      ['singing', 'vocals'],
      ['synth', 'synth'],
      ['synthesizer', 'synth'],
      ['synth lead', 'synth-lead'],
      ['synth-lead', 'synth-lead'],
      ['lead synth', 'synth-lead'],
      ['synth pad', 'synth-pad'],
      ['synth-pad', 'synth-pad'],
      ['pad', 'synth-pad']
    ])
  }
}

// Helper function to get the best available instrument for AI suggestions
const getAvailableInstrument = (aiSuggestion: string, fallback: string = 'piano'): string => {
  if (!aiSuggestion) return fallback
  
  const instrumentMap = availableInstruments.value.instrumentMap
  const suggestion = aiSuggestion.toLowerCase()
  
  // Try exact match first
  if (instrumentMap.has(suggestion)) {
    return instrumentMap.get(suggestion)!
  }
  
  // Try partial matches
  for (const [key, value] of instrumentMap.entries()) {
    if (key.includes(suggestion) || suggestion.includes(key)) {
      return value
    }
  }
  
  // Use fallback if no match found
  console.warn(`No available instrument found for AI suggestion: ${aiSuggestion}, using fallback: ${fallback}`)
  return fallback
}

// Helper function to get instrument type and category
const getInstrumentTypeAndCategory = (instrument: string): { type: string, category?: string } => {
  // For sample-based instruments, use 'sample' type
  for (const category in availableInstruments.value.categories) {
    const instruments = availableInstruments.value.categories[category]
    const foundInstrument = instruments.find((inst: any) => 
      (inst.name || inst) === instrument
    )
    if (foundInstrument) {
      return { type: 'sample', category }
    }
  }
  
  // Fallback to synth for built-in instruments
  return { type: 'synth' }
}

/**
 * Enhanced Action Button Generation for AI Chat
 * 
 * This system now analyzes AI responses more intelligently to create contextual action buttons that
 * reflect the specific suggestions made by the AI assistant. Instead of generic buttons, users now see
 * buttons like:
 * 
 * - "Apply Detailed Drum Pattern" (when AI provides step-by-step instructions)
 * - "Add Kick + Snare + Hihat Pattern" (when AI mentions specific drum elements)
 * - "Set Tempo to 120 BPM" (when AI suggests a specific BPM)
 * - "Add Minor Progression" (when AI suggests minor chords)
 * - "Apply Reverb + Delay" (when AI mentions specific effects)
 * 
 * The system extracts implementation details, musical elements, and specific parameters from the
 * AI's response text to create more relevant and actionable buttons.
 */

// Extract implementation steps from AI response for detailed actions
const extractImplementationSteps = (content: string): string[] => {
  const steps: string[] = []
  const lines = content.split('\n')
  
  let inImplementationSection = false
  for (const line of lines) {
    const trimmedLine = line.trim()
    
    // Start capturing when we see implementation suggestions
    if (trimmedLine.toLowerCase().includes('implementation suggestions:') || 
        trimmedLine.toLowerCase().includes('start with the kick drum:')) {
      inImplementationSection = true
      continue
    }
    
    // Stop capturing when we hit a new section or empty lines
    if (inImplementationSection && (trimmedLine === '' || trimmedLine.toLowerCase().includes('would you like'))) {
      break
    }
    
    // Capture numbered steps or bullet points
    if (inImplementationSection && (trimmedLine.match(/^\d+\./) || trimmedLine.startsWith('-'))) {
      steps.push(trimmedLine)
    }
  }
  
  return steps
}

// Extract musical elements and suggestions from AI response
const parseMusicalSuggestions = (content: string): any => {
  const suggestions: any = {
    drumElements: [],
    bpm: null,
    chordType: null,
    bassType: null,
    instrument: null,
    effects: [],
    sections: [],
    hasDetailedInstructions: false
  }
  
  const lowerContent = content.toLowerCase()
  
  // Detect detailed instructions
  if (lowerContent.includes('implementation suggestions:') || 
      lowerContent.includes('start with the kick drum:') ||
      lowerContent.includes('place kicks at') ||
      lowerContent.includes('layer the hi-hats:')) {
    suggestions.hasDetailedInstructions = true
  }
  
  // Extract BPM
  const bpmMatch = content.match(/(\d+)\s*bpm/i)
  if (bpmMatch) {
    suggestions.bpm = parseInt(bpmMatch[1])
  }
  
  // Extract drum elements
  if (lowerContent.includes('kick')) suggestions.drumElements.push('kick')
  if (lowerContent.includes('clap') || lowerContent.includes('snare')) suggestions.drumElements.push('snare')
  if (lowerContent.includes('hi-hat') || lowerContent.includes('hihat')) suggestions.drumElements.push('hihat')
  
  // Extract chord types
  if (lowerContent.includes('minor')) suggestions.chordType = 'minor'
  else if (lowerContent.includes('major')) suggestions.chordType = 'major'
  else if (lowerContent.includes('jazz')) suggestions.chordType = 'jazz'
  else if (lowerContent.includes('blues')) suggestions.chordType = 'blues'
  else if (lowerContent.includes('chord')) suggestions.chordType = 'pop'
  
  // Extract bass types
  if (lowerContent.includes('electric bass')) suggestions.bassType = 'electric'
  else if (lowerContent.includes('acoustic bass')) suggestions.bassType = 'acoustic'
  else if (lowerContent.includes('sub bass')) suggestions.bassType = 'sub'
  else if (lowerContent.includes('bass')) suggestions.bassType = 'synth'
  
  // Extract instruments for melody (enhanced to cover more instrument types)
  if (lowerContent.includes('piano')) suggestions.instrument = 'piano'
  else if (lowerContent.includes('electric piano') || lowerContent.includes('e-piano')) suggestions.instrument = 'electric-piano'
  else if (lowerContent.includes('acoustic guitar') || lowerContent.includes('acoustic-guitar')) suggestions.instrument = 'acoustic-guitar'
  else if (lowerContent.includes('electric guitar') || lowerContent.includes('electric-guitar')) suggestions.instrument = 'electric-guitar'
  else if (lowerContent.includes('guitar')) suggestions.instrument = 'guitar'
  else if (lowerContent.includes('violin') || lowerContent.includes('strings')) suggestions.instrument = 'strings'
  else if (lowerContent.includes('trumpet') || lowerContent.includes('brass')) suggestions.instrument = 'brass'
  else if (lowerContent.includes('flute') || lowerContent.includes('woodwind')) suggestions.instrument = 'woodwinds'
  else if (lowerContent.includes('saxophone') || lowerContent.includes('sax')) suggestions.instrument = 'saxophone'
  else if (lowerContent.includes('synth pad') || lowerContent.includes('pad')) suggestions.instrument = 'synth-pad'
  else if (lowerContent.includes('synth lead') || lowerContent.includes('lead synth')) suggestions.instrument = 'synth-lead'
  else if (lowerContent.includes('synthesizer') || lowerContent.includes('synth')) suggestions.instrument = 'synth'
  else if (lowerContent.includes('melody') || lowerContent.includes('lead')) suggestions.instrument = 'synth'
  
  // Extract effects
  if (lowerContent.includes('reverb')) suggestions.effects.push('reverb')
  if (lowerContent.includes('delay')) suggestions.effects.push('delay')
  if (lowerContent.includes('distortion')) suggestions.effects.push('distortion')
  if (lowerContent.includes('compression')) suggestions.effects.push('compression')
  
  // Extract song sections
  if (lowerContent.includes('verse')) suggestions.sections.push('verse')
  if (lowerContent.includes('chorus')) suggestions.sections.push('chorus')
  if (lowerContent.includes('bridge')) suggestions.sections.push('bridge')
  if (lowerContent.includes('intro')) suggestions.sections.push('intro')
  if (lowerContent.includes('outro')) suggestions.sections.push('outro')
  
  return suggestions
}

// Generate instrument-specific action buttons based on actual instruments mentioned in AI response
const generateInstrumentSpecificActions = (responseContent: string): ChatAction[] => {
  const actions: ChatAction[] = []
  console.log('=== generateInstrumentSpecificActions called ===')
  console.log('Response content length:', responseContent.length)
  console.log('First 500 chars:', responseContent.substring(0, 500))
  
  // Parse the AI response for instrument categories and specific instruments
  const lines = responseContent.split('\n')
  console.log('Total lines to parse:', lines.length)
  
  const instrumentMentions: { type: string, instruments: string[] }[] = []
  
  let currentCategory = ''
  let currentInstruments: string[] = []
  
  for (const line of lines) {
    const trimmedLine = line.trim()
    
    // Look for markdown category headers (like "### Strings:" or "### Woodwinds:")
    const markdownCategoryMatch = trimmedLine.match(/^###\s*([^:]+):?\s*$/i)
    if (markdownCategoryMatch) {
      // Save previous category if it exists
      if (currentCategory && currentInstruments.length > 0) {
        instrumentMentions.push({ type: currentCategory, instruments: [...currentInstruments] })
      }
      
      currentCategory = markdownCategoryMatch[1].toLowerCase().trim()
      currentInstruments = []
      console.log('Found markdown category:', currentCategory)
      continue
    }
    
    // Look for numbered category headers (like "1. **Guitar Acoustic**:" or "1. Acoustic Guitar:")
    const numberedCategoryMatch = trimmedLine.match(/^\d+\.\s*([^:]+):?\s*/i)
    if (numberedCategoryMatch) {
      // Save previous category if it exists
      if (currentCategory && currentInstruments.length > 0) {
        instrumentMentions.push({ type: currentCategory, instruments: [...currentInstruments] })
        console.log('Saved previous category:', currentCategory, 'with instruments:', currentInstruments)
      }
      
      // Clean up the category name by removing bold markdown
      let categoryName = numberedCategoryMatch[1].trim()
      categoryName = categoryName.replace(/\*\*(.*?)\*\*/g, '$1') // Remove **bold** markdown
      currentCategory = categoryName.toLowerCase()
      currentInstruments = []
      console.log('Found numbered category:', currentCategory)
      
      // Look for quoted instrument names in the same line
      const quotedInstruments = trimmedLine.match(/"([^"]+)"/g)
      if (quotedInstruments) {
        for (const quoted of quotedInstruments) {
          const instrumentName = quoted.replace(/"/g, '')
          const matchedInstrument = findBestInstrumentMatch(instrumentName)
          if (matchedInstrument) {
            currentInstruments.push(matchedInstrument)
            console.log('Found instrument in category line:', instrumentName, '→', matchedInstrument)
          }
        }
      }
      continue
    }
    
    // Look for bullet point instrument names (like "- Acoustic Bass" or "   - Guitar_Acoustic")
    if (trimmedLine.startsWith('-') && trimmedLine.length > 2 && currentCategory) {
      let instrumentName = trimmedLine.substring(1).trim()
      
      // If the line contains quoted text, extract the first quoted instrument
      const quotedMatch = instrumentName.match(/"([^"]+)"/)
      if (quotedMatch) {
        instrumentName = quotedMatch[1]
      }
      
      // Remove any remaining quotes
      const cleanInstrumentName = instrumentName.replace(/"/g, '')
      
      console.log('Processing bullet point line:', trimmedLine)
      console.log('Extracted instrument name:', cleanInstrumentName)
      
      const matchedInstrument = findBestInstrumentMatch(cleanInstrumentName)
      if (matchedInstrument) {
        currentInstruments.push(matchedInstrument)
        console.log('Found bullet point instrument:', cleanInstrumentName, '→', matchedInstrument)
      } else {
        console.log('No match found for bullet point instrument:', cleanInstrumentName)
      }
      continue
    }
    
    // Look for quoted instrument names in regular text lines
    if (currentCategory) {
      const quotedInstruments = trimmedLine.match(/"([^"]+)"/g)
      if (quotedInstruments) {
        for (const quoted of quotedInstruments) {
          const instrumentName = quoted.replace(/"/g, '')
          const matchedInstrument = findBestInstrumentMatch(instrumentName)
          if (matchedInstrument) {
            currentInstruments.push(matchedInstrument)
            console.log('Found quoted instrument in text:', instrumentName, '→', matchedInstrument)
          }
        }
      }
    }
  }
  
  // Don't forget the last category
  if (currentCategory && currentInstruments.length > 0) {
    instrumentMentions.push({ type: currentCategory, instruments: [...currentInstruments] })
    console.log('Saved final category:', currentCategory, 'with instruments:', currentInstruments)
  }
  console.log('Found instrument mentions:', instrumentMentions)
  
  // Generate action buttons for found instruments
  const addedInstruments = new Set<string>() // Track to prevent duplicates
  
  for (const mention of instrumentMentions) {
    console.log('Processing mention:', mention)
    
    // Take the first 2-3 instruments from each category to avoid too many buttons
    const instrumentsToUse = mention.instruments.slice(0, 3)
    
    for (const instrument of instrumentsToUse) {
      // Skip if we've already added an action for this instrument
      if (addedInstruments.has(instrument)) {
        console.log('Skipping duplicate instrument:', instrument)
        continue
      }
      
      addedInstruments.add(instrument)
      const displayName = getInstrumentDisplayName(instrument)
      console.log('Creating action for instrument:', instrument, '→', displayName)
      
      let action = 'add_melody'
      let icon = Music
      let label = `Add ${displayName}`
      
      // Determine action type based on category
      if (mention.type.includes('bass')) {
        action = 'add_bass_track'
        label = `Add Bass Track (${displayName})`
        icon = Plus
      } else if (mention.type.includes('drum') || mention.type.includes('percussion')) {
        action = 'add_drum_pattern'
        label = `Add Drum Pattern (${displayName})`
        icon = Plus
      } else if (mention.type.includes('guitar') || mention.type.includes('string')) {
        action = 'add_melody'
        // If the instrument name contains specific model info, show it
        if (instrument.toLowerCase().includes('acoustic') || instrument.includes('_')) {
          label = `Add Guitar Track (${displayName})`
        } else {
          label = `Add Guitar Track (${displayName})`
        }
        icon = Music
      } else {
        action = 'add_melody'
        label = `Add ${displayName} Track`
        icon = Music
      }
      
      console.log('Generated action:', { label, action, params: { instrument } })
      
      actions.push({
        label,
        icon,
        action,
        params: { 
          instrument: instrument
        }
      })
    }
  }
  
  console.log('Returning actions:', actions)
  return actions
}

// Helper function to find the best matching instrument from available instruments
const findBestInstrumentMatch = (searchName: string): string | null => {
  console.log('findBestInstrumentMatch called with:', searchName)
  console.log('Available instruments structure:', availableInstruments.value)
  
  if (!availableInstruments.value?.categories) {
    console.log('No availableInstruments.categories found')
    return null
  }
  
  const lowerSearchName = searchName.toLowerCase().trim()
  console.log('Searching for (lowercase):', lowerSearchName)
  
  let bestMatch: string | null = null
  let exactMatch: string | null = null
  
  // Check each category for matches
  for (const category in availableInstruments.value.categories) {
    const instruments = availableInstruments.value.categories[category]
    console.log(`Checking category ${category} with ${instruments.length} instruments`)
    
    for (const instrument of instruments) {
      const instrumentName = instrument.name || instrument
      const displayName = instrument.display_name || instrumentName
      
      console.log(`  Checking instrument: ${instrumentName} (display: ${displayName})`)
      
      // Check for exact display name matches first
      if (displayName.toLowerCase() === lowerSearchName) {
        console.log(`  EXACT DISPLAY MATCH FOUND: ${instrumentName}`)
        exactMatch = instrumentName
        break
      }
      
      // Check exact instrument name match
      if (instrumentName.toLowerCase() === lowerSearchName) {
        console.log(`  EXACT NAME MATCH FOUND: ${instrumentName}`)
        exactMatch = instrumentName
        break
      }
      
      // Store first partial match but don't return it yet
      if (!bestMatch) {
        if (displayName.toLowerCase().includes(lowerSearchName) || 
            lowerSearchName.includes(displayName.toLowerCase())) {
          console.log(`  PARTIAL MATCH FOUND: ${instrumentName}`)
          bestMatch = instrumentName
        }
        // Check internal name matches too
        else {
          const formattedName = instrumentName.toLowerCase().replace(/_/g, ' ')
          if (formattedName.includes(lowerSearchName) ||
              lowerSearchName.includes(formattedName)) {
            console.log(`  FORMATTED MATCH FOUND: ${instrumentName}`)
            bestMatch = instrumentName
          }
        }
      }
    }
    
    // If we found an exact match, return immediately
    if (exactMatch) {
      return exactMatch
    }
  }
  
  // If no exact match found, return best partial match
  if (bestMatch) {
    console.log('  RETURNING PARTIAL MATCH:', bestMatch)
    return bestMatch
  }
  
  console.log('  NO MATCH FOUND for:', searchName)
  return null
}

// Helper function to get display name for an instrument
const getInstrumentDisplayName = (instrument: string): string => {
  if (!availableInstruments.value?.categories) {
    return instrument.replace(/_/g, ' ').replace(/-/g, ' ')
  }
  
  // Check if we have display name info from available instruments
  for (const category in availableInstruments.value.categories) {
    const instruments = availableInstruments.value.categories[category]
    const foundInstrument = instruments.find((inst: any) => 
      (inst.name || inst) === instrument
    )
    if (foundInstrument) {
      return foundInstrument.display_name || foundInstrument.name || instrument.replace(/_/g, ' ').replace(/-/g, ' ')
    }
  }
  
  // Fallback to formatted name
  return instrument.replace(/_/g, ' ').replace(/-/g, ' ')
}

// Generate contextual action buttons based on AI response content
const generateContextualActions = (responseContent: string): ChatAction[] => {
  console.log('=== generateContextualActions called ===')
  const actions: ChatAction[] = []
  const content = responseContent.toLowerCase()
  const originalContent = responseContent
  const suggestions = parseMusicalSuggestions(originalContent)
  
  console.log('generateContextualActions called with content length:', originalContent.length)
  
  // Enhanced parsing for specific instruments mentioned in AI response
  console.log('Calling generateInstrumentSpecificActions...')
  const specificInstrumentActions = generateInstrumentSpecificActions(originalContent)
  console.log('specificInstrumentActions returned:', specificInstrumentActions.length, 'actions')
  console.log('Actions details:', specificInstrumentActions)
  
  if (specificInstrumentActions.length > 0) {
    console.log('Using specific instrument actions, skipping fallback logic')
    return specificInstrumentActions
  }
  
  console.log('No specific instrument actions found, using fallback logic')
  console.log('Parsed suggestions:', suggestions)
  
  // Handle detailed drum pattern suggestions first
  if (suggestions.hasDetailedInstructions && suggestions.drumElements.length > 0) {
    actions.push({
      label: 'Apply Detailed Drum Pattern',
      icon: Plus,
      action: 'add_drum_pattern',
      params: { 
        detailed: true,
        pattern: 'backbeat',
        elements: suggestions.drumElements,
        implementation: extractImplementationSteps(originalContent)
      }
    })
  }
  // Regular drum patterns
  else if (suggestions.drumElements.length > 0) {
    actions.push({
      label: `Add ${suggestions.drumElements.map((p: string) => p.charAt(0).toUpperCase() + p.slice(1)).join(' + ')} Pattern`,
      icon: Plus,
      action: 'add_drum_pattern',
      params: { 
        elements: suggestions.drumElements,
        pattern: content.includes('backbeat') ? 'backbeat' : 'house'
      }
    })
  }
  // Generic drum patterns
  else if (content.includes('drum') || content.includes('beat') || content.includes('rhythm')) {
    actions.push({
      label: 'Add Drum Pattern',
      icon: Plus,
      action: 'add_drum_pattern',
      params: { genre: 'house' }
    })
  }
  
  // Tempo/BPM suggestions
  if (suggestions.bpm || content.includes('tempo') || content.includes('speed')) {
    actions.push({
      label: suggestions.bpm ? `Set Tempo to ${suggestions.bpm} BPM` : 'Adjust Tempo',
      icon: Settings,
      action: 'adjust_tempo',
      params: suggestions.bpm ? { bpm: suggestions.bpm } : {}
    })
  }
  
  // Chord progression suggestions
  if (suggestions.chordType) {
    actions.push({
      label: `Add ${suggestions.chordType.charAt(0).toUpperCase() + suggestions.chordType.slice(1)} Progression`,
      icon: Music,
      action: 'add_chord_progression',
      params: { 
        type: suggestions.chordType,
        instrument: suggestions.instrument || 'piano' // Use AI-suggested instrument or default to piano
      }
    })
  }
  
  // Bass suggestions
  if (suggestions.bassType) {
    actions.push({
      label: `Add ${suggestions.bassType.charAt(0).toUpperCase() + suggestions.bassType.slice(1)} Bass`,
      icon: Plus,
      action: 'add_bass_track',
      params: { type: suggestions.bassType }
    })
  }
  
  // Melody suggestions
  if (suggestions.instrument) {
    actions.push({
      label: `Add ${suggestions.instrument.charAt(0).toUpperCase() + suggestions.instrument.slice(1)} Melody`,
      icon: Music,
      action: 'add_melody',
      params: { instrument: suggestions.instrument }
    })
  }
  
  // Effects suggestions
  if (suggestions.effects.length > 0) {
    actions.push({
      label: `Apply ${suggestions.effects.join(' + ').charAt(0).toUpperCase() + suggestions.effects.join(' + ').slice(1)}`,
      icon: Volume2,
      action: 'apply_effects',
      params: { effects: suggestions.effects }
    })
  } else if (content.includes('effect') || content.includes('mix')) {
    actions.push({
      label: 'Apply Effects',
      icon: Volume2,
      action: 'apply_effects'
    })
  }
  
  // Vocal/lyrics suggestions
  if (content.includes('vocal') || content.includes('lyrics') || content.includes('singing') || content.includes('voice')) {
    actions.push({
      label: 'Add Vocal Track',
      icon: Mic2,
      action: 'add_vocal_track'
    })
  }
  
  // Song structure suggestions
  if (suggestions.sections.length > 0) {
    actions.push({
      label: `Add ${suggestions.sections.join(' + ').charAt(0).toUpperCase() + suggestions.sections.join(' + ').slice(1)} Section`,
      icon: Upload,
      action: 'apply_song_structure',
      params: { sections: suggestions.sections }
    })
  } else if (content.includes('structure') || content.includes('arrangement')) {
    // Try to extract JSON structure from the content
    let songStructure = null
    try {
      const jsonMatches = content.match(/```json\s*([\s\S]*?)\s*```/g)
      if (jsonMatches) {
        for (const jsonMatch of jsonMatches) {
          const jsonContent = jsonMatch.replace(/```json\s*/, '').replace(/\s*```/, '')
          try {
            const jsonData = JSON.parse(jsonContent)
            // Check if this looks like a song structure (has tracks)
            if (jsonData.tracks || jsonData.clips || jsonData.voices) {
              songStructure = jsonData
              break
            }
          } catch (e) {
            // Not valid JSON, continue
          }
        }
      }
    } catch (e) {
      console.log('No JSON structure found in content')
    }
    
    actions.push({
      label: 'Apply Structure',
      icon: Upload,
      action: 'apply_song_structure',
      params: { songStructure: songStructure }
    })
  }
  
  // Export suggestions
  if (content.includes('export') || content.includes('download') || content.includes('save') || content.includes('render')) {
    actions.push({
      label: 'Export Track',
      icon: Download,
      action: 'export_track'
    })
  }
  
  // Playback suggestions
  if (content.includes('play') || content.includes('listen') || content.includes('preview')) {
    actions.push({
      label: 'Play Preview',
      icon: Play,
      action: 'play_preview'
    })
  }
  
  return actions
}

// Methods
const sendMessage = async (content: string) => {
  if (!content.trim()) return
  
  // Clear current message and hide suggestions
  currentMessage.value = ''
  showSuggestions.value = false
  
  // Scroll to bottom
  await nextTick()
  scrollToBottom()
  
  try {
    // Check if we have uploaded scores to include in context
    const scoreFileIds = uploadedScores.value
      .filter(score => score.status === 'success')
      .map(score => score.file_id)
    
    console.log('[AIChat] DEBUG: Current uploadedScores state:', {
      uploadedScoresValue: uploadedScores.value,
      uploadedScoresLength: uploadedScores.value.length,
      allScoreStatuses: uploadedScores.value.map(s => ({id: s.file_id, status: s.status})),
      scoreFileIds: scoreFileIds,
      scoreFileIdsLength: scoreFileIds.length
    })
    
    console.log('[AIChat] Sending message with uploaded scores:', {
      message: content.substring(0, 100) + (content.length > 100 ? '...' : ''),
      uploadedScoresCount: uploadedScores.value.length,
      successfulScores: scoreFileIds.length,
      scoreFileIds
    })
    
    // Use score-aware messaging if scores are uploaded, otherwise regular chat
    let result
    if (scoreFileIds.length > 0) {
      result = await sendMessageWithScores(content, scoreFileIds)
      console.log('AI response received:', result)
      console.log('Result structure:', {
        hasResult: !!result,
        hasContent: !!result?.content,
        hasResponse: !!result?.response,
        resultKeys: result ? Object.keys(result).slice(0, 10) : 'no result',
        resultType: typeof result,
        isString: typeof result === 'string'
      })
      
      // Extract the response content
      let responseContent = null
      if (typeof result === 'string') {
        responseContent = result
      } else if (result?.content) {
        responseContent = result.content
      } else if (result?.response) {
        responseContent = result.response
      }
      
      // Add the AI response to chat messages (sendMessageWithScores doesn't do this automatically)
      if (responseContent) {
        console.log('[AIChat] Adding AI response to messages:', responseContent.substring(0, 100) + '...')
        aiStore.addMessage('assistant', responseContent)
      }
    } else {
      result = await aiStore.sendMessage(content)
    }

    // Generate contextual action buttons based on the AI response
    let responseContent = null
    if (typeof result === 'string') {
      // If result is directly the string response
      responseContent = result
    } else if (result?.content) {
      responseContent = result.content
    } else if (result?.response) {
      responseContent = result.response
    }    if (responseContent) {
      console.log('Generating actions for content:', responseContent.substring(0, 100) + '...')
      
      // Check for lyrics in text format and convert to JSON
      const hasTextLyrics = detectAndConvertTextLyrics(responseContent)
      
      // Also check for JSON format with vocals/lyrics
      let hasJSONLyrics = false
      try {
        // Look for JSON blocks in the response - handle both ```json and `json formats
        const jsonMatches = responseContent.match(/```json\s*([\s\S]*?)\s*```/g) || 
                           responseContent.match(/`json\s*([\s\S]*?)(?=`[^`]|$)/g)
        
        if (jsonMatches) {
          for (const jsonMatch of jsonMatches) {
            let jsonContent = jsonMatch
              .replace(/```json\s*/, '')
              .replace(/\s*```/, '')
              .replace(/`json\s*/, '')
              .replace(/`$/, '')
            
            // If JSON appears to be truncated, try to parse what we have
            if (!jsonContent.trim().endsWith('}')) {
              console.log('⚠️ JSON appears truncated, attempting to parse partial JSON')
              // Try to find the last complete object/array
              const lastBrace = jsonContent.lastIndexOf('}')
              if (lastBrace > 0) {
                jsonContent = jsonContent.substring(0, lastBrace + 1)
              }
            }
            
            try {
              const jsonData = JSON.parse(jsonContent)
              if (isLyricsJSON(jsonData)) {
                console.log('✅ Detected lyrics in JSON format:', jsonData)
                currentLyricsJSON.value = jsonData
                hasJSONLyrics = true
                break
              }
            } catch (e) {
              console.log('❌ JSON parse error:', e.message, 'Content:', jsonContent.substring(0, 100) + '...')
              // Not valid JSON, continue
            }
          }
        }
      } catch (e) {
        console.log('No JSON blocks found')
      }
      
      const actions = generateContextualActions(responseContent)
      
      // Add vocal track action if lyrics were detected (either text or JSON format)
      if ((hasTextLyrics || hasJSONLyrics) && currentLyricsJSON.value) {
        console.log('✅ Detected lyrics, adding vocal track action. currentLyricsJSON:', currentLyricsJSON.value)
        actions.push({
          label: 'Add Vocal Track & Apply to Song',
          action: 'add_vocal_track',
          icon: Mic
        })
      } else {
        console.log('❌ No lyrics detected. hasTextLyrics:', hasTextLyrics, 'hasJSONLyrics:', hasJSONLyrics, 'currentLyricsJSON:', currentLyricsJSON.value)
      }
      
      if (actions.length > 0) {
        console.log('Generated actions:', actions)
        // Update the last message with generated actions
        const lastMessage = aiStore.messages[aiStore.messages.length - 1]
        if (lastMessage && lastMessage.role === 'assistant') {
          // Replace with new actions since backend no longer generates generic ones
          lastMessage.actions = actions
          console.log('Updated last message with actions')
        }
      } else {
        console.log('No actions generated')
      }
    } else {
      console.log('No valid response content found for action generation')
    }
    
  } catch (error) {
    console.error('AI chat error:', error)
    
    // Fallback is handled by the AI store
  } finally {
    nextTick(() => {
      scrollToBottom()
    })
  }
}

const sendCurrentMessage = () => {
  sendMessage(currentMessage.value)
}

const executeAction = (action: ChatAction) => {
  switch (action.action) {
    case 'apply_song_structure':
      applySongStructureChanges(action.params?.songStructure)
      break
    case 'add_chord_progression':
      addChordProgression(action.params?.type || 'pop', action.params?.instrument)
      break
    case 'add_drum_pattern':
      addDrumPattern(
        action.params?.genre || 'house', 
        action.params?.elements || [], 
        action.params?.pattern,
        action.params?.detailed,
        action.params?.implementation
      )
      break
    case 'add_bass_track':
      addBassTrack(action.params?.type)
      break
    case 'add_vocal_track':
      addVocalTrackAction()
      break
    case 'add_melody':
      addMelodyTrack(action.params?.instrument || 'synth')
      break
    case 'add_lyrics_json':
      addLyricsFromJSON(action.data)
      break
    case 'adjust_tempo':
      adjustTempo(action.params?.bpm)
      break
    case 'apply_effects':
      applyEffects(action.params?.effects)
      break
    case 'export_track':
      exportTrack()
      break
    case 'play_preview':
      playPreview()
      break
    case 'new_project':
      createNewProject()
      break
    case 'analyze_project':
      analyzeProject()
      break
    default:
      console.log('Action not implemented:', action.action)
  }
}

const applySongStructureChanges = async (songStructure: any) => {
  if (!songStructure) {
    console.warn('No song structure provided to apply')
    return
  }

  try {
    console.log('🎵 Applying AI-generated song structure changes:', songStructure)
    
    // Stop any current playback to prevent conflicts
    if (audioStore.isPlaying) {
      audioStore.stop()
    }
    
    // Extract lyrics from tracks/clips if not already present at top level
    if (!songStructure.lyrics && songStructure.tracks) {
      let extractedLyricsText = ''
      
      for (const track of songStructure.tracks) {
        if (track.clips) {
          for (const clip of track.clips) {
            if (clip.voices) {
              for (const voice of clip.voices) {
                if (voice.lyrics) {
                  for (const lyric of voice.lyrics) {
                    if (lyric.text) {
                      extractedLyricsText += lyric.text + '\n'
                    }
                  }
                }
              }
            }
          }
        }
      }
      
      if (extractedLyricsText.trim()) {
        songStructure.lyrics = extractedLyricsText.trim()
        console.log('Extracted lyrics from tracks/clips for lyrics panel')
      }
    } else if (songStructure.lyrics) {
      // If song-level lyrics exist, ensure clips are synchronized
      const updateClipsWithLyrics = (structure: any, lyrics: string) => {
        if (!structure.tracks) return structure
        
        const lyricsLines = lyrics.split('\n').filter(line => line.trim().length > 0)
        let currentLineIndex = 0
        
        const updatedTracks = structure.tracks.map((track: any) => {
          // Handle voice tracks (new structure)
          if (track.instrument === 'vocals' && track.voiceId && track.clips) {
            const updatedClips = track.clips.map((clip: any) => {
              if (clip.type === 'lyrics' && clip.lyrics) {
                const updatedLyrics = clip.lyrics.map((lyric: any) => {
                  if (currentLineIndex < lyricsLines.length) {
                    const result = {
                      ...lyric,
                      text: lyricsLines[currentLineIndex]
                    }
                    currentLineIndex++
                    return result
                  }
                  return lyric
                })
                
                return {
                  ...clip,
                  lyrics: updatedLyrics
                }
              }
              return clip
            })
            
            return {
              ...track,
              clips: updatedClips
            }
          }
          
          // Handle legacy multi-voice structure for backward compatibility
          if (track.instrument === 'vocals' && track.clips) {
            const updatedClips = track.clips.map((clip: any) => {
              if (clip.voices) {
                const updatedVoices = clip.voices.map((voice: any) => {
                  if (voice.lyrics) {
                    const updatedLyrics = voice.lyrics.map((lyric: any) => {
                      if (currentLineIndex < lyricsLines.length) {
                        const result = {
                          ...lyric,
                          text: lyricsLines[currentLineIndex]
                        }
                        currentLineIndex++
                        return result
                      }
                      return lyric
                    })
                    
                    return {
                      ...voice,
                      lyrics: updatedLyrics
                    }
                  }
                  return voice
                })
                
                return {
                  ...clip,
                  voices: updatedVoices
                }
              }
              return clip
            })
            
            return {
              ...track,
              clips: updatedClips
            }
          }
          return track
        })
        
        return {
          ...structure,
          tracks: updatedTracks
        }
      }
      
      songStructure = updateClipsWithLyrics(songStructure, songStructure.lyrics)
      console.log('Synchronized clips with song-level lyrics in song structure changes')
    }
    
    // Load the new song structure into the audio store
    audioStore.loadSongStructure(songStructure)
    
    // Force multiple UI refresh cycles to ensure all components reflect the changes
    await nextTick()
    await new Promise(resolve => setTimeout(resolve, 100)) // Small delay for DOM updates
    await nextTick()
    
    // Trigger reactive updates by touching relevant reactive properties
    if (songStructure.tracks && songStructure.tracks.length > 0) {
      // Select the first track to trigger UI updates
      audioStore.selectTrack(songStructure.tracks[0].id)
      await nextTick()
      
      // Clear selection to show all tracks
      audioStore.selectTrack(null)
    }
    
    // Count the changes that were applied
    const trackCount = songStructure.tracks?.length || 0
    const clipCount = songStructure.tracks?.reduce((total: number, track: any) => 
      total + (track.clips?.length || 0), 0) || 0
    
    // Notify user that changes were applied with detailed info
    const confirmationMessage = `✅ **Changes Applied Successfully!**

The AI suggestions have been applied to your song:
- **Tracks**: ${trackCount} track${trackCount !== 1 ? 's' : ''} 
- **Clips**: ${clipCount} clip${clipCount !== 1 ? 's' : ''}
- **Tempo**: ${songStructure.tempo || 120} BPM  
- **Key**: ${songStructure.key || 'C'}
- **Duration**: ${songStructure.duration || 0} bars

Your timeline and track visualization have been updated. You can now see the new structure in the editor!

${trackCount > 0 ? '🎼 **Tip**: You can now play, edit, or further modify these tracks using the timeline controls.' : ''}`
    
    // Add confirmation message to chat
    aiStore.addMessage('assistant', confirmationMessage)
    
    // Scroll to show the confirmation
    await nextTick()
    scrollToBottom()
    
  } catch (error) {
    console.error('Failed to apply song structure changes:', error)
    
    const errorMessage = `❌ **Failed to Apply Changes**

There was an error applying the AI suggestions to your song. Please try again or check the browser console for more details.

Error: ${error instanceof Error ? error.message : 'Unknown error'}`
    
    aiStore.addMessage('assistant', errorMessage)
  }
}

const addChordProgression = (type: string, suggestedInstrument?: string) => {
  // Get the best available instrument from AI suggestion or use a chord-capable fallback
  const instrument = suggestedInstrument ? 
    getAvailableInstrument(suggestedInstrument, 'piano') : 
    getAvailableInstrument('piano', 'piano')
  
  const trackId = audioStore.addTrack(`${type.charAt(0).toUpperCase() + type.slice(1)} Chords`, instrument)
  if (trackId) {
    // Get instrument type for proper clip creation
    const { type: clipType } = getInstrumentTypeAndCategory(instrument)
    
    // Add chord clips based on type
    const chordDuration = 4
    for (let i = 0; i < 4; i++) {
      audioStore.addClip(trackId, {
        startTime: i * chordDuration,
        duration: chordDuration,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        volume: 0.7,
        effects: { 
          reverb: 0.2, 
          delay: 0, 
          distortion: 0,
          pitchShift: 0,
          chorus: 0,
          filter: 0,
          bitcrush: 0
        }
      })
    }
    
    sendMessage(`✅ Added ${type} chord progression track with ${instrument}! The chords are now in your timeline.`)
  }
}

const addDrumPattern = (genre: string = 'house', elements: string[] = [], pattern?: string, detailed?: boolean, implementation?: string[]) => {
  // Get the best available drum instrument
  const instrument = getAvailableInstrument('drums', 'drums')
  
  const patternName = pattern === 'backbeat' ? 'Backbeat' : genre.charAt(0).toUpperCase() + genre.slice(1)
  const elementsText = elements.length > 0 ? ` (${elements.join(', ')})` : ''
  const trackName = detailed ? 'AI-Suggested Drum Pattern' : `${patternName} Drums${elementsText}`
  const trackId = audioStore.addTrack(trackName, instrument)
  
  if (trackId) {
    // Get instrument type for proper clip creation
    const { type: clipType } = getInstrumentTypeAndCategory(instrument)
    
    // Add drum pattern clips with different settings based on elements
    const clipCount = pattern === 'backbeat' || detailed ? 4 : 8
    const clipDuration = pattern === 'backbeat' || detailed ? 4 : 2
    
    for (let i = 0; i < clipCount; i++) {
      audioStore.addClip(trackId, {
        startTime: i * clipDuration,
        duration: clipDuration,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        volume: 0.8,
        effects: { 
          reverb: 0.1, 
          delay: 0, 
          distortion: 0,
          pitchShift: 0,
          chorus: 0,
          filter: 0,
          bitcrush: 0
        }
      })
    }
    
    let message = ''
    if (detailed && implementation && implementation.length > 0) {
      message = `🥁 Added detailed drum pattern with ${instrument} following AI suggestions!\n\nImplemented elements:\n${implementation.slice(0, 3).map(step => `• ${step.replace(/^\d+\.\s*/, '').replace(/^-\s*/, '')}`).join('\n')}\n\nYour backbeat foundation is ready!`
    } else if (elements.length > 0) {
      message = `🥁 Added ${patternName.toLowerCase()} drum pattern with ${instrument} featuring ${elements.join(', ')}! Your beat is ready to groove.`
    } else {
      message = `🥁 Added ${patternName.toLowerCase()} drum pattern with ${instrument}! Your beat is ready to groove.`
    }
    
    sendMessage(message)
  }
}

const addBassTrack = (type?: string) => {
  const bassType = type || 'synth'
  
  // Get the best available bass instrument
  const instrument = getAvailableInstrument('bass', 'bass')
  
  const trackName = `${bassType.charAt(0).toUpperCase() + bassType.slice(1)} Bass`
  const trackId = audioStore.addTrack(trackName, instrument)
  
  if (trackId) {
    // Get instrument type for proper clip creation
    const { type: clipType } = getInstrumentTypeAndCategory(instrument)
    
    // Add bass clips with different settings based on type
    const effects = bassType === 'sub' 
      ? { 
          reverb: 0, 
          delay: 0, 
          distortion: 0,
          pitchShift: 0,
          chorus: 0,
          filter: 0,
          bitcrush: 0
        }
      : bassType === 'electric'
        ? { 
            reverb: 0.1, 
            delay: 0, 
            distortion: 0.2,
            pitchShift: 0,
            chorus: 0,
            filter: 0,
            bitcrush: 0
          }
        : { 
            reverb: 0, 
            delay: 0, 
            distortion: 0.1,
            pitchShift: 0,
            chorus: 0,
            filter: 0,
            bitcrush: 0
          }
    
    for (let i = 0; i < 4; i++) {
      audioStore.addClip(trackId, {
        startTime: i * 4,
        duration: 4,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        volume: bassType === 'sub' ? 0.9 : 0.8,
        effects
      })
    }
    
    sendMessage(`🎸 Added ${bassType} bass track with ${instrument} and fuller sound settings! Check out that low-end presence.`)
  }
}

const addVocalTrack = () => {
  // Get the best available vocal instrument, fallback to vocals
  const instrument = getAvailableInstrument('vocals', 'vocals')
  
  const trackId = audioStore.addTrack('Vocals', instrument)
  if (trackId) {
    audioStore.updateTrack(trackId, {
      effects: { 
        reverb: 0.3, 
        delay: 0.2, 
        distortion: 0, 
        pitchShift: 0, 
        chorus: 0, 
        filter: 0, 
        bitcrush: 0 
      }
    })
    
    sendMessage(`🎤 Added vocal track with ${instrument} and professional effects chain! Ready for recording.`)
  }
}

const addMelodyTrack = (suggestedInstrument: string = 'synth') => {
  try {
    // Get the best available instrument from AI suggestion
    const instrument = getAvailableInstrument(suggestedInstrument, 'synth')
    
    const trackId = audioStore.addTrack('Melody', instrument)
    if (trackId) {
      // Get instrument type for proper clip creation
      const { type: clipType } = getInstrumentTypeAndCategory(instrument)
      
      // Add a basic melody clip
      audioStore.addClip(trackId, {
        startTime: 0,
        duration: 16,
        type: (clipType === 'sample' ? 'sample' : 'synth') as 'synth' | 'sample',
        instrument: instrument,
        notes: ['C4', 'E4', 'G4', 'C5'],
        volume: 0.7,
        effects: { 
          reverb: 0.2, 
          delay: 0, 
          distortion: 0,
          pitchShift: 0,
          chorus: 0,
          filter: 0,
          bitcrush: 0
        }
      })
      sendMessage(`🎵 ${instrument} melody track added with a basic pattern!`)
    }
  } catch (error) {
    console.error('Error adding melody track:', error)
    sendMessage('❌ Error adding melody track.')
  }
}

const adjustTempo = (targetBpm?: number) => {
  try {
    const currentTempo = audioStore.songStructure.tempo || 120
    const newTempo = targetBpm || (currentTempo + 10) // Use target BPM or increase by 10
    audioStore.songStructure.tempo = newTempo
    
    const message = targetBpm 
      ? `🥁 Tempo set to ${newTempo} BPM as suggested!`
      : `🥁 Tempo adjusted to ${newTempo} BPM!`
    
    sendMessage(message)
  } catch (error) {
    console.error('Error adjusting tempo:', error)
    sendMessage('❌ Error adjusting tempo.')
  }
}

const applyEffects = (specificEffects?: string[]) => {
  try {
    const tracks = audioStore.songStructure.tracks
    if (tracks.length > 0) {
      tracks.forEach(track => {
        if (specificEffects && specificEffects.length > 0) {
          // Apply specific effects mentioned by AI
          const effects: any = { reverb: 0, delay: 0, distortion: 0, compression: 0 }
          
          specificEffects.forEach(effect => {
            switch (effect) {
              case 'reverb':
                effects.reverb = track.instrument === 'vocals' ? 0.3 : 0.2
                break
              case 'delay':
                effects.delay = track.instrument === 'vocals' ? 0.2 : 0.1
                break
              case 'distortion':
                effects.distortion = track.instrument === 'drums' ? 0.1 : 0.05
                break
              case 'compression':
                effects.compression = 0.3
                break
            }
          })
          
          track.effects = effects
        } else {
          // Apply default effects
          if (track.instrument === 'vocals') {
            track.effects = { 
              reverb: 0.3, 
              delay: 0.2, 
              distortion: 0, 
              pitchShift: 0, 
              chorus: 0, 
              filter: 0, 
              bitcrush: 0 
            }
          } else if (track.instrument === 'drums') {
            track.effects = { 
              reverb: 0.1, 
              delay: 0, 
              distortion: 0.1, 
              pitchShift: 0, 
              chorus: 0, 
              filter: 0, 
              bitcrush: 0 
            }
          } else {
            track.effects = { 
              reverb: 0.2, 
              delay: 0.1, 
              distortion: 0, 
              pitchShift: 0, 
              chorus: 0, 
              filter: 0, 
              bitcrush: 0 
            }
          }
        }
      })
      
      const message = specificEffects && specificEffects.length > 0
        ? `✨ Applied ${specificEffects.join(', ')} effects to your tracks as suggested! Your mix sounds more polished now.`
        : '✨ Effects applied to your tracks! Your mix sounds more polished now.'
      
      sendMessage(message)
    } else {
      sendMessage('ℹ️ No tracks to apply effects to. Add some tracks first!')
    }
  } catch (error) {
    console.error('Error applying effects:', error)
    sendMessage('❌ Error applying effects.')
  }
}

const exportTrack = () => {
  try {
    // For now, just show a message - you can implement actual export later
    sendMessage('📁 Export feature coming soon! Your track structure is ready for rendering.')
  } catch (error) {
    console.error('Error exporting track:', error)
    sendMessage('❌ Error exporting track.')
  }
}

const playPreview = () => {
  try {
    if (audioStore.songStructure.tracks.length > 0) {
      // Toggle playback
      if (audioStore.isPlaying) {
        audioStore.stop()
        sendMessage('⏹️ Playback stopped.')
      } else {
        audioStore.play()
        sendMessage('▶️ Playing your track! Listen to your creation.')
      }
    } else {
      sendMessage('ℹ️ No tracks to play. Add some music first!')
    }
  } catch (error) {
    console.error('Error playing preview:', error)
    sendMessage('❌ Error playing preview.')
  }
}

const addLyricsFromJSON = (lyricsData: any) => {
  try {
    if (!lyricsData || !lyricsData.json) {
      console.warn('No lyrics JSON data provided')
      sendMessage('❌ No lyrics data to add. Please generate lyrics first.')
      return
    }

    const lyricsJSON = lyricsData.json
    console.log('Adding lyrics from JSON:', lyricsJSON)

    // Extract lyrics text for the lyrics panel
    let extractedLyricsText = ''

    // Check if it's a complete track or just a clip
    if (lyricsJSON.clips && lyricsJSON.instrument === 'vocals') {
      // It's a complete track - add the entire track
      const trackId = audioStore.addTrack(lyricsJSON.name || 'Lyrics & Vocals', 'vocals')
      if (trackId) {
        // Update track properties
        audioStore.updateTrack(trackId, {
          volume: lyricsJSON.volume || 0.8,
          pan: lyricsJSON.pan || 0,
          effects: lyricsJSON.effects || { reverb: 0, delay: 0, distortion: 0 }
        })

        // Add all clips from the track and extract lyrics
        for (const clip of lyricsJSON.clips) {
          audioStore.addClip(trackId, {
            ...clip,
            trackId: trackId
          })
          
          // Extract lyrics text from clip with enhanced structure support
          if (clip.voices) {
            for (const voice of clip.voices) {
              if (voice.lyrics) {
                for (const lyric of voice.lyrics) {
                  if (lyric.text) {
                    extractedLyricsText += lyric.text + ' '
                    
                    // Log enhanced structure if available
                    if (lyric.syllables) {
                      console.log('Syllable breakdown:', lyric.syllables)
                    }
                    if (lyric.phonemes) {
                      console.log('Phonemes:', lyric.phonemes)
                    }
                  }
                }
                extractedLyricsText += '\n'
              }
            }
          }
        }

        sendMessage(`🎤 Added complete lyrics track with ${lyricsJSON.clips.length} clips! Your vocals are ready to shine.`)
      }
    } else if (lyricsJSON.type === 'lyrics' && lyricsJSON.voices) {
      // It's a single clip - find or create vocals track
      let vocalsTrack = audioStore.songStructure.tracks.find(t => t.instrument === 'vocals')
      let trackId = vocalsTrack?.id

      if (!trackId) {
        // Create new vocals track
        trackId = audioStore.addTrack('Lyrics & Vocals', 'vocals')
        if (trackId) {
          audioStore.updateTrack(trackId, {
            volume: 0.8,
            pan: 0,
            effects: { 
              reverb: 0, 
              delay: 0, 
              distortion: 0, 
              pitchShift: 0, 
              chorus: 0, 
              filter: 0, 
              bitcrush: 0 
            }
          })
        }
      }

      if (trackId) {
        // Add the lyrics clip
        audioStore.addClip(trackId, {
          ...lyricsJSON,
          trackId: trackId
        })

        // Extract lyrics text from single clip with enhanced structure support
        if (lyricsJSON.voices) {
          for (const voice of lyricsJSON.voices) {
            if (voice.lyrics) {
              for (const lyric of voice.lyrics) {
                if (lyric.text) {
                  extractedLyricsText += lyric.text + ' '
                  
                  // Log enhanced structure if available
                  if (lyric.syllables) {
                    console.log('Syllable breakdown for:', lyric.text, lyric.syllables)
                  }
                  if (lyric.phonemes) {
                    console.log('Phonemes for:', lyric.text, lyric.phonemes)
                  }
                }
              }
              extractedLyricsText += '\n'
            }
          }
        }

        const voiceCount = lyricsJSON.voices?.length || 1
        const lyricsCount = lyricsJSON.voices?.reduce((total: number, voice: any) => total + (voice.lyrics?.length || 0), 0) || 0
        
        sendMessage(`🎵 Added lyrics clip with ${voiceCount} voice(s) and ${lyricsCount} lyric fragments! Your song has words now.`)
      }
    } else {
      console.warn('Unknown lyrics JSON structure:', lyricsJSON)
      sendMessage('❌ Unknown lyrics format. Please check the JSON structure.')
    }

    // Update the song structure with extracted lyrics text for the lyrics panel
    if (extractedLyricsText.trim()) {
      // Create a helper function to update clips with synchronized lyrics
      const updateClipsWithLyrics = (structure: any, lyrics: string) => {
        if (!structure.tracks) return structure
        
        const lyricsLines = lyrics.split('\n').filter(line => line.trim().length > 0)
        let currentLineIndex = 0
        
        const updatedTracks = structure.tracks.map((track: any) => {
          if (track.instrument === 'vocals' && track.clips) {
            const updatedClips = track.clips.map((clip: any) => {
              if (clip.voices) {
                const updatedVoices = clip.voices.map((voice: any) => {
                  if (voice.lyrics) {
                    const updatedLyrics = voice.lyrics.map((lyric: any) => {
                      if (currentLineIndex < lyricsLines.length) {
                        const result = {
                          ...lyric,
                          text: lyricsLines[currentLineIndex]
                        }
                        currentLineIndex++
                        return result
                      }
                      return lyric
                    })
                    
                    return {
                      ...voice,
                      lyrics: updatedLyrics
                    }
                  }
                  return voice
                })
                
                return {
                  ...clip,
                  voices: updatedVoices
                }
              }
              return clip
            })
            
            return {
              ...track,
              clips: updatedClips
            }
          }
          return track
        })
        
        return {
          ...structure,
          tracks: updatedTracks
        }
      }
      
      let updatedStructure = {
        ...audioStore.songStructure,
        lyrics: extractedLyricsText.trim()
      }
      
      // Synchronize lyrics between song level and clips
      updatedStructure = updateClipsWithLyrics(updatedStructure, extractedLyricsText.trim())
      
      audioStore.loadSongStructure(updatedStructure)
      console.log('Lyrics text added to song structure and synchronized with clips')
    }

  } catch (error) {
    console.error('Error adding lyrics from JSON:', error)
    sendMessage(`❌ Error adding lyrics: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

const createNewProject = () => {
  if (confirm('Create a new project? This will clear your current work.')) {
    // Reset the audio store
    audioStore.songStructure.tracks = []
    audioStore.songStructure.name = 'New Project'
    audioStore.songStructure.updatedAt = new Date().toISOString()
    
    sendMessage(`🎵 New project created! Ready to make some music.`)
  }
}

const analyzeProject = () => {
  const tracks = audioStore.songStructure.tracks
  const analysis = `📊 **Project Analysis:**

**Tracks**: ${tracks.length}
**Tempo**: ${audioStore.songStructure.tempo} BPM
**Key**: ${audioStore.songStructure.key}
**Duration**: ${audioStore.songStructure.duration} bars

**Instruments**: ${tracks.map(t => t.instrument).join(', ') || 'None'}

${tracks.length === 0 ? '💡 **Suggestion**: Start by adding a drum track for rhythm!' : ''}
${tracks.length < 3 ? '💡 **Suggestion**: Consider adding bass and melody instruments!' : ''}
${tracks.length > 8 ? '💡 **Suggestion**: You have many tracks - focus on mixing and arrangement!' : ''}`

  sendMessage(analysis)
}

const clearChat = () => {
  if (confirm('Clear all chat messages?')) {
    aiStore.clearMessages()
  }
}

const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendCurrentMessage()
  }
  
  // Voice input shortcut: Ctrl + ; (semicolon)
  if (event.ctrlKey && event.key === ';') {
    event.preventDefault()
    toggleVoiceInput()
  }
  
  // Language cycling shortcut: Ctrl + L
  if (event.ctrlKey && event.key === 'l') {
    event.preventDefault()
    cycleLanguage()
  }
}

const adjustTextareaHeight = () => {
  const textarea = messageInput.value
  if (textarea) {
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 260) + 'px' // Match max-height
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatMessage = (content: string | undefined): string => {
  // Handle undefined or null content
  if (!content || typeof content !== 'string') {
    return ''
  }
  
  // First handle JSON code blocks (```json...``` or `json...) and detect if they contain lyrics
  content = content.replace(/```json\n?([\s\S]*?)```/g, (_, jsonContent) => {
    const uniqueId = 'json-' + Math.random().toString(36).substr(2, 9)
    
    try {
      const jsonData = JSON.parse(jsonContent.trim())
      
      // Check if this is lyrics JSON
      if (isLyricsJSON(jsonData)) {
        console.log('✅ Detected lyrics JSON in formatMessage:', jsonData)
        // Store the lyrics JSON for the Apply button
        currentLyricsJSON.value = jsonData
        
        const formattedLyrics = formatLyricsFromJSON(jsonData)
        
        return `<div class="lyrics-display">
          <div class="lyrics-header">
            <span class="lyrics-icon">🎤</span>
            <span class="lyrics-title">Generated Lyrics</span>
          </div>
          <div class="lyrics-content">
            ${formattedLyrics}
          </div>
        </div>`
      }
    } catch (error) {
      // If parsing fails, fall back to regular JSON display
    }
    
    // Regular JSON display (non-lyrics) - no action buttons
    return `<div class="json-code-block">
      <div class="json-header" onclick="toggleJsonBlock('${uniqueId}')">
        <span class="json-label">JSON Structure</span>
        <span class="json-toggle" id="toggle-${uniqueId}">›</span>
      </div>
      <pre class="json-content" id="${uniqueId}" style="display: none;"><code>${jsonContent.trim()}</code></pre>
    </div>`
  })
  
  // Also handle single backtick JSON format (`json...)
  content = content.replace(/`json\s*([\s\S]*?)(?=`[^`]|$)/g, (_, jsonContent) => {
    const uniqueId = 'json-' + Math.random().toString(36).substr(2, 9)
    
    // Remove trailing backtick if present
    jsonContent = jsonContent.replace(/`$/, '')
    
    try {
      // If JSON appears to be truncated, try to parse what we have
      if (!jsonContent.trim().endsWith('}')) {
        console.log('⚠️ Single backtick JSON appears truncated, attempting to parse partial JSON')
        const lastBrace = jsonContent.lastIndexOf('}')
        if (lastBrace > 0) {
          jsonContent = jsonContent.substring(0, lastBrace + 1)
        }
      }
      
      const jsonData = JSON.parse(jsonContent.trim())
      
      // Check if this is lyrics JSON
      if (isLyricsJSON(jsonData)) {
        console.log('✅ Detected lyrics JSON in single backtick format:', jsonData)
        currentLyricsJSON.value = jsonData
        
        const formattedLyrics = formatLyricsFromJSON(jsonData)
        
        return `<div class="lyrics-display">
          <div class="lyrics-header">
            <span class="lyrics-icon">🎤</span>
            <span class="lyrics-title">Generated Lyrics</span>
          </div>
          <div class="lyrics-content">
            ${formattedLyrics}
          </div>
        </div>`
      }
    } catch (error: any) {
      console.log('❌ Single backtick JSON parse error:', error.message)
    }
    
    // Regular JSON display (non-lyrics)
    return `<div class="json-code-block">
      <div class="json-header" onclick="toggleJsonBlock('${uniqueId}')">
        <span class="json-label">JSON Structure</span>
        <span class="json-toggle" id="toggle-${uniqueId}">›</span>
      </div>
      <pre class="json-content" id="${uniqueId}" style="display: none;"><code>${jsonContent.trim()}</code></pre>
    </div>`
  })
  
  // Handle regular code blocks
  content = content.replace(/```(\w+)?\n?([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="code-block ${lang || ''}"><code>${code.trim()}</code></pre>`
  })
  
  // Convert other markdown-like formatting to HTML
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

const isLyricsJSON = (jsonData: any): boolean => {
  const result = (
    jsonData.instrument === 'vocals' || 
    jsonData.type === 'lyrics' || 
    jsonData.voices || 
    (jsonData.clips && jsonData.clips.some && jsonData.clips.some((c: any) => c.voices))
  )
  
  console.log('🔍 isLyricsJSON check:', {
    hasInstrumentVocals: jsonData.instrument === 'vocals',
    hasTypeLyrics: jsonData.type === 'lyrics', 
    hasVoices: !!jsonData.voices,
    hasClipsWithVoices: !!(jsonData.clips && jsonData.clips.some && jsonData.clips.some((c: any) => c.voices)),
    result: result,
    jsonKeys: Object.keys(jsonData || {})
  })
  
  return result
}

// Function to detect lyrics in text format and convert to JSON
const detectAndConvertTextLyrics = (messageContent: string): boolean => {
  // Look for lyrics patterns in text
  const lyricsPatterns = [
    /###?\s*(?:verse|chorus|bridge|pre-?chorus|outro|intro)/i,
    /####?\s*(?:verse|chorus|bridge|pre-?chorus|outro|intro)/i,
    /(?:verse|chorus|bridge|pre-?chorus|outro|intro)\s*\d*/i,
    /generated\s+lyrics/i,
    /song\s+structure/i
  ]
  
  const hasLyricsPattern = lyricsPatterns.some(pattern => pattern.test(messageContent))
  
  if (hasLyricsPattern) {
    // Extract only actual lyrics, not AI explanations or metadata
    const lines = messageContent.split('\n')
    const lyricsLines = []
    let inLyricsSection = false
    
    for (const line of lines) {
      const trimmed = line.trim()
      
      // Skip empty lines
      if (!trimmed) continue
      
      // Skip AI explanatory text and instructions
      if (trimmed.toLowerCase().includes('here\'s') ||
          trimmed.toLowerCase().includes('i\'ll') ||
          trimmed.toLowerCase().includes('certainly') ||
          trimmed.toLowerCase().includes('to create') ||
          trimmed.toLowerCase().includes('inspired by') ||
          trimmed.toLowerCase().includes('style') ||
          trimmed.toLowerCase().includes('provide') ||
          trimmed.toLowerCase().includes('format') ||
          trimmed.toLowerCase().includes('view json') ||
          trimmed.toLowerCase().includes('generated lyrics')) {
        continue
      }
      
      // Detect section headers
      if (trimmed.startsWith('#') || /^(verse|chorus|bridge|pre-?chorus|outro|intro)/i.test(trimmed)) {
        inLyricsSection = true
        continue // Skip the header itself
      }
      
      // If we're in a lyrics section and this looks like actual lyrics
      if (inLyricsSection && 
          trimmed.length > 0 && 
          !trimmed.startsWith('#') &&
          !trimmed.startsWith('```') &&
          !/^(verse|chorus|bridge|pre-?chorus|outro|intro)/i.test(trimmed)) {
        
        // This looks like actual lyrics content
        lyricsLines.push(trimmed)
      }
    }
    
    if (lyricsLines.length > 0) {
      // Create JSON structure
      const lyricsJSON = {
        instrument: 'vocals',
        type: 'lyrics',
        voices: [
          {
            voice_id: 'lead',
            lyrics: lyricsLines.map((line, index) => ({
              text: line.trim(),
              start: index * 4, // 4 seconds per line
              duration: 4,
              syllables: []
            }))
          }
        ]
      }
      
      // Set the current lyrics JSON for action buttons
      currentLyricsJSON.value = lyricsJSON
      return true
    }
  }
  
  return false
}

const formatLyricsFromJSON = (jsonData: any): string => {
  let formattedLyrics = ''
  
  console.log('🎵 formatLyricsFromJSON called with:', jsonData)
  
  try {
    // Handle different JSON structures
    if (jsonData.clips && Array.isArray(jsonData.clips)) {
      // Multiple clips structure
      jsonData.clips.forEach((clip: any, clipIndex: number) => {
        if (clip.voices) {
          formattedLyrics += `<div class="lyrics-section">`
          if (jsonData.clips.length > 1) {
            formattedLyrics += `<div class="lyrics-section-title">Section ${clipIndex + 1}</div>`
          }
          
          clip.voices.forEach((voice: any, voiceIndex: number) => {
            if (voice.lyrics && voice.lyrics.length > 0) {
              if (clip.voices.length > 1) {
                formattedLyrics += `<div class="lyrics-voice">Voice ${voiceIndex + 1} (${voice.voice_id || 'Unknown'})</div>`
              }
              
              const lyricsLine = voice.lyrics.map((lyric: any) => lyric.text || '').join(' ')
              formattedLyrics += `<div class="lyrics-line">${lyricsLine}</div>`
              
              // Add syllable breakdown if available
              if (voice.lyrics.some((l: any) => l.syllables && l.syllables.length > 0)) {
                formattedLyrics += `<div class="lyrics-syllables">`
                voice.lyrics.forEach((lyric: any) => {
                  if (lyric.syllables && lyric.syllables.length > 0) {
                    const syllableText = lyric.syllables.map((s: any) => s.t || s.text || s).join('-')
                    formattedLyrics += `<span class="syllable-group">${lyric.text}: ${syllableText}</span> `
                  }
                })
                formattedLyrics += `</div>`
              }
            }
          })
          formattedLyrics += `</div>`
        }
      })
    } else if (jsonData.voices) {
      // Single clip structure
      jsonData.voices.forEach((voice: any, voiceIndex: number) => {
        if (voice.lyrics && voice.lyrics.length > 0) {
          if (jsonData.voices.length > 1) {
            formattedLyrics += `<div class="lyrics-voice">Voice ${voiceIndex + 1} (${voice.voice_id || 'Unknown'})</div>`
          }
          
          const lyricsLine = voice.lyrics.map((lyric: any) => lyric.text || '').join(' ')
          formattedLyrics += `<div class="lyrics-line">${lyricsLine}</div>`
          
          // Add syllable breakdown if available
          if (voice.lyrics.some((l: any) => l.syllables && l.syllables.length > 0)) {
            formattedLyrics += `<div class="lyrics-syllables">`
            voice.lyrics.forEach((lyric: any) => {
              if (lyric.syllables && lyric.syllables.length > 0) {
                const syllableText = lyric.syllables.map((s: any) => s.t || s.text || s).join('-')
                formattedLyrics += `<span class="syllable-group">${lyric.text}: ${syllableText}</span> `
              }
            })
            formattedLyrics += `</div>`
          }
        }
      })
    }
  } catch (error) {
    console.warn('Error formatting lyrics:', error)
    formattedLyrics = '<div class="lyrics-error">Error formatting lyrics</div>'
  }
  
  // Store the current lyrics JSON for actions (will show buttons in footer)
  currentLyricsJSON.value = jsonData
  
  // Add collapsible JSON section
  const jsonId = 'lyrics-json-' + Math.random().toString(36).substr(2, 9)
  const jsonSection = `
    <div class="lyrics-json-section">
      <div class="lyrics-json-header" onclick="toggleJsonBlock('${jsonId}')">
        <span class="lyrics-json-label">📄 View JSON Structure</span>
        <span class="lyrics-json-toggle" id="toggle-${jsonId}">›</span>
      </div>
      <pre class="lyrics-json-content" id="${jsonId}" style="display: none;"><code>${JSON.stringify(jsonData, null, 2)}</code></pre>
    </div>
  `
  
  const finalLyrics = formattedLyrics || '<div class="lyrics-empty">No lyrics content found</div>'
  console.log('🎵 formatLyricsFromJSON result:', { formattedLyrics, finalLyrics })
  return finalLyrics + jsonSection
}

const generateActionButtonsFromJSON = (jsonContent: string): string => {
  try {
    const jsonData = JSON.parse(jsonContent)
    const buttons: string[] = []
    
    // Detect different types of JSON structures and generate appropriate action buttons
    
    // Complete song structure
    if (jsonData.tracks && Array.isArray(jsonData.tracks)) {
      buttons.push(`<button class="json-action-btn" onclick="applySongStructureFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎵</span> Apply Song Structure
      </button>`)
    }
    
    // Single track
    if (jsonData.name && jsonData.instrument && (jsonData.clips || jsonData.type)) {
      const instrument = jsonData.instrument
      const trackName = jsonData.name
      
      buttons.push(`<button class="json-action-btn" onclick="addTrackFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">${getInstrumentIcon(instrument)}</span> Add ${trackName} Track
      </button>`)
    }
    
    // Chord progression
    if (jsonData.chords || (jsonData.pattern && jsonData.pattern.some && jsonData.pattern.some((p: any) => p.chord))) {
      buttons.push(`<button class="json-action-btn" onclick="addChordProgressionFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎹</span> Add Chord Progression
      </button>`)
    }
    
    // Drum pattern
    if (jsonData.instrument === 'drums' || jsonData.type === 'drum_pattern' || 
        (jsonData.pattern && jsonData.pattern.some && jsonData.pattern.some((p: any) => p.drum || p.note === 'kick' || p.note === 'snare'))) {
      buttons.push(`<button class="json-action-btn" onclick="addDrumPatternFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🥁</span> Add Drum Pattern
      </button>`)
    }
    
    // Bass line
    if (jsonData.instrument === 'bass' || jsonData.type === 'bass_line') {
      buttons.push(`<button class="json-action-btn" onclick="addBassLineFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎸</span> Add Bass Line
      </button>`)
    }
    
    // Melody/lead
    if (jsonData.instrument === 'lead' || jsonData.instrument === 'synth' || jsonData.type === 'melody') {
      buttons.push(`<button class="json-action-btn" onclick="addMelodyFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎼</span> Add Melody
      </button>`)
    }
    
    // Lyrics/vocals - Merged action for vocal track creation and song integration
    if (jsonData.instrument === 'vocals' || jsonData.type === 'lyrics' || jsonData.voices || 
        (jsonData.clips && jsonData.clips.some && jsonData.clips.some((c: any) => c.voices))) {
      
      // Single comprehensive action that creates track AND applies to song structure
      buttons.push(`<button class="json-action-btn primary" onclick="addLyricsFromJSONAction('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎤</span> Add Vocal Track & Apply to Song
      </button>`)
    }
    
    // Effects configuration
    if (jsonData.effects && typeof jsonData.effects === 'object') {
      buttons.push(`<button class="json-action-btn" onclick="applyEffectsFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎛️</span> Apply Effects
      </button>`)
    }
    
    // Mix settings
    if (jsonData.mix || (jsonData.tracks && jsonData.tracks.some && jsonData.tracks.some((t: any) => t.volume !== undefined || t.pan !== undefined))) {
      buttons.push(`<button class="json-action-btn" onclick="applyMixFromJSON('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎚️</span> Apply Mix Settings
      </button>`)
    }
    
    return buttons.length > 0 ? `<div class="json-actions">${buttons.join('')}</div>` : ''
    
  } catch (error) {
    // If JSON parsing fails, don't show action buttons
    console.warn('Failed to parse JSON for action buttons:', error)
    return ''
  }
}

const getInstrumentIcon = (instrument: string): string => {
  const icons: Record<string, string> = {
    'piano': '🎹',
    'drums': '🥁',
    'bass': '🎸',
    'guitar': '🎸',
    'vocals': '🎤',
    'synth': '🎛️',
    'lead': '🎼',
    'pad': '🌊',
    'strings': '🎻',
    'brass': '🎺',
    'woodwind': '🎷',
    'percussion': '🥁',
    'organ': '⛪',
    'harp': '🪕'
  }
  return icons[instrument.toLowerCase()] || '🎵'
}

const formatTime = (date: Date): string => {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const attachFile = () => {
  console.log('Attach file clicked')
  
  // Create file input element if not exists
  if (!fileInput.value) {
    console.log('Creating new file input')
    const input = document.createElement('input')
    input.type = 'file'
    input.multiple = true
    input.accept = '.pdf,.png,.jpg,.jpeg,.tiff,.bmp,.svg,.gtp,.gpx,.gp5,.gp4,.ptb,.tef,.xml,.musicxml,.mxl,.mid,.midi,.abc,.ly,.txt,.tab'
    input.style.display = 'none'
    input.addEventListener('change', handleFileSelection)
    document.body.appendChild(input)
    fileInput.value = input
    console.log('File input created and added to DOM')
  }
  
  console.log('Clicking file input')
  fileInput.value?.click()
}

const handleFileSelection = async (event: Event) => {
  console.log('File selection event triggered', event)
  const input = event.target as HTMLInputElement
  const files = input.files
  
  console.log('Files selected:', files?.length, Array.from(files || []).map(f => f.name))
  
  if (!files || files.length === 0) {
    console.log('No files selected')
    return
  }
  
  // Validate files using ScoreService
  const validFiles: File[] = []
  const errors: string[] = []
  
  for (const file of Array.from(files)) {
    console.log('Validating file:', file.name)
    const validation = ScoreService.validateFile(file)
    
    console.log('Validation result:', validation)
    
    if (!validation.valid) {
      errors.push(`${file.name}: ${validation.error}`)
      continue
    }
    
    validFiles.push(file)
  }
  
  if (errors.length > 0) {
    console.warn('File validation errors:', errors)
    alert('File validation errors: ' + errors.join(', '))
  }
  
  if (validFiles.length === 0) {
    console.log('No valid files to upload')
    return
  }
  
  console.log('Valid files to upload:', validFiles.map(f => f.name))
  
  // Upload valid files
  await uploadScoreFiles(validFiles)
  
  // Reset input
  input.value = ''
}

const uploadScoreFiles = async (files: File[]) => {
  isUploading.value = true
  
  try {
    console.log('Uploading score files:', files.map(f => f.name))
    const result = await ScoreService.uploadScores(files)
    
    console.log('Upload result:', result)
    
    // Add uploaded scores to state
    uploadedScores.value.push(...result.results)
    
    console.log('Successfully uploaded score files:', result.results)
    console.log('Current uploaded scores:', uploadedScores.value)
    
  } catch (error) {
    console.error('Score upload error:', error)
    // Show error to user
    alert(`Failed to upload scores: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    isUploading.value = false
  }
}

const sendMessageWithScores = async (message: string, scoreFileIds: string[]) => {
  console.log('[AIChat] sendMessageWithScores called:', {
    message: message.substring(0, 100) + (message.length > 100 ? '...' : ''),
    scoreFileIds,
    provider: selectedProvider.value.toLowerCase(),
    model: selectedModel.value
  })

  try {
    const result = await ScoreService.chatWithScores(
      message,
      scoreFileIds,
      selectedProvider.value.toLowerCase(),
      selectedModel.value,
      {
        tracks: audioStore.songStructure.tracks,
        tempo: audioStore.songStructure.tempo,
        key: audioStore.songStructure.key,
        song_structure: audioStore.songStructure
      }
    )
    
    console.log('[AIChat] Score-aware response received:', {
      hasResult: !!result,
      hasResponse: !!result?.response,
      hasContent: !!result?.content,
      responseLength: result?.response?.length || result?.content?.length || 0
    })
    
    return result.response || result.content
    
  } catch (error) {
    console.error('[AIChat] Error sending message with scores:', error)
    console.log('[AIChat] Falling back to regular AI message')
    // Fallback to regular message if score-aware fails
    return await aiStore.sendMessage(message)
  }
}

const removeUploadedScore = (fileId: string) => {
  uploadedScores.value = uploadedScores.value.filter(score => score.file_id !== fileId)
}

// Voice recognition functions
const initializeSpeechRecognition = () => {
  // Check if speech recognition is supported
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  
  if (!SpeechRecognition) {
    speechSupported.value = false
    console.warn('Speech recognition not supported in this browser')
    return
  }
  
  speechSupported.value = true
  recognition.value = new SpeechRecognition()
  
  // Configure recognition for single utterance to prevent duplicates
  recognition.value.continuous = false
  recognition.value.interimResults = true
  recognition.value.lang = currentLanguage.value
  recognition.value.maxAlternatives = 1 // Reduced to prevent confusion
  
  // State tracking for preventing duplicates (closure variables)
  let lastProcessedResultIndex = -1
  let baseTextBeforeRecognition = ''
  
  // Expose reset function for external access
  ;(recognition.value as any).resetTracking = () => {
    lastProcessedResultIndex = -1
    baseTextBeforeRecognition = currentMessage.value.trim()
  }
  
  // Handle results
  recognition.value.onresult = (event: any) => {
    let finalTranscript = ''
    let interimTranscript = ''
    
    // Process only new results to avoid duplicates
    for (let i = Math.max(event.resultIndex, lastProcessedResultIndex + 1); i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript
      
      if (event.results[i].isFinal) {
        finalTranscript += transcript
        lastProcessedResultIndex = i
      } else {
        interimTranscript += transcript
      }
    }
    
    // Handle interim results (preview)
    if (interimTranscript && !finalTranscript) {
      // Show interim results by appending to base text
      const currentText = baseTextBeforeRecognition
      currentMessage.value = currentText + (currentText ? ' ' : '') + interimTranscript
    }
    
    // Handle final results (commit)
    if (finalTranscript) {
      const trimmed = finalTranscript.trim()
      if (trimmed) {
        // Build the expected new text
        const newText = baseTextBeforeRecognition + (baseTextBeforeRecognition ? ' ' : '') + trimmed
        const currentText = currentMessage.value.trim()
        
        // Only update if the new text is different and doesn't create duplicates
        const words = trimmed.split(' ')
        const currentWords = currentText.split(' ')
        
        // Check if these words are already at the end of current text
        let isDuplicate = false
        if (currentWords.length >= words.length) {
          const lastWords = currentWords.slice(-words.length)
          isDuplicate = words.every((word, index) => 
            lastWords[index] && lastWords[index].toLowerCase() === word.toLowerCase()
          )
        }
        
        if (!isDuplicate && newText !== currentText) {
          currentMessage.value = newText
          baseTextBeforeRecognition = newText // Update base for next recognition
        }
        
        // Check recognition confidence
        const result = event.results[event.results.length - 1]
        if (result && result[0]) {
          const confidence = result[0].confidence
          const currentLangName = supportedLanguages.value.find(l => l.code === currentLanguage.value)?.name
          
          // Log recognition confidence for debugging
          console.log(`Speech recognized in ${currentLangName}: "${trimmed}" (confidence: ${confidence?.toFixed(2) || 'unknown'})`)
          
          // If confidence is very low, suggest language detection
          if (confidence && confidence < 0.3) {
            console.warn(`Low confidence (${confidence.toFixed(2)}) - consider checking language setting`)
          }
        }
        
        // Adjust textarea height after adding text
        nextTick(() => {
          adjustTextareaHeight()
        })
      }
    }
  }
  
  // Handle errors
  recognition.value.onerror = (event: any) => {
    console.error('Speech recognition error:', event.error)
    isListening.value = false
    
    // Show user-friendly error messages
    switch (event.error) {
      case 'no-speech':
        console.warn('No speech detected. Please try again.')
        break
      case 'audio-capture':
        console.error('Microphone access denied or not available.')
        break
      case 'not-allowed':
        console.error('Microphone permission denied. Please allow microphone access.')
        break
      default:
        console.error('Speech recognition failed. Please try again.')
    }
  }
  
  // Handle end of recognition
  recognition.value.onend = () => {
    isListening.value = false
    // Reset tracking variables for next session
    lastProcessedResultIndex = -1
    baseTextBeforeRecognition = ''
  }
  
  // Handle start of recognition
  recognition.value.onstart = () => {
    isListening.value = true
  }
}

// Language detection functionality
const detectLanguage = async () => {
  if (!speechSupported.value || !recognition.value) return

  isDetectingLanguage.value = true
  
  try {
    // Use browser's language preferences as starting point
    const browserLang = navigator.language || navigator.languages?.[0] || 'en-US'
    const detectedLang = findBestMatchingLanguage(browserLang)
    
    if (detectedLang) {
      currentLanguage.value = detectedLang.code
      detectedLanguage.value = detectedLang.name
      
      if (recognition.value) {
        recognition.value.lang = currentLanguage.value
      }
      
      console.log(`Auto-detected language: ${detectedLang.name} based on browser settings`)
    } else {
      // Fallback to interactive detection
      await performInteractiveDetection()
    }
  } catch (error) {
    console.error('Language detection failed:', error)
  } finally {
    isDetectingLanguage.value = false
  }
}

const findBestMatchingLanguage = (browserLang: string) => {
  // Direct match
  const directMatch = supportedLanguages.value.find(lang => lang.code === browserLang)
  if (directMatch) return directMatch
  
  // Language code match (e.g., 'en' matches 'en-US')
  const langCode = browserLang.split('-')[0]
  const langMatch = supportedLanguages.value.find(lang => lang.code.startsWith(langCode))
  if (langMatch) return langMatch
  
  return null
}

const performInteractiveDetection = async () => {
  // Show user-friendly detection prompt
  const userConfirm = confirm(
    'Voice language detection requires you to speak a few words. Click OK to start, then say something in your preferred language.'
  )
  
  if (!userConfirm) {
    isDetectingLanguage.value = false
    return
  }
  
  try {
    const detectedLang = await listenForLanguageDetection()
    if (detectedLang) {
      currentLanguage.value = detectedLang
      const langName = supportedLanguages.value.find(l => l.code === detectedLang)?.name || 'Unknown'
      console.log(`Detected language: ${langName}`)
    }
  } catch (error) {
    console.error('Interactive language detection failed:', error)
  }
}

const listenForLanguageDetection = (): Promise<string> => {
  return new Promise((resolve) => {
    const detectionRecognition = new ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition)()
    
    // Try multiple languages and see which one gives the best result
    let attempts = 0
    const maxAttempts = supportedLanguages.value.length
    let bestResult = { lang: 'en-US', confidence: 0 }
    
    const tryNextLanguage = () => {
      if (attempts >= maxAttempts) {
        resolve(bestResult.lang)
        return
      }
      
      const currentLang = supportedLanguages.value[attempts]
      detectionRecognition.lang = currentLang.code
      
      let hasResult = false
      const timeout = setTimeout(() => {
        if (!hasResult) {
          hasResult = true
          detectionRecognition.stop()
          attempts++
          tryNextLanguage()
        }
      }, 3000)
      
      detectionRecognition.onresult = (event: any) => {
        if (!hasResult) {
          hasResult = true
          clearTimeout(timeout)
          
          const confidence = event.results[0][0].confidence || 0
          if (confidence > bestResult.confidence) {
            bestResult = { lang: currentLang.code, confidence }
          }
          
          attempts++
          tryNextLanguage()
        }
      }
      
      detectionRecognition.onerror = () => {
        if (!hasResult) {
          hasResult = true
          clearTimeout(timeout)
          attempts++
          tryNextLanguage()
        }
      }
      
      try {
        detectionRecognition.start()
      } catch (error) {
        attempts++
        tryNextLanguage()
      }
    }
    
    tryNextLanguage()
  })
}

const setLanguage = (langCode: string) => {
  currentLanguage.value = langCode
  if (recognition.value) {
    recognition.value.lang = langCode
  }
  
  const selectedLang = supportedLanguages.value.find(l => l.code === langCode)
  if (selectedLang) {
    console.log(`Voice input language changed to: ${selectedLang.name}`)
  }
}

const cycleLanguage = () => {
  if (isListening.value) return // Don't cycle while listening
  
  const currentIndex = supportedLanguages.value.findIndex(l => l.code === currentLanguage.value)
  const nextIndex = (currentIndex + 1) % supportedLanguages.value.length
  const nextLang = supportedLanguages.value[nextIndex]
  
  setLanguage(nextLang.code)
  
  // Show brief notification
  console.log(`Switched to ${nextLang.flag} ${nextLang.name} (Ctrl+L to cycle)`)
}

const toggleVoiceInput = async () => {
  if (!speechSupported.value) {
    console.warn('Speech recognition is not supported in this browser')
    return
  }
  
  if (!recognition.value) {
    initializeSpeechRecognition()
    return
  }
  
  if (isListening.value) {
    // Stop listening
    recognition.value.stop()
    isListening.value = false
  } else {
    // Start listening with current language
    try {
      // Reset tracking to prevent duplicates
      if (recognition.value.resetTracking) {
        recognition.value.resetTracking()
      }
      
      recognition.value.lang = currentLanguage.value
      recognition.value.start()
    } catch (error) {
      console.error('Failed to start speech recognition:', error)
      isListening.value = false
    }
  }
}

// Sample-related functions
const extractedSamples = (content: string) => {
  if (!content) return []
  
  // Extract sample information from AI response
  const samples: any[] = []
  
  // Look for the detailed sample format that the AI returns
  // Pattern: {'name': 'sample_name', 'id': 'sample_id', ...}
  const sampleRegex = /\{'name':\s*'([^']+)',\s*'id':\s*'([^']+)'[^}]*\}/g
  let match
  
  while ((match = sampleRegex.exec(content)) !== null) {
    const sampleId = match[2]
    
    // Find the actual sample in the sample store
    const actualSample = sampleStore.localSamples.find((s: any) => s.id === sampleId)
    if (actualSample && !samples.find(existing => existing.id === sampleId)) {
      samples.push(actualSample)
    }
  }
  
  // Also look for sample names mentioned in the text (for backup)
  if (samples.length === 0) {
    const allSamples = sampleStore.localSamples
    allSamples.forEach((sample: any) => {
      if (content.includes(sample.name) && !samples.find(existing => existing.id === sample.id)) {
        samples.push(sample)
      }
    })
  }
  
  return samples.slice(0, 5) // Limit to 5 samples to avoid overwhelming the UI
}

const formatDuration = (duration: number): string => {
  if (!duration || isNaN(duration)) return '0:00'
  const minutes = Math.floor(duration / 60)
  const seconds = Math.floor(duration % 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const toggleSamplePlayback = async (sample: any) => {
  if (playingSampleId.value === sample.id) {
    // Stop current playback
    if (currentAudio.value) {
      audioStore.unregisterPreviewAudio(currentAudio.value)
      currentAudio.value.pause()
      currentAudio.value = null
    }
    playingSampleId.value = null
    return
  }

  // Stop any existing playback
  if (currentAudio.value) {
    audioStore.unregisterPreviewAudio(currentAudio.value)
    currentAudio.value.pause()
  }

  try {
    const audio = new Audio(sample.url)
    audio.volume = 0.7
    
    // Register with audio store for global stop functionality
    audioStore.registerPreviewAudio(audio)
    currentAudio.value = audio
    playingSampleId.value = sample.id
    
    audio.onended = () => {
      playingSampleId.value = null
      if (currentAudio.value) {
        audioStore.unregisterPreviewAudio(currentAudio.value)
      }
      currentAudio.value = null
    }
    
    audio.onerror = () => {
      playingSampleId.value = null
      if (currentAudio.value) {
        audioStore.unregisterPreviewAudio(currentAudio.value)
      }
      currentAudio.value = null
    }

    await audio.play()
  } catch (error) {
    console.error('Failed to play sample:', error)
    playingSampleId.value = null
    if (currentAudio.value) {
      audioStore.unregisterPreviewAudio(currentAudio.value)
    }
    currentAudio.value = null
  }
}

const addSampleToTrack = (sample: any) => {
  // Create a new track with the sample
  const trackId = audioStore.addTrack(
    sample.name,
    'sample',
    sample.url,
    sample.category
  )
  
  if (trackId) {
    audioStore.addClip(trackId, {
      startTime: audioStore.currentTime || 0,
      duration: sample.duration,
      type: 'sample',
      instrument: 'sample',
      sampleUrl: sample.url,
      volume: 0.8,
      effects: { 
        reverb: 0, 
        delay: 0, 
        distortion: 0,
        pitchShift: 0,
        chorus: 0,
        filter: 0,
        bitcrush: 0
      },
      waveform: sample.waveform
    })
    
    // Show success message
    console.log(`Added sample "${sample.name}" to new track`)
  }
}

// Waveform drawing function
const drawSampleWaveform = (canvas: HTMLCanvasElement, waveform: number[], progress = 0) => {
  const ctx = canvas.getContext('2d')
  if (!ctx || !waveform || waveform.length === 0) return
  
  const { width, height } = canvas
  
  // Clear canvas
  ctx.clearRect(0, 0, width, height)
  
  // Set colors based on theme
  ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--primary') || '#6c63ff'
  ctx.fillStyle = ctx.strokeStyle + '20' // Add transparency
  ctx.lineWidth = 1
  
  // Draw waveform
  ctx.beginPath()
  const centerY = height / 2
  const amplitude = height * 0.4
  
  for (let i = 0; i < waveform.length; i++) {
    const x = (i / (waveform.length - 1)) * width
    const y = centerY - (waveform[i] * amplitude)
    
    if (i === 0) {
      ctx.moveTo(x, y)
    } else {
      ctx.lineTo(x, y)
    }
  }
  
  ctx.stroke()
  
  // Draw progress indicator if playing
  if (progress > 0 && progress <= 1) {
    const progressX = width * progress
    ctx.save()
    ctx.globalAlpha = 0.3
    ctx.fillRect(0, 0, progressX, height)
    ctx.restore()
  }
}

// Watch for canvas refs and draw waveforms
watch(sampleWaveformCanvases, (canvases) => {
  nextTick(() => {
    Object.keys(canvases).forEach(sampleId => {
      const canvas = canvases[sampleId]
      const sample = sampleStore.localSamples.find((s: any) => s.id === sampleId)
      if (canvas && sample && sample.waveform) {
        drawSampleWaveform(canvas, sample.waveform)
      }
    })
  })
}, { deep: true })

// Update waveform progress during playback
watch(currentAudio, (audio) => {
  if (audio && playingSampleId.value) {
    const updateProgress = () => {
      if (audio && !audio.paused && !audio.ended && playingSampleId.value) {
        const sample = sampleStore.localSamples.find((s: any) => s.id === playingSampleId.value)
        const canvas = sampleWaveformCanvases.value[playingSampleId.value]
        if (sample && canvas && sample.waveform && sample.duration) {
          const progress = audio.currentTime / sample.duration
          drawSampleWaveform(canvas, sample.waveform, progress)
        }
        requestAnimationFrame(updateProgress)
      }
    }
    requestAnimationFrame(updateProgress)
  }
})
</script>

<style scoped>
.ai-chat {
  --primary-dark: #6c63ff;
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.model-selection-bar {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.75rem 1rem 0.5rem 1rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
}

.model-select-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  min-width: 0; /* Allow flex items to shrink */
}

.model-select {
  padding: 0.4rem 1.2rem 0.4rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text);
  font-size: 0.95rem;
  flex: 1;
  min-width: 0; /* Allow select to shrink */
  max-width: 150px; /* Prevent selects from being too wide */
}

.api-key-status {
  font-size: 0.92rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.api-key-status.set {
  color: var(--success);
}

.api-key-status.checking {
  color: var(--warning, #ffa500);
}

.api-key-check {
  color: var(--success);
  font-size: 1.1em;
  font-weight: bold;
  margin-right: 0.2em;
}

.api-key-label {
  color: var(--text-secondary);
  margin-right: 0.2em;
}

.api-key-set {
  color: var(--success);
}

.api-key-not-set {
  color: var(--error);
}

.api-key-checking {
  color: var(--warning, #ffa500);
}

.api-key-spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
  color: var(--warning, #ffa500);
  font-size: 1.1em;
  font-weight: bold;
  margin-right: 0.2em;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.chat-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.header-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.header-title h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--error);
  transition: background-color 0.3s ease;
}

.status-indicator.online {
  background: var(--success);
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.welcome-message {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-secondary);
}

.welcome-icon {
  width: 64px;
  height: 64px;
  background: var(--gradient-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 1rem;
}

.welcome-icon .icon {
  width: 32px;
  height: 32px;
  color: white;
}

.welcome-message h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
  font-size: 1.25rem;
}

.welcome-message p {
  margin: 0 0 1rem 0;
}

.help-list {
  text-align: left;
  max-width: 300px;
  margin: 0 auto 1.5rem;
  padding-left: 0;
  list-style: none;
}

.help-list li {
  padding: 0.25rem 0;
  font-size: 0.875rem;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-width: 300px;
  margin: 0 auto;
}

.suggestion-btn {
  padding: 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.875rem;
  text-align: left;
}

.suggestion-btn:hover {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
}

.message {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--gradient-primary);
}

.message.ai .message-avatar {
  background: var(--surface);
  border: 1px solid var(--border);
}

.avatar-icon {
  width: 16px;
  height: 16px;
  color: white;
}

.message.ai .avatar-icon {
  color: var(--primary);
}

.message-content {
  flex: 1;
  max-width: 80%;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  background: var(--surface);
  padding: 0.875rem 1rem;
  border-radius: 12px;
  color: var(--text);
  line-height: 1.5;
  font-size: 0.875rem;
  word-wrap: break-word;
  overflow-wrap: break-word;
  max-width: 100%;
}

.message.user .message-text {
  background: var(--primary);
  color: white;
}

.message-time {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  opacity: 0.7;
}

.message-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.action-btn {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  transition: all 0.2s ease;
}

.action-btn:hover {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
}

.action-btn .icon {
  width: 14px;
  height: 14px;
}

.typing {
  opacity: 0.7;
}

.typing-indicator {
  display: flex;
  gap: 0.25rem;
  padding: 1rem;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: var(--text-secondary);
  border-radius: 50%;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.chat-input {
  border-top: 1px solid var(--border);
  background: var(--surface);
  padding: 1rem;
}

.input-wrapper {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
  margin-bottom: 0.5rem;
  position: relative;
}

.voice-indicator {
  position: absolute;
  right: 60px;
  bottom: 12px;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: rgba(239, 68, 68, 0.1);
  padding: 6px 10px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #ef4444;
  font-size: 0.75rem;
  z-index: 10;
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.15);
}

.voice-wave {
  display: flex;
  align-items: center;
  gap: 2px;
}

.voice-wave span {
  width: 2px;
  height: 8px;
  background: #ef4444;
  border-radius: 1px;
  animation: voice-wave 1.2s infinite ease-in-out;
}

.voice-wave span:nth-child(1) { animation-delay: -1.1s; }
.voice-wave span:nth-child(2) { animation-delay: -1.0s; }
.voice-wave span:nth-child(3) { animation-delay: -0.9s; }

@keyframes voice-wave {
  0%, 40%, 100% { transform: scaleY(0.4); }
  20% { transform: scaleY(1.0); }
}

.message-textarea {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--background);
  color: var(--text);
  font-size: 0.95rem;
  resize: none;
  min-height: 100px; /* Increased from 60px */
  max-height: 260px; /* Increased from 180px */
  font-family: inherit;
}

.message-textarea:focus {
  outline: none;
  border-color: var(--primary);
}

.message-textarea.listening {
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.1);
}

.message-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.send-btn {
  width: 40px;
  height: 40px;
  border: none;
  background: var(--primary);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  flex-shrink: 0;
}

.send-btn:hover:not(:disabled) {
  background: var(--primary);
  transform: scale(1.05);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.send-btn .icon {
  width: 16px;
  height: 16px;
}

.input-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: center;
  align-items: center;
  flex-wrap: wrap;
}

.action-btn-small {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.action-btn-small:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.action-btn-small.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.action-btn-small.recording {
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
  100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
}

.action-btn-small:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-btn-small:disabled:hover {
  border-color: var(--border);
  color: var(--text-secondary);
}

.voice-input-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 3px 4px;
  height: 32px;
  box-sizing: border-box;
  position: relative;
}

.voice-input-group::after {
  content: '';
  position: absolute;
  right: -0.75rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1px;
  height: 16px;
  background: var(--border);
  opacity: 0.5;
}

.voice-input-group:hover {
  border-color: var(--primary);
  box-shadow: 0 0 0 1px rgba(var(--primary-rgb), 0.1);
}

.voice-input-group:focus-within {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(var(--primary-rgb), 0.1);
}

.language-select {
  border: none;
  background: transparent;
  color: var(--text);
  font-size: 0.8rem;
  padding: 4px 8px;
  border-radius: 4px;
  cursor: pointer;
  min-width: 90px;
  max-width: 110px;
  height: 24px;
  line-height: 1;
  outline: none;
}

.language-select:focus {
  background: var(--background);
  box-shadow: 0 0 0 1px var(--primary);
}

.language-select:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.detect-btn {
  width: 24px;
  height: 24px;
  border: none !important;
  background: transparent !important;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.detect-btn:hover {
  background: var(--surface) !important;
  color: var(--primary);
}

.detect-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.detect-btn:disabled:hover {
  background: transparent !important;
  color: var(--text-secondary);
}

.detect-icon {
  width: 12px;
  height: 12px;
}

.detect-spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.voice-lang {
  font-size: 0.65rem;
  opacity: 0.8;
  margin-left: 0.25rem;
}

.mic-btn {
  margin-left: 0.25rem;
}

.action-btn-small .icon {
  width: 14px;
  height: 14px;
}

.suggestions-panel {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 8px;
}

.suggestions-panel h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.875rem;
  color: var(--text);
}

.suggestions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.5rem;
}

/* Scrollbar */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.get-api-key-btn {
  background: none;
  border: none;
  color: var(--primary);
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0.4rem 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
  flex-shrink: 0; /* Prevent button from shrinking */
  min-width: 40px; /* Ensure minimum visible width */
  border-radius: 6px; /* Add some visual consistency */
}

.get-api-key-btn:hover {
  color: var(--primary-dark, #6c63ff);
  background: rgba(108, 99, 255, 0.1); /* Add subtle hover background */
}

.get-api-key-btn .icon {
  width: 20px;
  height: 20px;
}

/* JSON Code Block Styles */
.json-code-block {
  margin: 0.75rem 0;
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--background);
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  /* Ensure containment within message */
  overflow-x: hidden;
}

.json-header {
  padding: 0.75rem 1rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s ease;
  user-select: none;
  font-size: 0.875rem;
}

.json-header:hover {
  background: var(--border);
  transform: translateY(-1px);
}

.json-label {
  font-weight: 600;
  color: var(--text);
  font-size: 0.875rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.json-label::before {
  content: "{ }";
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  color: var(--primary);
  font-weight: bold;
  font-size: 1rem;
  background: rgba(108, 99, 255, 0.1);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  border: 1px solid rgba(108, 99, 255, 0.2);
}

.json-toggle {
  color: var(--text-secondary);
  font-size: 1rem;
  transition: all 0.2s ease;
  line-height: 1;
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0.25rem;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}

.json-toggle:hover {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.json-content {
  margin: 0;
  padding: 1rem;
  background: var(--background);
  overflow-x: auto;
  border: none;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8125rem;
  line-height: 1.4;
  color: var(--text);
  white-space: pre;
  max-height: 400px;
  overflow-y: auto;
  width: 100%;
  box-sizing: border-box;
  border-top: 1px solid var(--border);
  /* Ensure proper containment */
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.json-content::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.json-content::-webkit-scrollbar-track {
  background: var(--surface);
  border-radius: 4px;
}

.json-content::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.json-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.json-content code {
  background: none;
  padding: 0;
  color: inherit;
  font-family: inherit;
  font-size: inherit;
  white-space: pre;
  word-wrap: normal;
  overflow-wrap: normal;
}

/* JSON Action Buttons */
.json-actions {
  padding: 0.75rem 1rem;
  background: var(--surface);
  border-top: 1px solid var(--border);
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  justify-content: flex-start;
}

.json-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
  min-height: 32px;
  text-decoration: none;
}

.json-action-btn:hover {
  background: var(--primary-dark);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(108, 99, 255, 0.3);
}

.json-action-btn:active {
  transform: translateY(0);
  box-shadow: 0 1px 4px rgba(108, 99, 255, 0.4);
}

.json-action-btn .action-icon {
  font-size: 1rem;
  line-height: 1;
  display: inline-block;
  min-width: 16px;
  text-align: center;
}

/* Responsive design for action buttons */
@media (max-width: 768px) {
  .json-actions {
    padding: 0.5rem;
    gap: 0.25rem;
  }
  
  .json-action-btn {
    padding: 0.375rem 0.5rem;
    font-size: 0.8125rem;
    min-height: 28px;
  }
  
  .json-action-btn .action-icon {
    font-size: 0.875rem;
  }
}

/* Regular code blocks */
.code-block {
  margin: 0.75rem 0;
  padding: 1rem;
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow-x: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8125rem;
  line-height: 1.4;
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.code-block::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.code-block::-webkit-scrollbar-track {
  background: var(--surface);
  border-radius: 4px;
}

.code-block::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.code-block::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

.code-block code {
  background: none;
  padding: 0;
  color: var(--text);
  font-family: inherit;
  font-size: inherit;
  white-space: pre;
  word-wrap: normal;
  overflow-wrap: normal;
}

@media (max-width: 768px) {
  .message-content {
    max-width: 90%;
  }
  
  .suggestions-grid {
    grid-template-columns: 1fr;
  }
  
  .quick-actions {
    max-width: none;
  }
  
  .help-list {
    max-width: none;
  }
  
  .input-actions {
    justify-content: flex-start;
  }
  
  /* Model selection responsive adjustments */
  .model-selection-bar {
    padding: 0.5rem 0.75rem;
  }
  
  .model-select-row {
    gap: 0.5rem;
  }
  
  .model-select {
    font-size: 0.875rem;
    padding: 0.35rem 1rem 0.35rem 0.6rem;
    max-width: 120px; /* Smaller max-width on mobile */
  }
  
  .get-api-key-btn {
    padding: 0.35rem 0.4rem;
    min-width: 36px;
  }
  
  .get-api-key-btn .icon {
    width: 18px;
    height: 18px;
  }
  
  .api-key-status {
    font-size: 0.85rem;
  }
  
  .json-content {
    font-size: 0.75rem;
    max-height: 250px;
    padding: 0.75rem;
  }
  
  .json-header {
    padding: 0.5rem 0.75rem;
  }
  
  .json-label {
    font-size: 0.8125rem;
  }
  
  .json-label::before {
    font-size: 0.875rem;
    padding: 0.125rem 0.375rem;
  }
  
  .code-block {
    font-size: 0.75rem;
    padding: 0.75rem;
    max-height: 250px;
  }
}

/* Sample Controls Styles */
.sample-controls {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 12px;
}

.sample-controls-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
}

.sample-controls-title .icon {
  width: 16px;
  height: 16px;
  color: var(--primary);
}

.sample-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.sample-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background: var(--background);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: all 0.2s ease;
  min-height: 60px;
}

.sample-item:hover {
  border-color: var(--primary);
  box-shadow: 0 2px 8px rgba(108, 99, 255, 0.12);
  transform: translateY(-1px);
}

.sample-waveform {
  flex-shrink: 0;
  width: 80px;
  height: 32px;
}

.waveform-canvas {
  border-radius: 4px;
  background: var(--surface-subtle);
  border: 1px solid var(--border);
  display: block;
  width: 100%;
  height: 100%;
}

.sample-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.sample-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.3;
}

.sample-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.sample-meta .duration {
  background: var(--primary);
  color: white;
  padding: 0.2rem 0.5rem;
  border-radius: 12px;
  font-weight: 600;
  white-space: nowrap;
  font-size: 0.7rem;
}

.sample-meta .bpm {
  background: var(--surface-subtle);
  padding: 0.2rem 0.4rem;
  border-radius: 8px;
  white-space: nowrap;
  font-weight: 500;
  font-size: 0.7rem;
}

.sample-meta .category {
  text-transform: capitalize;
  background: var(--warning, #f59e0b);
  color: white;
  padding: 0.2rem 0.4rem;
  border-radius: 8px;
  font-weight: 500;
  white-space: nowrap;
  font-size: 0.7rem;
}

.sample-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.sample-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0.4rem;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.sample-action-btn:hover {
  border-color: var(--primary);
  background: var(--primary);
  color: white;
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(108, 99, 255, 0.2);
}

.sample-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.sample-action-btn.playing {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
}

.sample-action-btn.play-btn:hover {
  background: var(--success);
  border-color: var(--success);
}

.sample-action-btn.add-btn {
  background: var(--success);
  border-color: var(--success);
  color: white;
}

.sample-action-btn.add-btn:hover {
  background: var(--success-dark, #16a34a);
  border-color: var(--success-dark, #16a34a);
  transform: translateY(-1px);
}

.sample-action-btn .icon {
  width: 14px;
  height: 14px;
}

/* Lyrics Display Styles */
.lyrics-display {
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  border: 2px solid var(--primary);
  border-radius: 12px;
  margin: 16px 0 0 0;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.lyrics-header {
  background: var(--primary);
  color: white;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.lyrics-icon {
  font-size: 18px;
}

.lyrics-title {
  flex: 1;
}

.lyrics-content {
  padding: 20px;
  color: var(--text);
  line-height: 1.6;
}

.lyrics-section {
  margin-bottom: 16px;
}

.lyrics-section:last-child {
  margin-bottom: 0;
}

.lyrics-section-title {
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 8px;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.5px;
}

.lyrics-voice {
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-size: 14px;
}

.lyrics-line {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  border-left: 4px solid var(--primary);
}

.lyrics-line:last-child {
  margin-bottom: 0;
}

.lyrics-error {
  color: var(--danger);
  font-style: italic;
  text-align: center;
  padding: 20px;
}

.lyrics-empty {
  color: var(--text-secondary);
  font-style: italic;
  text-align: center;
  padding: 20px;
}

/* Enhanced action button for lyrics */
.json-action-btn.primary {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
  font-weight: 600;
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(var(--primary-rgb), 0.3);
}

.json-action-btn.primary:hover {
  background: var(--primary-dark);
  border-color: var(--primary-dark);
  transform: scale(1.08) translateY(-2px);
  box-shadow: 0 6px 20px rgba(var(--primary-rgb), 0.4);
}

.json-action-btn.primary .action-icon {
  font-size: 16px;
}

/* Lyrics Footer Actions */
.lyrics-footer-actions {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  margin: 12px 0;
  justify-content: flex-start;
  flex-wrap: wrap;
  animation: slideInUp 0.3s ease-out;
}

.lyrics-footer-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 140px;
  justify-content: center;
  font-family: inherit;
}

.lyrics-footer-btn .icon {
  width: 16px;
  height: 16px;
}

.lyrics-footer-btn.primary {
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark, #6d28d9) 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(var(--primary-rgb), 0.2);
}

.lyrics-footer-btn.primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(var(--primary-rgb), 0.3);
}

.lyrics-footer-btn.secondary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.2);
}

.lyrics-footer-btn.secondary:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%);
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.3);
}

.lyrics-footer-btn:active {
  transform: translateY(0);
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Lyrics JSON section styling */
.lyrics-json-section {
  margin-top: 0px;
  border-top: 1px solid #e2e8f0;
  padding-top: 8px;
  margin-bottom: -16px;
}

.lyrics-json-header {
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transition: all 0.2s ease;
  font-size: 13px;
  border: 1px solid #cbd5e1;
}

.lyrics-json-header:hover {
  background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.lyrics-json-label {
  color: #475569;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
}

.lyrics-json-toggle {
  color: #64748b;
  font-weight: bold;
  transition: transform 0.2s ease;
  font-size: 12px;
}

.lyrics-json-toggle.expanded {
  transform: rotate(90deg);
}

.lyrics-json-content {
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #374151;
  border-radius: 8px;
  padding: 16px;
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
}

.lyrics-json-content code {
  color: #e2e8f0;
}

/* Lyrics action buttons styling - High specificity */
.chat-messages .message.ai .message-content .lyrics-actions,
.lyrics-actions {
  margin: 16px 0 !important;
  display: flex !important;
  gap: 12px !important;
  flex-wrap: wrap !important;
  justify-content: flex-start !important;
}

.chat-messages .message.ai .message-content .lyrics-action-btn,
.message-content .lyrics-action-btn,
.lyrics-action-btn,
button.lyrics-action-btn {
  display: inline-flex !important;
  align-items: center !important;
  gap: 8px !important;
  padding: 10px 16px !important;
  border: none !important;
  border-radius: 20px !important;
  font-size: 13px !important;
  font-weight: 600 !important;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  cursor: pointer !important;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
  text-decoration: none !important;
  min-height: 36px !important;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1) !important;
  outline: none !important;
  position: relative !important;
  overflow: hidden !important;
  background: none !important;
}

.lyrics-action-btn::before,
.message-content .lyrics-action-btn::before,
button.lyrics-action-btn::before {
  content: '' !important;
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  right: 0 !important;
  bottom: 0 !important;
  background: linear-gradient(45deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0)) !important;
  opacity: 0 !important;
  transition: opacity 0.2s ease !important;
}

.lyrics-action-btn:hover::before,
.message-content .lyrics-action-btn:hover::before,
button.lyrics-action-btn:hover::before {
  opacity: 1 !important;
}

.chat-messages .message.ai .message-content .lyrics-action-btn.primary,
.lyrics-action-btn.primary,
.message-content .lyrics-action-btn.primary,
button.lyrics-action-btn.primary {
  background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%) !important;
  color: white !important;
}

.chat-messages .message.ai .message-content .lyrics-action-btn.primary:hover,
.lyrics-action-btn.primary:hover,
.message-content .lyrics-action-btn.primary:hover,
button.lyrics-action-btn.primary:hover {
  background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 16px rgba(139, 92, 246, 0.4) !important;
}

.chat-messages .message.ai .message-content .lyrics-action-btn.secondary,
.lyrics-action-btn.secondary,
.message-content .lyrics-action-btn.secondary,
button.lyrics-action-btn.secondary {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
  color: white !important;
}

.chat-messages .message.ai .message-content .lyrics-action-btn.secondary:hover,
.lyrics-action-btn.secondary:hover,
.message-content .lyrics-action-btn.secondary:hover,
button.lyrics-action-btn.secondary:hover {
  background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
  transform: translateY(-2px) !important;
  box-shadow: 0 6px 16px rgba(16, 185, 129, 0.4) !important;
}

.lyrics-action-btn .action-icon,
.message-content .lyrics-action-btn .action-icon,
button.lyrics-action-btn .action-icon {
  font-size: 14px !important;
  flex-shrink: 0 !important;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.2)) !important;
}

.lyrics-action-btn:active,
.message-content .lyrics-action-btn:active,
button.lyrics-action-btn:active {
  transform: translateY(0) !important;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
}

.lyrics-action-btn:focus,
.message-content .lyrics-action-btn:focus,
button.lyrics-action-btn:focus {
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.3) !important;
}

/* Lyrics sections styling */
.lyrics-response {
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-radius: 12px;
  padding: 20px;
  margin: 16px 0 0 0;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.lyrics-display h4 {
  margin: 0 0 16px 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.lyrics-section {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin: 12px 0;
  border-left: 4px solid var(--primary);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.lyrics-section-title {
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 8px;
  font-size: 14px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.lyrics-voice {
  font-weight: 500;
  color: #64748b;
  margin-bottom: 6px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.lyrics-line {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 12px;
  color: #1e293b;
  font-weight: 500;
}

.lyrics-syllables {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 10px;
  border-radius: 6px;
}

.syllable-group {
  display: inline-block;
  margin-right: 16px;
  margin-bottom: 6px;
  font-size: 11px;
  color: #64748b;
  font-style: italic;
  font-family: Monaco, monospace;
  background: white;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid #e2e8f0;
}

.lyrics-empty {
  color: #64748b;
  font-style: italic;
  text-align: center;
  padding: 30px 20px;
  background: #f8fafc;
  border-radius: 8px;
  border: 2px dashed #cbd5e1;
}

.lyrics-error {
  color: #dc2626;
  font-style: italic;
  text-align: center;
  padding: 30px 20px;
  background: #fef2f2;
  border-radius: 8px;
  border: 2px dashed #fca5a5;
}

/* Uploaded Scores Styles */
.uploaded-scores {
  background: var(--surface);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  border: 1px solid var(--border);
}

.uploaded-scores h5 {
  margin: 0 0 0.75rem 0;
  color: var(--text);
  font-size: 0.875rem;
  font-weight: 600;
}

.score-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.score-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem;
  background: var(--background);
  border-radius: 6px;
  border: 1px solid var(--border);
  transition: all 0.2s ease;
}

.score-item.success {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.05);
}

.score-item.error {
  border-color: #ef4444;
  background: rgba(239, 68, 68, 0.05);
}

.score-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.score-name {
  font-weight: 500;
  color: var(--text);
  font-size: 0.875rem;
}

.score-category {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.score-status {
  font-size: 0.875rem;
  font-weight: 600;
  margin-left: 0.5rem;
}

.score-status.success {
  color: #10b981;
}

.score-status.error {
  color: #ef4444;
}

.score-status.uploading {
  color: #f59e0b;
}

.score-details {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.25rem;
  flex-wrap: wrap;
}

.score-details .detail {
  font-size: 0.75rem;
  color: var(--text-secondary);
  padding: 0.125rem 0.375rem;
  background: var(--surface);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.remove-score-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  font-size: 1.125rem;
  line-height: 1;
  transition: all 0.2s ease;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-score-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.scores-help {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--border);
  text-align: center;
}

.scores-help small {
  color: var(--text-secondary);
  font-style: italic;
}

/* Upload button states */
.action-btn-small.uploading {
  opacity: 0.6;
  cursor: not-allowed;
}

.icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
