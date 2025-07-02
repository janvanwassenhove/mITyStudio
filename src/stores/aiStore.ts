import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
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
  const selectedProvider = ref('openai')
  const selectedModel = ref('gpt-4')
  
  const providers: AIProvider[] = [
    {
      id: 'openai',
      name: 'OpenAI',
      models: ['gpt-4', 'gpt-3.5-turbo']
    },
    {
      id: 'anthropic',
      name: 'Anthropic',
      models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku']
    },
    {
      id: 'google',
      name: 'Google',
      models: ['gemini-pro', 'gemini-pro-vision']
    },
    {
      id: 'azure',
      name: 'Azure OpenAI',
      models: ['gpt-4', 'gpt-35-turbo']
    }
  ]

  // Actions
  const addMessage = (role: 'user' | 'assistant', content: string) => {
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
      // Simulate AI response for demo purposes
      // In a real implementation, this would call the actual AI API
      await new Promise(resolve => setTimeout(resolve, 1500))
      
      const response = generateMockResponse(content)
      addMessage('assistant', response)
      
      return response
    } catch (error) {
      console.error('Failed to send message:', error)
      addMessage('assistant', 'Sorry, I encountered an error while processing your request.')
      throw error
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
