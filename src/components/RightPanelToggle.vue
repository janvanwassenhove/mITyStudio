<template>
  <div class="right-panel">
    <div class="panel-tabs">
      <button 
        v-for="tab in tabs"
        :key="tab.id"
        class="tab-btn"
        :class="{ 'active': activeTab === tab.id }"
        @click="activeTab = tab.id"
        :title="tab.name"
      >
        <component :is="tab.icon" class="icon" />
        <span class="tab-label">{{ tab.name }}</span>
      </button>
    </div>
    
    <div class="panel-content">
      <!-- AI Chat Tab -->
      <div v-if="activeTab === 'ai'" class="tab-panel">
        <AiChat />
      </div>
      
      <!-- Sample Library Tab -->
      <div v-if="activeTab === 'samples'" class="tab-panel">
        <SampleLibrary />
      </div>
      
      <!-- JSON Song Structure Tab (replaces Effects) -->
      <div v-if="activeTab === 'effects'" class="tab-panel">
        <JSONStructurePanel />
      </div>
      
      <!-- Settings Tab -->
      <div v-if="activeTab === 'settings'" class="tab-panel">
        <div class="settings-panel">
          <div class="panel-header align-timeline-header">
            <Settings class="header-icon" />
            <h3>Settings</h3>
          </div>
          
          <div class="settings-content">
            <div class="setting-section">
              <h4>Theme Settings</h4>
              
              <div class="setting-item">
                <label>Theme Mode</label>
                <ThemeToggle />
              </div>
              
              <div class="setting-item">
                <label>Preset Themes</label>
                <div class="preset-themes-grid">
                  <button 
                    v-for="(preset, name) in themeStore.presetThemes"
                    :key="name"
                    class="preset-theme-btn"
                    @click="themeStore.applyPresetTheme(name)"
                    :title="`Apply ${name} theme`"
                  >
                    <div 
                      class="preset-preview"
                      :style="{ 
                        background: `linear-gradient(135deg, ${preset.primary} 0%, ${preset.secondary} 100%)`
                      }"
                    ></div>
                    <span>{{ formatPresetName(name) }}</span>
                  </button>
                </div>
              </div>
            </div>
            
            <div class="setting-section">
              <h4>Audio Settings</h4>
              
              <div class="setting-item">
                <label>Sample Rate</label>
                <select v-model="sampleRate" class="setting-select">
                  <option value="44100">44.1 kHz</option>
                  <option value="48000">48 kHz</option>
                  <option value="96000">96 kHz</option>
                </select>
              </div>
              
              <div class="setting-item">
                <label>Buffer Size</label>
                <select v-model="bufferSize" class="setting-select">
                  <option value="128">128 samples</option>
                  <option value="256">256 samples</option>
                  <option value="512">512 samples</option>
                  <option value="1024">1024 samples</option>
                </select>
              </div>
            </div>
            
            <div class="setting-section">
              <h4>Interface</h4>
              
              <div class="setting-item">
                <label>Language</label>
                <select v-model="language" class="setting-select">
                  <option value="en">English</option>
                  <option value="es">Español</option>
                </select>
              </div>
              
              <div class="setting-item">
                <label>Animations</label>
                <select v-model="animations" class="setting-select">
                  <option value="full">Full Animations</option>
                  <option value="reduced">Reduced Motion</option>
                  <option value="none">No Animations</option>
                </select>
              </div>
            </div>
            
            <div class="setting-section">
              <h4>Export Settings</h4>
              
              <div class="setting-item">
                <label>Export Format</label>
                <select v-model="exportFormat" class="setting-select">
                  <option value="wav">WAV</option>
                  <option value="mp3">MP3</option>
                  <option value="ogg">OGG</option>
                </select>
              </div>
              
              <div class="setting-item">
                <label>Export Quality</label>
                <select v-model="exportQuality" class="setting-select">
                  <option value="high">High (320kbps)</option>
                  <option value="medium">Medium (192kbps)</option>
                  <option value="low">Low (128kbps)</option>
                </select>
              </div>
            </div>
            
            <div class="setting-section">
              <h4>Actions</h4>
              
              <button class="btn btn-ghost full-width" @click="resetSettings">
                <RotateCcw class="icon" />
                Reset to Defaults
              </button>
              
              <button class="btn btn-ghost full-width" @click="exportSettings">
                <Download class="icon" />
                Export Settings
              </button>
              
              <button class="btn btn-ghost full-width" @click="importSettings">
                <Upload class="icon" />
                Import Settings
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useThemeStore } from '../stores/themeStore'
import { Bot, FileAudio, Sliders, Settings, RotateCcw, Download, Upload } from 'lucide-vue-next'
import AiChat from './AiChat.vue'
import SampleLibrary from './SampleLibrary.vue'
import ThemeToggle from './ThemeToggle.vue'
import JSONStructurePanel from './JSONStructurePanel.vue'

const themeStore = useThemeStore()

// Tab management
const activeTab = ref('ai')

const tabs = [
  { id: 'ai', name: 'AI Chat', icon: Bot },
  { id: 'samples', name: 'Samples', icon: FileAudio },
  { id: 'effects', name: 'JSON Song Structure', icon: Sliders }, // Renamed tab for clarity
  { id: 'settings', name: 'Settings', icon: Settings }, // Ensure settings tab remains
]

// Settings state
const sampleRate = ref('44100')
const bufferSize = ref('256')
const language = ref('en')
const animations = ref('full')
const exportFormat = ref('wav')
const exportQuality = ref('high')

// Methods
const formatPresetName = (name: string): string => {
  return name.charAt(0).toUpperCase() + name.slice(1)
}

const resetSettings = () => {
  if (confirm('Reset all settings to defaults?')) {
    sampleRate.value = '44100'
    bufferSize.value = '256'
    language.value = 'en'
    animations.value = 'full'
    exportFormat.value = 'wav'
    exportQuality.value = 'high'
    themeStore.setMode('dark')
  }
}

const exportSettings = () => {
  const settings = {
    theme: themeStore.mode,
    sampleRate: sampleRate.value,
    bufferSize: bufferSize.value,
    language: language.value,
    animations: animations.value,
    exportFormat: exportFormat.value,
    exportQuality: exportQuality.value,
  }
  
  const blob = new Blob([JSON.stringify(settings, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'mity-studio-settings.json'
  a.click()
  URL.revokeObjectURL(url)
}

const importSettings = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const settings = JSON.parse(e.target?.result as string)
          if (settings.theme) themeStore.setMode(settings.theme)
          sampleRate.value = settings.sampleRate || '44100'
          bufferSize.value = settings.bufferSize || '256'
          language.value = settings.language || 'en'
          animations.value = settings.animations || 'full'
          exportFormat.value = settings.exportFormat || 'wav'
          exportQuality.value = settings.exportQuality || 'high'
        } catch (error) {
          alert('Invalid settings file')
        }
      }
      reader.readAsText(file)
    }
  }
  input.click()
}
</script>

<style scoped>
.right-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
  transition: background-color var(--transition-normal);
}

.panel-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  transition: all var(--transition-normal);
}

.tab-btn {
  flex: 1;
  padding: 0.75rem 0.5rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  transition: all var(--transition-normal);
  font-size: 0.75rem;
}

.tab-btn:hover {
  background: var(--border);
  color: var(--text);
}

.tab-btn.active {
  background: var(--primary);
  color: white;
}

.tab-btn .icon {
  width: 16px;
  height: 16px;
}

.tab-label {
  font-size: 0.625rem;
  font-weight: 500;
}

.panel-content {
  flex: 1;
  overflow: hidden;
}

.tab-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.effects-panel,
.settings-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.panel-header {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  transition: all var(--transition-normal);
}

.header-icon {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.panel-header h3 {
  margin: 0;
  font-size: 1.125rem;
  color: var(--text);
}

.align-timeline-header {
  /* Set height to match the sum of track header heights (e.g. 3 tracks * 48px = 144px) */
  height: 144px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  padding-top: 0;
  padding-bottom: 0;
}

.effects-content,
.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}

.effect-section,
.setting-section {
  margin-bottom: 2rem;
}

.effect-section h4,
.setting-section h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
  color: var(--text);
  font-weight: 600;
}

.effect-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.effect-control label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  min-width: 80px;
}

.slider {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
  transition: background-color var(--transition-normal);
}

.slider::-webkit-slider-thumb {
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  cursor: pointer;
  transition: background-color var(--transition-normal);
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  background: var(--primary);
  border-radius: 50%;
  border: none;
  cursor: pointer;
}

.value {
  font-size: 0.75rem;
  color: var(--text-secondary);
  min-width: 40px;
  text-align: right;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
  gap: 1rem;
}

.setting-item label {
  font-size: 0.875rem;
  color: var(--text);
  flex-shrink: 0;
}

.setting-select {
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--background);
  color: var(--text);
  font-size: 0.875rem;
  min-width: 120px;
  transition: all var(--transition-normal);
}

.setting-select:focus {
  outline: none;
  border-color: var(--primary);
}

.preset-themes-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.5rem;
  width: 100%;
}

.preset-theme-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  transition: all var(--transition-normal);
  font-size: 0.75rem;
}

.preset-theme-btn:hover {
  background: var(--border);
  transform: translateY(-1px);
}

.preset-preview {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 2px solid var(--border);
  transition: all var(--transition-normal);
}

.preset-theme-btn:hover .preset-preview {
  transform: scale(1.1);
}

.full-width {
  width: 100%;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.empty-state {
  text-align: center;
  padding: 2rem 1rem;
  color: var(--text-secondary);
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 1rem;
  opacity: 0.5;
}

.empty-state p {
  margin: 0;
}

/* Scrollbar */
.effects-content::-webkit-scrollbar,
.settings-content::-webkit-scrollbar {
  width: 5px;
}

.effects-content::-webkit-scrollbar-track,
.settings-content::-webkit-scrollbar-track {
  background: transparent;
}

.effects-content::-webkit-scrollbar-thumb,
.settings-content::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

.effects-content::-webkit-scrollbar-thumb:hover,
.settings-content::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

@media (max-width: 768px) {
  .tab-btn {
    padding: 0.5rem 0.25rem;
  }
  
  .tab-label {
    display: none;
  }
  
  .effect-control,
  .setting-item {
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
  }
  
  .effect-control label,
  .setting-item label {
    min-width: auto;
  }
  
  .setting-select {
    min-width: auto;
  }
  
  .preset-themes-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}
</style>
