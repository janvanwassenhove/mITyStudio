<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'
import type { VoiceProfile } from '../api/types'
import { useStudioStore } from '../stores/studio'

const emit = defineEmits<{ close: [] }>()
const studio = useStudioStore()

interface InstrumentCard {
  type: string
  icon: string
  label: string
  blurb: string
}

const INSTRUMENTS: InstrumentCard[] = [
  { type: 'drums', icon: '🥁', label: 'Drums', blurb: 'Beat matching the song style' },
  { type: 'bass', icon: '🎸', label: 'Bass', blurb: 'Bassline following the chords' },
  { type: 'guitar', icon: '🎸', label: 'Guitar', blurb: 'Strummed chords' },
  { type: 'keys', icon: '🎹', label: 'Keys / Piano', blurb: 'Chords on piano or organ' },
  { type: 'synth', icon: '🎛️', label: 'Synth', blurb: 'Melodic synth line' },
  { type: 'strings', icon: '🎻', label: 'Strings', blurb: 'String ensemble pads' },
  { type: 'brass', icon: '🎺', label: 'Brass', blurb: 'Horn section stabs' },
  { type: 'lead_vocal', icon: '🎤', label: 'Voice', blurb: 'Singing with lyrics — your voice or synthetic' },
  { type: 'sample', icon: '🔁', label: 'Samples', blurb: 'Empty lane — drop loops from the Samples browser' },
]

const picked = ref<InstrumentCard | null>(null)
const generate = ref(true)
const lyricsText = ref('')
const voiceProfileId = ref('')
const vocalStyle = ref<'sing' | 'rap'>('sing')
const profiles = ref<VoiceProfile[]>([])
const busy = ref(false)
const error = ref('')
const done = ref('')

const isVocal = computed(() => picked.value?.type === 'lead_vocal')

onMounted(async () => {
  profiles.value = await api.get<VoiceProfile[]>('/voice/profiles')
  if (profiles.value.length) voiceProfileId.value = profiles.value[0].id
})

async function add() {
  const p = studio.project
  if (!p || !picked.value) return
  busy.value = true
  error.value = ''
  try {
    const lines = lyricsText.value.split('\n').map((l) => l.trim()).filter(Boolean)
    const res = await api.post<{ track_name: string; applied: string[]; errors: string[] }>(
      `/projects/${p.id}/tracks/quick-add`, {
        track_type: picked.value.type,
        generate: picked.value.type === 'sample' ? false : generate.value,
        voice_profile_id: isVocal.value && voiceProfileId.value ? voiceProfileId.value : null,
        lyrics: isVocal.value && lines.length ? lines : null,
        vocal_style: vocalStyle.value,
      })
    await studio.reloadCurrent()
    if (res.errors.length) {
      error.value = res.errors.join('; ')
    } else {
      done.value = `Added ${res.track_name}. Press ▶ to hear it — audio renders automatically.`
      setTimeout(() => emit('close'), 1600)
    }
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="dialog panel">
      <div class="head">
        <h3>{{ picked ? picked.icon + ' ' + picked.label : 'Add a track' }}</h3>
        <button class="close" @click="emit('close')">✕</button>
      </div>

      <!-- step 1: pick instrument -->
      <div v-if="!picked" class="cards">
        <button v-for="c in INSTRUMENTS" :key="c.type" class="card" @click="picked = c">
          <span class="icon">{{ c.icon }}</span>
          <span class="card-label">{{ c.label }}</span>
          <span class="dim blurb">{{ c.blurb }}</span>
        </button>
      </div>

      <!-- step 2: options -->
      <div v-else class="options">
        <label v-if="picked.type !== 'sample'" class="opt-row">
          <input type="checkbox" v-model="generate" />
          <span>
            <strong>Write the part for me</strong>
            <span class="dim block">
              {{ isVocal ? 'Lyrics and a melody are created — no music theory needed.'
                         : 'A ' + picked.label.toLowerCase() + ' part is generated for the whole song, matching key, tempo and style. You never have to enter chords or tabs.' }}
            </span>
          </span>
        </label>

        <template v-if="isVocal">
          <label class="field">
            Style
            <select v-model="vocalStyle">
              <option value="sing">🎵 Singing — melody with vibrato</option>
              <option value="rap">🎤 Rap — rhythm-locked flow, natural pitch</option>
            </select>
          </label>
          <label class="field">
            Singing voice
            <select v-model="voiceProfileId">
              <option v-if="profiles.length === 0" value="">Synthetic voice (no profile yet)</option>
              <option v-for="p in profiles" :key="p.id" :value="p.id">🎙 {{ p.name }} — your voice</option>
              <option v-if="profiles.length" value="">Synthetic voice instead</option>
            </select>
            <span v-if="!profiles.length" class="dim block small">
              To sing with <em>your</em> voice: go to <strong>Voices</strong> → record or upload
              yourself → create a voice profile (with consent). It then appears here.
            </span>
          </label>
          <label class="field">
            Lyrics (optional — leave empty and I'll write some)
            <textarea v-model="lyricsText" rows="4" placeholder="One line per lyric line…" />
          </label>
        </template>

        <div v-if="picked.type === 'sample'" class="dim small">
          A sample lane is added. Open the <strong>Samples</strong> tab below the
          timeline to search your 2,900+ samples and click “+ shot” or “+ loop”.
        </div>

        <div class="actions">
          <button @click="picked = null">← Back</button>
          <button class="primary" :disabled="busy" @click="add">
            {{ busy ? 'Adding…' : 'Add ' + picked.label }}
          </button>
        </div>
        <div v-if="done" class="ok-box">{{ done }}</div>
        <div v-if="error" class="err-box">{{ error }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 50; }
.dialog { width: 560px; max-width: 92vw; max-height: 85vh; overflow-y: auto; padding: 16px; }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
h3 { margin: 0; }
.close { border: none; background: transparent; font-size: 14px; }
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.card { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 14px 8px; border-radius: 10px; }
.card:hover { border-color: var(--accent); background: var(--bg-elevated); }
.icon { font-size: 28px; }
.card-label { font-weight: 600; font-size: 13px; }
.blurb { font-size: 10px; text-align: center; line-height: 1.3; }
.options { display: flex; flex-direction: column; gap: 14px; }
.opt-row { display: flex; gap: 10px; align-items: flex-start; font-size: 13px; }
.block { display: block; font-size: 11px; margin-top: 2px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.small { font-size: 11px; }
.actions { display: flex; justify-content: space-between; }
.ok-box { border: 1px solid var(--ok); color: var(--ok); border-radius: 6px; padding: 8px; font-size: 12px; }
.err-box { border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; }
</style>
