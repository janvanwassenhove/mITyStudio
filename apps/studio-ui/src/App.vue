<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { Info, Moon, PanelBottom, PanelLeft, PanelRight, Sun } from 'lucide-vue-next'
import { getHealth, type HealthResponse } from './api/client'
import { LOCALES, currentLocale, setLocale, type LocaleCode } from './i18n'
import { useStudioStore } from './stores/studio'
import { isDesktop, showBottomPanel, showLeftPanel, showRightPanel,
         theme, toggleTheme } from './composables/uiPrefs'
import OnboardingGuide from './components/OnboardingGuide.vue'
import CountdownOverlay from './components/CountdownOverlay.vue'
import AboutBox from './components/AboutBox.vue'

const showAbout = ref(false)

const health = ref<HealthResponse | null>(null)
const healthError = ref('')
// deep-link support: ?lang=nl forces a locale, ?noguide skips onboarding
const urlParams = new URLSearchParams(window.location.search)
const urlLang = urlParams.get('lang')
if (urlLang && LOCALES.some((l) => l.code === urlLang)) {
  setLocale(urlLang as LocaleCode)
}
const locale = ref<LocaleCode>(currentLocale())
const showOnboarding = ref(!localStorage.getItem('mity-onboarding-done')
  && !urlParams.has('noguide'))
const studio = useStudioStore()

function changeLocale() {
  setLocale(locale.value)
}

// --- reconnect flow: poll health, banner while offline, refresh on return --
const POLL_MS = 8000
const reconnected = ref(false)
const checking = ref(false)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function checkHealth() {
  if (checking.value) return
  checking.value = true
  const wasOffline = !!healthError.value
  try {
    health.value = await getHealth()
    healthError.value = ''
    if (wasOffline) {
      // backend came back: reload everything the views depend on
      reconnected.value = true
      await studio.refreshProjects()
      if (studio.project) await studio.reloadCurrent()
      setTimeout(() => { reconnected.value = false }, 4000)
    }
  } catch (e) {
    health.value = null
    healthError.value = String(e)
  } finally {
    checking.value = false
  }
}

onMounted(() => {
  void checkHealth()
  pollTimer = setInterval(checkHealth, POLL_MS)
})
onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div class="app-shell" :class="{ desktop: isDesktop }">
    <nav class="topnav">
      <span class="brand">mITy<span style="color: var(--accent)">Studio</span></span>
      <RouterLink to="/">{{ $t('nav.studio') }}</RouterLink>
      <RouterLink to="/assets">{{ $t('nav.assets') }}</RouterLink>
      <RouterLink to="/voices">{{ $t('nav.voices') }}</RouterLink>
      <RouterLink to="/settings">{{ $t('nav.settings') }}</RouterLink>
      <span class="spacer" />
      <div class="layout-toggles" :title="$t('nav.layoutTip')">
        <button class="tbtn" :class="{ off: !showLeftPanel }"
                :title="$t('nav.togglePanelLeft')"
                @click="showLeftPanel = !showLeftPanel"><PanelLeft :size="15" /></button>
        <button class="tbtn" :class="{ off: !showBottomPanel }"
                :title="$t('nav.togglePanelBottom')"
                @click="showBottomPanel = !showBottomPanel"><PanelBottom :size="15" /></button>
        <button class="tbtn" :class="{ off: !showRightPanel }"
                :title="$t('nav.togglePanelRight')"
                @click="showRightPanel = !showRightPanel"><PanelRight :size="15" /></button>
      </div>
      <button class="tbtn" :title="$t('nav.toggleTheme')" @click="toggleTheme">
        <Sun v-if="theme === 'dark'" :size="15" /><Moon v-else :size="15" />
      </button>
      <button class="tbtn" :title="$t('about.title')" @click="showAbout = true">
        <Info :size="15" />
      </button>
      <select v-model="locale" class="lang" :title="$t('nav.language')" @change="changeLocale">
        <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
      </select>
      <span v-if="health" class="health ok">● {{ $t('nav.backendConnected') }}</span>
      <span v-else-if="healthError" class="health err" :title="healthError">● {{ $t('nav.backendOffline') }}</span>
      <span v-else class="health dim">● {{ $t('nav.connecting') }}</span>
    </nav>
    <div v-if="healthError" class="offline-banner">
      {{ $t('nav.offlineBanner') }}
      <button class="retry" :disabled="checking" @click="checkHealth">
        {{ checking ? '…' : $t('nav.retryNow') }}
      </button>
    </div>
    <div v-else-if="reconnected" class="reconnected-banner">
      ✓ {{ $t('nav.reconnected') }}
    </div>
    <main class="main">
      <RouterView />
    </main>
    <OnboardingGuide v-if="showOnboarding" @close="showOnboarding = false" />
    <AboutBox v-if="showAbout" @close="showAbout = false" />
    <CountdownOverlay />
  </div>
</template>

<style scoped>
.app-shell { display: flex; flex-direction: column; height: 100%; }
.topnav {
  display: flex; align-items: center; gap: 16px;
  padding: 8px 16px; border-bottom: 1px solid var(--border);
  background: var(--bg-panel); flex: none;
}
/* desktop shell: the nav IS the window title bar — draggable, with room for
   the native window-control overlay on the right */
.desktop .topnav {
  -webkit-app-region: drag;
  height: 38px; padding-top: 0; padding-bottom: 0;
  padding-right: calc(100vw - env(titlebar-area-width, 100vw) + 8px);
}
.desktop .topnav a, .desktop .topnav button, .desktop .topnav select {
  -webkit-app-region: no-drag;
}
.layout-toggles { display: flex; gap: 2px; }
.tbtn {
  display: flex; align-items: center; padding: 4px 6px;
  background: transparent; border: none; color: var(--text-dim);
  border-radius: var(--radius-sm);
}
.tbtn:hover { color: var(--text); background: var(--bg-elevated); }
.tbtn.off { opacity: 0.38; }
.brand { font-weight: 700; font-size: 15px; margin-right: 8px; }
.topnav a { color: var(--text-dim); text-decoration: none; font-size: 13px; }
.topnav a.router-link-active { color: var(--text); font-weight: 600; }
.spacer { flex: 1; }
.health { font-size: 12px; }
.lang {
  background: var(--bg); color: var(--text-dim); border: 1px solid var(--border);
  border-radius: 6px; font-size: 12px; padding: 2px 6px;
}
.health.ok { color: var(--ok); }
.health.err { color: var(--err); }
.main { flex: 1; min-height: 0; overflow: hidden; }
.offline-banner {
  flex: none; display: flex; align-items: center; justify-content: center; gap: 12px;
  background: rgba(242, 85, 90, 0.14); border-bottom: 1px solid var(--err);
  color: var(--err); font-size: 13px; padding: 6px 12px;
}
.offline-banner .retry { padding: 2px 12px; font-size: 12px; border-color: var(--err); color: var(--err); }
.reconnected-banner {
  flex: none; text-align: center; background: rgba(62, 207, 142, 0.12);
  border-bottom: 1px solid var(--ok); color: var(--ok); font-size: 12px; padding: 4px;
}
</style>
