<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AudioWaveform, Cloud, Drum, Guitar, KeyboardMusic, Mic, Piano,
         Repeat, Sparkles, Speaker, Zap } from 'lucide-vue-next'
import { api } from '../api/client'
import { useStudioStore } from '../stores/studio'

const { t } = useI18n()

interface SearchHit {
  id: string
  filename: string
  tags: string[]
  analysis: { estimated_bpm: number | null; estimated_key: string | null; duration: number } | null
}

const studio = useStudioStore()
const query = ref('')
const bpmMin = ref<number | null>(null)
const bpmMax = ref<number | null>(null)
const hits = ref<SearchHit[]>([])
const busy = ref(false)
const message = ref('')

const CATEGORIES = [
  { tag: 'kick', icon: Zap }, { tag: 'snare', icon: Drum },
  { tag: 'hihat', icon: Drum }, { tag: '808', icon: Speaker },
  { tag: 'bass', icon: AudioWaveform }, { tag: 'pad', icon: Cloud },
  { tag: 'loop', icon: Repeat }, { tag: 'vocal', icon: Mic },
  { tag: 'guitar', icon: Guitar }, { tag: 'piano', icon: Piano },
  { tag: 'synth', icon: KeyboardMusic }, { tag: 'fx', icon: Sparkles },
]
const activeTag = ref('')
function toggleTag(tag: string) {
  activeTag.value = activeTag.value === tag ? '' : tag
  void search()
}

async function search() {
  busy.value = true
  try {
    const params = new URLSearchParams({ asset_type: 'sample' })
    if (query.value.trim()) params.set('text', query.value.trim())
    if (activeTag.value) params.set('tags', activeTag.value)
    if (bpmMin.value != null) params.set('bpm_min', String(bpmMin.value))
    if (bpmMax.value != null) params.set('bpm_max', String(bpmMax.value))
    hits.value = (await api.get<SearchHit[]>(`/assets/search?${params}`)).slice(0, 100)
  } finally {
    busy.value = false
  }
}

async function addToProject(hit: SearchHit, loop: boolean) {
  const p = studio.project
  if (!p) { message.value = t('export.noProject'); return }
  const beatsPerBar = studio.manifest?.beats_per_bar ?? 4
  const lastSection = p.sections[p.sections.length - 1]
  const startBeat = 0
  const durationBeats = loop
    ? (lastSection ? (lastSection.start_bar + lastSection.length_bars) * beatsPerBar : beatsPerBar * 8)
    : Math.max(((hit.analysis?.duration ?? 2) * p.bpm) / 60, 1)

  let track = p.tracks.find((t) => t.track_type === 'sample' && t.name === 'Samples')
  if (!track) {
    track = {
      id: crypto.randomUUID().replace(/-/g, ''),
      name: 'Samples', track_type: 'sample',
      instrument_config: { soundfont_asset_id: null, program: 0, is_drum_kit: false, bank: 0 },
      clips: [], effects: { effects: [] },
      volume: 1, pan: 0, mute: false, solo: false, voice_profile_id: null,
      vocal_style: 'sing',
    }
    p.tracks.push(track)
  }
  track.clips.push({
    id: crypto.randomUUID().replace(/-/g, ''),
    section_id: '', clip_type: 'sample',
    start_beat: startBeat, duration_beats: durationBeats,
    note_events: [], source_asset_id: hit.id, gain_db: 0, loop,
    fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
  })
  await studio.saveProject()
  message.value = t('samples.added', { name: hit.filename }) + (loop ? ` (${t('samples.looped')})` : ` (${t('samples.oneShot')})`)
}

onMounted(search)
</script>

<template>
  <div class="browser">
    <div class="cat-chips">
      <button v-for="c in CATEGORIES" :key="c.tag" class="chip"
              :class="{ on: activeTag === c.tag }" @click="toggleTag(c.tag)">
        <component :is="c.icon" class="icon" :size="11" /> {{ c.tag }}
      </button>
      <span class="dim small">{{ t('samples.chipsHint') }}</span>
    </div>
    <div class="controls">
      <input v-model="query" :placeholder="t('samples.searchPh')" style="flex: 1" @keyup.enter="search" />
      <input v-model.number="bpmMin" type="number" :placeholder="t('samples.minBpm')" style="width: 80px" />
      <input v-model.number="bpmMax" type="number" :placeholder="t('samples.maxBpm')" style="width: 80px" />
      <button :disabled="busy" @click="search">{{ t('common.search') }}</button>
      <span class="dim small">{{ message }}</span>
    </div>
    <div class="results">
      <div v-for="h in hits" :key="h.id" class="hit">
        <div class="hit-info">
          <div class="fname">{{ h.filename }}</div>
          <div class="dim small">
            <span v-if="h.analysis?.estimated_bpm">{{ h.analysis.estimated_bpm }} BPM · </span>
            <span v-if="h.analysis?.estimated_key">{{ h.analysis.estimated_key }} · </span>
            <span v-if="h.analysis?.duration">{{ h.analysis.duration.toFixed(2) }}s</span>
          </div>
        </div>
        <audio controls preload="none" :src="`/api/assets/${h.id}/file`" class="preview" />
        <button class="tiny-btn" :title="t('samples.addShotTip')" @click="addToProject(h, false)">{{ t('samples.addShot') }}</button>
        <button class="tiny-btn" :title="t('samples.addLoopTip')" @click="addToProject(h, true)">{{ t('samples.addLoop') }}</button>
      </div>
      <div v-if="!hits.length && !busy" class="dim small" style="padding: 12px">
        {{ t('samples.noResults') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.browser { display: flex; flex-direction: column; height: 100%; }
.controls { display: flex; gap: 6px; align-items: center; padding: 8px; border-bottom: 1px solid var(--border); flex: none; }
.cat-chips { display: flex; gap: 4px; flex-wrap: wrap; padding: 8px 8px 0; align-items: center; }
.chip { padding: 2px 8px; font-size: 11px; border-radius: 12px; }
.chip.on { border-color: var(--accent); color: var(--accent); }
.small { font-size: 11px; }
.results { flex: 1; overflow-y: auto; }
.hit { display: flex; align-items: center; gap: 8px; padding: 4px 10px; border-bottom: 1px solid var(--border); }
.hit-info { flex: 1; min-width: 0; }
.fname { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.preview { height: 28px; width: 220px; flex: none; }
.tiny-btn { padding: 2px 8px; font-size: 11px; flex: none; }
</style>
