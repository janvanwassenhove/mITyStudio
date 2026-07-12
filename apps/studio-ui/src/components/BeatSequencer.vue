<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import { DRUM_SVG } from '../lib/drumIcons'

const props = defineProps<{ track: Track; clip: Clip }>()
const emit = defineEmits<{ changed: [] }>()
const { t } = useI18n()
const studio = useStudioStore()
const playback = usePlaybackStore()
const uid = () => crypto.randomUUID().replace(/-/g, '')

// GarageBand-style lanes, each with its own color
const LANES = [
  { midi: 36, label: 'Kick', color: '#e73896' },
  { midi: 38, label: 'Snare', color: '#e6a23c' },
  { midi: 39, label: 'Clap', color: '#c99215' },
  { midi: 42, label: 'Hi-Hat', color: '#2dd4cf' },
  { midi: 46, label: 'Open Hat', color: '#1fa89b' },
  { midi: 51, label: 'Ride', color: '#3b82c4' },
  { midi: 49, label: 'Crash', color: '#2a7f8f' },
  { midi: 70, label: 'Shaker', color: '#a06cf2' },
  { midi: 45, label: 'Lo Tom', color: '#8d5cd4' },
  { midi: 50, label: 'Toms', color: '#3ecf6e' },
]

const STEP = 0.25
const bars = ref(1)
const beatsPerBar = computed(() => studio.manifest?.beats_per_bar ?? 4)
const stepCount = computed(() => Math.round(bars.value * beatsPerBar.value / STEP))

type EditTool = 'toggle' | 'velocity'
const tool = ref<EditTool>('toggle')
const msg = ref('')

// --- the pattern lives in a buffer, NOT in the clip: design freely, then
// "＋ Add as clip" drops it into the song where you fine-tune it ---
interface Hit { midi: number; step: number; vel: number }
const grid = ref<Hit[]>(
  props.clip.note_events
    .filter((n) => n.start_beat < 2 * (studio.manifest?.beats_per_bar ?? 4))
    .map((n) => ({ midi: n.midi_note,
                   step: Math.round(n.start_beat / STEP),
                   vel: n.velocity })))

function hitAt(midi: number, step: number): Hit | undefined {
  return grid.value.find((h) => h.midi === midi && h.step === step)
}

function tapStep(midi: number, step: number) {
  const existing = hitAt(midi, step)
  let added: Hit | null = null
  if (tool.value === 'velocity') {
    if (existing) {
      existing.vel = existing.vel < 75 ? 95 : existing.vel < 110 ? 122 : 60
      added = existing
    } else {
      added = { midi, step, vel: 95 }
      grid.value.push(added)
    }
  } else if (existing) {
    grid.value = grid.value.filter((h) => h !== existing)
  } else {
    added = { midi, step, vel: step % 4 === 0 ? 110 : 90 }
    grid.value.push(added)
  }
  // audition the drum right away when the loop is stopped (sounds loaded
  // after the first ▶); while playing the scheduler picks the edit up live
  if (added && !playing.value && ctx && oneShots.size) {
    playHit(added.midi, added.vel, ctx.currentTime)
  }
}

// --- pattern presets (steps are 16th indices within one bar) ---
const PATTERNS: Record<string, Partial<Record<number, number[]>>> = {
  'Modern 808': { 36: [0, 7, 10], 39: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 46: [15], 70: [1, 3, 5, 7, 9, 11, 13, 15] },
  'Hip-Hop': { 36: [0, 6, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 46: [7] },
  'House': { 36: [0, 4, 8, 12], 39: [4, 12], 46: [2, 6, 10, 14], 70: [0, 2, 4, 6, 8, 10, 12, 14] },
  'Rock': { 36: [0, 8, 10], 38: [4, 12], 42: [0, 2, 4, 6, 8, 10, 12, 14], 49: [0] },
  'Funk': { 36: [0, 3, 10], 38: [4, 12, 14], 42: [0, 2, 4, 5, 6, 8, 10, 12, 14, 15], 46: [7] },
  'Techno': { 36: [0, 4, 8, 12], 39: [4, 12], 42: [2, 6, 10, 14], 51: [0, 8], 70: [1, 3, 5, 7, 9, 11, 13, 15] },
}
const patternName = ref('')

function applyPattern(name: string) {
  const pat = PATTERNS[name]
  if (!pat) return
  grid.value = []
  for (let bar = 0; bar < bars.value; bar++) {
    for (const [midi, steps] of Object.entries(pat)) {
      for (const s of steps ?? []) {
        grid.value.push({ midi: Number(midi), step: bar * 16 + s,
                          vel: s % 4 === 0 ? 110 : 90 })
      }
    }
  }
  patternName.value = name
}

function clearGrid() {
  grid.value = []
}

// --- add the pattern to the song as a NEW clip on this track --------------
function addAsClip() {
  const p = studio.project
  const m = studio.manifest
  if (!p || !m) return
  const track = p.tracks.find((t) => t.id === props.track.id)
  if (!track) return
  if (!grid.value.length) { msg.value = t('seq.gridEmpty'); return }
  const bpb = m.beats_per_bar
  const startBar = Math.round(((playback.playhead * m.bpm) / 60) / bpb)
  const clip: Clip = {
    id: uid(), section_id: '', clip_type: 'midi',
    start_beat: startBar * bpb,
    duration_beats: stepCount.value * STEP,
    note_events: grid.value.map((h) => ({
      id: uid(), pitch: '', midi_note: h.midi, start_beat: h.step * STEP,
      duration_beats: 0.2, velocity: h.vel, lyric_syllable: '',
    } as NoteEvent)),
    source_asset_id: null, gain_db: 0, loop: false,
    fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
  }
  track.clips.push(clip)
  studio.selectedClip = { trackId: track.id, clipId: clip.id }
  msg.value = '✓ ' + t('seq.clipAdded', { bar: startBar + 1 })
  emit('changed')
}

// --- live loop: WebAudio step scheduler over per-drum one-shots ----------
// Each lane's drum is rendered ONCE by the real kit and cached; hits are
// then scheduled sample-accurately client-side. Result: a perfectly tight
// loop (no file-loop gap/drift) and edits that are audible on the very next
// step — no server round-trip while playing.
const playing = ref(false)
const loading = ref(false)
const currentStep = ref(-1)
let ctx: AudioContext | null = null
let raf = 0
let schedTimer: ReturnType<typeof setInterval> | null = null
const oneShots = new Map<number, AudioBuffer>()
let kitKey = ''

const stepSeconds = computed(() =>
  (STEP * 60) / (studio.project?.bpm ?? 120))

function currentKitKey(): string {
  const cfg = props.track.instrument_config
  return `${cfg.soundfont_asset_id}:${cfg.bank}:${cfg.program}`
}

async function fetchOneShot(midi: number): Promise<AudioBuffer | null> {
  const p = studio.project
  if (!p || !ctx) return null
  const cfg = props.track.instrument_config
  const res = await fetch('/api/projects/preview/instrument', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ soundfont_asset_id: cfg.soundfont_asset_id,
                           bank: cfg.bank, program: cfg.program,
                           is_drum_kit: true, bpm: p.bpm,
                           notes: [{ midi_note: midi, start_beat: 0,
                                     duration_beats: 0.3, velocity: 112 }] }),
  })
  if (!res.ok) return null
  return ctx.decodeAudioData(await res.arrayBuffer())
}

async function ensureOneShots(): Promise<void> {
  if (kitKey === currentKitKey() && oneShots.size) return
  oneShots.clear()
  kitKey = currentKitKey()
  await Promise.all(LANES.map(async (l) => {
    const buf = await fetchOneShot(l.midi)
    if (buf) oneShots.set(l.midi, buf)
  }))
}

function playHit(midi: number, vel: number, when: number) {
  const buf = oneShots.get(midi)
  if (!buf || !ctx) return
  const src = ctx.createBufferSource()
  src.buffer = buf
  const g = ctx.createGain()
  g.gain.value = Math.pow(vel / 127, 1.2)
  src.connect(g).connect(ctx.destination)
  src.start(when)
}

// lookahead scheduler: reads the LIVE grid each tick, so any edit plays on
// its next occurrence
let nextStep = 0
let nextTime = 0
let stepTimes: { step: number; at: number }[] = []
const LOOKAHEAD = 0.12

function schedule() {
  if (!ctx || !playing.value) return
  while (nextTime < ctx.currentTime + LOOKAHEAD) {
    const stepIdx = nextStep % stepCount.value
    for (const h of grid.value) {
      if (h.step === stepIdx) playHit(h.midi, h.vel, nextTime)
    }
    stepTimes.push({ step: stepIdx, at: nextTime })
    nextTime += stepSeconds.value
    nextStep++
  }
}

function tick() {
  if (!playing.value || !ctx) return
  while (stepTimes.length > 1 && stepTimes[1].at <= ctx.currentTime) {
    stepTimes.shift()
  }
  if (stepTimes.length && stepTimes[0].at <= ctx.currentTime) {
    currentStep.value = stepTimes[0].step
  }
  raf = requestAnimationFrame(tick)
}

async function togglePower() {
  if (playing.value) {
    playing.value = false
    currentStep.value = -1
    cancelAnimationFrame(raf)
    if (schedTimer) { clearInterval(schedTimer); schedTimer = null }
    return
  }
  loading.value = true
  msg.value = ''
  try {
    ctx = ctx ?? new AudioContext()
    await ctx.resume()
    await ensureOneShots()
    if (!oneShots.size) { msg.value = t('seq.audioBlocked'); return }
    playing.value = true
    nextStep = 0
    nextTime = ctx.currentTime + 0.06
    stepTimes = []
    schedule()
    schedTimer = setInterval(schedule, 30)
    raf = requestAnimationFrame(tick)
  } catch (e) {
    msg.value = String(e)
  } finally {
    loading.value = false
  }
}

// kit switched while playing → re-fetch the one-shots, loop keeps running
watch(currentKitKey, () => { if (playing.value) void ensureOneShots() })

onBeforeUnmount(() => {
  cancelAnimationFrame(raf)
  if (schedTimer) clearInterval(schedTimer)
  void ctx?.close()
})
</script>

<template>
  <div class="seq">
    <div class="seq-bar">
      <select class="pattern-pick" :value="patternName"
              @change="applyPattern(($event.target as HTMLSelectElement).value)">
        <option value="" disabled>{{ t('seq.choosePattern') }}</option>
        <option v-for="(_, name) in PATTERNS" :key="name" :value="name">{{ name }}</option>
      </select>
      <div class="tools">
        <button :class="{ on: tool === 'toggle' }" @click="tool = 'toggle'">{{ t('seq.stepOnOff') }}</button>
        <button :class="{ on: tool === 'velocity' }" @click="tool = 'velocity'">{{ t('seq.velocity') }}</button>
      </div>
      <div class="tools">
        <button :class="{ on: bars === 1 }" @click="bars = 1">{{ t('seq.oneBar') }}</button>
        <button :class="{ on: bars === 2 }" @click="bars = 2">{{ t('seq.twoBars') }}</button>
      </div>
      <span class="spacer" />
      <button class="tb" @click="clearGrid">✕ {{ t('common.clear') }}</button>
      <button class="power" :class="{ on: playing }" :disabled="loading"
              :title="t('seq.previewTip')"
              @click="togglePower">
        {{ loading ? '⏳ ' + t('seq.rendering') : playing ? '■ ' + t('common.stop') : '▶ ' + t('seq.previewLoop') }}
      </button>
      <button class="tb add" :title="t('seq.addTip')" @click="addAsClip">＋ {{ t('seq.addAsClip') }}</button>
    </div>
    <div class="seq-grid">
      <div v-for="lane in LANES" :key="lane.midi" class="seq-row">
        <div class="seq-icon" :style="{ color: lane.color }"
             v-html="DRUM_SVG[lane.label] ?? DRUM_SVG['Toms']" />
        <div class="seq-cells">
          <div v-for="s in stepCount" :key="s" class="seq-cell"
               :class="{ beat: (s - 1) % 4 === 0, playhead: currentStep === s - 1 }"
               :style="{ background: hitAt(lane.midi, s - 1)
                 ? lane.color : lane.color + '22' }"
               @pointerdown.prevent="tapStep(lane.midi, s - 1)">
            <div v-if="tool === 'velocity' && hitAt(lane.midi, s - 1)" class="vel-dot"
                 :style="{ opacity: (hitAt(lane.midi, s - 1)?.vel ?? 90) / 127 }" />
          </div>
        </div>
      </div>
    </div>
    <div v-if="msg" class="dim seq-msg">{{ msg }}</div>
  </div>
</template>

<style scoped>
.seq { flex: 1; display: flex; flex-direction: column; min-height: 0; padding: 0 12px 10px; }
.seq-grid { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 3px; }
.seq-row { display: flex; align-items: center; gap: 6px; flex: 1; min-height: 20px; }
.seq-icon { width: 24px; flex: none; display: flex; }
.seq-icon :deep(svg) { width: 20px; height: 20px; }
.seq-cells { display: flex; gap: 3px; flex: 1; height: 100%; }
.seq-cell { flex: 1; border-radius: 4px; cursor: pointer; position: relative; transition: filter 0.05s; }
.seq-cell.beat { margin-left: 5px; }
.seq-cell:hover { filter: brightness(1.5); }
.seq-cell.playhead { outline: 2px solid #fff; outline-offset: -1px; }
.vel-dot { position: absolute; inset: 25%; border-radius: 50%; background: #fff; }
.seq-bar { display: flex; align-items: center; gap: 8px; padding: 4px 0 8px; flex: none; flex-wrap: wrap; }
.spacer { flex: 1; }
.pattern-pick { font-size: 12px; background: rgba(0,0,0,0.5); }
.power { font-size: 13px; font-weight: 600; padding: 4px 14px; border-radius: 16px; color: var(--text); border-color: #3ecf6e; }
.power.on { color: #3ecf6e; box-shadow: 0 0 12px rgba(62,207,110,0.4); }
.tools { display: flex; gap: 2px; background: rgba(0,0,0,0.45); border-radius: 6px; padding: 2px; }
.tools button { border: none; background: transparent; color: var(--text-dim); font-size: 11px; padding: 2px 10px; }
.tools button.on { background: var(--bg-elevated); color: var(--text); border-radius: 4px; }
.tb { font-size: 11px; padding: 2px 10px; }
.tb.add { border-color: var(--accent); color: var(--accent); }
.seq-msg { font-size: 11px; padding-top: 4px; }
</style>
