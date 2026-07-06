<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import type { Asset } from '../api/types'

const TABS = [
  { key: 'score', label: 'Scores' },
  { key: 'soundfont', label: 'SoundFonts' },
  { key: 'sample', label: 'Samples' },
  { key: 'voice_recording', label: 'Voice Recordings' },
] as const

const tab = ref<string>('sample')
const assets = ref<Asset[]>([])
const search = ref('')
const tagFilter = ref('')
const selected = ref<Asset | null>(null)
const busy = ref(false)
const scanMsg = ref('')

// metadata editor state
const editTags = ref('')
const editDesc = ref('')
const editLicense = ref('')
const analysis = ref<Record<string, unknown> | null>(null)

async function load() {
  busy.value = true
  try {
    assets.value = await api.get<Asset[]>(`/assets?asset_type=${tab.value}`)
  } finally {
    busy.value = false
  }
}

const filtered = computed(() => {
  const q = search.value.toLowerCase()
  const tag = tagFilter.value.toLowerCase()
  return assets.value.filter((a) => {
    if (q && !a.filename.toLowerCase().includes(q) && !a.user_description.toLowerCase().includes(q)) return false
    if (tag && !a.tags.some((t) => t.toLowerCase().includes(tag))) return false
    return true
  })
})

function select(a: Asset) {
  selected.value = a
  editTags.value = a.tags.join(', ')
  editDesc.value = a.user_description
  editLicense.value = a.license_notes
  analysis.value = null
}

async function saveMetadata() {
  if (!selected.value) return
  const updated = await api.patch<Asset>(`/assets/${selected.value.id}/metadata`, {
    tags: editTags.value.split(',').map((t) => t.trim()).filter(Boolean),
    user_description: editDesc.value,
    license_notes: editLicense.value,
  })
  const i = assets.value.findIndex((a) => a.id === updated.id)
  if (i >= 0) assets.value[i] = updated
  selected.value = updated
}

async function rescan() {
  busy.value = true
  scanMsg.value = 'scanning…'
  try {
    const stats = await api.post<Record<string, number>>('/assets/rescan')
    scanMsg.value = `new: ${stats.new}, changed: ${stats.changed}, missing: ${stats.missing}`
    await load()
  } finally {
    busy.value = false
  }
}

async function analyse() {
  if (!selected.value) return
  busy.value = true
  try {
    analysis.value = await api.post<Record<string, unknown>>(`/assets/${selected.value.id}/analyse`)
    await load()
  } catch (e) {
    analysis.value = { error: String(e) }
  } finally {
    busy.value = false
  }
}

const isAudio = computed(() =>
  selected.value != null &&
  ['.wav', '.mp3', '.flac', '.ogg', '.aiff', '.aif', '.m4a'].includes(selected.value.extension))

function switchTab(t: string) {
  tab.value = t
  selected.value = null
  load()
}

function fmtSize(bytes: number): string {
  if (bytes > 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes > 1024) return (bytes / 1024).toFixed(0) + ' KB'
  return bytes + ' B'
}

onMounted(load)
</script>

<template>
  <div class="library">
    <div class="toolbar">
      <div class="tabs">
        <button v-for="t in TABS" :key="t.key" :class="{ active: tab === t.key }" @click="switchTab(t.key)">
          {{ t.label }}
        </button>
      </div>
      <input v-model="search" placeholder="Search filename / description…" style="width: 220px" />
      <input v-model="tagFilter" placeholder="Filter by tag…" style="width: 140px" />
      <span class="spacer" />
      <span class="dim small">{{ scanMsg }}</span>
      <button :disabled="busy" @click="rescan">Rescan folders</button>
    </div>
    <div class="content">
      <div class="list panel">
        <div class="dim small count">{{ filtered.length }} / {{ assets.length }} assets</div>
        <div
          v-for="a in filtered" :key="a.id" class="item"
          :class="{ active: selected?.id === a.id, missing: a.is_missing }"
          @click="select(a)"
        >
          <div class="fname">{{ a.filename }} <span v-if="a.is_missing" class="err-text">(missing)</span></div>
          <div class="dim small">
            {{ fmtSize(a.file_size) }} · {{ a.analysis_status }}
            <span v-for="t in a.tags.slice(0, 4)" :key="t" class="tag">{{ t }}</span>
          </div>
        </div>
      </div>
      <div class="detail panel">
        <div v-if="!selected" class="dim" style="padding: 20px">Select an asset to see details.</div>
        <div v-else class="detail-body">
          <h3>{{ selected.filename }}</h3>
          <div class="dim small">{{ selected.relative_path }} · {{ fmtSize(selected.file_size) }}</div>

          <audio v-if="isAudio && !selected.is_missing" controls :src="`/api/assets/${selected.id}/file`" style="width: 100%" />

          <label class="field">Tags (comma-separated)
            <input v-model="editTags" />
          </label>
          <label class="field">Description
            <textarea v-model="editDesc" rows="3" />
          </label>
          <label class="field">License notes
            <input v-model="editLicense" />
          </label>
          <div class="row-btns">
            <button class="primary" @click="saveMetadata">Save metadata</button>
            <button v-if="tab === 'sample' || tab === 'voice_recording'" :disabled="busy" @click="analyse">Analyse</button>
          </div>
          <div v-if="selected.generated_description" class="gen-desc">
            <span class="dim small">auto description:</span> {{ selected.generated_description }}
          </div>
          <pre v-if="analysis" class="analysis">{{ JSON.stringify(analysis, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.library { display: flex; flex-direction: column; height: 100%; padding: 8px; gap: 8px; }
.toolbar { display: flex; align-items: center; gap: 8px; flex: none; }
.tabs { display: flex; gap: 4px; }
.tabs button.active { border-color: var(--accent); color: var(--accent); }
.spacer { flex: 1; }
.small { font-size: 11px; }
.content { flex: 1; display: flex; gap: 8px; min-height: 0; }
.list { flex: 1; overflow-y: auto; padding: 6px; }
.count { padding: 4px 8px; }
.item { padding: 6px 10px; border-radius: 6px; cursor: pointer; }
.item:hover { background: var(--bg-elevated); }
.item.active { background: var(--bg-elevated); outline: 1px solid var(--accent); }
.item.missing { opacity: 0.55; }
.fname { font-size: 13px; }
.tag { background: var(--bg-elevated); border-radius: 3px; padding: 0 5px; margin-left: 4px; font-size: 10px; }
.detail { width: 380px; flex: none; overflow-y: auto; }
.detail-body { padding: 14px; display: flex; flex-direction: column; gap: 10px; }
h3 { margin: 0; font-size: 15px; word-break: break-all; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.row-btns { display: flex; gap: 8px; }
.gen-desc { font-size: 12px; }
.analysis { font-size: 11px; background: var(--bg); border-radius: 6px; padding: 8px; overflow-x: auto; }
.err-text { color: var(--err); }
</style>
