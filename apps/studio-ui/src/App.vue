<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth, type HealthResponse } from './api/client'
import { LOCALES, currentLocale, setLocale, type LocaleCode } from './i18n'

const health = ref<HealthResponse | null>(null)
const healthError = ref('')
const locale = ref<LocaleCode>(currentLocale())

function changeLocale() {
  setLocale(locale.value)
}

onMounted(async () => {
  try {
    health.value = await getHealth()
  } catch (e) {
    healthError.value = String(e)
  }
})
</script>

<template>
  <div class="app-shell">
    <nav class="topnav">
      <span class="brand">mITy<span style="color: var(--accent)">Studio</span></span>
      <RouterLink to="/">{{ $t('nav.studio') }}</RouterLink>
      <RouterLink to="/assets">{{ $t('nav.assets') }}</RouterLink>
      <RouterLink to="/voices">{{ $t('nav.voices') }}</RouterLink>
      <RouterLink to="/settings">{{ $t('nav.settings') }}</RouterLink>
      <span class="spacer" />
      <select v-model="locale" class="lang" :title="$t('nav.language')" @change="changeLocale">
        <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
      </select>
      <span v-if="health" class="health ok">● {{ $t('nav.backendConnected') }}</span>
      <span v-else-if="healthError" class="health err" :title="healthError">● {{ $t('nav.backendOffline') }}</span>
      <span v-else class="health dim">● {{ $t('nav.connecting') }}</span>
    </nav>
    <main class="main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell { display: flex; flex-direction: column; height: 100%; }
.topnav {
  display: flex; align-items: center; gap: 16px;
  padding: 8px 16px; border-bottom: 1px solid var(--border);
  background: var(--bg-panel); flex: none;
}
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
</style>
