<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import type { ClipTiming, ManifestTrack, NoteTiming } from '../api/types'

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

const playheadX = computed(() => {
  const m = manifest.value
  if (!m) return 0
  return ((playback.playhead * m.bpm) / 60) * pxPerBeat.value
})

function clipsFor(t: ManifestTrack): ClipTiming[] {
  return manifest.value?.clips.filter((c) => c.track_id === t.track_id) ?? []
}
function notesFor(c: ClipTiming): NoteTiming[] {
  return manifest.value?.midi_note_metadata.filter((n) => n.clip_id === c.clip_id) ?? []
}
function noteRange(notes: NoteTiming[]): [number, number] {
  if (!notes.length) return [48, 72]
  let lo = 127, hi = 0
  for (const n of notes) { lo = Math.min(lo, n.midi_note); hi = Math.max(hi, n.midi_note) }
  return [Math.max(0, lo - 1), Math.min(127, hi + 1)]
}
function waveformFor(trackId: string): number[] | null {
  const w = manifest.value?.waveform_metadata.find((x) => x.track_id === trackId)
  return w?.peaks ?? null
}
function waveformPath(peaks: number[], w: number, h: number): string {
  const mid = h / 2
  let d = `M 0 ${mid}`
  peaks.forEach((p, i) => {
    const x = (i / (peaks.length - 1 || 1)) * w
    d += ` L ${x.toFixed(1)} ${(mid - p * mid * 0.9).toFixed(1)}`
  })
  for (let i = peaks.length - 1; i >= 0; i--) {
    const x = (i / (peaks.length - 1 || 1)) * w
    d += ` L ${x.toFixed(1)} ${(mid + peaks[i] * mid * 0.9).toFixed(1)}`
  }
  return d + ' Z'
}

const TRACK_COLORS: Record<string, string> = {
  drums: '#e6a23c', bass: '#f2555a', guitar: '#f78fb3', keys: '#4f9cf9',
  synth: '#9d6ff2', strings: '#3ecf8e', brass: '#e0c341', sample: '#41c9e0',
  lead_vocal: '#ff7eb6', backing_vocal: '#c792ea', fx: '#8d96a8',
}
const color = (t: string) => TRACK_COLORS[t] ?? '#8d96a8'

function seekAt(e: MouseEvent) {
  const m = manifest.value
  if (!m) return
  const el = e.currentTarget as HTMLElement
  const x = e.clientX - el.getBoundingClientRect().left + el.scrollLeft
  const beats = x / pxPerBeat.value
  playback.seek((beats * 60) / m.bpm)
}
</script>

<template>
  <div v-if="!manifest" class="empty dim">
    Open or create a project to see the timeline.
  </div>
  <div v-else class="timeline-root">
    <div class="zoom-bar">
      <span class="dim small">zoom</span>
      <input type="range" min="4" max="48" v-model.number="pxPerBeat" style="width: 120px" />
      <span class="spacer" />
      <span class="dim small">{{ manifest.total_bars }} bars · {{ manifest.duration_seconds.toFixed(1) }}s</span>
    </div>
    <div class="scroll-area">
      <div class="grid" :style="{ width: LABEL_W + contentWidth + 'px' }">
        <!-- ruler -->
        <div class="row ruler-row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">bars</div>
          <div class="lane ruler" :style="{ width: contentWidth + 'px' }" @click="seekAt">
            <div v-for="b in bars" :key="b.bar" class="bar-tick" :style="{ left: b.x + 'px' }">
              <span class="bar-num">{{ b.bar }}</span>
            </div>
            <div class="playhead" :style="{ left: playheadX + 'px' }" />
          </div>
        </div>
        <!-- section lane -->
        <div class="row">
          <div class="label small dim" :style="{ width: LABEL_W + 'px' }">sections</div>
          <div class="lane section-lane" :style="{ width: contentWidth + 'px' }">
            <div
              v-for="s in manifest.sections" :key="s.section_id" class="section-block"
              :style="{ left: s.start_beat * pxPerBeat + 'px', width: (s.end_beat - s.start_beat) * pxPerBeat + 'px' }"
            >{{ s.name }}</div>
            <div class="playhead" :style="{ left: playheadX + 'px' }" />
          </div>
        </div>
        <!-- track lanes -->
        <div v-for="t in manifest.tracks" :key="t.track_id" class="row track-row"
             :class="{ selected: studio.selectedTrackId === t.track_id }"
             @click="studio.selectedTrackId = t.track_id">
          <div class="label" :style="{ width: LABEL_W + 'px' }">
            <span class="track-dot" :style="{ background: color(t.track_type) }" />
            <span class="track-name">{{ t.name }}</span>
            <span class="dim small">{{ t.track_type }}</span>
          </div>
          <div class="lane track-lane" :style="{ width: contentWidth + 'px', height: TRACK_H + 'px' }">
            <div
              v-for="c in clipsFor(t)" :key="c.clip_id" class="clip"
              :class="c.clip_type"
              :style="{
                left: c.start_beat * pxPerBeat + 'px',
                width: Math.max((c.end_beat - c.start_beat) * pxPerBeat, 4) + 'px',
                borderColor: color(t.track_type),
              }"
            >
              <!-- MIDI notes -->
              <svg v-if="c.clip_type === 'midi' || c.clip_type === 'vocal'" class="notes-svg"
                   :viewBox="`0 0 ${(c.end_beat - c.start_beat) * pxPerBeat} ${TRACK_H - 6}`"
                   preserveAspectRatio="none">
                <template v-for="n in notesFor(c)" :key="n.note_id">
                  <rect
                    :x="(n.start_beat - c.start_beat) * pxPerBeat"
                    :y="(TRACK_H - 6) * (1 - (n.midi_note - noteRange(notesFor(c))[0]) / (noteRange(notesFor(c))[1] - noteRange(notesFor(c))[0] || 1)) - 2"
                    :width="Math.max((n.end_beat - n.start_beat) * pxPerBeat - 0.5, 1)"
                    height="3" rx="1"
                    :fill="color(t.track_type)" :opacity="0.4 + (n.velocity / 127) * 0.6"
                  />
                </template>
              </svg>
              <!-- audio clip waveform (real peaks if rendered, placeholder otherwise) -->
              <svg v-else-if="waveformFor(t.track_id)" class="notes-svg"
                   :viewBox="`0 0 200 ${TRACK_H - 6}`" preserveAspectRatio="none">
                <path :d="waveformPath(waveformFor(t.track_id)!, 200, TRACK_H - 6)"
                      :fill="color(t.track_type)" opacity="0.55" />
              </svg>
              <div v-else class="wave-placeholder" :style="{ background: color(t.track_type) }" />
            </div>
            <div class="playhead" :style="{ left: playheadX + 'px' }" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.empty { display: flex; align-items: center; justify-content: center; height: 100%; }
.timeline-root { display: flex; flex-direction: column; height: 100%; }
.zoom-bar { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-bottom: 1px solid var(--border); flex: none; }
.spacer { flex: 1; }
.small { font-size: 11px; }
.scroll-area { flex: 1; overflow: auto; }
.grid { min-width: 100%; }
.row { display: flex; border-bottom: 1px solid var(--border); }
.label { flex: none; padding: 4px 8px; display: flex; align-items: center; gap: 6px; position: sticky; left: 0; background: var(--bg-panel); z-index: 3; border-right: 1px solid var(--border); overflow: hidden; }
.track-name { font-size: 12px; font-weight: 600; white-space: nowrap; }
.track-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.lane { position: relative; flex: none; }
.ruler { height: 24px; cursor: pointer; }
.bar-tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--border); }
.bar-num { font-size: 9px; color: var(--text-dim); padding-left: 2px; }
.section-lane { height: 26px; background: rgba(0,0,0,0.15); }
.section-block { position: absolute; top: 3px; bottom: 3px; background: var(--bg-elevated); border: 1px solid var(--accent-2); border-radius: 4px; font-size: 11px; padding: 1px 6px; overflow: hidden; white-space: nowrap; }
.track-row.selected .label { outline: 1px solid var(--accent); outline-offset: -1px; }
.track-lane { background: rgba(0,0,0,0.1); }
.clip { position: absolute; top: 3px; bottom: 3px; border: 1px solid; border-radius: 4px; background: rgba(255,255,255,0.05); overflow: hidden; }
.notes-svg { width: 100%; height: 100%; display: block; }
.wave-placeholder { position: absolute; left: 2px; right: 2px; top: 40%; bottom: 40%; opacity: 0.35; border-radius: 2px; }
.playhead { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--err); z-index: 2; pointer-events: none; }
</style>
