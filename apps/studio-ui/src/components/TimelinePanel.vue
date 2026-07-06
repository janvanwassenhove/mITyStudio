<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import AddTrackDialog from './AddTrackDialog.vue'
import type { Clip, Track } from '../api/types'

const studio = useStudioStore()
const playback = usePlaybackStore()

const pxPerBeat = ref(14)
const TRACK_H = 56
const LABEL_W = 150

const manifest = computed(() => studio.manifest)

const totalBeats = computed(() => {
  const m = manifest.value
  if (!m) return 0
  return Math.max(m.total_bars * m.beats_per_bar, m.beats_per_bar * 8)
})
const contentWidth = computed(() => totalBeats.value * pxPerBeat.value)

const bars = computed(() => {
  const m = manifest.value
  if (!m) return []
  const out: { bar: number; x: number }[] = []
  const count = Math.ceil(totalBeats.value / m.beats_per_bar)
  for (let i = 0; i <= count; i++) out.push({ bar: i + 1, x: i * m.beats_per_bar * pxPerBeat.value })
  return out
})

const TRACK_COLORS: Record<string, string> = {
  drums: '#e6a23c', bass: '#f2555a', guitar: '#f78fb3', keys: '#4f9cf9',
  synth: '#9d6ff2', strings: '#3ecf8e', brass: '#e0c341', sample: '#41c9e0',
  lead_vocal: '#ff7eb6', backing_vocal: '#c792ea', fx: '#8d96a8',
}
const color = (t: string) => TRACK_COLORS[t] ?? '#8d96a8'

// ------- precomputed layout (rebuilt only when manifest/zoom change) -------
interface NoteRect { x: number; y: number; w: number; o: number }
interface ClipLayout {
  clipId: string; type: string; x: number; w: number
  notes: NoteRect[]; wavePath: string | null
}
interface TrackLayout { track: { track_id: string; name: string; track_type: string }; clips: ClipLayout[] }

function wavePathFor(peaks: number[], w: number, h: number): string {
  const mid = h / 2
  const n = peaks.length - 1 || 1
  let top = '', bottom = ''
  for (let i = 0; i < peaks.length; i++) {
    const x = ((i / n) * w).toFixed(1)
    top += ` L ${x} ${(mid - peaks[i] * mid * 0.9).toFixed(1)}`
    bottom = ` L ${x} ${(mid + peaks[i] * mid * 0.9).toFixed(1)}` + bottom
  }
  return `M 0 ${mid}${top}${bottom} Z`
}

const layout = computed<TrackLayout[]>(() => {
  const m = manifest.value
  if (!m) return []
  const ppb = pxPerBeat.value
  const noteH = TRACK_H - 6
  const notesByClip = new Map<string, typeof m.midi_note_metadata>()
  for (const n of m.midi_note_metadata) {
    const arr = notesByClip.get(n.clip_id)
    if (arr) arr.push(n)
    else notesByClip.set(n.clip_id, [n])
  }
  const waveByTrack = new Map(m.waveform_metadata.map((w) => [w.track_id, w.peaks]))
  return m.tracks.map((t) => {
    const clips: ClipLayout[] = m.clips
      .filter((c) => c.track_id === t.track_id)
      .map((c) => {
        const w = Math.max((c.end_beat - c.start_beat) * ppb, 4)
        const notes: NoteRect[] = []
        let wavePath: string | null = null
        const clipNotes = notesByClip.get(c.clip_id) ?? []
        if (clipNotes.length) {
          let lo = 127, hi = 0
          for (const n of clipNotes) { lo = Math.min(lo, n.midi_note); hi = Math.max(hi, n.midi_note) }
          lo = Math.max(0, lo - 1); hi = Math.min(127, hi + 1)
          const range = hi - lo || 1
          for (const n of clipNotes) {
            notes.push({
              x: (n.start_beat - c.start_beat) * ppb,
              y: noteH * (1 - (n.midi_note - lo) / range) - 2,
              w: Math.max((n.end_beat - n.start_beat) * ppb - 0.5, 1),
              o: 0.4 + (n.velocity / 127) * 0.6,
            })
          }
        } else if (c.clip_type === 'sample') {
          const peaks = waveByTrack.get(t.track_id)
          if (peaks) wavePath = wavePathFor(peaks, 200, noteH)
        }
        return { clipId: c.clip_id, type: c.clip_type, x: c.start_beat * ppb, w, notes, wavePath }
      })
    return { track: t, clips }
  })
})

// ------- playhead: zero Vue re-renders, direct DOM transform -------
const playheadEl = ref<HTMLElement | null>(null)
const scrollEl = ref<HTMLElement | null>(null)
let followScroll = true

const stopWatch = watch(
  () => playback.playhead,
  (seconds) => {
    const m = manifest.value
    const el = playheadEl.value
    if (!m || !el) return
    const x = LABEL_W + ((seconds * m.bpm) / 60) * pxPerBeat.value
    el.style.transform = `translateX(${x}px)`
    const sc = scrollEl.value
    if (sc && followScroll && playback.playing) {
      const view = sc.clientWidth
      if (x < sc.scrollLeft + LABEL_W || x > sc.scrollLeft + view - 80) {
        sc.scrollLeft = Math.max(0, x - LABEL_W - view * 0.25)
      }
    }
  },
  { flush: 'sync' },
)
watch([pxPerBeat, manifest], () => {
  // reposition after zoom/manifest changes
  const m = manifest.value
  const el = playheadEl.value
  if (m && el) {
    el.style.transform = `translateX(${LABEL_W + ((playback.playhead * m.bpm) / 60) * pxPerBeat.value}px)`
  }
})
onBeforeUnmount(stopWatch)

// ------- playhead scrubbing (drag anywhere on the ruler/sections lane) -----
let scrubbing = false
let scrubWasPlaying = false
let scrubLane: HTMLElement | null = null

function laneSeconds(e: PointerEvent): number {
  const m = manifest.value
  if (!m || !scrubLane) return 0
  const x = e.clientX - scrubLane.getBoundingClientRect().left
  return Math.max(0, ((x / pxPerBeat.value) * 60) / m.bpm)
}

function scrubStart(e: PointerEvent) {
  if (!manifest.value) return
  scrubbing = true
  scrubLane = e.currentTarget as HTMLElement
  scrubWasPlaying = playback.playing
  if (scrubWasPlaying) playback.pause()
  playback.playhead = laneSeconds(e)
  window.addEventListener('pointermove', scrubMove)
  window.addEventListener('pointerup', scrubEnd, { once: true })
}
function scrubMove(e: PointerEvent) {
  if (scrubbing) playback.playhead = laneSeconds(e)
}
function scrubEnd(e: PointerEvent) {
  scrubbing = false
  window.removeEventListener('pointermove', scrubMove)
  const t = laneSeconds(e)
  if (scrubWasPlaying) { playback.playhead = t; void playback.play() }
  else playback.seek(t)
  scrubLane = null
}

// ------- clip dragging (direct DOM transform while dragging) ---------------
interface ClipDrag {
  trackId: string; clipId: string; el: HTMLElement
  startX: number; deltaBeats: number; moved: boolean
}
let clipDrag: ClipDrag | null = null

function clipPointerDown(e: PointerEvent, trackId: string, clipId: string) {
  if (e.button !== 0) return
  studio.selectedTrackId = trackId
  selectedClip.value = { trackId, clipId }
  clipDrag = { trackId, clipId, el: e.currentTarget as HTMLElement,
               startX: e.clientX, deltaBeats: 0, moved: false }
  window.addEventListener('pointermove', clipDragMove)
  window.addEventListener('pointerup', clipDragEnd, { once: true })
}
function clipDragMove(e: PointerEvent) {
  if (!clipDrag) return
  const dx = e.clientX - clipDrag.startX
  if (Math.abs(dx) > 3) clipDrag.moved = true
  if (!clipDrag.moved) return
  const snap = 0.25
  clipDrag.deltaBeats = Math.round(dx / pxPerBeat.value / snap) * snap
  clipDrag.el.style.transform = `translateX(${clipDrag.deltaBeats * pxPerBeat.value}px)`
  clipDrag.el.style.zIndex = '3'
}
async function clipDragEnd() {
  window.removeEventListener('pointermove', clipDragMove)
  const d = clipDrag
  clipDrag = null
  if (!d) return
  d.el.style.transform = ''
  d.el.style.zIndex = ''
  if (!d.moved || d.deltaBeats === 0) return
  const p = studio.project
  const track = p?.tracks.find((t) => t.id === d.trackId)
  const clip = track?.clips.find((c) => c.id === d.clipId)
  if (!p || !clip) return
  clip.start_beat = Math.max(0, clip.start_beat + d.deltaBeats)
  clip.section_id = ''   // manual placement detaches from section regeneration
  await save()
}

// ------- editing: add track, select clip, split / duplicate / delete -------
const showAddTrack = ref(false)
const selectedClip = computed({
  get: () => studio.selectedClip,
  set: (v) => { studio.selectedClip = v },
})
const saving = ref(false)

const uid = () => crypto.randomUUID().replace(/-/g, '')

async function save() {
  saving.value = true
  try { await studio.saveProject() } finally { saving.value = false }
}

const hasTracks = computed(() => (manifest.value?.tracks.length ?? 0) > 0)

function findClip(): { track: Track; clip: Clip; index: number } | null {
  const p = studio.project
  if (!p || !selectedClip.value) return null
  const track = p.tracks.find((t) => t.id === selectedClip.value!.trackId)
  if (!track) return null
  const index = track.clips.findIndex((c) => c.id === selectedClip.value!.clipId)
  if (index < 0) return null
  return { track, clip: track.clips[index], index }
}

function playheadBeat(): number {
  const m = manifest.value
  return m ? (playback.playhead * m.bpm) / 60 : 0
}

async function splitClip() {
  const found = findClip()
  const m = manifest.value
  if (!found || !m) return
  const { track, clip, index } = found
  const at = playheadBeat()
  const rel = at - clip.start_beat
  if (rel <= 0.01 || rel >= clip.duration_beats - 0.01) return
  const second: Clip = JSON.parse(JSON.stringify(clip))
  second.id = uid()
  second.start_beat = clip.start_beat + rel
  second.duration_beats = clip.duration_beats - rel
  second.fade_in_seconds = 0
  clip.fade_out_seconds = 0
  if (clip.clip_type === 'sample') {
    second.source_offset_seconds = (clip.source_offset_seconds ?? 0) + (rel * 60) / m.bpm
    second.note_events = []
  } else {
    // notes before the cut stay in the first clip (truncated at the cut);
    // notes after move to the second with rebased start
    const first = []
    const moved = []
    for (const n of clip.note_events) {
      if (n.start_beat < rel) {
        n.duration_beats = Math.min(n.duration_beats, rel - n.start_beat)
        if (n.duration_beats > 0.01) first.push(n)
      } else {
        moved.push(n)
      }
    }
    clip.note_events = first
    second.note_events = moved.map((n) => ({ ...n, id: uid(), start_beat: n.start_beat - rel }))
  }
  clip.duration_beats = rel
  track.clips.splice(index + 1, 0, second)
  selectedClip.value = { trackId: track.id, clipId: second.id }
  await save()
}

async function duplicateClip() {
  const found = findClip()
  if (!found) return
  const { track, clip, index } = found
  const copy: Clip = JSON.parse(JSON.stringify(clip))
  copy.id = uid()
  copy.start_beat = clip.start_beat + clip.duration_beats
  copy.note_events = copy.note_events.map((n) => ({ ...n, id: uid() }))
  track.clips.splice(index + 1, 0, copy)
  selectedClip.value = { trackId: track.id, clipId: copy.id }
  await save()
}

async function deleteClip() {
  const found = findClip()
  if (!found) return
  found.track.clips.splice(found.index, 1)
  selectedClip.value = null
  await save()
}
</script>

<template>
  <div v-if="!manifest" class="empty dim">
    Open or create a project to see the timeline.
  </div>
  <div v-else class="timeline-root">
    <div class="zoom-bar">
      <span class="dim small">zoom</span>
      <input type="range" min="4" max="48" v-model.number="pxPerBeat" style="width: 100px" />
      <span class="sep" />
      <button class="tb primary" :disabled="saving" @click="showAddTrack = true">＋ Add Track</button>
      <span class="sep" />
      <button class="tb" :disabled="!selectedClip || saving" title="Split selected clip at playhead" @click="splitClip">✂ Split</button>
      <button class="tb" :disabled="!selectedClip || saving" title="Duplicate selected clip after itself" @click="duplicateClip">⧉ Duplicate</button>
      <button class="tb danger" :disabled="!selectedClip || saving" title="Delete selected clip" @click="deleteClip">✕ Clip</button>
      <span class="spacer" />
      <span class="dim small">{{ manifest.total_bars }} bars · {{ manifest.duration_seconds.toFixed(1) }}s<template v-if="saving"> · saving…</template></span>
    </div>
    <div v-if="!hasTracks" class="starter">
      <p class="dim">This song is empty. What do you want to do?</p>
      <div class="starter-btns">
        <button class="starter-card" @click="showAddTrack = true">
          <span class="starter-icon">🎹</span>
          <strong>Add an instrument</strong>
          <span class="dim small">Drums, bass, guitar, keys… the part is written for you</span>
        </button>
        <button class="starter-card" @click="showAddTrack = true">
          <span class="starter-icon">🎤</span>
          <strong>Add vocals</strong>
          <span class="dim small">Lyrics + melody, in your voice or a synthetic one</span>
        </button>
        <div class="starter-card static">
          <span class="starter-icon">💬</span>
          <strong>Or ask the chat</strong>
          <span class="dim small">“create a punk song about summer” → full song with vocals</span>
        </div>
      </div>
    </div>
    <div v-show="hasTracks" ref="scrollEl" class="scroll-area">
      <div class="grid" :style="{ width: LABEL_W + contentWidth + 'px' }">
        <div ref="playheadEl" class="playhead-overlay" />
        <!-- ruler -->
        <div class="row ruler-row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">bars</div>
          <div class="lane ruler" :style="{ width: contentWidth + 'px' }" @pointerdown="scrubStart">
            <div v-for="b in bars" :key="b.bar" class="bar-tick" :style="{ left: b.x + 'px' }">
              <span class="bar-num">{{ b.bar }}</span>
            </div>
          </div>
        </div>
        <!-- section lane -->
        <div class="row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">sections</div>
          <div class="lane section-lane" :style="{ width: contentWidth + 'px' }" @pointerdown="scrubStart">
            <div
              v-for="s in manifest.sections" :key="s.section_id" class="section-block"
              :style="{ left: s.start_beat * pxPerBeat + 'px', width: (s.end_beat - s.start_beat) * pxPerBeat + 'px' }"
            >{{ s.name }}</div>
          </div>
        </div>
        <!-- track lanes -->
        <div v-for="tl in layout" :key="tl.track.track_id" class="row track-row"
             :class="{ selected: studio.selectedTrackId === tl.track.track_id }"
             @click="studio.selectedTrackId = tl.track.track_id">
          <div class="label" :style="{ width: LABEL_W + 'px' }">
            <span class="track-dot" :style="{ background: color(tl.track.track_type) }" />
            <span class="track-name">{{ tl.track.name }}</span>
            <span class="dim small">{{ tl.track.track_type }}</span>
          </div>
          <div class="lane track-lane" :style="{ width: contentWidth + 'px', height: TRACK_H + 'px' }">
            <div
              v-for="c in tl.clips" :key="c.clipId" class="clip"
              :class="{ selected: selectedClip?.clipId === c.clipId }"
              :style="{ left: c.x + 'px', width: c.w + 'px', borderColor: color(tl.track.track_type) }"
              :title="'drag to move · double-click to edit'"
              @pointerdown.stop="clipPointerDown($event, tl.track.track_id, c.clipId)"
              @dblclick.stop="studio.openClipEditor(tl.track.track_id, c.clipId)"
            >
              <svg v-if="c.notes.length" class="notes-svg"
                   :viewBox="`0 0 ${c.w} ${TRACK_H - 6}`" preserveAspectRatio="none">
                <rect v-for="(n, i) in c.notes" :key="i"
                      :x="n.x" :y="n.y" :width="n.w" height="3" rx="1"
                      :fill="color(tl.track.track_type)" :opacity="n.o" />
              </svg>
              <svg v-else-if="c.wavePath" class="notes-svg"
                   :viewBox="`0 0 200 ${TRACK_H - 6}`" preserveAspectRatio="none">
                <path :d="c.wavePath" :fill="color(tl.track.track_type)" opacity="0.55" />
              </svg>
              <div v-else class="wave-placeholder" :style="{ background: color(tl.track.track_type) }" />
            </div>
          </div>
        </div>
      </div>
    </div>
    <AddTrackDialog v-if="showAddTrack" @close="showAddTrack = false" />
  </div>
</template>

<style scoped>
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.timeline-root { display: flex; flex-direction: column; height: 100%; }
.zoom-bar { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-bottom: 1px solid var(--border); flex: none; flex-wrap: wrap; }
.spacer { flex: 1; }
.sep { width: 1px; height: 18px; background: var(--border); margin: 0 4px; }
.small { font-size: 11px; }
.starter { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; }
.starter-btns { display: flex; gap: 14px; flex-wrap: wrap; justify-content: center; }
.starter-card { display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 18px 20px; width: 200px; border-radius: 12px; }
.starter-card:hover:not(.static) { border-color: var(--accent); background: var(--bg-elevated); }
.starter-card.static { border: 1px dashed var(--border); background: transparent; cursor: default; }
.starter-icon { font-size: 30px; }
.tb { padding: 3px 9px; font-size: 12px; }
.tb.danger:not(:disabled) { border-color: var(--err); color: var(--err); }
.scroll-area { flex: 1; overflow: auto; }
.grid { min-width: 100%; position: relative; }
.playhead-overlay { position: absolute; top: 0; bottom: 0; left: 0; width: 1px; background: var(--err); z-index: 4; pointer-events: none; will-change: transform; }
.row { display: flex; border-bottom: 1px solid var(--border); }
.label { flex: none; padding: 4px 8px; display: flex; align-items: center; gap: 6px; position: sticky; left: 0; background: var(--bg-panel); z-index: 5; border-right: 1px solid var(--border); overflow: hidden; }
.track-name { font-size: 12px; font-weight: 600; white-space: nowrap; }
.track-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.lane { position: relative; flex: none; }
.ruler { height: 24px; cursor: pointer; }
.bar-tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--border); pointer-events: none; }
.bar-num { font-size: 9px; color: var(--text-dim); padding-left: 2px; }
.section-lane { height: 26px; background: rgba(0,0,0,0.15); cursor: pointer; }
.section-block { position: absolute; top: 3px; bottom: 3px; background: var(--bg-elevated); border: 1px solid var(--accent-2); border-radius: 4px; font-size: 11px; padding: 1px 6px; overflow: hidden; white-space: nowrap; pointer-events: none; }
.track-row.selected .label { outline: 1px solid var(--accent); outline-offset: -1px; }
.track-lane { background: rgba(0,0,0,0.1); }
.clip { position: absolute; top: 3px; bottom: 3px; border: 1px solid; border-radius: 4px; background: rgba(255,255,255,0.05); overflow: hidden; cursor: pointer; }
.clip.selected { outline: 2px solid var(--accent); outline-offset: -1px; background: rgba(79,156,249,0.12); }
.notes-svg { width: 100%; height: 100%; display: block; pointer-events: none; }
.wave-placeholder { position: absolute; left: 2px; right: 2px; top: 40%; bottom: 40%; opacity: 0.35; border-radius: 2px; pointer-events: none; }
</style>
