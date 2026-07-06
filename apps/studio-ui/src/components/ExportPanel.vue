<script setup lang="ts">
import { computed, ref } from 'vue'
import { api } from '../api/client'
import type { ExportJob } from '../api/types'
import { useStudioStore } from '../stores/studio'

const studio = useStudioStore()
const formats = ref<{ wav: boolean; mp3: boolean }>({ wav: true, mp3: true })
const busy = ref(false)
const rendering = ref('')
const jobs = ref<ExportJob[]>([])
const error = ref('')

const pid = computed(() => studio.project?.id)

async function refreshJobs() {
  if (!pid.value) return
  jobs.value = await api.get<ExportJob[]>(`/projects/${pid.value}/exports`)
}

async function renderAll() {
  if (!pid.value) return
  error.value = ''
  try {
    rendering.value = 'instruments…'
    await api.post(`/projects/${pid.value}/midi/export`)
    await api.post(`/projects/${pid.value}/render/instrument-stems`)
    rendering.value = 'samples…'
    await api.post(`/projects/${pid.value}/render/sample-stems`)
    rendering.value = 'vocals…'
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
    <div v-if="!studio.project" class="dim">Open a project first.</div>
    <template v-else>
      <h4>Render</h4>
      <button :disabled="!!rendering" @click="renderAll">
        {{ rendering ? `rendering ${rendering}` : 'Render all stems (MIDI → instruments, samples, vocals)' }}
      </button>
      <div class="dim small">{{ studio.project.stems.length }} stems rendered</div>

      <h4>Export mix</h4>
      <label><input type="checkbox" v-model="formats.wav" /> WAV</label>
      <label><input type="checkbox" v-model="formats.mp3" /> MP3</label>
      <button class="primary" :disabled="busy || (!formats.wav && !formats.mp3)" @click="exportMix">
        {{ busy ? 'exporting…' : 'Export combined song' }}
      </button>
      <button :disabled="busy" @click="exportPackage">Export project package (ZIP)</button>

      <div v-if="error" class="err-box">{{ error }}</div>

      <h4 v-if="jobs.length">Exports</h4>
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
