<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { getVersion, type VersionResponse } from '../api/client'

const { t } = useI18n()
defineEmits<{ close: [] }>()

const info = ref<VersionResponse | null>(null)
const error = ref('')

onMounted(async () => {
  try {
    info.value = await getVersion()
  } catch (e) {
    error.value = String(e)
  }
})

// UI version is baked in at build time so it can be compared against the
// backend — if they disagree, the install is half-updated.
const uiVersion = import.meta.env.VITE_APP_VERSION || 'dev'

function ok(v: boolean) { return v ? '✓' : '✗' }
</script>

<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="about panel">
      <div class="head">
        <h3>mITy<span style="color: var(--accent)">Studio</span></h3>
        <button class="close" @click="$emit('close')">✕</button>
      </div>

      <div v-if="error" class="err">{{ error }}</div>
      <template v-else-if="info">
        <table class="rows">
          <tr><td>{{ t('about.appVersion') }}</td><td class="val">{{ info.app_version }}</td></tr>
          <tr><td>{{ t('about.uiVersion') }}</td><td class="val">{{ uiVersion }}</td></tr>
          <tr><td>{{ t('about.backendBuild') }}</td><td class="val">{{ info.backend_build }}</td></tr>
          <tr><td>{{ t('about.python') }}</td><td class="val">{{ info.python }}</td></tr>
          <tr><td>{{ t('about.engines') }}</td>
              <td class="val">vocal v{{ info.engines.vocal }} · inst v{{ info.engines.instrument }}</td></tr>
        </table>

        <h4>{{ t('about.capabilities') }}</h4>
        <ul class="caps">
          <li :class="{ no: !info.capabilities.fluidsynth }">
            {{ ok(info.capabilities.fluidsynth) }} {{ t('about.fluidsynth') }}</li>
          <li :class="{ no: !info.capabilities.ffmpeg }">
            {{ ok(info.capabilities.ffmpeg) }} {{ t('about.ffmpeg') }}</li>
          <li :class="{ no: !info.capabilities.voice_clone }">
            {{ ok(!!info.capabilities.voice_clone) }} {{ t('about.voiceClone') }}</li>
          <li :class="{ no: !info.singing_engine.svs_runtime }">
            {{ ok(info.singing_engine.svs_runtime) }} {{ t('about.svsRuntime') }}</li>
          <li :class="{ no: !info.singing_engine.vocoder_installed }">
            {{ ok(info.singing_engine.vocoder_installed) }} {{ t('about.vocoder') }}</li>
          <li :class="{ no: !info.singing_engine.voicebanks.length }">
            {{ ok(!!info.singing_engine.voicebanks.length) }}
            {{ t('about.voicebanks') }}:
            <span v-if="info.singing_engine.voicebanks.length">
              {{ info.singing_engine.voicebanks.join(', ') }}</span>
            <span v-else class="dim">{{ t('about.none') }}</span>
          </li>
        </ul>
        <div v-for="(reason, dir) in info.singing_engine.voicebank_problems" :key="dir"
             class="prob">⚠ {{ dir }}: {{ reason }}</div>

        <p class="dim small tip">{{ t('about.tip') }}</p>
      </template>
      <div v-else class="dim">…</div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 80; }
.about { width: 460px; max-width: 92vw; max-height: 88vh; overflow-y: auto; padding: 18px 22px; }
.head { display: flex; align-items: center; }
.head h3 { margin: 0; flex: 1; font-size: 17px; }
.close { border: none; background: transparent; }
.rows { width: 100%; border-collapse: collapse; margin: 8px 0; }
.rows td { padding: 4px 0; font-size: 13px; color: var(--text-dim); }
.rows .val { text-align: right; color: var(--text); font-family: 'Consolas', monospace; }
h4 { margin: 14px 0 6px; font-size: 13px; }
.caps { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.caps li { font-size: 13px; color: var(--ok); }
.caps li.no { color: var(--text-dim); }
.prob { color: var(--warn); font-size: 12px; margin-top: 4px; }
.tip { margin-top: 14px; }
.err { color: var(--err); font-size: 13px; }
</style>
