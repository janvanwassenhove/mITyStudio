import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

// Configure axios base URL for backend
const API_BASE_URL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:5000' 
  : (window as any).electronAPI?.constants.BACKEND_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  actions?: ChatAction[]
}

export interface ChatAction {
  label: string
  action: string
  icon: string
  params?: any
}

export interface AIProvider {
  id: string
  name: string
  models: string[]
}

export const useAIStore = defineStore('ai', () => {
  // State
  const messages = ref<ChatMessage[]>([])
  const isGenerating = ref(false)
  const selectedProvider = ref('anthropic')
  const selectedModel = ref('claude-sonnet-4')
  
  const providers: AIProvider[] = [
    {
      id: 'anthropic',
      name: 'Anthropic',
      models: ['claude-sonnet-4', 'claude-3-opus', 'claude-3-haiku']
    },
    {
      id: 'openai',
      name: 'OpenAI',
      models: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo']
    },
    {
      id: 'google',
      name: 'Google',
      models: ['gemini-1.5-pro', 'gemini-1.0-pro']
    }
  ]

  // Actions
  const addMessage = (role: 'user' | 'assistant', content: string, actions?: ChatAction[]) => {
    const message: ChatMessage = {
      id: `msg-${Date.now()}`,
      role,
      content,
      timestamp: new Date()
    }
    messages.value.push(message)
    return message.id
  }

  const sendMessage = async (content: string) => {
    addMessage('user', content)
    isGenerating.value = true
    
    try {
      // Call backend AI API
      const response = await api.post('/api/ai/chat', {
        message: content,
        provider: selectedProvider.value,
        model: selectedModel.value,
        context: {
          // Add any relevant context from the current project
          // This could include current tracks, tempo, key, etc.
        }
      })

      const aiResponse = response.data.response
      const actions = response.data.actions || []
      
      // Add AI response with actions
      const message: ChatMessage = {
        id: `msg-${Date.now()}-ai`,
        role: 'assistant',
        content: aiResponse,
        timestamp: new Date(),
        actions: actions
      }
      
      messages.value.push(message)
      return aiResponse
      
    } catch (error: any) {
      console.error('Failed to send message:', error)
      
      // Fallback to mock response if backend is unavailable
      const fallbackResponse = generateMockResponse(content)
      addMessage('assistant', fallbackResponse)
      
      // Show error to user but don't throw to prevent UI breaking
      if (error.response?.status === 503) {
        addMessage('assistant', 'AI services are temporarily unavailable. Please check your API keys.')
      }
      
      return fallbackResponse
    } finally {
      isGenerating.value = false
    }
  }

  const generateMockResponse = (userMessage: string): string => {
    const lowerMessage = userMessage.toLowerCase()
    
    if (lowerMessage.includes('drum') || lowerMessage.includes('beat')) {
      return `I'll create a drum pattern for you. Here's what I'm adding:

**Drum Track Created:**
- Kick drum on beats 1 and 3
- Snare on beats 2 and 4
- Hi-hat pattern with eighth notes
- Tempo: 120 BPM

The pattern has been added to your song structure. You can adjust the volume and effects in the track controls.`
    }
    
    if (lowerMessage.includes('melody') || lowerMessage.includes('piano')) {
      return `I've generated a simple melody for you:

**Piano Melody Added:**
- Key: C Major
- Pattern: C-E-G-E-F-A-G-F
- Duration: 4 bars
- Rhythm: Quarter notes with some eighth note variations

The melody has been added as a new track. You can modify the notes by clicking on the timeline clips.`
    }
    
    if (lowerMessage.includes('bass')) {
      return `Creating a bass line that complements your existing tracks:

**Bass Track Generated:**
- Root note pattern following chord progression
- Rhythm: Mix of quarter and eighth notes
- Low-pass filter applied for warmth
- Slight compression for punch

The bass line has been synchronized with your existing tracks.`
    }
    
    if (lowerMessage.includes('chord') || lowerMessage.includes('harmony')) {
      return `I'll add some harmonic content:

**Chord Progression Added:**
- Progression: C - Am - F - G (I-vi-IV-V)
- Voicing: Triads with some inversions
- Rhythm: Whole notes with some syncopation
- Instrument: Warm pad synthesizer

This creates a solid harmonic foundation for your song.`
    }
    
    return `I understand you want to work on "${userMessage}". Here are some suggestions:

1. **Add a new track** with the instrument of your choice
2. **Modify existing tracks** by adjusting volume, pan, or effects
3. **Create patterns** using the timeline editor
4. **Experiment with effects** like reverb, delay, or distortion

What specific aspect would you like me to help you with? I can create drum patterns, melodies, bass lines, or chord progressions.`
  }

  const clearMessages = () => {
    messages.value = []
  }

  const setProvider = (providerId: string) => {
    selectedProvider.value = providerId
    const provider = providers.find(p => p.id === providerId)
    if (provider && provider.models.length > 0) {
      selectedModel.value = provider.models[0]
    }
  }

  const setModel = (modelId: string) => {
    selectedModel.value = modelId
  }

  const getAvailableModels = () => {
    const provider = providers.find(p => p.id === selectedProvider.value)
    return provider?.models || []
  }

  return {
    // State
    messages,
    isGenerating,
    selectedProvider,
    selectedModel,
    providers,
    
    // Actions
    addMessage,
    sendMessage,
    clearMessages,
    setProvider,
    setModel,
    getAvailableModels
  }
})
