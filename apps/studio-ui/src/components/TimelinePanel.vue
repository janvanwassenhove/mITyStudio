<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { api } from '../api/client'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import AddTrackDialog from './AddTrackDialog.vue'
import type { Clip, Track } from '../api/types'

const studio = useStudioStore()
const playback = usePlaybackStore()

const pxPerBeat = ref(14)
const TRACK_H = 56
const LABEL_W = 200

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
  const out: { label: string; x: number }[] = []
  if (studio.timeMode === 'seconds') {
    const pxPerSec = (m.bpm / 60) * pxPerBeat.value
    const step = pxPerSec < 26 ? 5 : 1
    const totalSec = (totalBeats.value * 60) / m.bpm
    for (let s = 0; s <= totalSec; s += step) out.push({ label: `${s}s`, x: s * pxPerSec })
  } else {
    const count = Math.ceil(totalBeats.value / m.beats_per_bar)
    for (let i = 0; i <= count; i++) out.push({ label: String(i + 1), x: i * m.beats_per_bar * pxPerBeat.value })
  }
  return out
})

// project-side track lookup for live mixer controls on the lane headers
function projTrack(trackId: string): Track | null {
  return studio.project?.tracks.find((t) => t.id === trackId) ?? null
}
function toggleMute(trackId: string) {
  const t = projTrack(trackId)
  if (t) { t.mute = !t.mute; void save() }
}
function toggleSolo(trackId: string) {
  const t = projTrack(trackId)
  if (t) { t.solo = !t.solo; void save() }
}
function setVolume(trackId: string, v: number) {
  const t = projTrack(trackId)
  if (t) { t.volume = v; void save() }
}

// --- quick instrument switch: categorized catalog popover ------------------
interface CatalogPreset { label: string; asset_id: string; soundfont: string; bank: number; program: number }
interface CatalogCategory { category: string; presets: CatalogPreset[] }
const CATEGORY_ICONS: Record<string, string> = {
  'Piano & Keys': '🎹', Organ: '🪗', Guitar: '🎸', Bass: '🎸', Strings: '🎻',
  Brass: '🎺', 'Sax & Winds': '🎷', 'Voice & Choir': '🎤', 'Synth Lead': '🎛️',
  'Synth Pad': '🌫️', 'Drum Kits': '🥁', Percussion: '🪘', FX: '✨', Other: '🎵',
}
const catalog = ref<CatalogCategory[]>([])
const instSwitch = ref<string | null>(null)
const instQuery = ref('')
const instCategory = ref('')

async function openInstSwitch(trackId: string) {
  instSwitch.value = instSwitch.value === trackId ? null : trackId
  instQuery.value = ''
  if (instSwitch.value && !catalog.value.length) {
    catalog.value = await api.get<CatalogCategory[]>('/assets/instruments')
    if (!instCategory.value && catalog.value.length) instCategory.value = catalog.value[0].category
  }
}

const instHits = computed<CatalogPreset[]>(() => {
  const q = instQuery.value.trim().toLowerCase()
  if (q.length >= 2) {
    return catalog.value.flatMap((c) => c.presets)
      .filter((p) => p.label.toLowerCase().includes(q)).slice(0, 30)
  }
  return catalog.value.find((c) => c.category === instCategory.value)?.presets.slice(0, 100) ?? []
})

async function pickInstrument(hit: CatalogPreset) {
  const t = projTrack(instSwitch.value ?? '')
  if (!t) return
  t.instrument_config.soundfont_asset_id = hit.asset_id
  t.instrument_config.bank = hit.bank
  t.instrument_config.program = hit.program
  instSwitch.value = null
  await save()
}
const canSwitchInstrument = (type: string) =>
  !['sample', 'lead_vocal', 'backing_vocal'].includes(type)

// readable type abbreviations so track types aren't distinguished by color alone
const TYPE_ABBR: Record<string, string> = {
  drums: 'DR', bass: 'BA', guitar: 'GT', keys: 'KY', synth: 'SY',
  strings: 'ST', brass: 'BR', sample: 'SMP', lead_vocal: 'VOX',
  backing_vocal: 'BVX', fx: 'FX',
}

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
    {{ $t('timeline.noProject') }}
  </div>
  <div v-else class="timeline-root">
    <div class="zoom-bar">
      <span class="dim small">{{ $t('timeline.zoom') }}</span>
      <input type="range" min="4" max="48" v-model.number="pxPerBeat" style="width: 100px" />
      <span class="sep" />
      <button class="tb primary" :disabled="saving" @click="showAddTrack = true">＋ {{ $t('timeline.addTrack') }}</button>
      <span class="sep" />
      <button class="tb" :disabled="!selectedClip || saving" :title="$t('timeline.splitTip')" @click="splitClip">✂ {{ $t('timeline.split') }}</button>
      <button class="tb" :disabled="!selectedClip || saving" :title="$t('timeline.duplicateTip')" @click="duplicateClip">⧉ {{ $t('timeline.duplicate') }}</button>
      <button class="tb danger" :disabled="!selectedClip || saving" :title="$t('timeline.deleteTip')" @click="deleteClip">✕ {{ $t('timeline.clip') }}</button>
      <span class="spacer" />
      <span class="dim small">{{ $t('timeline.barsSeconds', { bars: manifest.total_bars, s: manifest.duration_seconds.toFixed(1) }) }}<template v-if="saving"> · {{ $t('common.saving') }}</template></span>
    </div>
    <div v-if="!hasTracks" class="starter">
      <p class="dim">{{ $t('timeline.emptySong') }}</p>
      <div class="starter-btns">
        <button class="starter-card" @click="showAddTrack = true">
          <span class="starter-icon">🎹</span>
          <strong>{{ $t('timeline.addInstrument') }}</strong>
          <span class="dim small">{{ $t('timeline.addInstrumentBlurb') }}</span>
        </button>
        <button class="starter-card" @click="showAddTrack = true">
          <span class="starter-icon">🎤</span>
          <strong>{{ $t('timeline.addVocals') }}</strong>
          <span class="dim small">{{ $t('timeline.addVocalsBlurb') }}</span>
        </button>
        <div class="starter-card static">
          <span class="starter-icon">💬</span>
          <strong>{{ $t('timeline.orChat') }}</strong>
          <span class="dim small">{{ $t('timeline.orChatBlurb') }}</span>
        </div>
      </div>
    </div>
    <div v-show="hasTracks" ref="scrollEl" class="scroll-area">
      <div class="grid" :style="{ width: LABEL_W + contentWidth + 'px' }">
        <div ref="playheadEl" class="playhead-overlay" />
        <!-- ruler -->
        <div class="row ruler-row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">{{ $t('timeline.bars') }}</div>
          <div class="lane ruler" :style="{ width: contentWidth + 'px' }" @pointerdown="scrubStart">
            <div v-for="b in bars" :key="b.label" class="bar-tick" :style="{ left: b.x + 'px' }">
              <span class="bar-num">{{ b.label }}</span>
            </div>
          </div>
        </div>
        <!-- section lane -->
        <div class="row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">{{ $t('timeline.sections') }}</div>
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
          <div class="label track-label" :class="{ 'pop-open': instSwitch === tl.track.track_id }"
               :style="{ width: LABEL_W + 'px' }"
               :title="$t('timeline.dblClickInspector')"
               @dblclick="studio.openTrackInspector(tl.track.track_id)">
            <div class="label-top">
              <span class="type-chip" :style="{ background: color(tl.track.track_type) }"
                    :title="$t('timeline.trackType') + ': ' + tl.track.track_type.replace('_', ' ')">
                {{ TYPE_ABBR[tl.track.track_type] ?? '??' }}</span>
              <span class="track-name" :title="tl.track.name">{{ tl.track.name }}</span>
            </div>
            <div class="label-controls" @dblclick.stop>
              <button class="mini" :class="{ mute: projTrack(tl.track.track_id)?.mute }"
                      :title="$t('timeline.muteTip')"
                      @click.stop="toggleMute(tl.track.track_id)">M</button>
              <button class="mini" :class="{ solo: projTrack(tl.track.track_id)?.solo }"
                      :title="$t('timeline.soloTip')"
                      @click.stop="toggleSolo(tl.track.track_id)">S</button>
              <input class="mini-vol" type="range" min="0" max="1.5" step="0.01" :title="$t('timeline.volume')"
                     :value="projTrack(tl.track.track_id)?.volume ?? 1"
                     @click.stop
                     @input="setVolume(tl.track.track_id, Number(($event.target as HTMLInputElement).value))" />
              <button v-if="canSwitchInstrument(tl.track.track_type)" class="mini"
                      :title="$t('timeline.switchInstrument')"
                      @click.stop="openInstSwitch(tl.track.track_id)">🎛</button>
              <button class="mini" :title="$t('timeline.instrumentFx')"
                      @click.stop="studio.openTrackInspector(tl.track.track_id)">✎</button>
            </div>
            <div v-if="instSwitch === tl.track.track_id" class="inst-pop" @click.stop @dblclick.stop>
              <input v-model="instQuery" :placeholder="$t('timeline.searchInstruments')"
                     autofocus @pointerdown.stop />
              <div v-if="instQuery.trim().length < 2" class="cat-row">
                <button v-for="c in catalog" :key="c.category" class="cat-chip"
                        :class="{ on: instCategory === c.category }"
                        :title="c.category"
                        @click="instCategory = c.category">
                  {{ CATEGORY_ICONS[c.category] ?? '🎵' }}
                </button>
              </div>
              <div v-if="instQuery.trim().length < 2" class="dim tiny cat-name">
                {{ CATEGORY_ICONS[instCategory] }} {{ instCategory }}
              </div>
              <div class="inst-hits">
                <div v-for="(h, i) in instHits" :key="i" class="inst-hit" @click="pickInstrument(h)">
                  <strong>{{ h.label }}</strong>
                </div>
                <div v-if="!instHits.length" class="dim small" style="padding: 6px">
                  {{ catalog.length ? $t('timeline.noMatches') : $t('timeline.loadingInstruments') }}
                </div>
              </div>
            </div>
          </div>
          <div class="lane track-lane" :style="{ width: contentWidth + 'px', height: TRACK_H + 'px' }">
            <div
              v-for="c in tl.clips" :key="c.clipId" class="clip"
              :class="{ selected: selectedClip?.clipId === c.clipId }"
              :style="{ left: c.x + 'px', width: c.w + 'px', borderColor: color(tl.track.track_type) }"
              :title="$t('timeline.clipTip')"
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
.label { flex: none; padding: 4px 8px; display: flex; align-items: center; gap: 6px; position: sticky; left: 0; background: var(--bg-panel); z-index: 5; border-right: 1px solid var(--border); }
.ruler-row .label, .row .label.small { overflow: hidden; }
.track-name { font-size: 12px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.track-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.type-chip { flex: none; font-size: 8px; font-weight: 800; color: #101216; border-radius: 4px; padding: 1px 4px; letter-spacing: 0.04em; }
.track-label { flex-direction: column; align-items: stretch !important; gap: 3px !important; justify-content: center; cursor: default; }
.track-label.pop-open { z-index: 30; }
.label-top { display: flex; align-items: center; gap: 6px; min-width: 0; }
.label-controls { display: flex; align-items: center; gap: 4px; }
.mini { padding: 0 6px; font-size: 10px; height: 18px; line-height: 1; }
.mini.mute { background: var(--warn); color: #000; border-color: var(--warn); }
.mini.solo { background: var(--ok); color: #000; border-color: var(--ok); }
.mini-vol { width: 70px; height: 14px; }
.inst-pop { position: absolute; top: 100%; left: 4px; width: 280px; background: var(--bg-elevated); border: 1px solid var(--accent); border-radius: 8px; padding: 6px; z-index: 20; box-shadow: 0 6px 18px rgba(0,0,0,0.6); }
.inst-pop input { width: 100%; }
.cat-row { display: flex; flex-wrap: wrap; gap: 2px; margin-top: 5px; }
.cat-chip { padding: 2px 5px; font-size: 14px; border-radius: 5px; border: 1px solid transparent; background: transparent; }
.cat-chip.on { border-color: var(--accent); background: var(--bg-panel); }
.cat-name { padding: 3px 4px 0; }
.tiny { font-size: 10px; }
.inst-hits { max-height: 170px; overflow-y: auto; margin-top: 4px; }
.inst-hit { padding: 3px 6px; border-radius: 4px; cursor: pointer; }
.inst-hit:hover { background: var(--bg-panel); }
.inst-hit strong { font-size: 12px; font-weight: 500; }
.small { font-size: 10px; }
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
