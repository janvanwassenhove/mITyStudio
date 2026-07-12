import { ref, watch } from 'vue'

/** Theme + panel-layout preferences, persisted and applied globally.
 *  The layout toggles mirror the VS Code title-bar controls: left sidebar,
 *  bottom panel, right sidebar. */

export type Theme = 'dark' | 'light'

const storedTheme = localStorage.getItem('mity-theme') as Theme | null
export const theme = ref<Theme>(storedTheme === 'light' ? 'light' : 'dark')

function applyTheme() {
  document.documentElement.dataset.theme = theme.value
  // desktop shell: recolor the native window-control overlay to match
  const w = window as unknown as {
    mity?: { setTitleBarTheme?: (t: Theme) => void }
  }
  w.mity?.setTitleBarTheme?.(theme.value)
}

export function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}
watch(theme, () => {
  localStorage.setItem('mity-theme', theme.value)
  applyTheme()
})
applyTheme()

// ---- panel visibility (VS Code-style layout toggles) ----------------------
function persistedFlag(key: string, dflt: boolean) {
  const v = ref(localStorage.getItem(key) !== null
    ? localStorage.getItem(key) === '1' : dflt)
  watch(v, () => localStorage.setItem(key, v.value ? '1' : '0'))
  return v
}

export const showLeftPanel = persistedFlag('mity-panel-left', true)
export const showBottomPanel = persistedFlag('mity-panel-bottom', true)
export const showRightPanel = persistedFlag('mity-panel-right', true)

/** Running inside the Electron shell (integrated title bar active)? */
export const isDesktop = navigator.userAgent.includes('Electron')
