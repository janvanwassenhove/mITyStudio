<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { Pencil, Piano } from 'lucide-vue-next'
import type { Clip, NoteEvent, Track } from '../api/types'
import { TRACK_COLORS } from '../lib/trackColors'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import InstrumentPlayView from './InstrumentPlayView.vue'
import TrackIcon from './TrackIcon.vue'

const studio = useStudioStore()
const playback = usePlaybackStore()

const found = computed<{ track: Track; clip: Clip } | null>(() => {
  const sel = studio.selectedClip
  const p = studio.project
  if (!sel || !p) return null
  const track = p.tracks.find((t) => t.id === sel.trackId)
  const clip = track?.clips.find((c) => c.id === sel.clipId)
  return track && clip ? { track, clip } : null
})

const trackColor = computed(() =>
  TRACK_COLORS[found.value?.track.track_type ?? ''] ?? TRACK_COLORS.keys)

const isDrums = computed(() => found.value?.track.track_type === 'drums')
const isSample = computed(() => found.value?.clip.clip_type === 'sample')
const viewMode = ref<'edit' | 'play'>('edit')

// a fresh empty clip opens on its PLAY surface (Smart Drums / chord strips /
// keyboard) — the natural place to start making sound, not an empty grid
watch(() => found.value?.clip.id, () => {
  const f = found.value
  if (f && f.clip.clip_type === 'midi' && !f.clip.note_events.length) {
    viewMode.value = 'play'
  }
}, { immediate: true })

// no clip selected: offer to create one on the selected track right here
const selectedTrack = computed(() =>
  studio.project?.tracks.find((t) => t.id === studio.selectedTrackId) ?? null)
const canCreateHere = computed(() =>
  !found.value && selectedTrack.value != null
  && selectedTrack.value.track_type !== 'sample')

async function createClipHere() {
  const track = selectedTrack.value
  const m = studio.manifest
  if (!track || !m) return
  const bpb = m.beats_per_bar
  const beat = Math.max(0, Math.floor(((playback.playhead * m.bpm) / 60) / bpb) * bpb)
  const clip: Clip = {
    id: uid(), section_id: '', clip_type: 'midi',
    start_beat: beat, duration_beats: bpb * 4, note_events: [],
    source_asset_id: null, gain_db: 0, loop: false,
    fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
  }
  track.clips.push(clip)
  studio.selectedClip = { trackId: track.id, clipId: clip.id }
  save()
}

const saving = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null
function save() {
  if (timer) clearTimeout(timer)
  timer = setTimeout(async () => {
    saving.value = true
    try { await studio.saveProject() } finally { saving.value = false }
  }, 500)
}

const uid = () => crypto.randomUUID().replace(/-/g, '')
const selectedNoteId = ref<string | null>(null)
const selectedNote = computed(() =>
  found.value?.clip.note_events.find((n) => n.id === selectedNoteId.value) ?? null)

// --- note preview beep (GarageBand-style audible feedback) ---
let previewCtx: AudioContext | null = null
function beep(midi: number, drum = false) {
  try {
    if (!previewCtx) previewCtx = new AudioContext()
    const ctx = previewCtx
    const t = ctx.currentTime
    const g = ctx.createGain()
    g.connect(ctx.destination)
    if (drum) {
      const osc = ctx.createOscillator()
      osc.frequency.setValueAtTime(midi === 36 ? 150 : midi === 38 ? 220 : 800, t)
      osc.frequency.exponentialRampToValueAtTime(midi === 36 ? 50 : 120, t + 0.08)
      g.gain.setValueAtTime(0.3, t)
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.1)
      osc.connect(g); osc.start(t); osc.stop(t + 0.12)
    } else {
      const osc = ctx.createOscillator()
      osc.type = 'triangle'
      osc.frequency.value = 440 * 2 ** ((midi - 69) / 12)
      g.gain.setValueAtTime(0.22, t)
      g.gain.exponentialRampToValueAtTime(0.001, t + 0.25)
      osc.connect(g); osc.start(t); osc.stop(t + 0.28)
    }
  } catch { /* no audio available */ }
}

// ---------------- piano roll ----------------
const pxPerBeatEd = ref(28)
const ROW_H = 14
const SNAP = 0.25
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const isBlack = (m: number) => [1, 3, 6, 8, 10].includes(m % 12)
const pitchName = (m: number) => `${NOTE_NAMES[m % 12]}${Math.floor(m / 12) - 1}`

const pitchRange = computed<[number, number]>(() => {
  const notes = found.value?.clip.note_events ?? []
  if (!notes.length) return [48, 72]
  let lo = 127, hi = 0
  for (const n of notes) { lo = Math.min(lo, n.midi_note); hi = Math.max(hi, n.midi_note) }
  return [Math.max(0, lo - 6), Math.min(127, hi + 6)]
})
const rows = computed(() => {
  const [lo, hi] = pitchRange.value
  const out = []
  for (let m = hi; m >= lo; m--) out.push(m)
  return out
})
const gridWidth = computed(() => (found.value?.clip.duration_beats ?? 4) * pxPerBeatEd.value)
const gridHeight = computed(() => rows.value.length * ROW_H)
const beatsPerBar = computed(() => studio.manifest?.beats_per_bar ?? 4)

function noteY(midi: number) { return (pitchRange.value[1] - midi) * ROW_H }
function rowMidi(y: number) { return pitchRange.value[1] - Math.floor(y / ROW_H) }

function gridAddNote(e: MouseEvent) {
  const c = found.value?.clip
  if (!c) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const beat = Math.floor(((e.clientX - rect.left) / pxPerBeatEd.value) / SNAP) * SNAP
  const midi = rowMidi(e.clientY - rect.top)
  if (midi < 0 || midi > 127 || beat >= c.duration_beats) return
  const note: NoteEvent = {
    id: uid(), pitch: pitchName(midi), midi_note: midi,
    start_beat: beat, duration_beats: 0.5, velocity: 96, lyric_syllable: '',
  }
  c.note_events.push(note)
  selectedNoteId.value = note.id
  beep(midi)
  save()
}

interface NoteDrag { note: NoteEvent; mode: 'move' | 'resize'; startX: number; startY: number; b0: number; m0: number; d0: number; lastMidi: number }
let noteDrag: NoteDrag | null = null

function notePointerDown(e: PointerEvent, note: NoteEvent) {
  e.stopPropagation()
  selectedNoteId.value = note.id
  beep(note.midi_note)
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const mode = e.clientX > rect.right - 7 ? 'resize' : 'move'
  noteDrag = { note, mode, startX: e.clientX, startY: e.clientY,
               b0: note.start_beat, m0: note.midi_note, d0: note.duration_beats,
               lastMidi: note.midi_note }
  window.addEventListener('pointermove', noteDragMove)
  window.addEventListener('pointerup', noteDragEnd, { once: true })
}
function noteDragMove(e: PointerEvent) {
  const d = noteDrag
  const c = found.value?.clip
  if (!d || !c) return
  const dBeats = Math.round(((e.clientX - d.startX) / pxPerBeatEd.value) / SNAP) * SNAP
  if (d.mode === 'move') {
    d.note.start_beat = Math.max(0, Math.min(c.duration_beats - 0.1, d.b0 + dBeats))
    const dRows = Math.round((e.clientY - d.startY) / ROW_H)
    d.note.midi_note = Math.max(0, Math.min(127, d.m0 - dRows))
    d.note.pitch = pitchName(d.note.midi_note)
    if (d.note.midi_note !== d.lastMidi) {
      beep(d.note.midi_note)
      d.lastMidi = d.note.midi_note
    }
  } else {
    d.note.duration_beats = Math.max(SNAP, d.d0 + dBeats)
  }
}
function noteDragEnd() {
  window.removeEventListener('pointermove', noteDragMove)
  if (noteDrag) save()
  noteDrag = null
}

function deleteSelectedNote() {
  const c = found.value?.clip
  if (!c || !selectedNoteId.value) return
  c.note_events = c.note_events.filter((n) => n.id !== selectedNoteId.value)
  selectedNoteId.value = null
  save()
}

// ---------------- drum grid ----------------
const DRUM_LANES = [
  { midi: 49, label: 'Crash', icon: '💥' }, { midi: 51, label: 'Ride', icon: '🛎' },
  { midi: 46, label: 'Open Hat', icon: '🎩' }, { midi: 42, label: 'Hi-Hat', icon: '🎩' },
  { midi: 50, label: 'Hi Tom', icon: '🥁' }, { midi: 47, label: 'Mid Tom', icon: '🥁' },
  { midi: 45, label: 'Lo Tom', icon: '🥁' }, { midi: 38, label: 'Snare', icon: '🥁' },
  { midi: 37, label: 'Rimshot', icon: '🪘' }, { midi: 36, label: 'Kick', icon: '🦶' },
]
const STEP = 0.25
const CELL_W = 18
const stepCount = computed(() => Math.ceil((found.value?.clip.duration_beats ?? 4) / STEP))

function drumCellNote(midi: number, step: number): NoteEvent | undefined {
  const c = found.value?.clip
  return c?.note_events.find((n) =>
    n.midi_note === midi && Math.abs(n.start_beat - step * STEP) < STEP / 2)
}
function toggleDrumCell(midi: number, step: number, e: MouseEvent) {
  const c = found.value?.clip
  if (!c) return
  const existing = drumCellNote(midi, step)
  if (existing && !e.shiftKey) {
    c.note_events = c.note_events.filter((n) => n.id !== existing.id)
  } else if (existing && e.shiftKey) {
    existing.velocity = existing.velocity >= 110 ? 70 : 120  // accent toggle
  } else {
    c.note_events.push({
      id: uid(), pitch: pitchName(midi), midi_note: midi,
      start_beat: step * STEP, duration_beats: 0.2,
      velocity: step % 4 === 0 ? 110 : 90, lyric_syllable: '',
    })
    beep(midi, true)
  }
  save()
}

// ---------------- editor playhead (direct DOM, zero re-renders) -----------
const edPlayheadEl = ref<HTMLElement | null>(null)
const drumPlayheadEl = ref<HTMLElement | null>(null)

const stopPh = watch(() => playback.playhead, (seconds) => {
  const f = found.value
  const m = studio.manifest
  if (!f || !m) return
  const beat = (seconds * m.bpm) / 60 - f.clip.start_beat
  const visible = beat >= 0 && beat <= f.clip.duration_beats
  const pr = edPlayheadEl.value
  if (pr) {
    pr.style.display = visible ? 'block' : 'none'
    if (visible) pr.style.transform = `translateX(${beat * pxPerBeatEd.value}px)`
  }
  const dr = drumPlayheadEl.value
  if (dr) {
    dr.style.display = visible ? 'block' : 'none'
    if (visible) dr.style.transform = `translateX(${(beat / STEP) * CELL_W}px)`
  }
}, { flush: 'sync' })
onBeforeUnmount(stopPh)
</script>

<template>
  <div v-if="!found" class="dim empty">
    <template v-if="canCreateHere">
      <button class="primary" @click="createClipHere">
        ＋ {{ $t('clipEditor.createHere', { name: selectedTrack!.name }) }}
      </button>
    </template>
    <template v-else>{{ $t('clipEditor.empty') }}</template>
  </div>
  <div v-else class="editor">
    <div class="ed-toolbar" :style="{ borderLeft: `3px solid ${trackColor}` }">
      <TrackIcon class="ed-icon" :type="found.track.track_type" :size="16" colored />
      <strong>{{ found.track.name }}</strong>
      <span class="dim small">{{ isSample ? $t('clipEditor.audioClip') : isDrums ? $t('clipEditor.beatGrid') : $t('clipEditor.pianoRoll') }} · {{ $t('clipEditor.beats', { n: found.clip.duration_beats }) }}</span>
      <div v-if="!isSample" class="view-toggle">
        <button :class="{ on: viewMode === 'edit' }" @click="viewMode = 'edit'"><Pencil class="icon" :size="12" /> {{ $t('clipEditor.edit') }}</button>
        <button :class="{ on: viewMode === 'play' }" @click="viewMode = 'play'"><Piano class="icon" :size="12" /> {{ $t('clipEditor.play') }}</button>
      </div>
      <span class="spacer" />
      <template v-if="!isSample">
        <template v-if="!isDrums">
          <span class="dim small">{{ $t('timeline.zoom') }}</span>
          <input type="range" min="14" max="64" v-model.number="pxPerBeatEd" style="width: 80px" />
        </template>
        <template v-if="selectedNote">
          <span class="dim small">{{ selectedNote.pitch }} · {{ $t('clipEditor.velocity') }}</span>
          <input type="range" min="1" max="127" style="width: 90px"
                 :value="selectedNote.velocity"
                 @input="selectedNote!.velocity = Number(($event.target as HTMLInputElement).value); save()" />
          <button class="tb danger" @click="deleteSelectedNote">✕</button>
        </template>
        <span v-else class="dim small">{{ isDrums ? $t('clipEditor.drumHint') : $t('clipEditor.rollHint') }}</span>
      </template>
      <template v-if="!isSample">
        <label class="fade-inline">{{ $t('clipEditor.fadeIn') }}
          <input type="number" step="0.1" min="0" :value="found.clip.fade_in_seconds"
                 @change="found!.clip.fade_in_seconds = Number(($event.target as HTMLInputElement).value); save()" />
        </label>
        <label class="fade-inline">{{ $t('clipEditor.fadeOut') }}
          <input type="number" step="0.1" min="0" :value="found.clip.fade_out_seconds"
                 @change="found!.clip.fade_out_seconds = Number(($event.target as HTMLInputElement).value); save()" />
        </label>
      </template>
      <span v-if="saving" class="dim small">{{ $t('common.saving') }}</span>
    </div>

    <!-- audio clip properties -->
    <div v-if="isSample" class="sample-props">
      <label>{{ $t('clipEditor.gain') }} <input type="number" step="0.5" v-model.number="found.clip.gain_db" @change="save" /></label>
      <label><input type="checkbox" v-model="found.clip.loop" @change="save" /> {{ $t('clipEditor.loop') }}</label>
      <label>{{ $t('clipEditor.fadeIn') }} <input type="number" step="0.05" min="0" v-model.number="found.clip.fade_in_seconds" @change="save" /></label>
      <label>{{ $t('clipEditor.fadeOut') }} <input type="number" step="0.05" min="0" v-model.number="found.clip.fade_out_seconds" @change="save" /></label>
      <label>{{ $t('clipEditor.startOffset') }} <input type="number" step="0.1" min="0" v-model.number="found.clip.source_offset_seconds" @change="save" /></label>
    </div>

    <!-- playable instrument surface (GarageBand-style) -->
    <InstrumentPlayView v-else-if="viewMode === 'play'"
                        :track="found.track" :clip="found.clip"
                        @changed="save" />

    <!-- drum beat grid -->
    <div v-else-if="isDrums" class="grid-scroll">
      <div class="drum-grid" :style="{ '--cell': CELL_W + 'px' }">
        <div class="drum-row header-row">
          <div class="drum-label" />
          <div class="drum-cells beat-header">
            <div v-for="s in stepCount" :key="s" class="beat-num"
                 :class="{ bar: (s - 1) % (beatsPerBar * 4) === 0 }">
              {{ (s - 1) % 4 === 0 ? Math.floor((s - 1) / 4) + 1 : '' }}
            </div>
            <div ref="drumPlayheadEl" class="ed-playhead" />
          </div>
        </div>
        <div v-for="lane in DRUM_LANES" :key="lane.midi" class="drum-row">
          <div class="drum-label"><span class="lane-icon">{{ lane.icon }}</span> {{ lane.label }}</div>
          <div class="drum-cells">
            <div
              v-for="s in stepCount" :key="s" class="cell"
              :class="{ beat: (s - 1) % 4 === 0, bar: (s - 1) % (beatsPerBar * 4) === 0,
                        group: Math.floor((s - 1) / 4) % 2 === 1 }"
              @click="toggleDrumCell(lane.midi, s - 1, $event)"
            >
              <div v-if="drumCellNote(lane.midi, s - 1)" class="pad"
                   :style="{ background: trackColor,
                             opacity: 0.45 + ((drumCellNote(lane.midi, s - 1)?.velocity ?? 90) / 127) * 0.55 }" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- piano roll -->
    <div v-else class="grid-scroll">
      <div class="proll" :style="{ width: gridWidth + 56 + 'px' }">
        <div class="proll-keys">
          <div v-for="m in rows" :key="m" class="key" :class="{ black: isBlack(m), c: m % 12 === 0 }"
               :style="{ height: ROW_H + 'px' }" @click="beep(m)">
            <span v-if="m % 12 === 0">{{ pitchName(m) }}</span>
          </div>
        </div>
        <div class="proll-grid" :style="{ width: gridWidth + 'px', height: gridHeight + 'px' }" @click="gridAddNote">
          <div v-for="(m, i) in rows" :key="'r' + m" v-show="isBlack(m)"
               class="row-stripe" :style="{ top: i * ROW_H + 'px', height: ROW_H + 'px' }" />
          <template v-for="b in Math.ceil(found.clip.duration_beats)" :key="'b' + b">
            <div class="beat-line" :class="{ bar: (b - 1) % beatsPerBar === 0 }"
                 :style="{ left: (b - 1) * pxPerBeatEd + 'px' }" />
          </template>
          <div
            v-for="n in found.clip.note_events" :key="n.id" class="pnote"
            :class="{ sel: n.id === selectedNoteId }"
            :style="{ left: n.start_beat * pxPerBeatEd + 'px', top: noteY(n.midi_note) + 1 + 'px',
                      width: Math.max(n.duration_beats * pxPerBeatEd - 1, 5) + 'px', height: ROW_H - 2 + 'px',
                      background: trackColor, opacity: 0.55 + (n.velocity / 280) }"
            :title="`${n.pitch} · vel ${n.velocity}${n.lyric_syllable ? ' · “' + n.lyric_syllable + '”' : ''}`"
            @pointerdown="notePointerDown($event, n)"
            @click.stop
          ><span class="resize-grip" /></div>
          <div ref="edPlayheadEl" class="ed-playhead" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.editor { display: flex; flex-direction: column; height: 100%; }
.ed-toolbar { display: flex; align-items: center; gap: 10px; padding: 6px 12px; border-bottom: 1px solid var(--border); flex: none; }
.ed-icon { font-size: 16px; }
.spacer { flex: 1; }
.small { font-size: 11px; }
.tb { padding: 2px 8px; font-size: 11px; }
.tb.danger { border-color: var(--err); color: var(--err); }
.fade-inline { display: flex; gap: 4px; align-items: center; font-size: 11px; color: var(--text-dim); }
.fade-inline input { width: 52px; padding: 1px 4px; font-size: 11px; }
.view-toggle { display: flex; gap: 2px; background: var(--bg); border-radius: 6px; padding: 2px; }
.view-toggle button { border: none; background: transparent; padding: 2px 10px; font-size: 11px; color: var(--text-dim); }
.view-toggle button.on { background: var(--bg-elevated); color: var(--text); border-radius: 4px; }
.grid-scroll { flex: 1; overflow: auto; position: relative; }
.sample-props { display: flex; gap: 18px; padding: 16px; flex-wrap: wrap; align-items: center; }
.sample-props label { display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--text-dim); }
.sample-props input[type=number] { width: 80px; }
/* drums */
.drum-grid { padding: 4px 0 10px; }
.drum-row { display: flex; align-items: center; }
.header-row { position: sticky; top: 0; background: var(--bg-panel); z-index: 3; }
.drum-label { width: 92px; flex: none; font-size: 11px; color: var(--text-dim); padding-left: 10px; position: sticky; left: 0; background: var(--bg-panel); z-index: 2; display: flex; gap: 4px; align-items: center; height: 20px; }
.lane-icon { font-size: 11px; }
.drum-cells { display: flex; position: relative; }
.beat-header { height: 16px; }
.beat-num { width: var(--cell); flex: none; font-size: 9px; color: var(--text-dim); border-left: 1px solid transparent; }
.beat-num.bar { color: var(--text); }
.cell { width: var(--cell); height: 19px; border: 1px solid var(--border); border-left-width: 0; cursor: pointer; flex: none; padding: 2px; }
.cell.group { background: rgba(255,255,255,0.025); }
.cell.beat { border-left: 1px solid var(--text-dim); }
.cell.bar { border-left: 2px solid var(--text); }
.cell:hover { background: var(--bg-elevated); }
.pad { width: 100%; height: 100%; border-radius: 3px; }
/* piano roll */
.proll { display: flex; }
.proll-keys { flex: none; width: 48px; position: sticky; left: 0; background: var(--bg-panel); z-index: 2; border-right: 1px solid var(--border); }
.key { font-size: 9px; color: #666; box-sizing: border-box; border-bottom: 1px solid rgba(0,0,0,0.25); background: #e8e8e8; padding-left: 4px; display: flex; align-items: center; cursor: pointer; }
.key.black { background: #2a2d34; color: var(--text-dim); width: 65%; border-radius: 0 3px 3px 0; }
.key.c { font-weight: 700; color: #333; }
.key:hover { filter: brightness(1.15); }
.proll-grid { position: relative; background: rgba(0,0,0,0.15); cursor: crosshair; }
.beat-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border); pointer-events: none; }
.beat-line.bar { width: 2px; background: var(--text-dim); opacity: 0.5; }
.row-stripe { position: absolute; left: 0; right: 0; background: rgba(0,0,0,0.22); pointer-events: none; }
.pnote { position: absolute; border-radius: 3px; cursor: grab; box-shadow: 0 1px 2px rgba(0,0,0,0.5); }
.pnote.sel { outline: 2px solid #fff; z-index: 2; }
.pnote:hover { filter: brightness(1.25); }
.resize-grip { position: absolute; right: 0; top: 0; bottom: 0; width: 7px; cursor: ew-resize; border-right: 2px solid rgba(255,255,255,0.45); border-radius: 0 3px 3px 0; }
.ed-playhead { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--err); pointer-events: none; display: none; will-change: transform; z-index: 3; }
</style>
