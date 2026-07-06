<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api } from '../api/client'
import type { Asset, Effect, VoiceProfile } from '../api/types'
import { useStudioStore } from '../stores/studio'

const studio = useStudioStore()

const track = computed(() =>
  studio.project?.tracks.find((t) => t.id === studio.selectedTrackId) ?? null)

const soundfonts = ref<Asset[]>([])
const sfSearch = ref('')
const presets = ref<{ name: string; bank: number; program: number }[]>([])
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

const EFFECT_TYPES = ['gain', 'pan', 'eq', 'compressor', 'reverb', 'delay', 'distortion']
const DEFAULT_PARAMS: Record<string, Record<string, number>> = {
  gain: { gain_db: 0 },
  pan: { position: 0 },
  eq: { low_gain_db: 0, mid_gain_db: 0, high_gain_db: 0 },
  compressor: { threshold_db: -18, ratio: 4, makeup_db: 0 },
  reverb: { mix: 0.25, decay: 0.5 },
  delay: { time_seconds: 0.3, feedback: 0.35, mix: 0.3 },
  distortion: { drive: 3, mix: 1 },
}
const newEffectType = ref('reverb')

function addEffect() {
  if (!track.value) return
  track.value.effects.effects.push({
    id: crypto.randomUUID().replace(/-/g, ''),
    effect_type: newEffectType.value,
    enabled: true,
    params: { ...DEFAULT_PARAMS[newEffectType.value] },
  } as Effect)
  save()
}

function removeEffect(i: number) {
  track.value?.effects.effects.splice(i, 1)
  save()
}

function removeTrack() {
  if (!studio.project || !track.value) return
  if (!confirm(`Remove track "${track.value.name}"?`)) return
  studio.project.tracks = studio.project.tracks.filter((t) => t.id !== track.value!.id)
  studio.selectedTrackId = null
  save()
}

const currentFontName = computed(() => {
  const id = track.value?.instrument_config.soundfont_asset_id
  return soundfonts.value.find((a) => a.id === id)?.filename ?? '(auto-match at render)'
})

loadLibraries()
</script>

<template>
  <div v-if="!track" class="dim empty">Select a track in the timeline to inspect it.</div>
  <div v-else class="inspector">
    <div class="col">
      <h4>{{ track.name }} <span class="dim small">{{ track.track_type }}</span></h4>
      <label class="field">Name
        <input v-model="track.name" @change="save" />
      </label>

      <template v-if="isInstrument">
        <div class="field">
          <span>SoundFont — <span class="current">{{ currentFontName }}</span></span>
          <input v-model="sfSearch" placeholder="Search 196 SoundFonts…" />
          <div class="picker">
            <div
              v-for="a in filteredFonts" :key="a.id" class="pick-item"
              :class="{ active: track.instrument_config.soundfont_asset_id === a.id }"
              @click="pickFont(a)"
            >{{ a.filename }}</div>
          </div>
        </div>
        <div v-if="presets.length" class="field">
          <span>Preset (bank / program)</span>
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
        <label class="field">Voice profile
          <select :value="track.voice_profile_id ?? ''"
                  @change="track.voice_profile_id = ($event.target as HTMLSelectElement).value || null; save()">
            <option value="">(none — formant engine default)</option>
            <option v-for="p in profiles" :key="p.id" :value="p.id">{{ p.name }}</option>
          </select>
        </label>
        <p class="dim small">Profiles require recorded consent and are only used when selected here.</p>
      </template>
    </div>

    <div class="col">
      <h4>Effects <span v-if="saving" class="dim small">saving…</span></h4>
      <div class="add-fx">
        <select v-model="newEffectType">
          <option v-for="t in EFFECT_TYPES" :key="t" :value="t">{{ t }}</option>
        </select>
        <button @click="addEffect">+ Add</button>
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
      <div v-if="!track.effects.effects.length" class="dim small">No effects on this track.</div>
      <button class="danger" @click="removeTrack">Remove track</button>
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
</style>
