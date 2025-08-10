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
          placeholder="Ask me anything about music production..."
          class="message-textarea"
          rows="1"
          :disabled="isTyping"
        ></textarea>
        
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
          title="Attach file"
        >
          <Paperclip class="icon" />
        </button>
        
        <button 
          class="action-btn-small"
          @click="toggleVoiceInput"
          :class="{ 'active': isListening }"
          title="Voice input"
        >
          <Mic class="icon" />
        </button>
        
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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { useAIStore } from '../stores/aiStore'
import { checkApiKeyStatus as apiCheckApiKeyStatus, getAllSampleInstruments } from '../utils/api'
import { 
  Bot, User, Trash2, Send, Paperclip, Mic, Lightbulb, Key,
  Music, Play, Plus, Download, Upload, Settings, Volume2, Mic2
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

// State - Use AI store messages instead of local state
const currentMessage = ref('')
const isListening = ref(false)
const showSuggestions = ref(false)
const messagesContainer = ref<HTMLElement>()
const messageInput = ref<HTMLTextAreaElement>()

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
  "Suggest some effects for vocals"
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
    addLyricsFromJSON({ json: lyricsData })
  } catch (error) {
    console.error('Error adding lyrics from JSON:', error)
    sendMessage('❌ Error adding lyrics. Please check the JSON format.')
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

onMounted(() => {
  // Focus the input
  messageInput.value?.focus()
  
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
  ;(window as any).applyEffectsFromJSON = applyEffectsFromJSON
  ;(window as any).applyMixFromJSON = applyMixFromJSON
  
  // Load available instruments on component mount
  loadAvailableInstruments()
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

// Generate contextual action buttons based on AI response content
const generateContextualActions = (responseContent: string): ChatAction[] => {
  const actions: ChatAction[] = []
  const content = responseContent.toLowerCase()
  const originalContent = responseContent
  const suggestions = parseMusicalSuggestions(originalContent)
  
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
    actions.push({
      label: 'Apply Structure',
      icon: Upload,
      action: 'apply_song_structure'
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
    // Use the regular AI chat service that we know works
    const result = await aiStore.sendMessage(content)
    console.log('AI response received:', result)
    
    // Generate contextual action buttons based on the AI response
    if (result && result.content) {
      const actions = generateContextualActions(result.content)
      if (actions.length > 0) {
        // Update the last message with generated actions
        const lastMessage = aiStore.messages[aiStore.messages.length - 1]
        if (lastMessage && lastMessage.role === 'assistant') {
          lastMessage.actions = [...(lastMessage.actions || []), ...actions]
        }
      }
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
      addVocalTrack()
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
        effects: { reverb: 0.2, delay: 0, distortion: 0 }
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
        effects: { reverb: 0.1, delay: 0, distortion: 0 }
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
      ? { reverb: 0, delay: 0, distortion: 0 }
      : bassType === 'electric'
        ? { reverb: 0.1, delay: 0, distortion: 0.2 }
        : { reverb: 0, delay: 0, distortion: 0.1 }
    
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
      effects: { reverb: 0.3, delay: 0.2, distortion: 0 }
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
        effects: { reverb: 0.2, delay: 0, distortion: 0 }
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
            track.effects = { reverb: 0.3, delay: 0.2, distortion: 0 }
          } else if (track.instrument === 'drums') {
            track.effects = { reverb: 0.1, delay: 0, distortion: 0.1 }
          } else {
            track.effects = { reverb: 0.2, delay: 0.1, distortion: 0 }
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
          
          // Extract lyrics text from clip
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
            effects: { reverb: 0, delay: 0, distortion: 0 }
          })
        }
      }

      if (trackId) {
        // Add the lyrics clip
        audioStore.addClip(trackId, {
          ...lyricsJSON,
          trackId: trackId
        })

        // Extract lyrics text from single clip
        if (lyricsJSON.voices) {
          for (const voice of lyricsJSON.voices) {
            if (voice.lyrics) {
              for (const lyric of voice.lyrics) {
                if (lyric.text) {
                  extractedLyricsText += lyric.text + '\n'
                }
              }
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
  
  // First handle JSON code blocks (```json...```) and make them collapsible with action buttons
  content = content.replace(/```json\n?([\s\S]*?)```/g, (_, jsonContent) => {
    const uniqueId = 'json-' + Math.random().toString(36).substr(2, 9)
    const actionButtons = generateActionButtonsFromJSON(jsonContent.trim())
    
    return `<div class="json-code-block">
      <div class="json-header" onclick="toggleJsonBlock('${uniqueId}')">
        <span class="json-label">JSON Structure</span>
        <span class="json-toggle" id="toggle-${uniqueId}">›</span>
      </div>
      <pre class="json-content" id="${uniqueId}" style="display: none;"><code>${jsonContent.trim()}</code></pre>
      ${actionButtons}
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
    
    // Lyrics/vocals
    if (jsonData.instrument === 'vocals' || jsonData.type === 'lyrics' || jsonData.voices || 
        (jsonData.clips && jsonData.clips.some && jsonData.clips.some((c: any) => c.voices))) {
      buttons.push(`<button class="json-action-btn" onclick="addLyricsFromJSONAction('${encodeURIComponent(jsonContent)}')">
        <span class="action-icon">🎤</span> Add Lyrics & Vocals
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
  // File attachment functionality
  console.log('Attach file clicked')
}

const toggleVoiceInput = () => {
  isListening.value = !isListening.value
  // Voice input functionality would go here
  console.log('Voice input toggled:', isListening.value)
}
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
</style>
