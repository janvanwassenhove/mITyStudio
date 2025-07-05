import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'auto'

export interface ThemeColors {
  primary: string
  secondary: string
  accent: string
  background: string
  surface: string
  text: string
  textSecondary: string
  border: string
  success: string
  warning: string
  error: string
}

export const useThemeStore = defineStore('theme', () => {
  // State
  const mode = ref<ThemeMode>('dark')
  const systemPrefersDark = ref(false)
  
  // Theme definitions
  const lightTheme: ThemeColors = {
    primary: '#9E7FFF',
    secondary: '#38bdf8',
    accent: '#f472b6',
    background: '#FFFFFF',
    surface: '#F8FAFC',
    text: '#1E293B',
    textSecondary: '#64748B',
    border: '#E2E8F0',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
  }

  const darkTheme: ThemeColors = {
    primary: '#9E7FFF',
    secondary: '#38bdf8',
    accent: '#f472b6',
    background: '#171717',
    backgroundSecondary: '#38bdf8',
    surface: '#262626',
    text: '#FFFFFF',
    textSecondary: '#A3A3A3',
    border: '#2F2F2F',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444'
  }

  // Computed
  const isDark = computed(() => {
    if (mode.value === 'auto') {
      return systemPrefersDark.value
    }
    return mode.value === 'dark'
  })

  const currentTheme = computed(() => {
    return isDark.value ? darkTheme : lightTheme
  })

  const themeDisplayName = computed(() => {
    switch (mode.value) {
      case 'light': return 'Light'
      case 'dark': return 'Dark'
      case 'auto': return `Auto (${isDark.value ? 'Dark' : 'Light'})`
      default: return 'Dark'
    }
  })

  // Methods
  const setMode = (newMode: ThemeMode) => {
    mode.value = newMode
    saveToStorage()
    applyTheme()
  }

  const toggleMode = () => {
    if (mode.value === 'light') {
      setMode('dark')
    } else if (mode.value === 'dark') {
      setMode('auto')
    } else {
      setMode('light')
    }
  }

  const applyTheme = () => {
    const root = document.documentElement
    const theme = currentTheme.value
    
    // Apply CSS custom properties
    Object.entries(theme).forEach(([key, value]) => {
      const cssVar = `--${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`
      root.style.setProperty(cssVar, value)
    })

    // Apply theme class to body
    document.body.className = document.body.className.replace(/theme-\w+/g, '')
    document.body.classList.add(`theme-${isDark.value ? 'dark' : 'light'}`)
    
    // Update meta theme-color for mobile browsers
    updateMetaThemeColor(theme.background)
    
    console.log(`🎨 Applied ${isDark.value ? 'dark' : 'light'} theme`)
  }

  const updateMetaThemeColor = (color: string) => {
    let metaThemeColor = document.querySelector('meta[name="theme-color"]')
    if (!metaThemeColor) {
      metaThemeColor = document.createElement('meta')
      metaThemeColor.setAttribute('name', 'theme-color')
      document.head.appendChild(metaThemeColor)
    }
    metaThemeColor.setAttribute('content', color)
  }

  const detectSystemTheme = () => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      systemPrefersDark.value = mediaQuery.matches
      
      // Listen for system theme changes
      mediaQuery.addEventListener('change', (e) => {
        systemPrefersDark.value = e.matches
        if (mode.value === 'auto') {
          applyTheme()
        }
      })
    }
  }

  const saveToStorage = () => {
    try {
      localStorage.setItem('mity-studio-theme', mode.value)
    } catch (error) {
      console.warn('Failed to save theme to localStorage:', error)
    }
  }

  const loadFromStorage = () => {
    try {
      const saved = localStorage.getItem('mity-studio-theme')
      if (saved && ['light', 'dark', 'auto'].includes(saved)) {
        mode.value = saved as ThemeMode
      }
    } catch (error) {
      console.warn('Failed to load theme from localStorage:', error)
    }
  }

  const initializeTheme = () => {
    detectSystemTheme()
    loadFromStorage()
    applyTheme()
  }

  // Custom theme creation
  const createCustomTheme = (baseTheme: 'light' | 'dark', overrides: Partial<ThemeColors>): ThemeColors => {
    const base = baseTheme === 'light' ? lightTheme : darkTheme
    return { ...base, ...overrides }
  }

  // Preset themes
  const presetThemes = {
    'ocean': createCustomTheme('dark', {
      primary: '#0EA5E9',
      secondary: '#06B6D4',
      accent: '#8B5CF6',
      background: '#0F172A',
      surface: '#1E293B'
    }),
    'forest': createCustomTheme('dark', {
      primary: '#10B981',
      secondary: '#059669',
      accent: '#F59E0B',
      background: '#064E3B',
      surface: '#065F46'
    }),
    'sunset': createCustomTheme('light', {
      primary: '#F97316',
      secondary: '#EF4444',
      accent: '#EC4899',
      background: '#FFF7ED',
      surface: '#FFEDD5'
    }),
    'midnight': createCustomTheme('dark', {
      primary: '#6366F1',
      secondary: '#8B5CF6',
      accent: '#EC4899',
      background: '#0C0A09',
      surface: '#1C1917'
    })
  }

  const applyPresetTheme = (presetName: keyof typeof presetThemes) => {
    const preset = presetThemes[presetName]
    const root = document.documentElement
    
    Object.entries(preset).forEach(([key, value]) => {
      const cssVar = `--${key.replace(/([A-Z])/g, '-$1').toLowerCase()}`
      root.style.setProperty(cssVar, value)
    })
    
    document.body.className = document.body.className.replace(/theme-\w+/g, '')
    document.body.classList.add(`theme-preset-${presetName}`)
    
    updateMetaThemeColor(preset.background)
  }

  // Watch for mode changes
  watch(mode, () => {
    applyTheme()
  })

  watch(systemPrefersDark, () => {
    if (mode.value === 'auto') {
      applyTheme()
    }
  })

  return {
    // State
    mode,
    systemPrefersDark,
    
    // Computed
    isDark,
    currentTheme,
    themeDisplayName,
    
    // Methods
    setMode,
    toggleMode,
    applyTheme,
    initializeTheme,
    createCustomTheme,
    applyPresetTheme,
    
    // Constants
    lightTheme,
    darkTheme,
    presetThemes
  }
})
