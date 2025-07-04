<template>
  <div class="theme-toggle">
    <button 
      class="theme-btn"
      @click="toggleTheme"
      :title="`Switch to ${getNextThemeLabel()}`"
    >
      <div class="theme-icon-container">
        <Sun 
          v-if="!themeStore.isDark" 
          class="theme-icon sun-icon"
          :class="{ 'active': !themeStore.isDark }"
        />
        <Moon 
          v-if="themeStore.isDark" 
          class="theme-icon moon-icon"
          :class="{ 'active': themeStore.isDark }"
        />
        <Monitor 
          v-if="themeStore.mode === 'auto'" 
          class="theme-icon auto-icon"
        />
      </div>
      
      <span class="theme-label">{{ themeStore.themeDisplayName }}</span>
      
      <div class="theme-indicator">
        <div 
          class="indicator-dot"
          :class="{ 
            'light': !themeStore.isDark && themeStore.mode !== 'auto',
            'dark': themeStore.isDark && themeStore.mode !== 'auto',
            'auto': themeStore.mode === 'auto'
          }"
        ></div>
      </div>
    </button>
    
    <!-- Advanced theme options dropdown -->
    <div v-if="showAdvanced" class="theme-dropdown">
      <div class="dropdown-header">
        <h4>Theme Options</h4>
        <button class="close-btn" @click="showAdvanced = false">
          <X class="icon" />
        </button>
      </div>
      
      <div class="theme-modes">
        <button 
          v-for="mode in themeModes"
          :key="mode.value"
          class="mode-btn"
          :class="{ 'active': themeStore.mode === mode.value }"
          @click="setThemeMode(mode.value)"
        >
          <component :is="mode.icon" class="mode-icon" />
          <div class="mode-info">
            <span class="mode-name">{{ mode.name }}</span>
            <span class="mode-desc">{{ mode.description }}</span>
          </div>
        </button>
      </div>
      
      <div class="preset-themes">
        <h5>Preset Themes</h5>
        <div class="preset-grid">
          <button 
            v-for="(preset, name) in themeStore.presetThemes"
            :key="name"
            class="preset-btn"
            @click="applyPreset(name)"
            :title="`Apply ${name} theme`"
          >
            <div 
              class="preset-preview"
              :style="{ 
                background: `linear-gradient(135deg, ${preset.primary} 0%, ${preset.secondary} 100%)`,
                border: `2px solid ${preset.border}`
              }"
            ></div>
            <span class="preset-name">{{ formatPresetName(name) }}</span>
          </button>
        </div>
      </div>
    </div>
    
    <!-- Quick toggle for mobile -->
    <button 
      v-if="isMobile"
      class="mobile-toggle"
      @click="quickToggle"
      :title="themeStore.themeDisplayName"
    >
      <Sun v-if="!themeStore.isDark" class="icon" />
      <Moon v-else class="icon" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useThemeStore, type ThemeMode } from '../stores/themeStore'
import { Sun, Moon, Monitor, X } from 'lucide-vue-next'

const themeStore = useThemeStore()

// Component state
const showAdvanced = ref(false)
const isMobile = ref(false)

// Theme mode options
const themeModes = [
  {
    value: 'light' as ThemeMode,
    name: 'Light',
    description: 'Always use light theme',
    icon: Sun
  },
  {
    value: 'dark' as ThemeMode,
    name: 'Dark',
    description: 'Always use dark theme',
    icon: Moon
  },
  {
    value: 'auto' as ThemeMode,
    name: 'Auto',
    description: 'Follow system preference',
    icon: Monitor
  }
]

// Methods
const toggleTheme = () => {
  themeStore.toggleMode()
}

const quickToggle = () => {
  if (themeStore.mode === 'auto') {
    themeStore.setMode('light')
  } else {
    themeStore.toggleMode()
  }
}

const setThemeMode = (mode: ThemeMode) => {
  themeStore.setMode(mode)
  showAdvanced.value = false
}

const applyPreset = (presetName: string) => {
  themeStore.applyPresetTheme(presetName as keyof typeof themeStore.presetThemes)
  showAdvanced.value = false
}

const formatPresetName = (name: string): string => {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const getNextThemeLabel = (): string => {
  switch (themeStore.mode) {
    case 'light': return 'Dark Mode'
    case 'dark': return 'Auto Mode'
    case 'auto': return 'Light Mode'
    default: return 'Dark Mode'
  }
}

// Responsive handling
const checkMobile = () => {
  isMobile.value = window.innerWidth < 768
}

const handleResize = () => {
  checkMobile()
}

const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as HTMLElement
  if (!target.closest('.theme-toggle')) {
    showAdvanced.value = false
  }
}

onMounted(() => {
  checkMobile()
  window.addEventListener('resize', handleResize)
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  document.removeEventListener('click', handleClickOutside)
})
</script>

<style scoped>
.theme-toggle {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.theme-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text);
  cursor: pointer;
  transition: all var(--transition-normal);
  font-size: 0.875rem;
  min-width: 120px;
}

.theme-btn:hover {
  background: var(--border);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.theme-icon-container {
  position: relative;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.theme-icon {
  width: 16px;
  height: 16px;
  transition: all var(--transition-normal);
  position: absolute;
}

.sun-icon {
  color: #F59E0B;
  transform: rotate(0deg);
}

.moon-icon {
  color: #6366F1;
  transform: rotate(0deg);
}

.auto-icon {
  color: var(--text-secondary);
  width: 12px;
  height: 12px;
  top: -2px;
  right: -2px;
}

.theme-icon.active {
  transform: rotate(360deg) scale(1.1);
}

.theme-label {
  flex: 1;
  text-align: left;
  font-weight: 500;
}

.theme-indicator {
  width: 8px;
  height: 8px;
}

.indicator-dot {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  transition: all var(--transition-normal);
}

.indicator-dot.light {
  background: #F59E0B;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
}

.indicator-dot.dark {
  background: #6366F1;
  box-shadow: 0 0 8px rgba(99, 102, 241, 0.4);
}

.indicator-dot.auto {
  background: linear-gradient(45deg, #F59E0B 50%, #6366F1 50%);
  box-shadow: 0 0 8px rgba(158, 127, 255, 0.4);
}

.mobile-toggle {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.mobile-toggle:hover {
  background: var(--border);
  transform: scale(1.05);
}

.mobile-toggle .icon {
  width: 18px;
  height: 18px;
  color: var(--text);
}

.theme-dropdown {
  position: absolute;
  top: calc(100% + 0.5rem);
  right: 0;
  width: 320px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-xl);
  z-index: 1000;
  overflow: hidden;
  animation: fadeIn var(--transition-normal) ease-out;
}

.dropdown-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--gradient-surface);
}

.dropdown-header h4 {
  margin: 0;
  font-size: 1rem;
  color: var(--text);
}

.close-btn {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all var(--transition-fast);
}

.close-btn:hover {
  background: var(--border);
  color: var(--text);
}

.close-btn .icon {
  width: 14px;
  height: 14px;
}

.theme-modes {
  padding: 1rem;
}

.mode-btn {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-normal);
  margin-bottom: 0.5rem;
}

.mode-btn:hover {
  background: var(--border);
}

.mode-btn.active {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.mode-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.mode-info {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
}

.mode-name {
  font-weight: 500;
  font-size: 0.875rem;
}

.mode-desc {
  font-size: 0.75rem;
  opacity: 0.8;
  margin-top: 0.125rem;
}

.preset-themes {
  padding: 1rem;
  border-top: 1px solid var(--border);
}

.preset-themes h5 {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  color: var(--text);
  font-weight: 600;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.preset-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.preset-btn:hover {
  background: var(--border);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.preset-preview {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  transition: all var(--transition-normal);
}

.preset-btn:hover .preset-preview {
  transform: scale(1.1);
}

.preset-name {
  font-size: 0.75rem;
  color: var(--text);
  font-weight: 500;
  text-transform: capitalize;
}

/* Animations */
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .theme-btn {
    min-width: auto;
    padding: 0.5rem;
  }
  
  .theme-label {
    display: none;
  }
  
  .theme-dropdown {
    width: 280px;
    right: -50px;
  }
  
  .preset-grid {
    grid-template-columns: repeat(4, 1fr);
  }
  
  .preset-btn {
    padding: 0.5rem;
  }
  
  .preset-preview {
    width: 24px;
    height: 24px;
  }
  
  .preset-name {
    font-size: 0.625rem;
  }
}

/* High contrast mode */
@media (prefers-contrast: high) {
  .theme-btn,
  .mode-btn,
  .preset-btn {
    border-width: 2px;
  }
  
  .indicator-dot {
    border: 2px solid var(--text);
  }
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .theme-icon,
  .indicator-dot,
  .preset-preview {
    transition: none;
  }
  
  .theme-icon.active {
    transform: none;
  }
}
</style>
