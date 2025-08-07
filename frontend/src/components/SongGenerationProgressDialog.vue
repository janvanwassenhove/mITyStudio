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
              'pending': agent.status === 'pending'
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
import { ref, computed, watch } from 'vue'
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

interface Agent {
  id: string
  icon: any
  status: 'pending' | 'active' | 'completed'
}

interface Props {
  isVisible: boolean
  currentAgent: string
  completedAgents: string[]
  isCompleted?: boolean
  isMultiAgentSuccess?: boolean
  projectInfo?: { name: string; track_count: number } | null
}

interface Emits {
  (e: 'cancel'): void
  (e: 'close'): void
  (e: 'proceed'): void
}

const { t } = useI18n()

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Agent definitions with icons and descriptions
const agents = ref<Agent[]>([
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
    status: 'pending'
  },
  {
    id: 'vocal',
    icon: Mic,
    status: 'pending'
  },
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
])

const progressPercentage = computed(() => {
  const totalAgents = agents.value.length
  const completedCount = props.completedAgents.length
  const currentCount = props.currentAgent ? 1 : 0
  return ((completedCount + currentCount * 0.5) / totalAgents) * 100
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
watch([() => props.currentAgent, () => props.completedAgents], () => {
  agents.value.forEach(agent => {
    if (props.completedAgents.includes(agent.id)) {
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
  overflow: hidden;
  border: 1px solid var(--border);
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
</style>
