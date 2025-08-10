<template>
  <div v-if="isVisible" class="progress-overlay" @click="handleOverlayClick">
    <div class="progress-dialog" @click.stop>
      <!-- Success State -->
      <div v-if="isCompleted" class="success-header">
        <div class="success-title">
          <CheckCircle :size="32" class="success-icon" />
          <h2>{{ $t('songGeneration.success.title') }}</h2>
        </div>
        <div class="success-subtitle">
          {{ isMultiAgentSuccess ? $t('songGeneration.success.multiAgent') : $t('songGeneration.success.fallback') }}
        </div>
        <div v-if="projectInfo" class="project-info">
          {{ $t('songGeneration.success.projectCreated', projectInfo) }}
        </div>
        <div class="success-message">
          {{ $t('songGeneration.success.tracksVisible') }}
        </div>
        <div class="success-actions">
          <button @click="handleProceed" class="btn btn-primary success-btn">
            <Check :size="16" />
            {{ $t('common.proceed') }}
          </button>
        </div>
      </div>

      <!-- Progress State -->
      <div v-else class="progress-header">
        <div class="progress-title">
          <Music :size="24" class="title-icon" />
          <h2>{{ $t('songGeneration.generating') }}</h2>
        </div>
        <div class="progress-subtitle">
          {{ $t('songGeneration.multiAgentSystem') }}
        </div>
      </div>

      <div v-if="!isCompleted" class="progress-content">
        <!-- Musical Animation -->
        <div class="musical-animation">
          <div class="note-container">
            <div v-for="i in 8" :key="i" class="musical-note" :style="{ animationDelay: `${i * 0.2}s` }">
              ♪
            </div>
          </div>
          <div class="wave-container">
            <div class="wave wave-1"></div>
            <div class="wave wave-2"></div>
            <div class="wave wave-3"></div>
          </div>
        </div>

        <!-- Progress Bar -->
        <div class="progress-bar-container">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: `${progressPercentage}%` }"></div>
          </div>
          <div class="progress-text">
            {{ Math.round(progressPercentage) }}% {{ $t('common.complete') }}
          </div>
        </div>

        <!-- Agent Phases -->
        <div class="agents-grid">
          <div 
            v-for="(agent, index) in agents" 
            :key="agent.id"
            class="agent-card"
            :class="{ 
              'active': agent.status === 'active',
              'completed': agent.status === 'completed',
              'pending': agent.status === 'pending',
              'skipped': agent.status === 'skipped'
            }"
          >
            <div class="agent-number">{{ index + 1 }}</div>
            <div class="agent-icon">
              <component :is="agent.icon" :size="20" />
            </div>
            <div class="agent-info">
              <div class="agent-name">
                {{ $t(`songGeneration.agents.${agent.id}`) || agent.id }}
              </div>
              <div class="agent-status">
                <span v-if="agent.status === 'active'" class="status-active">
                  <Loader2 :size="12" class="animate-spin" />
                  {{ $t('songGeneration.processing') }}
                </span>
                <span v-else-if="agent.status === 'completed'" class="status-completed">
                  <Check :size="12" />
                  {{ $t('songGeneration.completed') }}
                </span>
                <span v-else-if="agent.status === 'skipped'" class="status-skipped">
                  <X :size="12" />
                  {{ $t('songGeneration.skipped') }}
                </span>
                <span v-else class="status-pending">
                  <Clock :size="12" />
                  {{ $t('songGeneration.pending') }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Current Phase -->
        <div class="current-phase">
          <div class="phase-label">{{ $t('songGeneration.currentPhase') }}:</div>
          <div class="phase-name">
            {{ currentAgentName || 'Initializing...' }}
          </div>
          <div class="phase-description">
            {{ currentAgentDescription || 'Preparing multi-agent song generation system...' }}
          </div>
          <div class="phase-progress">
            <div class="progress-dots">
              <span v-for="i in 3" :key="i" class="dot" :class="{ active: (Date.now() / 500) % 3 >= i - 1 }"></span>
            </div>
          </div>
        </div>

        <!-- User Decision Required -->
        <div v-if="userDecisionData" class="user-decision-panel">
          <div class="decision-header">
            <div class="decision-icon">
              <CheckCircle :size="20" />
            </div>
            <div class="decision-title">
              {{ $t('songGeneration.userDecision.title') }}
            </div>
          </div>
          
          <!-- Song Information -->
          <div v-if="userDecisionData.song_info" class="song-info">
            <h4>{{ userDecisionData.song_info.title }}</h4>
            <p class="song-description">{{ userDecisionData.song_info.description }}</p>
            <div class="song-details">
              <span class="detail-item">
                <strong>{{ $t('songGeneration.genre') }}:</strong> {{ userDecisionData.song_info.genre }}
              </span>
              <span class="detail-item">
                <strong>{{ $t('songGeneration.mood') }}:</strong> {{ userDecisionData.song_info.mood }}
              </span>
              <span class="detail-item">
                <strong>{{ $t('songGeneration.duration') }}:</strong> {{ userDecisionData.song_info.duration }}s
              </span>
            </div>
          </div>

          <!-- Quality Assessment -->
          <div v-if="userDecisionData.quality_assessment" class="quality-assessment">
            <h5>{{ $t('songGeneration.userDecision.qualityAssessment') }}</h5>
            <div class="assessment-scores">
              <div class="score-item">
                <span class="score-label">{{ $t('songGeneration.creativity') }}:</span>
                <span class="score-value">{{ userDecisionData.quality_assessment.creativity_score }}/10</span>
              </div>
              <div class="score-item">
                <span class="score-label">{{ $t('songGeneration.coherence') }}:</span>
                <span class="score-value">{{ userDecisionData.quality_assessment.coherence_score }}/10</span>
              </div>
              <div class="score-item">
                <span class="score-label">{{ $t('songGeneration.overall') }}:</span>
                <span class="score-value">{{ userDecisionData.quality_assessment.overall_score }}/10</span>
              </div>
            </div>
            <div v-if="userDecisionData.quality_assessment.feedback" class="assessment-feedback">
              <p>{{ userDecisionData.quality_assessment.feedback }}</p>
            </div>
          </div>

          <!-- User Decision Options -->
          <div class="decision-actions">
            <div class="decision-prompt">
              {{ $t('songGeneration.userDecision.prompt') }}
            </div>
            <div class="decision-buttons">
              <button 
                @click="submitUserDecision('accept')" 
                class="btn btn-success decision-btn"
                :disabled="submittingDecision"
              >
                <Check :size="16" />
                {{ $t('songGeneration.userDecision.accept') }}
              </button>
              <button 
                @click="submitUserDecision('improve')" 
                class="btn btn-warning decision-btn"
                :disabled="submittingDecision"
              >
                <Search :size="16" />
                {{ $t('songGeneration.userDecision.improve') }}
              </button>
            </div>
          </div>
        </div>

        <!-- QA Restart Feedback -->
        <div v-if="restartFeedback" class="restart-feedback">
          <div class="restart-header">
            <div class="restart-icon">
              <Search :size="16" />
            </div>
            <div class="restart-title">
              {{ $t('songGeneration.qaRestart.title', { attempt: restartFeedback.attempt }) }}
            </div>
          </div>
          <div class="restart-reason">
            {{ restartFeedback.reason }}
          </div>
          <div class="restart-action">
            {{ $t('songGeneration.qaRestart.improving') }}
          </div>
        </div>

        <!-- Cancel Button -->
        <div class="progress-actions">
          <button @click="cancelGeneration" class="btn btn-secondary">
            <X :size="16" />
            {{ $t('common.cancel') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { 
  Music, 
  Loader2, 
  Check, 
  X,
  Palette,
  Mic,
  Piano,
  Volume2,
  Search,
  CheckCircle,
  Sliders,
  FileMusic,
  Clock
} from 'lucide-vue-next'


interface Props {
  isVisible: boolean
  currentAgent: string
  completedAgents: string[]
  isCompleted?: boolean
  isMultiAgentSuccess?: boolean
  projectInfo?: { name: string; track_count: number } | null
  isInstrumental?: boolean
}

interface Emits {
  (e: 'cancel'): void
  (e: 'close'): void
  (e: 'proceed'): void
  (e: 'user-decision', decision: { choice: 'accept' | 'improve'; feedback_note?: string }): void
}

// User Decision Data Interface
interface UserDecisionData {
  type: 'user_decision_required'
  song_info?: {
    title: string
    description: string
    genre: string
    mood: string
    duration: number
  }
  quality_assessment?: {
    creativity_score: number
    coherence_score: number
    overall_score: number
    feedback: string
  }
  can_restart: boolean
}

const { t } = useI18n()

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// QA Restart Feedback
const restartFeedback = ref<{ reason: string; attempt: number } | null>(null)

// User Decision Data
const userDecisionData = ref<UserDecisionData | null>(null)
const submittingDecision = ref(false)

// Expose function to set restart feedback (called from parent)
const setRestartFeedback = (reason: string, attempt: number) => {
  restartFeedback.value = { reason, attempt }
  // Clear feedback after 10 seconds
  setTimeout(() => {
    restartFeedback.value = null
  }, 10000)
}

// Expose function to set user decision data (called from parent)
const setUserDecisionData = (data: UserDecisionData) => {
  userDecisionData.value = data
}

// Submit user decision
const submitUserDecision = async (choice: 'accept' | 'improve') => {
  if (submittingDecision.value) return
  
  submittingDecision.value = true
  try {
    // Emit decision to parent component
    emit('user-decision', { choice })
    
    // Clear user decision data after submission
    userDecisionData.value = null
  } catch (error) {
    console.error('Error submitting user decision:', error)
  } finally {
    submittingDecision.value = false
  }
}

// Expose the functions for parent component
defineExpose({ 
  setRestartFeedback, 
  setUserDecisionData 
})

// Agent definitions with icons and descriptions
const agents = computed(() => {
  const allAgents = [
    {
      id: 'composer',
      icon: FileMusic,
      status: 'pending'
    },
    {
      id: 'arrangement',
      icon: Sliders,
      status: 'pending'
    },
    {
      id: 'lyrics',
      icon: FileMusic,
      status: props.isInstrumental ? 'skipped' : 'pending'
    },
    {
      id: 'vocal',
      icon: Mic,
      status: props.isInstrumental ? 'skipped' : 'pending'
    }
  ]

  // Add remaining agents
  allAgents.push(
    {
      id: 'instrument',
      icon: Piano,
      status: 'pending'
    },
    {
      id: 'effects',
      icon: Volume2,
      status: 'pending'
    },
    {
      id: 'review',
      icon: Search,
      status: 'pending'
    },
    {
      id: 'design',
      icon: Palette,
      status: 'pending'
    },
    {
      id: 'qa',
      icon: CheckCircle,
      status: 'pending'
    }
  )

  return allAgents
})

const progressPercentage = computed(() => {
  // Filter completed agents to only include relevant ones for this track type
  const relevantAgentIds = agents.value.filter(agent => agent.status !== 'skipped').map(agent => agent.id)
  const relevantCompletedCount = props.completedAgents.filter(agentId => 
    relevantAgentIds.includes(agentId)
  ).length
  const currentCount = props.currentAgent && relevantAgentIds.includes(props.currentAgent) ? 1 : 0
  return ((relevantCompletedCount + currentCount * 0.5) / relevantAgentIds.length) * 100
})

const currentAgentName = computed(() => {
  if (!props.currentAgent) return ''
  return t(`songGeneration.agents.${props.currentAgent}`)
})

const currentAgentDescription = computed(() => {
  if (!props.currentAgent) return ''
  return t(`songGeneration.descriptions.${props.currentAgent}`)
})

// Update agent statuses based on props
watch([() => props.currentAgent, () => props.completedAgents, () => props.isInstrumental], () => {
  agents.value.forEach(agent => {
    // Skip lyrics and vocal agents for instrumental tracks
    if (props.isInstrumental && (agent.id === 'lyrics' || agent.id === 'vocal')) {
      agent.status = 'skipped'
    } else if (props.completedAgents.includes(agent.id)) {
      agent.status = 'completed'
    } else if (agent.id === props.currentAgent) {
      agent.status = 'active'
    } else {
      agent.status = 'pending'
    }
  })
}, { immediate: true })

const cancelGeneration = () => {
  emit('cancel')
}

const handleOverlayClick = () => {
  // Only allow closing on overlay click if completed
  if (props.isCompleted) {
    emit('close')
  }
}

const handleProceed = () => {
  emit('proceed')
}
</script>

<style scoped>
.progress-overlay {
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
  backdrop-filter: blur(8px);
}

.progress-dialog {
  background: var(--surface);
  border-radius: 16px;
  box-shadow: var(--shadow-xl), var(--shadow-glow);
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

/* Custom scrollbar */
.progress-dialog::-webkit-scrollbar {
  width: 8px;
}

.progress-dialog::-webkit-scrollbar-track {
  background: var(--surface-elevated);
  border-radius: 4px;
}

.progress-dialog::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 4px;
}

.progress-dialog::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

/* Dark theme support */
@media (prefers-color-scheme: dark) {
  .progress-dialog {
    background: rgba(31, 41, 55, 0.98);
    border: 2px solid rgba(75, 85, 99, 0.8);
  }
}

.progress-header {
  padding: 24px 24px 0;
  text-align: center;
}

.progress-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 8px;
}

.title-icon {
  color: var(--primary);
  animation: float 3s ease-in-out infinite;
}

.progress-title h2 {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text);
}

.progress-subtitle {
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
}

.progress-content {
  padding: 1.5rem;
  flex: 1;
  min-height: 0;
}

@keyframes float {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
}

/* Musical Animation */
.musical-animation {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  margin-bottom: 2rem;
}

.note-container {
  display: flex;
  justify-content: center;
  gap: 1rem;
  height: 2rem;
}

.musical-note {
  font-size: 1.5rem;
  color: var(--primary);
  animation: bounce 2s infinite;
  animation-fill-mode: both;
  font-weight: bold;
}

@keyframes bounce {
  0%, 20%, 50%, 80%, 100% {
    transform: translateY(0);
  }
  40% {
    transform: translateY(-10px);
  }
  60% {
    transform: translateY(-5px);
  }
}

.wave-container {
  display: flex;
  justify-content: center;
  gap: 0.25rem;
  height: 2rem;
  align-items: end;
}

.wave {
  width: 4px;
  background: linear-gradient(to top, var(--primary), var(--secondary));
  border-radius: 2px;
  animation: wave 1.5s ease-in-out infinite;
}

.wave-1 { animation-delay: 0s; height: 1rem; }
.wave-2 { animation-delay: 0.1s; height: 1.5rem; }
.wave-3 { animation-delay: 0.2s; height: 1.2rem; }
.wave-3 { animation-delay: 2s; }

@keyframes wave {
  0%, 100% {
    transform: scaleY(0.5) scaleX(1);
  }
  50% {
    transform: scaleY(1) scaleX(0.8);
  }
}

/* Progress Bar */
.progress-bar-container {
  margin-bottom: 24px;
}

/* Progress Bar */
.progress-bar-container {
  margin-bottom: 2rem;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: var(--surface-elevated);
  border-radius: 8px;
  overflow: hidden;
  margin-bottom: 0.5rem;
  border: 1px solid var(--border);
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), var(--secondary));
  border-radius: 8px;
  transition: width 0.6s ease;
  position: relative;
}

.progress-fill::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    45deg,
    transparent 30%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 70%
  );
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.progress-text {
  text-align: center;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--primary);
}

/* Agents Grid - Updated to match GenerateSongDialog theme */
.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 2rem;
}

.agent-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1rem;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  transition: all var(--transition-normal);
  position: relative;
}

.agent-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.agent-number {
  position: absolute;
  top: -8px;
  left: -8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--border);
  color: var(--text-secondary);
  font-size: 0.75rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  border: 2px solid var(--surface);
}

.agent-card.pending {
  opacity: 0.6;
}

.agent-card.active {
  border-color: var(--primary);
  background: linear-gradient(135deg, var(--surface) 0%, rgba(158, 127, 255, 0.1) 100%);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg), 0 0 20px rgba(158, 127, 255, 0.2);
}

.agent-card.active .agent-number {
  background: var(--primary);
  color: white;
  animation: pulse 2s infinite;
}

.agent-card.completed {
  border-color: var(--success);
  background: linear-gradient(135deg, var(--surface) 0%, rgba(16, 185, 129, 0.1) 100%);
}

.agent-card.completed .agent-number {
  background: var(--success);
  color: white;
}

.agent-card.skipped {
  border-color: var(--text-secondary);
  background: var(--surface-elevated);
  opacity: 0.7;
}

.agent-card.skipped .agent-number {
  background: var(--text-secondary);
  color: white;
}

.agent-card.skipped .agent-icon {
  background: var(--text-secondary);
  color: white;
  opacity: 0.7;
}

@keyframes pulse {
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(158, 127, 255, 0.7); }
  70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(158, 127, 255, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(158, 127, 255, 0); }
}

.agent-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--surface-elevated);
  color: var(--text-secondary);
  transition: all var(--transition-normal);
}

.agent-card.active .agent-icon {
  background: var(--primary);
  color: white;
  transform: scale(1.1);
}

.agent-card.completed .agent-icon {
  background: var(--success);
  color: white;
}

.agent-info {
  flex: 1;
  min-width: 0;
}

.agent-name {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text);
  margin-bottom: 0.25rem;
}

.agent-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-active {
  color: var(--primary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-completed {
  color: var(--success);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-pending {
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.status-skipped {
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.25rem;
  opacity: 0.7;
  font-style: italic;
}

/* Current Phase - Updated styling */
.current-phase {
  text-align: center;
  margin-bottom: 2rem;
  padding: 1.5rem;
  background: var(--surface-elevated);
  border-radius: 12px;
  border: 1px solid var(--border);
}

.phase-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.phase-name {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--primary);
  margin-bottom: 0.75rem;
}

.phase-description {
  font-size: 0.875rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 1rem;
  font-weight: 500;
}

.phase-progress {
  display: flex;
  justify-content: center;
}

.progress-dots {
  display: flex;
  gap: 0.5rem;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border);
  transition: all var(--transition-normal);
}

.dot.active {
  background: var(--primary);
  transform: scale(1.2);
  box-shadow: 0 0 8px rgba(158, 127, 255, 0.5);
}

/* QA Restart Feedback */
.restart-feedback {
  background: linear-gradient(135deg, rgba(255, 193, 7, 0.1) 0%, rgba(255, 193, 7, 0.05) 100%);
  border: 1px solid rgba(255, 193, 7, 0.3);
  border-radius: 12px;
  padding: 1rem;
  margin-bottom: 1.5rem;
  animation: slideInRestart 0.3s ease-out;
}

.restart-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.restart-icon {
  background: rgba(255, 193, 7, 0.2);
  border-radius: 8px;
  padding: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(255, 193, 7);
}

.restart-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(217, 119, 6);
}

.restart-reason {
  font-size: 0.8rem;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
  line-height: 1.4;
  padding-left: 0.25rem;
}

.restart-action {
  font-size: 0.75rem;
  color: var(--text-secondary);
  font-style: italic;
  padding-left: 0.25rem;
}

@keyframes slideInRestart {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Actions - Updated to match GenerateSongDialog button style */
.progress-actions {
  text-align: center;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 12px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-normal);
  font-family: inherit;
}

.btn-secondary {
  background: var(--surface-elevated);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.btn-secondary:hover {
  background: var(--surface-hover);
  border-color: var(--border-hover);
}

.btn-primary {
  background: var(--primary);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

/* Success State Styles */
.success-header {
  padding: 2rem 2rem 1.5rem;
  text-align: center;
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%);
  border-bottom: 1px solid var(--border);
}

.success-title {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-bottom: 12px;
}

.success-icon {
  color: var(--success);
  animation: successPulse 2s ease-in-out infinite;
}

.success-title h2 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text);
}

.success-subtitle {
  color: var(--text-secondary);
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 16px;
}

.project-info {
  background: var(--surface-elevated);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  margin: 16px 0;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.success-message {
  color: var(--text);
  font-size: 1rem;
  margin: 16px 0 24px;
  line-height: 1.5;
}

.success-actions {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.success-btn {
  min-width: 140px;
  font-size: 1rem;
  padding: 0.875rem 2rem;
  background: var(--success);
  color: white;
  border: none;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
}

.success-btn:hover {
  background: #16a34a;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(34, 197, 94, 0.4);
}

@keyframes successPulse {
  0%, 100% { 
    transform: scale(1);
    opacity: 1;
  }
  50% { 
    transform: scale(1.1);
    opacity: 0.8;
  }
}

/* Dark theme support for success state */
@media (prefers-color-scheme: dark) {
  .success-header {
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%);
  }
  
  .project-info {
    background: rgba(31, 41, 55, 0.8);
    border-color: rgba(75, 85, 99, 0.6);
  }
}

.btn-secondary:hover {
  background: var(--border);
  color: var(--text);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .agents-grid {
    grid-template-columns: 1fr;
    gap: 0.75rem;
  }
  
  .agent-card {
    padding: 0.75rem;
    gap: 0.5rem;
  }
  
  .agent-icon {
    width: 28px;
    height: 28px;
  }
  
  .agent-name {
    font-size: 0.8rem;
  }
  
  .agent-status {
    font-size: 0.7rem;
  }
  
  .progress-dialog {
    margin: 1rem;
    width: calc(100% - 2rem);
  }
}

/* User Decision Panel */
.user-decision-panel {
  background: linear-gradient(135deg, var(--surface-elevated) 0%, rgba(59, 130, 246, 0.05) 100%);
  border: 2px solid var(--primary);
  border-radius: 12px;
  padding: 1.5rem;
  margin: 1rem 0 2rem 0;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.1);
}

.decision-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.decision-icon {
  background: var(--primary);
  color: white;
  padding: 0.5rem;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.decision-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text);
}

.song-info {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.song-info h4 {
  margin: 0 0 0.5rem 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text);
}

.song-description {
  margin: 0 0 0.75rem 0;
  color: var(--text-secondary);
  line-height: 1.5;
}

.song-details {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.detail-item {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.detail-item strong {
  color: var(--text);
}

.quality-assessment {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
}

.quality-assessment h5 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
}

.assessment-scores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.score-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background: var(--surface-elevated);
  border-radius: 6px;
}

.score-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.score-value {
  font-weight: 600;
  color: var(--primary);
}

.assessment-feedback {
  padding: 0.75rem;
  background: var(--surface-elevated);
  border-radius: 6px;
  border-left: 3px solid var(--primary);
}

.assessment-feedback p {
  margin: 0;
  color: var(--text-secondary);
  font-style: italic;
  line-height: 1.5;
}

.decision-actions {
  margin-top: 1.5rem;
  padding-bottom: 1rem;
}

.decision-prompt {
  text-align: center;
  color: var(--text);
  font-weight: 500;
  margin-bottom: 1rem;
}

.decision-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  padding-top: 0.5rem;
}

.decision-btn {
  min-width: 140px;
  padding: 0.75rem 1.5rem;
  font-weight: 500;
  border-radius: 8px;
  transition: all var(--transition-normal);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.decision-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none !important;
}

.btn-success {
  background: var(--success);
  color: white;
  border: 1px solid var(--success);
}

.btn-success:hover:not(:disabled) {
  background: #16a34a;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
}

.btn-warning {
  background: #f59e0b;
  color: white;
  border: 1px solid #f59e0b;
}

.btn-warning:hover:not(:disabled) {
  background: #d97706;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
}

/* Dark theme support for user decision panel */
@media (prefers-color-scheme: dark) {
  .user-decision-panel {
    background: linear-gradient(135deg, rgba(31, 41, 55, 0.9) 0%, rgba(59, 130, 246, 0.1) 100%);
    border-color: rgba(59, 130, 246, 0.6);
  }
  
  .song-info,
  .quality-assessment {
    background: rgba(31, 41, 55, 0.8);
    border-color: rgba(75, 85, 99, 0.6);
  }
  
  .score-item,
  .assessment-feedback {
    background: rgba(31, 41, 55, 0.6);
  }
}

/* Mobile responsiveness for decision panel */
@media (max-width: 768px) {
  .user-decision-panel {
    padding: 1rem;
    margin: 0.75rem 0;
  }
  
  .decision-buttons {
    flex-direction: column;
    gap: 0.75rem;
  }
  
  .decision-btn {
    width: 100%;
  }
  
  .song-details {
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .assessment-scores {
    grid-template-columns: 1fr;
  }
}
</style>
