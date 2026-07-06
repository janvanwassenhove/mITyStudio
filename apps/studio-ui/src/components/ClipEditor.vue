<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Clip, NoteEvent, Track } from '../api/types'
import { useStudioStore } from '../stores/studio'

const studio = useStudioStore()

const found = computed<{ track: Track; clip: Clip } | null>(() => {
  const sel = studio.selectedClip
  const p = studio.project
  if (!sel || !p) return null
  const track = p.tracks.find((t) => t.id === sel.trackId)
  const clip = track?.clips.find((c) => c.id === sel.clipId)
  return track && clip ? { track, clip } : null
})

const isDrums = computed(() => found.value?.track.track_type === 'drums')
const isSample = computed(() => found.value?.clip.clip_type === 'sample')

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

// ---------------- piano roll ----------------
const PX_PER_BEAT = 28
const ROW_H = 12
const SNAP = 0.25
const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
const pitchName = (m: number) => `${NOTE_NAMES[m % 12]}${Math.floor(m / 12) - 1}`

const pitchRange = computed<[number, number]>(() => {
  const notes = found.value?.clip.note_events ?? []
  if (!notes.length) return [48, 72]
  let lo = 127, hi = 0
  for (const n of notes) { lo = Math.min(lo, n.midi_note); hi = Math.max(hi, n.midi_note) }
  return [Math.max(0, lo - 5), Math.min(127, hi + 5)]
})
const rows = computed(() => {
  const [lo, hi] = pitchRange.value
  const out = []
  for (let m = hi; m >= lo; m--) out.push(m)
  return out
})
const gridWidth = computed(() => (found.value?.clip.duration_beats ?? 4) * PX_PER_BEAT)
const gridHeight = computed(() => rows.value.length * ROW_H)

function noteY(midi: number) { return (pitchRange.value[1] - midi) * ROW_H }
function rowMidi(y: number) { return pitchRange.value[1] - Math.floor(y / ROW_H) }

function gridAddNote(e: MouseEvent) {
  const c = found.value?.clip
  if (!c) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const beat = Math.floor(((e.clientX - rect.left) / PX_PER_BEAT) / SNAP) * SNAP
  const midi = rowMidi(e.clientY - rect.top)
  if (midi < 0 || midi > 127 || beat >= c.duration_beats) return
  const note: NoteEvent = {
    id: uid(), pitch: pitchName(midi), midi_note: midi,
    start_beat: beat, duration_beats: 0.5, velocity: 96, lyric_syllable: '',
  }
  c.note_events.push(note)
  selectedNoteId.value = note.id
  save()
}

// note drag: move (body) or resize (right edge)
interface NoteDrag { note: NoteEvent; mode: 'move' | 'resize'; startX: number; startY: number; b0: number; m0: number; d0: number }
let noteDrag: NoteDrag | null = null

function notePointerDown(e: PointerEvent, note: NoteEvent) {
  e.stopPropagation()
  selectedNoteId.value = note.id
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const mode = e.clientX > rect.right - 6 ? 'resize' : 'move'
  noteDrag = { note, mode, startX: e.clientX, startY: e.clientY,
               b0: note.start_beat, m0: note.midi_note, d0: note.duration_beats }
  window.addEventListener('pointermove', noteDragMove)
  window.addEventListener('pointerup', noteDragEnd, { once: true })
}
function noteDragMove(e: PointerEvent) {
  const d = noteDrag
  const c = found.value?.clip
  if (!d || !c) return
  const dBeats = Math.round(((e.clientX - d.startX) / PX_PER_BEAT) / SNAP) * SNAP
  if (d.mode === 'move') {
    d.note.start_beat = Math.max(0, Math.min(c.duration_beats - 0.1, d.b0 + dBeats))
    const dRows = Math.round((e.clientY - d.startY) / ROW_H)
    d.note.midi_note = Math.max(0, Math.min(127, d.m0 - dRows))
    d.note.pitch = pitchName(d.note.midi_note)
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
  { midi: 49, label: 'Crash' }, { midi: 51, label: 'Ride' },
  { midi: 46, label: 'Open Hat' }, { midi: 42, label: 'Closed Hat' },
  { midi: 50, label: 'Hi Tom' }, { midi: 47, label: 'Mid Tom' },
  { midi: 45, label: 'Lo Tom' }, { midi: 38, label: 'Snare' },
  { midi: 37, label: 'Rimshot' }, { midi: 36, label: 'Kick' },
]
const STEP = 0.25
const stepCount = computed(() => Math.ceil((found.value?.clip.duration_beats ?? 4) / STEP))

function drumCellNote(midi: number, step: number): NoteEvent | undefined {
  const c = found.value?.clip
  return c?.note_events.find((n) =>
    n.midi_note === midi && Math.abs(n.start_beat - step * STEP) < STEP / 2)
}
function toggleDrumCell(midi: number, step: number) {
  const c = found.value?.clip
  if (!c) return
  const existing = drumCellNote(midi, step)
  if (existing) {
    c.note_events = c.note_events.filter((n) => n.id !== existing.id)
  } else {
    c.note_events.push({
      id: uid(), pitch: pitchName(midi), midi_note: midi,
      start_beat: step * STEP, duration_beats: 0.2,
      velocity: step % 4 === 0 ? 110 : 90, lyric_syllable: '',
    })
  }
  save()
}
</script>

<template>
  <div v-if="!found" class="dim empty">
    Double-click a clip in the timeline to edit it here.
  </div>
  <div v-else class="editor">
    <div class="ed-toolbar">
      <strong>{{ found.track.name }}</strong>
      <span class="dim small">{{ found.clip.duration_beats }} beats · {{ isSample ? 'audio clip' : isDrums ? 'drum grid' : 'piano roll' }}</span>
      <span class="spacer" />
      <template v-if="!isSample">
        <template v-if="selectedNote">
          <span class="dim small">velocity</span>
          <input type="range" min="1" max="127" style="width: 90px"
                 :value="selectedNote.velocity"
                 @input="selectedNote!.velocity = Number(($event.target as HTMLInputElement).value); save()" />
          <button class="tb danger" @click="deleteSelectedNote">✕ note</button>
        </template>
        <span v-else class="dim small">{{ isDrums ? 'click cells to toggle hits' : 'click = add note · drag = move · drag right edge = length' }}</span>
      </template>
      <span v-if="saving" class="dim small">saving…</span>
    </div>

    <!-- audio clip properties -->
    <div v-if="isSample" class="sample-props">
      <label>Gain (dB) <input type="number" step="0.5" v-model.number="found.clip.gain_db" @change="save" /></label>
      <label><input type="checkbox" v-model="found.clip.loop" @change="save" /> loop</label>
      <label>Fade in (s) <input type="number" step="0.05" min="0" v-model.number="found.clip.fade_in_seconds" @change="save" /></label>
      <label>Fade out (s) <input type="number" step="0.05" min="0" v-model.number="found.clip.fade_out_seconds" @change="save" /></label>
      <label>Start offset (s) <input type="number" step="0.1" min="0" v-model.number="found.clip.source_offset_seconds" @change="save" /></label>
    </div>

    <!-- drum grid -->
    <div v-else-if="isDrums" class="grid-scroll">
      <div class="drum-grid">
        <div v-for="lane in DRUM_LANES" :key="lane.midi" class="drum-row">
          <div class="drum-label">{{ lane.label }}</div>
          <div class="drum-cells">
            <div
              v-for="s in stepCount" :key="s" class="cell"
              :class="{ on: !!drumCellNote(lane.midi, s - 1), beat: (s - 1) % 4 === 0, bar: (s - 1) % 16 === 0 }"
              @click="toggleDrumCell(lane.midi, s - 1)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- piano roll -->
    <div v-else class="grid-scroll">
      <div class="proll" :style="{ width: gridWidth + 80 + 'px' }">
        <div class="proll-keys">
          <div v-for="m in rows" :key="m" class="key" :class="{ black: [1,3,6,8,10].includes(m % 12) }"
               :style="{ height: ROW_H + 'px' }">{{ m % 12 === 0 ? pitchName(m) : '' }}</div>
        </div>
        <div class="proll-grid" :style="{ width: gridWidth + 'px', height: gridHeight + 'px' }" @click="gridAddNote">
          <!-- beat lines -->
          <div v-for="b in Math.ceil(found.clip.duration_beats)" :key="'b' + b" class="beat-line"
               :style="{ left: (b - 1) * PX_PER_BEAT + 'px' }" />
          <!-- row stripes for black keys -->
          <div v-for="(m, i) in rows" :key="'r' + m" v-show="[1,3,6,8,10].includes(m % 12)"
               class="row-stripe" :style="{ top: i * ROW_H + 'px', height: ROW_H + 'px' }" />
          <!-- notes -->
          <div
            v-for="n in found.clip.note_events" :key="n.id" class="pnote"
            :class="{ sel: n.id === selectedNoteId }"
            :style="{ left: n.start_beat * PX_PER_BEAT + 'px', top: noteY(n.midi_note) + 1 + 'px',
                      width: Math.max(n.duration_beats * PX_PER_BEAT - 1, 4) + 'px', height: ROW_H - 2 + 'px',
                      opacity: 0.5 + (n.velocity / 254) }"
            :title="`${n.pitch} vel ${n.velocity}`"
            @pointerdown="notePointerDown($event, n)"
            @click.stop
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.editor { display: flex; flex-direction: column; height: 100%; }
.ed-toolbar { display: flex; align-items: center; gap: 10px; padding: 6px 10px; border-bottom: 1px solid var(--border); flex: none; }
.spacer { flex: 1; }
.small { font-size: 11px; }
.tb { padding: 2px 8px; font-size: 11px; }
.tb.danger { border-color: var(--err); color: var(--err); }
.grid-scroll { flex: 1; overflow: auto; }
.sample-props { display: flex; gap: 18px; padding: 16px; flex-wrap: wrap; align-items: center; }
.sample-props label { display: flex; gap: 6px; align-items: center; font-size: 12px; color: var(--text-dim); }
.sample-props input[type=number] { width: 80px; }
/* drums */
.drum-grid { padding: 6px 0; }
.drum-row { display: flex; align-items: center; }
.drum-label { width: 80px; flex: none; font-size: 11px; color: var(--text-dim); padding-left: 10px; position: sticky; left: 0; background: var(--bg-panel); z-index: 2; }
.drum-cells { display: flex; }
.cell { width: 16px; height: 15px; border: 1px solid var(--border); border-left-width: 0; cursor: pointer; flex: none; }
.cell.beat { border-left: 1px solid var(--text-dim); }
.cell.bar { border-left: 2px solid var(--text); }
.cell:hover { background: var(--bg-elevated); }
.cell.on { background: var(--accent); }
/* piano roll */
.proll { display: flex; }
.proll-keys { flex: none; width: 44px; position: sticky; left: 0; background: var(--bg-panel); z-index: 2; }
.key { font-size: 8px; color: var(--text-dim); border-bottom: 1px solid var(--border); padding-left: 4px; }
.key.black { background: rgba(0,0,0,0.3); }
.proll-grid { position: relative; background: rgba(0,0,0,0.15); cursor: crosshair; }
.beat-line { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--border); pointer-events: none; }
.row-stripe { position: absolute; left: 0; right: 0; background: rgba(0,0,0,0.18); pointer-events: none; }
.pnote { position: absolute; background: var(--accent); border-radius: 2px; cursor: grab; }
.pnote.sel { outline: 2px solid #fff; }
.pnote:hover { filter: brightness(1.2); }
</style>
