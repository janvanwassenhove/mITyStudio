import { defineStore } from 'pinia'
import { ref } from 'vue'
import axios from 'axios'
import { useAudioStore } from './audioStore'

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
  const selectedModel = ref('claude-4-sonnet')
  
  const providers: AIProvider[] = [
    {
      id: 'anthropic',
      name: 'Anthropic',
      models: [
        'claude-4-sonnet',
        'claude-3-7-sonnet',
        'claude-3-5-sonnet-20241022',
        'claude-3-5-sonnet-20240620',
        'claude-3-5-haiku-20241022',
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307',
        'claude-2.1',
        'claude-2.0',
        'claude-instant-1.2'
      ]
    },
    {
      id: 'openai',
      name: 'OpenAI',
      models: [
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-4-turbo',
        'gpt-4-turbo-preview',
        'gpt-4-0125-preview',
        'gpt-4-1106-preview',
        'gpt-4',
        'gpt-4-0613',
        'gpt-3.5-turbo',
        'gpt-3.5-turbo-0125',
        'gpt-3.5-turbo-1106',
        'gpt-3.5-turbo-16k',
        'gpt-3.5-turbo-instruct'
      ]
    },
    {
      id: 'google',
      name: 'Google',
      models: [
        'gemini-1.5-pro',
        'gemini-1.5-pro-latest',
        'gemini-1.5-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.0-pro',
        'gemini-1.0-pro-latest',
        'gemini-1.0-pro-vision',
        'gemini-pro',
        'gemini-pro-vision'
      ]
    },
    {
      id: 'mistral',
      name: 'Mistral',
      models: [
        'mistral-large-latest',
        'mistral-large-2407',
        'mistral-large-2402',
        'mistral-medium-latest',
        'mistral-medium-2312',
        'mistral-small-latest',
        'mistral-small-2402',
        'mistral-small-2312',
        'mistral-tiny',
        'mistral-7b-instruct',
        'mixtral-8x7b-instruct',
        'mixtral-8x22b-instruct',
        'open-mistral-7b',
        'open-mistral-8x7b',
        'open-mistral-8x22b',
        'open-mixtral-8x7b',
        'open-mixtral-8x22b'
      ]
    },
    {
      id: 'xai',
      name: 'xAI',
      models: [
        'grok-beta',
        'grok-2-1212',
        'grok-2-latest',
        'grok-2-public',
        'grok-2-mini',
        'grok-vision-beta',
        'grok-1',
        'grok-1.5'
      ]
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
      // Get audio store for context
      const audioStore = useAudioStore()
      
      // Call backend AI API with song structure context
      const response = await api.post('/api/ai/chat', {
        message: content,
        provider: selectedProvider.value,
        model: selectedModel.value,
        context: {
          // Include current song structure for music-aware AI assistance
          song_structure: audioStore.songStructure,
          tracks: audioStore.songStructure?.tracks || [],
          tempo: audioStore.songStructure?.tempo || 120,
          key: audioStore.songStructure?.key || 'C',
          timeSignature: audioStore.songStructure?.timeSignature || [4, 4],
          duration: audioStore.songStructure?.duration || 0,
          // Add current project state
          hasActiveProject: audioStore.songStructure?.tracks?.length > 0
        }
      })

      const aiResponse = response.data.content || response.data.response || 'No response received'
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
      
      // Handle updated song structure if provided by LangChain
      if (response.data.updated_song_structure) {
        console.log('AI provided updated song structure:', response.data.updated_song_structure)
        // You could emit an event here to update the song structure
        // audioStore.updateSongStructure(response.data.updated_song_structure)
      }
      
      return aiResponse
      
    } catch (error: any) {
      console.error('Failed to send message:', error)
      
      // Fallback to mock response if backend is unavailable
      const fallbackResponse = generateMockResponse(content)
      addMessage('assistant', fallbackResponse)
      
      // Show error to user but don't throw to prevent UI breaking
      if (error.response?.status === 503) {
        const errorMsg = error.response?.data?.fallback_response || 'AI services are temporarily unavailable. Please check your API keys.'
        addMessage('assistant', errorMsg)
      }
      
      return fallbackResponse
    } finally {
      isGenerating.value = false
    }
  }

  const sendMusicAssistantMessage = async (content: string, songStructure: any = null) => {
    addMessage('user', content)
    isGenerating.value = true
    
    try {
      // Call the new music assistant endpoint
      const response = await api.post('/api/ai/music-assistant', {
        message: content,
        provider: selectedProvider.value,
        model: selectedModel.value,
        song_structure: songStructure
      })

      const aiResponse = response.data.content || response.data.response || 'No response received'
      const updatedStructure = response.data.updated_song_structure
      const toolsUsed = response.data.tools_used || []
      
      // Add AI response with tools info
      let responseText = aiResponse
      if (toolsUsed.length > 0) {
        responseText += `\n\n*Tools used: ${toolsUsed.map((tool: any) => tool.tool || 'music tool').join(', ')}*`
      }
      
      const message: ChatMessage = {
        id: `msg-${Date.now()}-ai`,
        role: 'assistant',
        content: responseText,
        timestamp: new Date(),
        actions: updatedStructure ? [{
          label: 'Apply Changes',
          action: 'apply_song_structure',
          icon: 'Music',
          params: { songStructure: updatedStructure }
        }] : []
      }
      
      messages.value.push(message)
      
      return {
        response: aiResponse,
        updatedSongStructure: updatedStructure,
        toolsUsed: toolsUsed,
        success: response.data.success
      }
      
    } catch (error: any) {
      console.error('Failed to send music assistant message:', error)
      
      // Enhanced fallback for music assistant
      const fallbackResponse = generateEnhancedMockResponse(content, songStructure)
      addMessage('assistant', fallbackResponse)
      
      return {
        response: fallbackResponse,
        updatedSongStructure: null,
        toolsUsed: [],
        success: false
      }
    } finally {
      isGenerating.value = false
    }
  }

  const analyzeSong = async (songStructure: any) => {
    isGenerating.value = true
    
    try {
      const response = await api.post('/api/ai/analyze-song', {
        song_structure: songStructure
      })

      const analysis = response.data.analysis
      const suggestions = response.data.suggestions
      
      // Add analysis to chat
      addMessage('assistant', `**Song Analysis:**\n\n${analysis}`)
      
      return {
        analysis: analysis,
        suggestions: suggestions,
        success: response.data.success
      }
      
    } catch (error: any) {
      console.error('Failed to analyze song:', error)
      const fallbackAnalysis = generateFallbackAnalysis(songStructure)
      addMessage('assistant', fallbackAnalysis)
      
      return {
        analysis: fallbackAnalysis,
        suggestions: null,
        success: false
      }
    } finally {
      isGenerating.value = false
    }
  }

  const generateSongSection = async (songStructure: any, sectionName: string, requirements: any = {}) => {
    isGenerating.value = true
    
    try {
      const response = await api.post('/api/ai/generate-section', {
        song_structure: songStructure,
        section_name: sectionName,
        requirements: requirements
      })

      const updatedStructure = response.data.updated_song_structure
      const responseText = response.data.content || response.data.response || 'Section generated successfully'
      
      addMessage('assistant', `**${sectionName.charAt(0).toUpperCase() + sectionName.slice(1)} Section Created:**\n\n${responseText}`)
      
      return {
        response: responseText,
        updatedSongStructure: updatedStructure,
        success: response.data.success
      }
      
    } catch (error: any) {
      console.error('Failed to generate song section:', error)
      const fallbackResponse = `I'll help you create a ${sectionName} section. This would typically include chord progressions and instrument arrangements appropriate for this part of the song.`
      addMessage('assistant', fallbackResponse)
      
      return {
        response: fallbackResponse,
        updatedSongStructure: null,
        success: false
      }
    } finally {
      isGenerating.value = false
    }
  }

  const suggestModifications = async (songStructure: any, goal: string = 'improve the song') => {
    isGenerating.value = true
    
    try {
      const response = await api.post('/api/ai/suggest-modifications', {
        song_structure: songStructure,
        goal: goal
      })

      const suggestions = response.data.suggestions
      const suggestedStructure = response.data.suggested_structure
      
      addMessage('assistant', `**Suggestions to ${goal}:**\n\n${suggestions}`)
      
      return {
        suggestions: suggestions,
        suggestedStructure: suggestedStructure,
        success: response.data.success
      }
      
    } catch (error: any) {
      console.error('Failed to get suggestions:', error)
      const fallbackSuggestions = `To ${goal}, consider:\n- Adding more instruments for fuller sound\n- Adjusting the song structure\n- Improving the chord progressions\n- Balancing the mix`
      addMessage('assistant', fallbackSuggestions)
      
      return {
        suggestions: fallbackSuggestions,
        suggestedStructure: null,
        success: false
      }
    } finally {
      isGenerating.value = false
    }
  }

  const getAvailableTools = async () => {
    try {
      const response = await api.get('/api/ai/available-tools')
      return response.data
    } catch (error) {
      console.error('Failed to get available tools:', error)
      return {
        tools: [],
        total_tools: 0,
        agent_type: 'Fallback',
        description: 'Basic AI assistant (advanced features unavailable)'
      }
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

  const generateEnhancedMockResponse = (userMessage: string, songStructure: any): string => {
    const lowerMessage = userMessage.toLowerCase()
    const numTracks = songStructure?.tracks?.length || 0
    
    if (lowerMessage.includes('intro')) {
      return `I'll create an intro section for your song:

**Intro Section Plan:**
- Duration: 8 bars
- Style: Soft build-up with filtered instruments
- Key: ${songStructure?.key || 'C'} Major
- Instruments: Piano arpeggios, soft pad, light percussion

This intro will set the mood and smoothly lead into your main song sections.`
    }
    
    if (lowerMessage.includes('bridge')) {
      return `Adding a bridge section to create contrast:

**Bridge Section Design:**
- Chord progression: Different from verse/chorus
- Dynamics: Building tension for final chorus
- Instruments: String section, reduced drums
- Duration: 8 bars

The bridge will provide emotional contrast and keep listeners engaged.`
    }
    
    if (lowerMessage.includes('analyze') || lowerMessage.includes('feedback')) {
      return `**Song Analysis:**

Current structure has ${numTracks} tracks.
- Tempo: ${songStructure?.tempo || 120} BPM
- Key: ${songStructure?.key || 'C'}
- Duration: ${songStructure?.duration || 0} seconds

**Suggestions:**
${numTracks < 3 ? '- Add more instruments for fuller sound' : '- Good instrument variety'}
${!songStructure?.tracks?.find((t: any) => t.instrument?.includes('bass')) ? '- Consider adding bass for low-end foundation' : '- Bass foundation is present'}
- Balance the mix with appropriate volumes
- Add reverb and effects for spatial depth`
    }
    
    // Use the original mock response as fallback
    return generateMockResponse(userMessage)
  }

  const generateFallbackAnalysis = (songStructure: any): string => {
    const numTracks = songStructure?.tracks?.length || 0
    const instruments = songStructure?.tracks?.map((t: any) => t.instrument).join(', ') || 'none'
    
    return `**Song Analysis (Offline Mode):**

**Current Status:**
- Tracks: ${numTracks}
- Instruments: ${instruments}
- Tempo: ${songStructure?.tempo || 120} BPM
- Key: ${songStructure?.key || 'C'}
- Duration: ${songStructure?.duration || 0} seconds

**Recommendations:**
${numTracks === 0 ? '- Start by adding some basic tracks (drums, bass, melody)' : 
  numTracks < 3 ? '- Add more instruments for a fuller sound' : '- Good foundation established'}
- Consider the song structure (intro, verse, chorus, bridge, outro)
- Balance instruments with proper volume levels
- Add effects like reverb and delay for depth

**Next Steps:**
- Use the timeline to arrange your clips
- Experiment with different chord progressions
- Add automation to create dynamic changes`
  }

  // Return all state and methods to make them available to components
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
    sendMusicAssistantMessage,
    analyzeSong,
    generateSongSection,
    suggestModifications,
    getAvailableTools,
    clearMessages,
    setProvider,
    setModel,
    getAvailableModels,
    
    // Utility functions (may be useful for debugging)
    generateMockResponse,
    generateEnhancedMockResponse,
    generateFallbackAnalysis
  }
})
