<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { catColor, catIcon } from '../lib/instrumentIcons'
import { Bell, Drum, Guitar, Layers, Mic, Music, Music2, Piano, RefreshCw,
         Sparkles, Tag, Upload, Waves, Wind, Zap } from 'lucide-vue-next'
import { api } from '../api/client'
import type { Asset } from '../api/types'
import { CATEGORY_COLORS } from '../lib/trackColors'

// instrument icon + color per soundfont category tag (tags are lowercase
// category names from the preset scan)

const { t } = useI18n()
const TABS = ['score', 'soundfont', 'sample', 'voice_recording'] as const

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

// category chips (soundfont tab): every tag with its asset count — one
// click filters the list, click again clears
const tagCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const a of assets.value) {
    for (const tg of a.tags) counts[tg] = (counts[tg] ?? 0) + 1
  }
  return Object.entries(counts).sort((x, y) => y[1] - x[1])
})
function toggleTagChip(tg: string) {
  tagFilter.value = tagFilter.value === tg ? '' : tg
}

// soundfont detail: preset inventory + file metadata (author/copyright/…)
interface SfInfo {
  name?: string
  presets?: unknown[]
  info?: Record<string, string>
  categories?: { category: string; count: number }[]
}
const sfInfo = ref<SfInfo | null>(null)

function select(a: Asset) {
  selected.value = a
  editTags.value = a.tags.join(', ')
  editDesc.value = a.user_description
  editLicense.value = a.license_notes
  analysis.value = null
  sfInfo.value = null
  if (tab.value === 'soundfont' && !a.is_missing) {
    void api.get<SfInfo>(`/assets/${a.id}/soundfont-presets`)
      .then((r) => { if (selected.value?.id === a.id) sfInfo.value = r })
      .catch(() => { /* unparsable font — pane just stays basic */ })
  }
}

function copyrightToLicense() {
  const c = sfInfo.value?.info?.copyright
  if (c) editLicense.value = c
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
  scanMsg.value = t('assets.scanning')
  try {
    const stats = await api.post<Record<string, number>>('/assets/rescan')
    scanMsg.value = t('assets.scanResult', { new: stats.new, changed: stats.changed, missing: stats.missing })
    await load()
  } finally {
    busy.value = false
  }
}

const tagging = ref(false)
const tagProgress = ref('')
async function autoTagAll() {
  tagging.value = true
  try {
    let remaining = 1
    let done = 0
    while (remaining > 0) {
      const r = await api.post<{ analysed: number; remaining: number }>(
        '/assets/analyse-batch?limit=150')
      done += r.analysed
      remaining = r.remaining
      tagProgress.value = t('assets.tagProgress', { done, remaining })
      if (r.analysed === 0) break
    }
    tagProgress.value = ''
    scanMsg.value = t('assets.tagged', { n: done })
    await load()
  } catch (e) {
    scanMsg.value = String(e)
  } finally {
    tagging.value = false
  }
}

async function uploadScore(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (!f) return
  busy.value = true
  scanMsg.value = t('assets.uploading')
  try {
    await api.upload('/scores/upload', f, f.name)
    scanMsg.value = t('assets.uploaded', { name: f.name })
    input.value = ''
    await load()
  } catch (err) {
    scanMsg.value = String(err)
  } finally {
    busy.value = false
  }
}

const importing = ref(false)
const importMsg = ref('')
async function importScoreAsSong() {
  if (!selected.value) return
  importing.value = true
  importMsg.value = t('assets.readingScore')
  try {
    const res = await api.post<{ project_id?: string; supported: boolean; warnings: string[] }>(
      `/scores/${selected.value.id}/import`,
      { create_project: true, title: selected.value.filename.replace(/\.[^.]+$/, '') })
    importMsg.value = res.project_id
      ? '✓ ' + t('assets.songCreated')
      : res.warnings.join('; ')
  } catch (err) {
    importMsg.value = String(err)
  } finally {
    importing.value = false
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

function switchTab(next: string) {
  tab.value = next
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
        <button v-for="tb in TABS" :key="tb" :class="{ active: tab === tb }" @click="switchTab(tb)">
          {{ t(`assets.tab.${tb}`) }}
        </button>
      </div>
      <input v-model="search" :placeholder="t('assets.searchPh')" style="width: 220px" />
      <input v-model="tagFilter" :placeholder="t('assets.tagPh')" style="width: 140px" />
      <span class="spacer" />
      <button v-if="tab === 'sample'" :disabled="tagging" @click="autoTagAll">
        <template v-if="tagging">{{ t('assets.tagging') }} {{ tagProgress }}</template>
        <template v-else><Tag class="icon" :size="12" /> {{ t('assets.autoTag') }}</template>
      </button>
      <template v-if="tab === 'score'">
        <input ref="scoreFile" type="file" accept=".mid,.midi,.musicxml,.xml,.mxl,.gp3,.gp4,.gp5,.mscz,.pdf,.jpg,.jpeg,.png"
               style="display: none" @change="uploadScore" />
        <button :disabled="busy" @click="($refs.scoreFile as HTMLInputElement).click()">
          <Upload class="icon" :size="12" /> {{ t('assets.uploadScore') }}
        </button>
      </template>
      <span class="dim small">{{ scanMsg }}</span>
      <button :disabled="busy" @click="rescan"><RefreshCw class="icon" :size="12" /> {{ t('assets.rescan') }}</button>
    </div>
    <div class="content">
      <div class="list panel">
        <div v-if="tab === 'soundfont' && tagCounts.length" class="cat-chips">
          <button v-for="[tg, n] in tagCounts" :key="tg" class="cat-chip"
                  :class="{ on: tagFilter === tg }"
                  :style="{ borderColor: catColor(tg) }"
                  @click="toggleTagChip(tg)">
            <component :is="catIcon(tg)" :size="11"
                       :style="{ color: catColor(tg) }" />
            {{ tg }} <span class="dim">{{ n }}</span>
          </button>
        </div>
        <div class="dim small count">{{ t('assets.count', { shown: filtered.length, total: assets.length }) }}</div>
        <div v-if="!assets.length" class="dim empty-hint">
          <template v-if="tab === 'score'">{{ t('assets.emptyScores') }}</template>
          <template v-else-if="tab === 'soundfont'">{{ t('assets.emptyFonts') }}</template>
          <template v-else-if="tab === 'sample'">{{ t('assets.emptySamples') }}</template>
          <template v-else>{{ t('assets.emptyVoice') }}</template>
        </div>
        <div
          v-for="a in filtered" :key="a.id" class="item"
          :class="{ active: selected?.id === a.id, missing: a.is_missing }"
          @click="select(a)"
        >
          <div class="fname">
            <component :is="catIcon(a.tags[0] ?? '')" v-if="tab === 'soundfont'"
                       :size="14" class="cat-ic"
                       :style="{ color: catColor(a.tags[0] ?? '') }" />
            {{ a.filename }} <span v-if="a.is_missing" class="err-text">({{ t('assets.missing') }})</span>
          </div>
          <div class="dim small">
            {{ fmtSize(a.file_size) }} · {{ a.analysis_status }}
            <span v-for="tg in a.tags.slice(0, 4)" :key="tg" class="tag">{{ tg }}</span>
          </div>
        </div>
      </div>
      <div class="detail panel">
        <div v-if="!selected" class="dim" style="padding: 20px">{{ t('assets.selectAsset') }}</div>
        <div v-else class="detail-body">
          <h3>{{ selected.filename }}</h3>
          <div class="dim small">{{ selected.relative_path }} · {{ fmtSize(selected.file_size) }}</div>

          <audio v-if="isAudio && !selected.is_missing" controls :src="`/api/assets/${selected.id}/file`" style="width: 100%" />

          <!-- score viewer: PDFs embedded, images inline -->
          <template v-if="tab === 'score' && !selected.is_missing">
            <iframe v-if="selected.extension === '.pdf'" class="score-view"
                    :src="`/api/assets/${selected.id}/file`" />
            <img v-else-if="['.jpg', '.jpeg', '.png'].includes(selected.extension)"
                 class="score-view img" :src="`/api/assets/${selected.id}/file`" />
          </template>

          <!-- soundfont: what's inside + provenance from the file itself -->
          <div v-if="tab === 'soundfont' && sfInfo" class="sf-info">
            <div v-if="sfInfo.categories?.length" class="sf-cats">
              <span v-for="c in sfInfo.categories" :key="c.category" class="sf-cat"
                    :style="{ borderColor: catColor(c.category) }">
                <component :is="catIcon(c.category)" :size="11"
                           :style="{ color: catColor(c.category) }" />
                {{ c.category }} × {{ c.count }}
              </span>
            </div>
            <table v-if="sfInfo.info && Object.keys(sfInfo.info).length" class="sf-meta">
              <tr v-if="sfInfo.info.name && !selected.filename.toLowerCase().includes(sfInfo.info.name.toLowerCase())">
                <td>{{ t('assets.sfBankName') }}</td><td>{{ sfInfo.info.name }}</td></tr>
              <tr v-if="sfInfo.info.author"><td>{{ t('assets.sfAuthor') }}</td><td>{{ sfInfo.info.author }}</td></tr>
              <tr v-if="sfInfo.info.copyright"><td>{{ t('assets.sfCopyright') }}</td>
                <td>{{ sfInfo.info.copyright }}
                  <button class="mini-btn" :title="t('assets.sfCopyLicense')"
                          @click="copyrightToLicense">→ {{ t('assets.license') }}</button></td></tr>
              <tr v-if="sfInfo.info.date"><td>{{ t('assets.sfDate') }}</td><td>{{ sfInfo.info.date }}</td></tr>
              <tr v-if="sfInfo.info.comments"><td>{{ t('assets.sfComments') }}</td>
                <td class="sf-comments">{{ sfInfo.info.comments }}</td></tr>
            </table>
          </div>

          <label class="field">{{ t('assets.tags') }}
            <input v-model="editTags" />
          </label>
          <label class="field">{{ t('assets.description') }}
            <textarea v-model="editDesc" rows="3" />
          </label>
          <label class="field">{{ t('assets.license') }}
            <input v-model="editLicense" />
          </label>
          <div class="row-btns">
            <button class="primary" @click="saveMetadata">{{ t('assets.saveMeta') }}</button>
            <button v-if="tab === 'sample' || tab === 'voice_recording'" :disabled="busy" @click="analyse">{{ t('assets.analyse') }}</button>
            <button v-if="tab === 'score' && !selected.is_missing" :disabled="importing"
                    class="primary" @click="importScoreAsSong">
              <template v-if="importing">{{ t('assets.reading') }}</template>
              <template v-else><Music class="icon" :size="12" /> {{ t('assets.turnIntoSong') }}</template>
            </button>
          </div>
          <div v-if="importMsg" class="dim small">{{ importMsg }}</div>
          <div v-if="selected.generated_description" class="gen-desc">
            <span class="dim small">{{ t('assets.autoDesc') }}</span> {{ selected.generated_description }}
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
.empty-hint { padding: 24px 18px; font-size: 13px; line-height: 1.6; }
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
.cat-chips { display: flex; flex-wrap: wrap; gap: 4px; padding: 6px 8px 2px; }
.cat-chip {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  background: transparent; border: 1px solid var(--border);
}
.cat-chip.on { background: var(--bg-elevated); font-weight: 600; }
.cat-ic { vertical-align: -2px; margin-right: 3px; }
.sf-info { display: flex; flex-direction: column; gap: 8px; }
.sf-cats { display: flex; flex-wrap: wrap; gap: 4px; }
.sf-cat {
  display: inline-flex; align-items: center; gap: 4px; font-size: 11px;
  border: 1px solid var(--border); border-radius: 10px; padding: 1px 8px;
}
.sf-meta { font-size: 12px; border-collapse: collapse; }
.sf-meta td { padding: 2px 8px 2px 0; vertical-align: top; }
.sf-meta td:first-child { color: var(--text-dim); white-space: nowrap; }
.sf-comments { white-space: pre-line; max-height: 90px; overflow-y: auto; display: block; }
.mini-btn { font-size: 10px; padding: 0 6px; margin-left: 6px; }
.score-view { width: 100%; height: 420px; border: 1px solid var(--border); border-radius: 6px; background: #fff; }
.score-view.img { height: auto; max-height: 480px; object-fit: contain; background: transparent; }
</style>
