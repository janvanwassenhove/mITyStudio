<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { VoiceProfile } from '../api/types'
import { useStudioStore } from '../stores/studio'

const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const studio = useStudioStore()

interface InstrumentCard {
  type: string
  icon: string
}

// labels/blurbs live in the locale files under addTrack.inst.<type>
const INSTRUMENTS: InstrumentCard[] = [
  { type: 'drums', icon: '🥁' },
  { type: 'bass', icon: '🎸' },
  { type: 'guitar', icon: '🎸' },
  { type: 'keys', icon: '🎹' },
  { type: 'synth', icon: '🎛️' },
  { type: 'strings', icon: '🎻' },
  { type: 'brass', icon: '🎺' },
  { type: 'lead_vocal', icon: '🎤' },
  { type: 'sample', icon: '🔁' },
]

const label = (c: InstrumentCard) => t(`addTrack.inst.${c.type}.label`)

const picked = ref<InstrumentCard | null>(null)
const generate = ref(true)
const lyricsText = ref('')
const voiceProfileId = ref('')
const vocalStyle = ref<'sing' | 'rap'>('sing')

// duet support: which lyric sections does this voice sing?
const lyricSections = computed(() => {
  const p = studio.project
  if (!p) return []
  const withLyrics = new Set(p.lyrics.lines.map((l) => l.section_id))
  return p.sections.filter((s) => withLyrics.has(s.id))
})
const selectedSections = ref<string[]>([])
watch(lyricSections, (secs) => {
  selectedSections.value = secs.map((s) => s.id)
}, { immediate: true })
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
        sections: isVocal.value && !lines.length && selectedSections.value.length < lyricSections.value.length
          ? selectedSections.value : null,
      })
    await studio.reloadCurrent()
    if (res.errors.length) {
      error.value = res.errors.join('; ')
    } else {
      done.value = t('addTrack.added', { name: res.track_name })
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
        <h3>{{ picked ? picked.icon + ' ' + label(picked) : t('addTrack.title') }}</h3>
        <button class="close" @click="emit('close')">✕</button>
      </div>

      <!-- step 1: pick instrument -->
      <div v-if="!picked" class="cards">
        <button v-for="c in INSTRUMENTS" :key="c.type" class="card" @click="picked = c">
          <span class="icon">{{ c.icon }}</span>
          <span class="card-label">{{ label(c) }}</span>
          <span class="dim blurb">{{ t(`addTrack.inst.${c.type}.blurb`) }}</span>
        </button>
      </div>

      <!-- step 2: options -->
      <div v-else class="options">
        <label v-if="picked.type !== 'sample'" class="opt-row">
          <input type="checkbox" v-model="generate" />
          <span>
            <strong>{{ t('addTrack.writeForMe') }}</strong>
            <span class="dim block">
              {{ isVocal ? t('addTrack.genVocalBlurb')
                         : t('addTrack.genInstBlurb', { name: label(picked).toLowerCase() }) }}
            </span>
          </span>
        </label>

        <template v-if="isVocal">
          <label class="field">
            {{ t('addTrack.style') }}
            <select v-model="vocalStyle">
              <option value="sing">{{ t('addTrack.styleSing') }}</option>
              <option value="rap">{{ t('addTrack.styleRap') }}</option>
            </select>
          </label>
          <label class="field">
            {{ t('addTrack.singingVoice') }}
            <select v-model="voiceProfileId">
              <option v-if="profiles.length === 0" value="">{{ t('addTrack.syntheticNone') }}</option>
              <option v-for="p in profiles" :key="p.id" :value="p.id">🎙 {{ t('addTrack.yourVoice', { name: p.name }) }}</option>
              <option v-if="profiles.length" value="">{{ t('addTrack.syntheticInstead') }}</option>
            </select>
            <span v-if="!profiles.length" class="dim block small">
              {{ t('addTrack.voiceHint') }}
            </span>
          </label>
          <div v-if="lyricSections.length && !lyricsText.trim()" class="field">
            <span>{{ t('addTrack.singsSections') }}</span>
            <div class="sec-checks">
              <label v-for="s in lyricSections" :key="s.id" class="sec-check">
                <input type="checkbox" :value="s.id" v-model="selectedSections" />
                {{ s.name }}
              </label>
            </div>
          </div>
          <label class="field">
            {{ lyricSections.length ? t('addTrack.orNewLyrics') : t('addTrack.lyricsOptional') }}
            <textarea v-model="lyricsText" rows="3" :placeholder="t('addTrack.lyricsPlaceholder')" />
          </label>
        </template>

        <div v-if="picked.type === 'sample'" class="dim small">
          {{ t('addTrack.sampleHint') }}
        </div>

        <div class="actions">
          <button @click="picked = null">{{ t('common.back') }}</button>
          <button class="primary" :disabled="busy" @click="add">
            {{ busy ? t('addTrack.adding') : t('addTrack.addName', { name: label(picked) }) }}
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
.sec-checks { display: flex; flex-wrap: wrap; gap: 8px; }
.sec-check { display: flex; gap: 4px; align-items: center; font-size: 12px; color: var(--text); background: var(--bg-elevated); border-radius: 5px; padding: 3px 8px; }
.small { font-size: 11px; }
.actions { display: flex; justify-content: space-between; }
.ok-box { border: 1px solid var(--ok); color: var(--ok); border-radius: 6px; padding: 8px; font-size: 12px; }
.err-box { border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; }
</style>
