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
        <button class="btn btn-primary" @click="exportProject">
          <Download class="icon" />
          {{ $t('header.export') }}
        </button>
      </nav>
      
      <div class="header-controls">
        <select v-model="currentLocale" @change="changeLocale" class="input select locale-select">
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
        
        <ThemeToggle />
        
        <button class="btn btn-ghost" @click="openSettings">
          <Settings class="icon" />
        </button>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAudioStore } from '../stores/audioStore'
import { useThemeStore } from '../stores/themeStore'
import { Music, FileText, FolderOpen, Save, Download, Settings } from 'lucide-vue-next'
import ThemeToggle from './ThemeToggle.vue'

const { t, locale } = useI18n()
const audioStore = useAudioStore()
const themeStore = useThemeStore()

const currentLocale = ref(locale.value)

const changeLocale = () => {
  locale.value = currentLocale.value
}

const newProject = () => {
  if (confirm('Create a new project? Unsaved changes will be lost.')) {
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

const openProject = () => {
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
          alert('Invalid project file')
        }
      }
      reader.readAsText(file)
    }
  }
  input.click()
}

const saveProject = () => {
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
  alert('Export functionality coming soon!')
}

const openSettings = () => {
  // Settings modal would be implemented here
  alert('Settings panel coming soon!')
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
</style>
