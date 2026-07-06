<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth, type HealthResponse } from './api/client'

const health = ref<HealthResponse | null>(null)
const healthError = ref('')

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
      <RouterLink to="/">Studio</RouterLink>
      <RouterLink to="/assets">Assets</RouterLink>
      <RouterLink to="/voices">Voices</RouterLink>
      <RouterLink to="/settings">Settings</RouterLink>
      <span class="spacer" />
      <span v-if="health" class="health ok">● backend connected</span>
      <span v-else-if="healthError" class="health err" :title="healthError">● backend offline</span>
      <span v-else class="health dim">● connecting…</span>
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
.health.ok { color: var(--ok); }
.health.err { color: var(--err); }
.main { flex: 1; min-height: 0; overflow: hidden; }
</style>
