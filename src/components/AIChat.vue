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
import { ref, computed, nextTick, onMounted } from 'vue'
import { useAudioStore } from '../stores/audioStore'
import { 
  Bot, User, Trash2, Send, Paperclip, Mic, Lightbulb,
  Play, Plus, Settings, Download, Upload, Music
} from 'lucide-vue-next'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  actions?: ChatAction[]
}

interface ChatAction {
  label: string
  icon: any
  action: string
  params?: any
}

const audioStore = useAudioStore()

// State
const messages = ref<ChatMessage[]>([])
const currentMessage = ref('')
const isTyping = ref(false)
const isOnline = ref(true)
const isListening = ref(false)
const showSuggestions = ref(false)
const messagesContainer = ref<HTMLElement>()
const messageInput = ref<HTMLTextAreaElement>()

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

// Methods
const sendMessage = async (content: string) => {
  if (!content.trim()) return
  
  // Add user message
  const userMessage: ChatMessage = {
    id: `user-${Date.now()}`,
    type: 'user',
    content: content.trim(),
    timestamp: new Date()
  }
  
  messages.value.push(userMessage)
  currentMessage.value = ''
  showSuggestions.value = false
  
  // Scroll to bottom
  await nextTick()
  scrollToBottom()
  
  // Show typing indicator
  isTyping.value = true
  
  // Simulate AI response (in a real app, this would call an AI API)
  setTimeout(() => {
    const aiResponse = generateAIResponse(content)
    const aiMessage: ChatMessage = {
      id: `ai-${Date.now()}`,
      type: 'ai',
      content: aiResponse.content,
      timestamp: new Date(),
      actions: aiResponse.actions
    }
    
    messages.value.push(aiMessage)
    isTyping.value = false
    
    nextTick(() => {
      scrollToBottom()
    })
  }, 1000 + Math.random() * 2000) // Random delay for realism
}

const sendCurrentMessage = () => {
  sendMessage(currentMessage.value)
}

const generateAIResponse = (userMessage: string): { content: string, actions?: ChatAction[] } => {
  const message = userMessage.toLowerCase()
  
  // Chord progression suggestions
  if (message.includes('chord') || message.includes('progression')) {
    return {
      content: `Here are some popular chord progressions you can try:

**I-V-vi-IV (C-G-Am-F)** - The most popular progression in pop music
**vi-IV-I-V (Am-F-C-G)** - Great for emotional ballads  
**I-vi-IV-V (C-Am-F-G)** - Classic 50s progression
**ii-V-I (Dm-G-C)** - Essential jazz progression

Would you like me to create a track with one of these progressions?`,
      actions: [
        { label: 'Add Pop Progression', icon: Plus, action: 'add_chord_progression', params: { type: 'pop' } },
        { label: 'Add Jazz Progression', icon: Plus, action: 'add_chord_progression', params: { type: 'jazz' } }
      ]
    }
  }
  
  // Drum pattern suggestions
  if (message.includes('drum') || message.includes('beat') || message.includes('rhythm')) {
    return {
      content: `Here are some drum patterns for different genres:

**House Music**: Four-on-the-floor kick with hi-hats on off-beats
**Hip-Hop**: Kick on 1 and 3, snare on 2 and 4, with syncopated hi-hats
**Rock**: Basic rock beat with kick, snare, and steady hi-hat
**Trap**: Heavy 808 kicks with rapid hi-hat rolls

I can add any of these patterns to your project!`,
      actions: [
        { label: 'Add House Beat', icon: Plus, action: 'add_drum_pattern', params: { genre: 'house' } },
        { label: 'Add Hip-Hop Beat', icon: Plus, action: 'add_drum_pattern', params: { genre: 'hiphop' } }
      ]
    }
  }
  
  // Bass suggestions
  if (message.includes('bass')) {
    return {
      content: `To make your bass sound fuller, try these techniques:

1. **Layer different bass sounds** - Combine a sub bass with a mid-range bass
2. **Use saturation/distortion** - Adds harmonics and presence
3. **EQ boost around 80-100Hz** - For that chest-thumping low end
4. **Compress with slow attack** - Maintains punch while adding sustain
5. **Side-chain compression** - Creates space and rhythm

Would you like me to add a bass track with these settings?`,
      actions: [
        { label: 'Add Bass Track', icon: Plus, action: 'add_bass_track' },
        { label: 'Apply Bass Effects', icon: Settings, action: 'apply_bass_effects' }
      ]
    }
  }
  
  // Vocal effects
  if (message.includes('vocal') || message.includes('voice')) {
    return {
      content: `Great vocal effects to try:

**Reverb**: Adds space and depth - try hall reverb for ballads, plate for pop
**Delay**: Creates echoes - use 1/8 note delays for rhythmic interest  
**Compression**: Evens out dynamics - use 3:1 ratio with medium attack
**EQ**: High-pass at 80Hz, boost presence around 3-5kHz
**De-esser**: Reduces harsh sibilants
**Chorus**: Adds width and thickness

I can set up a vocal chain for you!`,
      actions: [
        { label: 'Add Vocal Track', icon: Plus, action: 'add_vocal_track' },
        { label: 'Setup Vocal Chain', icon: Settings, action: 'setup_vocal_chain' }
      ]
    }
  }
  
  // Arrangement suggestions
  if (message.includes('arrangement') || message.includes('improve') || message.includes('structure')) {
    const trackCount = audioStore.songStructure.tracks.length
    return {
      content: `Looking at your current project with ${trackCount} tracks, here are some arrangement tips:

**Song Structure**: Try Intro → Verse → Chorus → Verse → Chorus → Bridge → Chorus → Outro
**Frequency Balance**: Make sure you have elements covering lows, mids, and highs
**Dynamics**: Create contrast between sections with different energy levels
**Space**: Don't fill every frequency - leave room for each element to breathe

${trackCount < 3 ? 'Consider adding more instruments for a fuller sound!' : 'Your track count looks good - focus on mixing and effects!'}`,
      actions: [
        { label: 'Analyze Project', icon: Music, action: 'analyze_project' },
        { label: 'Suggest Instruments', icon: Plus, action: 'suggest_instruments' }
      ]
    }
  }
  
  // Default responses
  const defaultResponses = [
    {
      content: `I'd be happy to help with that! As your AI music assistant, I can provide guidance on:

• **Composition**: Chord progressions, melodies, and song structure
• **Production**: Recording techniques and workflow tips  
• **Mixing**: EQ, compression, and effects processing
• **Sound Design**: Creating and shaping sounds
• **Music Theory**: Scales, modes, and harmonic concepts

What specific aspect would you like to explore?`,
      actions: [
        { label: 'Start New Project', icon: Plus, action: 'new_project' },
        { label: 'Analyze Current Song', icon: Music, action: 'analyze_song' }
      ]
    },
    {
      content: `Great question! Music production is all about creativity and experimentation. Here are some general tips:

1. **Start with a strong foundation** - Get your drums and bass locked in first
2. **Less is often more** - Don't overcrowd your mix
3. **Reference other tracks** - Compare your work to professional releases
4. **Trust your ears** - If it sounds good, it probably is good
5. **Take breaks** - Fresh ears catch things tired ears miss

What genre or style are you working on?`
    },
    {
      content: `I'm here to help you create amazing music! Whether you're a beginner or experienced producer, I can assist with:

🎹 **Instrument selection and programming**
🎚️ **Mixing and mastering techniques** 
🎵 **Music theory and composition**
🎛️ **DAW workflow and productivity tips**
🎧 **Sound design and synthesis**

Feel free to ask me anything specific about your current project!`,
      actions: [
        { label: 'Get Project Tips', icon: Lightbulb, action: 'project_tips' }
      ]
    }
  ]
  
  return defaultResponses[Math.floor(Math.random() * defaultResponses.length)]
}

const executeAction = (action: ChatAction) => {
  switch (action.action) {
    case 'add_chord_progression':
      addChordProgression(action.params?.type || 'pop')
      break
    case 'add_drum_pattern':
      addDrumPattern(action.params?.genre || 'house')
      break
    case 'add_bass_track':
      addBassTrack()
      break
    case 'add_vocal_track':
      addVocalTrack()
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

const addChordProgression = (type: string) => {
  const trackId = audioStore.addTrack(`${type.charAt(0).toUpperCase() + type.slice(1)} Chords`, 'piano')
  if (trackId) {
    // Add chord clips based on type
    const chordDuration = 4
    for (let i = 0; i < 4; i++) {
      audioStore.addClip(trackId, {
        startTime: i * chordDuration,
        duration: chordDuration,
        type: 'synth',
        instrument: 'piano',
        volume: 0.7,
        effects: { reverb: 0.2, delay: 0, distortion: 0 }
      })
    }
    
    sendMessage(`✅ Added ${type} chord progression track! The chords are now in your timeline.`)
  }
}

const addDrumPattern = (genre: string) => {
  const trackId = audioStore.addTrack(`${genre.charAt(0).toUpperCase() + genre.slice(1)} Drums`, 'drums')
  if (trackId) {
    // Add drum pattern clips
    for (let i = 0; i < 8; i++) {
      audioStore.addClip(trackId, {
        startTime: i * 2,
        duration: 2,
        type: 'synth',
        instrument: 'drums',
        volume: 0.8,
        effects: { reverb: 0.1, delay: 0, distortion: 0 }
      })
    }
    
    sendMessage(`🥁 Added ${genre} drum pattern! Your beat is ready to groove.`)
  }
}

const addBassTrack = () => {
  const trackId = audioStore.addTrack('Bass', 'bass')
  if (trackId) {
    // Add bass clips
    for (let i = 0; i < 4; i++) {
      audioStore.addClip(trackId, {
        startTime: i * 4,
        duration: 4,
        type: 'synth',
        instrument: 'bass',
        volume: 0.8,
        effects: { reverb: 0, delay: 0, distortion: 0.1 }
      })
    }
    
    sendMessage(`🎸 Added bass track with fuller sound settings! Check out that low-end presence.`)
  }
}

const addVocalTrack = () => {
  const trackId = audioStore.addTrack('Vocals', 'vocals')
  if (trackId) {
    audioStore.updateTrack(trackId, {
      effects: { reverb: 0.3, delay: 0.2, distortion: 0 }
    })
    
    sendMessage(`🎤 Added vocal track with professional effects chain! Ready for recording.`)
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
    messages.value = []
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
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px'
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatMessage = (content: string): string => {
  // Convert markdown-like formatting to HTML
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
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

onMounted(() => {
  // Focus the input
  messageInput.value?.focus()
})
</script>

<style scoped>
.ai-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
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
  font-size: 0.875rem;
  resize: none;
  min-height: 40px;
  max-height: 120px;
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
}
</style>
