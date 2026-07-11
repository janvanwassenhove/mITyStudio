<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { ExportJob } from '../api/types'
import { useStudioStore } from '../stores/studio'

const { t } = useI18n()
const studio = useStudioStore()
const formats = ref<{ wav: boolean; mp3: boolean }>({ wav: true, mp3: true })
const busy = ref(false)
const rendering = ref('')
const jobs = ref<ExportJob[]>([])
const error = ref('')

const pid = computed(() => studio.project?.id)
const windowOpen = (url: string) => window.open(url, '_blank')

async function refreshJobs() {
  if (!pid.value) return
  jobs.value = await api.get<ExportJob[]>(`/projects/${pid.value}/exports`)
}

async function renderAll() {
  if (!pid.value) return
  error.value = ''
  try {
    rendering.value = t('export.instruments')
    await api.post(`/projects/${pid.value}/midi/export`)
    await api.post(`/projects/${pid.value}/render/instrument-stems`)
    rendering.value = t('export.samples')
    await api.post(`/projects/${pid.value}/render/sample-stems`)
    rendering.value = t('export.vocals')
    await api.post(`/projects/${pid.value}/vocals/render`)
    await studio.reloadCurrent()
  } catch (e) {
    error.value = String(e)
  } finally {
    rendering.value = ''
  }
}

async function exportMix() {
  if (!pid.value) return
  busy.value = true
  error.value = ''
  try {
    const fmts = [
      ...(formats.value.wav ? ['wav'] : []),
      ...(formats.value.mp3 ? ['mp3'] : []),
    ]
    await api.post(`/projects/${pid.value}/export/mix`, { formats: fmts })
    await refreshJobs()
    await studio.reloadCurrent()
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

async function exportPackage() {
  if (!pid.value) return
  busy.value = true
  error.value = ''
  try {
    await api.post(`/projects/${pid.value}/export/package`)
    await refreshJobs()
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

refreshJobs()
</script>

<template>
  <div class="export">
    <div v-if="!studio.project" class="dim">{{ $t('export.noProject') }}</div>
    <template v-else>
      <h4>{{ $t('export.render') }}</h4>
      <button :disabled="!!rendering" @click="renderAll">
        {{ rendering ? $t('export.rendering', { what: rendering }) : $t('export.renderAll') }}
      </button>
      <div class="dim small">{{ $t('export.stemsRendered', { n: studio.project.stems.length }) }}</div>

      <h4>{{ $t('export.exportMix') }}</h4>
      <label><input type="checkbox" v-model="formats.wav" /> WAV</label>
      <label><input type="checkbox" v-model="formats.mp3" /> MP3</label>
      <button class="primary" :disabled="busy || (!formats.wav && !formats.mp3)" @click="exportMix">
        {{ busy ? $t('export.exporting') : $t('export.exportSong') }}
      </button>
      <button :disabled="busy" @click="exportPackage">{{ $t('export.exportPackage') }}</button>
      <button @click="pid && windowOpen(`/api/projects/${pid}/export/bundle`)">
        {{ $t('export.exportBundle') }}</button>
      <div class="dim small">{{ $t('export.bundleHint') }}</div>

      <div v-if="error" class="err-box">{{ error }}</div>

      <h4 v-if="jobs.length">{{ $t('export.exports') }}</h4>
      <div v-for="j in jobs" :key="j.id" class="job">
        <div>
          <span class="status" :class="j.status">{{ j.status }}</span>
          <span class="dim small"> {{ j.requested_formats.join(', ') }}</span>
        </div>
        <div v-for="f in j.output_files" :key="f" class="small">
          <a :href="`/api/projects/${pid}/exports/download?path=${encodeURIComponent(f)}`" target="_blank">{{ f.split('/').pop() }}</a>
        </div>
        <div v-for="w in j.warnings" :key="w" class="warn-text small">⚠ {{ w }}</div>
        <div v-for="e2 in j.errors" :key="e2" class="err-text small">✗ {{ e2 }}</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.export { padding: 12px; display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }
h4 { margin: 8px 0 2px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-dim); }
label { font-size: 13px; display: flex; gap: 6px; align-items: center; }
.small { font-size: 11px; }
.job { border: 1px solid var(--border); border-radius: 6px; padding: 8px; }
.status { font-size: 11px; font-weight: 700; text-transform: uppercase; }
.status.completed { color: var(--ok); }
.status.failed { color: var(--err); }
.warn-text { color: var(--warn); }
.err-text { color: var(--err); }
.err-box { border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; white-space: pre-wrap; }
a { color: var(--accent); }
</style>
