<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { Asset, Effect, Track, VoiceProfile } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

const { t } = useI18n()
const studio = useStudioStore()
const playback = usePlaybackStore()

const track = computed(() =>
  studio.project?.tracks.find((t) => t.id === studio.selectedTrackId) ?? null)

const soundfonts = ref<Asset[]>([])
const sfSearch = ref('')
const presets = ref<{ name: string; bank: number; program: number }[]>([])

// global instrument search across ALL soundfont presets
interface PresetHit { asset_id: string; soundfont: string; preset: string; bank: number; program: number }
const instSearch = ref('')
const instHits = ref<PresetHit[]>([])
const instSearching = ref(false)
let instTimer: ReturnType<typeof setTimeout> | null = null

function queueInstSearch() {
  if (instTimer) clearTimeout(instTimer)
  instTimer = setTimeout(async () => {
    const q = instSearch.value.trim()
    if (q.length < 2) { instHits.value = []; return }
    instSearching.value = true
    try {
      instHits.value = await api.get<PresetHit[]>(
        `/assets/soundfont-presets/search?q=${encodeURIComponent(q)}`)
    } finally {
      instSearching.value = false
    }
  }, 300)
}

function pickInstrument(hit: PresetHit) {
  if (!track.value) return
  track.value.instrument_config.soundfont_asset_id = hit.asset_id
  track.value.instrument_config.bank = hit.bank
  track.value.instrument_config.program = hit.program
  instHits.value = []
  instSearch.value = hit.preset
  save()
}
const profiles = ref<VoiceProfile[]>([])
const saving = ref(false)

const isVocal = computed(() => track.value != null &&
  ['lead_vocal', 'backing_vocal'].includes(track.value.track_type))
const isInstrument = computed(() => track.value != null &&
  !['sample', 'lead_vocal', 'backing_vocal'].includes(track.value.track_type))

const filteredFonts = computed(() => {
  const q = sfSearch.value.toLowerCase()
  return soundfonts.value.filter((a) => a.filename.toLowerCase().includes(q)).slice(0, 60)
})

async function loadLibraries() {
  soundfonts.value = await api.get<Asset[]>('/assets/soundfonts')
  profiles.value = await api.get<VoiceProfile[]>('/voice/profiles')
}

async function loadPresets(assetId: string | null) {
  presets.value = []
  if (!assetId) return
  try {
    const inv = await api.get<{ presets: typeof presets.value }>(`/assets/${assetId}/soundfont-presets`)
    presets.value = inv.presets ?? []
  } catch { /* non-sf2 or parse error */ }
}

watch(() => track.value?.instrument_config.soundfont_asset_id,
  (id) => loadPresets(id ?? null), { immediate: true })

let timer: ReturnType<typeof setTimeout> | null = null
function save() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(async () => {
    saving.value = true
    try { await studio.saveProject() } finally { saving.value = false }
  }, 400)
}

function pickFont(a: Asset) {
  if (!track.value) return
  track.value.instrument_config.soundfont_asset_id = a.id
  save()
}

function pickPreset(p: { bank: number; program: number }) {
  if (!track.value) return
  track.value.instrument_config.bank = p.bank
  track.value.instrument_config.program = p.program
  save()
}

const EFFECT_TYPES = ['gain', 'pan', 'eq', 'compressor', 'reverb', 'delay',
  'distortion', 'robot', 'telephone', 'chorus', 'autotune']
const DEFAULT_PARAMS: Record<string, Record<string, number>> = {
  gain: { gain_db: 0 },
  pan: { position: 0 },
  eq: { low_gain_db: 0, mid_gain_db: 0, high_gain_db: 0 },
  compressor: { threshold_db: -18, ratio: 4, makeup_db: 0 },
  reverb: { mix: 0.25, decay: 0.5 },
  delay: { time_seconds: 0.3, feedback: 0.35, mix: 0.3 },
  distortion: { drive: 3, mix: 1 },
  robot: { carrier_hz: 55, mix: 1, crush: 0.15 },
  telephone: { low_freq: 300, high_freq: 3400, drive: 1.5 },
  chorus: { depth_ms: 8, rate_hz: 0.8, mix: 0.5 },
  autotune: { root: 0, minor: 0, strength: 1, speed: 0.8 },
}
const newEffectType = ref('reverb')

const KEY_ROOTS: Record<string, number> = { C: 0, 'C#': 1, Db: 1, D: 2, 'D#': 3,
  Eb: 3, E: 4, F: 5, 'F#': 6, Gb: 6, G: 7, 'G#': 8, Ab: 8, A: 9, 'A#': 10,
  Bb: 10, B: 11 }

function addEffect() {
  if (!track.value) return
  const params = { ...DEFAULT_PARAMS[newEffectType.value] }
  if (newEffectType.value === 'autotune' && studio.project) {
    // voicetune snaps to the song's key automatically
    const m = studio.project.key.match(/^([A-G][#b]?)\s*(minor|min|m)?/i)
    if (m) {
      params.root = KEY_ROOTS[m[1][0].toUpperCase() + m[1].slice(1)] ?? 0
      params.minor = m[2] ? 1 : 0
    }
  }
  track.value.effects.effects.push({
    id: crypto.randomUUID().replace(/-/g, ''),
    effect_type: newEffectType.value,
    enabled: true,
    params,
  } as Effect)
  save()
}

function removeEffect(i: number) {
  track.value?.effects.effects.splice(i, 1)
  save()
}

// --- live vocal take: record mic → save as voice recording → clip on track ---
const recording = ref(false)
const recordSeconds = ref(0)
const takeStatus = ref('')
let mediaRecorder: MediaRecorder | null = null
let chunks: Blob[] = []
let recTimer: ReturnType<typeof setInterval> | null = null
let takeStartSeconds = 0

async function startTake() {
  takeStatus.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunks = []
    takeStartSeconds = playback.playhead
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((s) => s.stop())
      const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
      const ext = (mediaRecorder?.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
      try {
        const asset = await api.upload<Asset>('/voice/recordings/upload', blob,
          `take-${track.value?.name ?? 'vocal'}-${Date.now()}.${ext}`,
          { source: 'live_recording' })
        const p = studio.project
        const m = studio.manifest
        if (p && m && track.value) {
          const durationBeats = Math.max((recordSeconds.value * p.bpm) / 60, 1)
          track.value.clips.push({
            id: crypto.randomUUID().replace(/-/g, ''),
            section_id: '', clip_type: 'sample',
            start_beat: (takeStartSeconds * p.bpm) / 60,
            duration_beats: durationBeats,
            note_events: [], source_asset_id: asset.id, gain_db: 0, loop: false,
            fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
          })
          await studio.saveProject()
          takeStatus.value = t('inspector.takePlaced')
        }
      } catch (e) {
        takeStatus.value = String(e)
      }
    }
    mediaRecorder.start()
    recording.value = true
    recordSeconds.value = 0
    recTimer = setInterval(() => recordSeconds.value++, 1000)
  } catch (e) {
    takeStatus.value = t('transport.micUnavailable') + String(e)
  }
}

function stopTake() {
  mediaRecorder?.stop()
  recording.value = false
  if (recTimer) clearInterval(recTimer)
}

onUnmounted(() => { if (recording.value) stopTake() })

function removeTrack() {
  if (!studio.project || !track.value) return
  if (!confirm(t('inspector.removeConfirm', { name: track.value.name }))) return
  studio.project.tracks = studio.project.tracks.filter((t) => t.id !== track.value!.id)
  studio.selectedTrackId = null
  save()
}

const currentFontName = computed(() => {
  const id = track.value?.instrument_config.soundfont_asset_id
  return soundfonts.value.find((a) => a.id === id)?.filename ?? t('inspector.autoMatch')
})

loadLibraries()
</script>

<template>
  <div v-if="!track" class="dim empty">{{ t('inspector.selectTrack') }}</div>
  <div v-else class="inspector">
    <div class="col">
      <h4>{{ track.name }} <span class="dim small">{{ track.track_type }}</span></h4>
      <label class="field">{{ t('inspector.name') }}
        <input v-model="track.name" @change="save" />
      </label>

      <template v-if="isInstrument">
        <div class="field">
          <span>🔎 {{ t('inspector.findInstrument') }}</span>
          <input v-model="instSearch" :placeholder="t('inspector.findPh')"
                 @input="queueInstSearch" />
          <div v-if="instHits.length" class="picker">
            <div v-for="(h, i) in instHits" :key="i" class="pick-item" @click="pickInstrument(h)">
              <strong>{{ h.preset }}</strong> <span class="dim">— {{ h.soundfont }}</span>
            </div>
          </div>
          <span v-else-if="instSearch.length >= 2 && !instSearching" class="dim small">
            {{ t('inspector.noPresetMatch') }}
          </span>
        </div>
        <div class="field">
          <span>SoundFont — <span class="current">{{ currentFontName }}</span></span>
          <input v-model="sfSearch" :placeholder="t('inspector.searchFonts')" />
          <div class="picker">
            <div
              v-for="a in filteredFonts" :key="a.id" class="pick-item"
              :class="{ active: track.instrument_config.soundfont_asset_id === a.id }"
              @click="pickFont(a)"
            >{{ a.filename }}</div>
          </div>
        </div>
        <div v-if="presets.length" class="field">
          <span>{{ t('inspector.preset') }}</span>
          <div class="picker">
            <div
              v-for="(p, i) in presets.slice(0, 100)" :key="i" class="pick-item"
              :class="{ active: track.instrument_config.bank === p.bank && track.instrument_config.program === p.program }"
              @click="pickPreset(p)"
            >{{ p.bank }}:{{ p.program }} — {{ p.name }}</div>
          </div>
        </div>
      </template>

      <template v-if="isVocal">
        <label class="field">{{ t('inspector.voiceProfile') }}
          <select :value="track.voice_profile_id ?? ''"
                  @change="track.voice_profile_id = ($event.target as HTMLSelectElement).value || null; save()">
            <option value="">{{ t('inspector.noProfile') }}</option>
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ t('inspector.aiVoice', { name: p.name }) }}</option>
          </select>
        </label>
        <label class="field">{{ t('inspector.vocalStyle') }}
          <select :value="track.vocal_style ?? 'sing'"
                  @change="track.vocal_style = ($event.target as HTMLSelectElement).value as Track['vocal_style']; save()">
            <option value="sing">{{ t('addTrack.styleSing') }}</option>
            <option value="soft">{{ t('addTrack.styleSoft') }}</option>
            <option value="powerful">{{ t('addTrack.stylePowerful') }}</option>
            <option value="rap">{{ t('addTrack.styleRap') }}</option>
          </select>
        </label>
        <p class="dim small">
          {{ t('inspector.profileBlurb') }}
        </p>
        <div class="field">
          <span>{{ t('inspector.recordTake') }}</span>
          <div class="rec-row">
            <button v-if="!recording" @click="startTake">● {{ t('inspector.recordAtPlayhead') }}</button>
            <button v-else class="rec-active" @click="stopTake">■ {{ t('common.stop') }} ({{ recordSeconds }}s)</button>
            <span class="dim small">{{ takeStatus }}</span>
          </div>
        </div>
      </template>
    </div>

    <div class="col">
      <h4>{{ t('inspector.effects') }} <span v-if="saving" class="dim small">{{ t('common.saving') }}</span></h4>
      <div class="add-fx">
        <select v-model="newEffectType">
          <option v-for="ft in EFFECT_TYPES" :key="ft" :value="ft">{{ ft }}</option>
        </select>
        <button @click="addEffect">+ {{ t('common.add') }}</button>
      </div>
      <div v-for="(fx, i) in track.effects.effects" :key="fx.id" class="fx">
        <div class="fx-head">
          <label class="small">
            <input type="checkbox" v-model="fx.enabled" @change="save" /> {{ fx.effect_type }}
          </label>
          <button class="tiny-btn" @click="removeEffect(i)">✕</button>
        </div>
        <div v-for="(v, k) in fx.params" :key="k" class="param">
          <span class="small dim">{{ k }}</span>
          <input type="number" step="0.05" :value="v"
                 @change="fx.params[k] = Number(($event.target as HTMLInputElement).value); save()" />
        </div>
      </div>
      <div v-if="!track.effects.effects.length" class="dim small">{{ t('inspector.noEffects') }}</div>
      <button class="danger" @click="removeTrack">{{ t('inspector.removeTrack') }}</button>
    </div>
  </div>
</template>

<style scoped>
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.inspector { display: flex; gap: 16px; padding: 12px; overflow-y: auto; height: 100%; }
.col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
h4 { margin: 0; }
.small { font-size: 11px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.current { color: var(--accent); }
.picker { max-height: 110px; overflow-y: auto; border: 1px solid var(--border); border-radius: 6px; }
.pick-item { padding: 3px 8px; font-size: 11px; cursor: pointer; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pick-item:hover { background: var(--bg-elevated); }
.pick-item.active { background: var(--accent); color: #fff; }
.add-fx { display: flex; gap: 6px; }
.fx { border: 1px solid var(--border); border-radius: 6px; padding: 6px 8px; }
.fx-head { display: flex; justify-content: space-between; align-items: center; }
.param { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: 3px; }
.param input { width: 90px; padding: 2px 6px; }
.tiny-btn { padding: 0 6px; font-size: 11px; }
.danger { border-color: var(--err); color: var(--err); margin-top: auto; }
.rec-row { display: flex; gap: 8px; align-items: center; }
.rec-active { background: var(--err); border-color: var(--err); color: #fff; }
</style>
