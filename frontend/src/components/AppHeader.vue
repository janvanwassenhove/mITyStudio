<template>
  <header class="app-header">
    <div class="header-content">
      <div class="logo-section">
        <div class="logo">
          <Music class="logo-icon" />
          <div class="logo-text">
            <h1>{{ $t('app.title') }}</h1>
            <p>{{ $t('app.subtitle') }}</p>
          </div>
        </div>
      </div>
      
      <nav class="header-nav">
        <button class="btn btn-ghost" @click="newProject">
          <FileText class="icon" />
          {{ $t('header.newProject') }}
        </button>
        <button class="btn btn-ghost" @click="openProject">
          <FolderOpen class="icon" />
          {{ $t('header.openProject') }}
        </button>
        <button class="btn btn-ghost" @click="saveProject">
          <Save class="icon" />
          {{ $t('header.saveProject') }}
        </button>
        <button class="btn btn-generate" @click="showGenerateSongDialog = true">
          <Music class="icon" />
          {{ $t('header.generateSong') }}
        </button>
        <button class="btn btn-primary" @click="exportProject">
          <Download class="icon" />
          {{ $t('header.export') }}
        </button>
      </nav>
      
      <div class="header-controls">
        <select v-model="currentLocale" @change="changeLocale" class="input select locale-select">
          <option value="en">{{ $t('languages.en') }}</option>
          <option value="es">{{ $t('languages.es') }}</option>
          <option value="nl">{{ $t('languages.nl') }}</option>
          <option value="fr">{{ $t('languages.fr') }}</option>
          <option value="de">{{ $t('languages.de') }}</option>
          <option value="it">{{ $t('languages.it') }}</option>
        </select>
        
        <ThemeToggle />
      
      </div>
    </div>
  </header>
  
  <GenerateSongDialog 
    :show="showGenerateSongDialog" 
    @close="showGenerateSongDialog = false" 
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useThemeStore } from '../stores/themeStore'
import { useAudioStore } from '../stores/audioStore'
import { projectService } from '../services/projectService'
import { Music, FileText, FolderOpen, Save, Download } from 'lucide-vue-next'
import ThemeToggle from './ThemeToggle.vue'
import GenerateSongDialog from './GenerateSongDialog.vue'

const { locale, t } = useI18n()
const audioStore = useAudioStore()
const themeStore = useThemeStore()

const currentLocale = ref(locale.value)
const showGenerateSongDialog = ref(false)

const changeLocale = () => {
  locale.value = currentLocale.value
}

const newProject = () => {
  if (confirm(t('dialogs.newProject'))) {
    // Reset to default song structure
    audioStore.loadSongStructure({
      id: `project-${Date.now()}`,
      name: 'Untitled Song',
      tempo: 120,
      timeSignature: [4, 4],
      key: 'C',
      tracks: [],
      duration: 32,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    })
  }
}

const openProject = async () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        try {
          const songStructure = JSON.parse(e.target?.result as string)
          audioStore.loadSongStructure(songStructure)
        } catch (error) {
          alert(t('dialogs.invalidProject'))
        }
      }
      reader.readAsText(file)
    }
  }
  input.click()
}

const saveProject = async () => {
  try {
    // Try to save to backend API first
    const project = await projectService.createProjectFromSongStructure(audioStore.songStructure)
    alert(`Project "${project.name}" saved successfully to workspace!`)
    return
  } catch (error) {
    console.warn('Backend save failed, falling back to file download:', error)
  }
  
  // Fallback to file download if backend fails
  const songData = audioStore.exportSongStructure()
  const blob = new Blob([songData], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${audioStore.songStructure.name}.json`
  a.click()
  URL.revokeObjectURL(url)
}

const exportProject = () => {
  // Export functionality would be implemented here
  alert(t('dialogs.exportSoon'))
}

onMounted(() => {
  // Initialize theme system
  themeStore.initializeTheme()
})
</script>

<style scoped>
.app-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 1.5rem;
  height: 64px;
  display: flex;
  align-items: center;
  position: relative;
  z-index: 100;
  transition: all var(--transition-normal);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  max-width: 100%;
}

.logo-section {
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-icon {
  width: 32px;
  height: 32px;
  color: var(--primary);
  transition: color var(--transition-normal);
}

.logo-text h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  transition: all var(--transition-normal);
}

.logo-text p {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin: 0;
  margin-top: -2px;
  transition: color var(--transition-normal);
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  justify-content: center;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.locale-select {
  width: auto;
  min-width: 100px;
  padding: 0.5rem 0.75rem;
  font-size: 0.8125rem;
}

.icon {
  width: 16px;
  height: 16px;
}

@media (max-width: 768px) {
  .app-header {
    padding: 0 1rem;
  }
  
  .header-nav {
    display: none;
  }
  
  .logo-text p {
    display: none;
  }
  
  .header-controls {
    gap: 0.5rem;
  }
  
  .locale-select {
    min-width: 80px;
    font-size: 0.75rem;
  }
}

/* Theme-specific adjustments */
.theme-light .app-header {
  backdrop-filter: blur(10px);
  background: color-mix(in srgb, var(--surface) 95%, transparent);
}

.theme-dark .app-header {
  backdrop-filter: blur(10px);
  background: color-mix(in srgb, var(--surface) 90%, transparent);
}

.btn-generate {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  border: 1px solid rgba(255, 255, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.btn-generate:hover {
  background: linear-gradient(135deg, #5855eb 0%, #7c3aed 100%);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
  transform: translateY(-1px);
}

.btn-generate:active {
  transform: translateY(0);
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.btn-generate::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.6s;
}

.btn-generate:hover::before {
  left: 100%;
}
</style>
