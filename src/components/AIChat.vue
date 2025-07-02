<template>
  <div class="ai-chat">
    <div class="chat-header">
      <div class="chat-title">
        <Bot class="chat-icon" />
        <h3>AI Assistant</h3>
      </div>
      
      <div class="ai-settings">
        <select 
          v-model="aiStore.selectedProvider" 
          @change="aiStore.setProvider($event.target.value)"
          class="input select provider-select"
        >
          <option v-for="provider in aiStore.providers" :key="provider.id" :value="provider.id">
            {{ provider.name }}
          </option>
        </select>
        
        <select 
          v-model="aiStore.selectedModel" 
          @change="aiStore.setModel($event.target.value)"
          class="input select model-select"
        >
          <option v-for="model in aiStore.getAvailableModels()" :key="model" :value="model">
            {{ model }}
          </option>
        </select>
      </div>
    </div>
    
    <div class="chat-messages" ref="messagesContainer">
      <div v-if="aiStore.messages.length === 0" class="welcome-message">
        <div class="welcome-content">
          <Sparkles class="welcome-icon" />
          <h4>Welcome to GarageAI!</h4>
          <p>I'm your AI music assistant. I can help you create beats, melodies, chord progressions, and more.</p>
          
          <div class="examples-section">
            <h5>{{ $t('ai.examples.title') }}</h5>
            <div class="example-buttons">
              <button 
                class="btn btn-ghost example-btn" 
                @click="sendExampleMessage($t('ai.examples.drum'))"
              >
                {{ $t('ai.examples.drum') }}
              </button>
              <button 
                class="btn btn-ghost example-btn" 
                @click="sendExampleMessage($t('ai.examples.melody'))"
              >
                {{ $t('ai.examples.melody') }}
              </button>
              <button 
                class="btn btn-ghost example-btn" 
                @click="sendExampleMessage($t('ai.examples.bass'))"
              >
                {{ $t('ai.examples.bass') }}
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <div 
        v-for="message in aiStore.messages" 
        :key="message.id"
        class="message"
        :class="{ 'user-message': message.role === 'user', 'assistant-message': message.role === 'assistant' }"
      >
        <div class="message-avatar">
          <User v-if="message.role === 'user'" class="avatar-icon" />
          <Bot v-else class="avatar-icon" />
        </div>
        
        <div class="message-content">
          <div class="message-text" v-html="formatMessage(message.content)"></div>
          <div class="message-time">
            {{ formatTime(message.timestamp) }}
          </div>
        </div>
      </div>
      
      <div v-if="aiStore.isGenerating" class="message assistant-message generating">
        <div class="message-avatar">
          <Bot class="avatar-icon" />
        </div>
        <div class="message-content">
          <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div class="message-text">{{ $t('ai.generating') }}</div>
        </div>
      </div>
    </div>
    
    <div class="chat-input">
      <div class="input-container">
        <textarea
          v-model="currentMessage"
          :placeholder="$t('ai.chatPlaceholder')"
          class="input message-input"
          rows="1"
          @keydown.enter.prevent="handleEnterKey"
          @input="adjustTextareaHeight"
          ref="messageInput"
        ></textarea>
        
        <button 
          class="btn btn-primary send-btn"
          @click="sendMessage"
          :disabled="!currentMessage.trim() || aiStore.isGenerating"
        >
          <Send class="icon" />
          {{ $t('ai.send') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useAIStore } from '../stores/aiStore'
import { useAudioStore } from '../stores/audioStore'
import { Bot, User, Sparkles, Send } from 'lucide-vue-next'

const aiStore = useAIStore()
const audioStore = useAudioStore()

const currentMessage = ref('')
const messagesContainer = ref<HTMLElement>()
const messageInput = ref<HTMLTextAreaElement>()

const sendMessage = async () => {
  if (!currentMessage.value.trim() || aiStore.isGenerating) return
  
  const message = currentMessage.value.trim()
  currentMessage.value = ''
  
  try {
    const response = await aiStore.sendMessage(message)
    
    // Process AI response to update song structure
    processAIResponse(response)
    
    // Scroll to bottom
    await nextTick()
    scrollToBottom()
  } catch (error) {
    console.error('Failed to send message:', error)
  }
}

const sendExampleMessage = (message: string) => {
  currentMessage.value = message
  sendMessage()
}

const handleEnterKey = (event: KeyboardEvent) => {
  if (event.shiftKey) {
    // Allow new line with Shift+Enter
    return
  }
  sendMessage()
}

const adjustTextareaHeight = () => {
  if (messageInput.value) {
    messageInput.value.style.height = 'auto'
    messageInput.value.style.height = messageInput.value.scrollHeight + 'px'
  }
}

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const formatMessage = (content: string) => {
  // Convert markdown-like formatting to HTML
  return content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>')
}

const formatTime = (timestamp: Date) => {
  return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

const processAIResponse = (response: string) => {
  // Simple AI response processing - in a real app, this would be more sophisticated
  const lowerResponse = response.toLowerCase()
  
  if (lowerResponse.includes('drum') && lowerResponse.includes('track')) {
    // Add a drum track
    const trackId = audioStore.addTrack('Drums', 'drums')
    
    // Add some drum clips
    audioStore.addClip(trackId, {
      startTime: 0,
      duration: 16, // 4 bars
      type: 'synth',
      instrument: 'drums',
      volume: 0.8,
      effects: { reverb: 0.1, delay: 0, distortion: 0 }
    })
  }
  
  if (lowerResponse.includes('melody') || lowerResponse.includes('piano')) {
    // Add a piano track
    const trackId = audioStore.addTrack('Piano Melody', 'piano')
    
    audioStore.addClip(trackId, {
      startTime: 0,
      duration: 16, // 4 bars
      type: 'synth',
      instrument: 'piano',
      volume: 0.7,
      effects: { reverb: 0.2, delay: 0, distortion: 0 }
    })
  }
  
  if (lowerResponse.includes('bass')) {
    // Add a bass track
    const trackId = audioStore.addTrack('Bass Line', 'bass')
    
    audioStore.addClip(trackId, {
      startTime: 0,
      duration: 16, // 4 bars
      type: 'synth',
      instrument: 'bass',
      volume: 0.9,
      effects: { reverb: 0, delay: 0, distortion: 0.1 }
    })
  }
}

// Watch for new messages to scroll to bottom
watch(() => aiStore.messages.length, () => {
  nextTick(() => scrollToBottom())
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
  flex-shrink: 0;
}

.chat-title {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.chat-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.chat-title h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.ai-settings {
  display: flex;
  gap: 0.5rem;
}

.provider-select,
.model-select {
  flex: 1;
  padding: 0.5rem;
  font-size: 0.8125rem;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 0;
}

.welcome-message {
  text-align: center;
  padding: 1rem;
}

.welcome-content {
  max-width: 280px;
  margin: 0 auto;
}

.welcome-icon {
  width: 40px;
  height: 40px;
  color: var(--primary);
  margin-bottom: 0.75rem;
}

.welcome-content h4 {
  margin: 0 0 0.5rem 0;
  color: var(--text);
  font-size: 1rem;
}

.welcome-content p {
  margin: 0 0 1rem 0;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  line-height: 1.4;
}

.examples-section h5 {
  margin: 0 0 0.5rem 0;
  font-size: 0.8125rem;
  color: var(--text);
}

.example-buttons {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.example-btn {
  font-size: 0.75rem;
  padding: 0.375rem 0.5rem;
  text-align: left;
  justify-content: flex-start;
}

.message {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}

.user-message {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.user-message .message-avatar {
  background: var(--gradient-primary);
}

.assistant-message .message-avatar {
  background: var(--surface);
  border: 1px solid var(--border);
}

.avatar-icon {
  width: 14px;
  height: 14px;
  color: white;
}

.assistant-message .avatar-icon {
  color: var(--primary);
}

.message-content {
  flex: 1;
  max-width: 75%;
}

.user-message .message-content {
  text-align: right;
}

.message-text {
  background: var(--surface);
  padding: 0.625rem 0.875rem;
  border-radius: 10px;
  color: var(--text);
  font-size: 0.8125rem;
  line-height: 1.4;
  word-wrap: break-word;
}

.user-message .message-text {
  background: var(--gradient-primary);
  color: white;
}

.message-time {
  font-size: 0.6875rem;
  color: var(--text-secondary);
  margin-top: 0.25rem;
  padding: 0 0.25rem;
}

.generating .message-text {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.typing-indicator {
  display: flex;
  gap: 4px;
}

.typing-indicator span {
  width: 5px;
  height: 5px;
  background: var(--primary);
  border-radius: 50%;
  animation: pulse 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

.chat-input {
  padding: 0.875rem;
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  margin-top: auto;
}

.input-container {
  display: flex;
  gap: 0.625rem;
  align-items: flex-end;
}

.message-input {
  flex: 1;
  resize: none;
  min-height: 36px;
  max-height: 80px;
  padding: 0.625rem 0.75rem;
  line-height: 1.3;
  font-size: 0.8125rem;
}

.send-btn {
  padding: 0.625rem 0.875rem;
  flex-shrink: 0;
  font-size: 0.8125rem;
}

.icon {
  width: 14px;
  height: 14px;
}

/* Scrollbar styling */
.chat-messages::-webkit-scrollbar {
  width: 5px;
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

@keyframes pulse {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

@media (max-width: 768px) {
  .ai-settings {
    flex-direction: column;
  }
  
  .message-content {
    max-width: 85%;
  }
  
  .welcome-content {
    padding: 0.75rem;
  }
  
  .welcome-icon {
    width: 32px;
    height: 32px;
  }
}
</style>
