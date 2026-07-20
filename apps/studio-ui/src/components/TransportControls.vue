<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Loader, Mic, Pause, Play, Redo2, Square, Timer, Undo2 } from 'lucide-vue-next'
import { api } from '../api/client'
import { runCountdown } from '../composables/countdown'
import type { Asset, SongProject } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

const { t } = useI18n()
const studio = useStudioStore()
const playback = usePlaybackStore()

const timeDisplay = computed(() => {
  const t = playback.playhead
  const m = Math.floor(t / 60)
  const s = (t % 60).toFixed(1).padStart(4, '0')
  return `${m}:${s}`
})

const barBeat = computed(() => {
  const man = studio.manifest
  if (!man || man.bpm <= 0) return '1.1'
  const beats = (playback.playhead * man.bpm) / 60
  const bar = Math.floor(beats / man.beats_per_bar) + 1
  const beat = Math.floor(beats % man.beats_per_bar) + 1
  return `${bar}.${beat}`
})

// --- record a vocal take from the transport -------------------------------
const recording = ref(false)
const recSeconds = ref(0)
const recStatus = ref('')
let mediaRecorder: MediaRecorder | null = null
let chunks: Blob[] = []
let recTimer: ReturnType<typeof setInterval> | null = null
let takeStart = 0

function vocalTrack() {
  const p = studio.project
  if (!p) return null
  const sel = p.tracks.find((t) => t.id === studio.selectedTrackId)
  if (sel && ['lead_vocal', 'backing_vocal'].includes(sel.track_type)) return sel
  return p.tracks.find((t) => t.track_type === 'lead_vocal') ?? null
}

async function toggleRecord() {
  if (recording.value) { stopRecord(); return }
  const p = studio.project
  if (!p) return
  let track = vocalTrack()
  if (!track) {
    // create an empty vocal track to record onto
    await api.post(`/projects/${p.id}/tracks/quick-add`,
      { track_type: 'lead_vocal', generate: false })
    await studio.reloadCurrent()
    track = vocalTrack()
    if (!track) { recStatus.value = t('transport.noVocalTrack'); return }
  }
  studio.selectedTrackId = track.id
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    await runCountdown()   // GarageBand-style count-in before we capture
    chunks = []
    takeStart = playback.playhead
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((s) => s.stop())
      const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
      const ext = (mediaRecorder?.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
      try {
        const asset = await api.upload<Asset>('/voice/recordings/upload', blob,
          `take-${Date.now()}.${ext}`, { source: 'live_recording' })
        const proj = studio.project as SongProject
        const tr = proj.tracks.find((t) => t.id === track!.id)
        if (tr) {
          tr.clips.push({
            id: crypto.randomUUID().replace(/-/g, ''),
            section_id: '', clip_type: 'sample',
            start_beat: (takeStart * proj.bpm) / 60,
            duration_beats: Math.max((recSeconds.value * proj.bpm) / 60, 1),
            note_events: [], source_asset_id: asset.id, gain_db: 0, loop: false,
            fade_in_seconds: 0, fade_out_seconds: 0, source_offset_seconds: 0,
          })
          await studio.saveProject()
          recStatus.value = t('transport.takeSaved', { name: tr.name })
          setTimeout(() => { recStatus.value = '' }, 4000)
        }
      } catch (e) { recStatus.value = String(e) }
    }
    mediaRecorder.start()
    recording.value = true
    recSeconds.value = 0
    recTimer = setInterval(() => recSeconds.value++, 1000)
    void playback.play()   // sing along with the song
  } catch (e) {
    recStatus.value = t('transport.micUnavailable') + String(e)
  }
}

function stopRecord() {
  mediaRecorder?.stop()
  recording.value = false
  if (recTimer) clearInterval(recTimer)
  playback.pause()
}

onUnmounted(() => { if (recording.value) stopRecord() })

// --- editable project title --------------------------------------------------
const editingTitle = ref(false)
const titleDraft = ref('')

function startTitleEdit() {
  if (!studio.project) return
  titleDraft.value = studio.project.title
  editingTitle.value = true
}
async function commitTitle() {
  editingTitle.value = false
  const p = studio.project
  const v = titleDraft.value.trim()
  if (!p || !v || v === p.title) return
  p.title = v
  await studio.saveProject()
  await studio.refreshProjects()
}

// --- BPM control: whole-song tempo (stems re-render at the new tempo). ------
// Steppers, type-to-edit, drag-to-scrub and tap-tempo — a proper DAW widget.
const MIN_BPM = 30
const MAX_BPM = 300
const editingBpm = ref(false)
const bpmDraft = ref(120)

function startBpmEdit() {
  if (!studio.project) return
  bpmDraft.value = studio.project.bpm
  editingBpm.value = true
}
async function commitBpm() {
  editingBpm.value = false
  const v = Math.round(Number(bpmDraft.value))
  if (!Number.isFinite(v)) return
  await applyBpm(v)
}

async function applyBpm(v: number) {
  const p = studio.project
  v = Math.round(Math.min(Math.max(v, MIN_BPM), MAX_BPM))
  if (!p || v === p.bpm) return
  p.bpm = v
  await studio.saveProject()   // fingerprints change → re-render on next ▶
}

// step ±1, or ±5 with Shift held
function nudgeBpm(dir: number, e?: MouseEvent) {
  if (!studio.project) return
  void applyBpm(studio.project.bpm + dir * (e?.shiftKey ? 5 : 1))
}

// drag the value up/down (or left/right) to scrub the tempo, DAW-style
function startBpmDrag(e: PointerEvent) {
  if (!studio.project || editingBpm.value) return
  const startY = e.clientY
  const startX = e.clientX
  const start = studio.project.bpm
  let moved = false
  const move = (ev: PointerEvent) => {
    const d = Math.round(((startY - ev.clientY) + (ev.clientX - startX)) / 4)
    if (d !== 0) moved = true
    const v = Math.min(Math.max(start + d, MIN_BPM), MAX_BPM)
    if (studio.project && v !== studio.project.bpm) studio.project.bpm = v
  }
  const up = () => {
    window.removeEventListener('pointermove', move)
    if (moved && studio.project) void applyBpm(studio.project.bpm)
    else startBpmEdit()          // a plain click opens type-to-edit
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up, { once: true })
}

// tap tempo: average the interval of the last few taps
let tapTimes: number[] = []
let tapReset: ReturnType<typeof setTimeout> | null = null
function tapTempo() {
  const now = performance.now()
  if (tapReset) clearTimeout(tapReset)
  tapReset = setTimeout(() => { tapTimes = [] }, 2000)
  tapTimes.push(now)
  if (tapTimes.length > 6) tapTimes.shift()
  if (tapTimes.length < 2) return
  const gaps = tapTimes.slice(1).map((t, i) => t - tapTimes[i])
  const avg = gaps.reduce((a, b) => a + b, 0) / gaps.length
  if (avg > 0) void applyBpm(60000 / avg)
}

// --- editable key + time signature (click the chips next to the BPM) -------
const KEY_OPTIONS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
  .flatMap((r) => [`${r} major`, `${r} minor`])
const TIME_SIG_OPTIONS = ['4/4', '3/4', '2/4', '6/8', '12/8']

async function setKey(k: string) {
  const p = studio.project
  if (!p || !k || k === p.key) return
  p.key = k
  await studio.saveProject()
}
async function setTimeSig(ts: string) {
  const p = studio.project
  if (!p || !ts || ts === p.time_signature) return
  p.time_signature = ts
  await studio.saveProject()
}
</script>

<template>
  <div class="transport panel">
    <button :title="t('transport.stop')" @click="playback.stop()"><Square class="icon" :size="14" /></button>
    <button class="primary" :title="playback.playing ? t('transport.pause') : t('transport.play')"
            :disabled="!studio.manifest || playback.preparing"
            @click="playback.playing ? playback.pause() : playback.play()">
      <Loader v-if="playback.preparing" class="icon spin" :size="14" />
      <Pause v-else-if="playback.playing" class="icon" :size="14" />
      <Play v-else class="icon" :size="14" />
    </button>
    <button :class="{ 'rec-on': recording }" :disabled="!studio.project"
            :title="recording ? t('transport.stopRecording') : t('transport.recordTip')"
            @click="toggleRecord">
      <template v-if="recording">■ {{ recSeconds }}s</template>
      <Mic v-else class="icon" :size="14" />
    </button>
    <button :class="{ active: playback.metronome }" :title="t('transport.metronome')"
            @click="playback.metronome = !playback.metronome"><Timer class="icon" :size="14" /></button>
    <button :disabled="!studio.canUndo" :title="t('transport.undo')" @click="studio.undo()"><Undo2 class="icon" :size="14" /></button>
    <button :disabled="!studio.canRedo" :title="t('transport.redo')" @click="studio.redo()"><Redo2 class="icon" :size="14" /></button>
    <button class="time-toggle" :title="studio.timeMode === 'bars' ? t('transport.switchToSeconds') : t('transport.switchToBars')"
            @click="studio.timeMode = studio.timeMode === 'bars' ? 'seconds' : 'bars'">
      <span class="time">{{ studio.timeMode === 'bars' ? t('transport.bar') + ' ' + barBeat : timeDisplay }}</span>
      <span class="dim small">{{ studio.timeMode === 'bars' ? timeDisplay : t('transport.bar') + ' ' + barBeat }}</span>
    </button>
    <span v-if="playback.preparing" class="preparing">{{ t('transport.preparing') }}</span>
    <span v-if="recStatus" class="dim small">{{ recStatus }}</span>
    <span class="spacer" />
    <template v-if="studio.project">
      <input v-if="editingTitle" v-model="titleDraft" class="title-input" autofocus
             @blur="commitTitle" @keyup.enter="($event.target as HTMLInputElement).blur()" />
      <button v-else class="title-btn" :title="t('transport.renameTip')" @click="startTitleEdit">
        <span class="title">{{ studio.project.title }}</span></button>
      <div class="bpm" :title="t('transport.bpmTip')">
        <button class="bpm-step" :disabled="studio.project.bpm <= MIN_BPM"
                :title="t('transport.bpmDown')"
                @click="nudgeBpm(-1, $event)">−</button>
        <input v-if="editingBpm" v-model.number="bpmDraft" type="number"
               :min="MIN_BPM" :max="MAX_BPM" class="bpm-input" autofocus
               @blur="commitBpm" @keyup.enter="($event.target as HTMLInputElement).blur()" />
        <button v-else class="bpm-val" @pointerdown="startBpmDrag">
          <span class="bpm-num">{{ studio.project.bpm }}</span>
          <span class="bpm-unit">BPM</span>
        </button>
        <button class="bpm-step" :disabled="studio.project.bpm >= MAX_BPM"
                :title="t('transport.bpmUp')"
                @click="nudgeBpm(1, $event)">+</button>
        <button class="bpm-tap" :title="t('transport.bpmTapTip')"
                @click="tapTempo">{{ t('transport.bpmTap') }}</button>
      </div>
      <select class="meta-select" :value="studio.project.key"
              :title="t('transport.keyTip')"
              @change="setKey(($event.target as HTMLSelectElement).value)">
        <option v-for="k in KEY_OPTIONS" :key="k" :value="k">{{ k }}</option>
        <option v-if="!KEY_OPTIONS.includes(studio.project.key)"
                :value="studio.project.key">{{ studio.project.key }}</option>
      </select>
      <select class="meta-select" :value="studio.project.time_signature"
              :title="t('transport.timeSigTip')"
              @change="setTimeSig(($event.target as HTMLSelectElement).value)">
        <option v-for="ts in TIME_SIG_OPTIONS" :key="ts" :value="ts">{{ ts }}</option>
        <option v-if="!TIME_SIG_OPTIONS.includes(studio.project.time_signature)"
                :value="studio.project.time_signature">{{ studio.project.time_signature }}</option>
      </select>
      <span v-if="studio.manifest && studio.manifest.stems.length" class="dim"
            :title="t('transport.stemsTip')">
        · {{ t('transport.stemsLoaded', { n: playback.stemsLoaded, total: studio.manifest.stems.length }) }}
      </span>
    </template>
    <span v-else class="dim">{{ t('transport.noProject') }}</span>
  </div>
</template>

<style scoped>
.transport { display: flex; align-items: center; gap: 10px; padding: 8px 12px; }
.time { font-family: 'Consolas', monospace; font-size: 15px; }
.time-toggle { display: flex; flex-direction: column; align-items: flex-start; padding: 3px 10px; line-height: 1.15; min-width: 92px; }
.small { font-size: 10px; }
.title { font-weight: 600; }
.spacer { flex: 1; }
.preparing { font-size: 12px; color: var(--warn); }
.rec-on { background: var(--err); border-color: var(--err); color: #fff; }
.title-btn { border: none; background: transparent; padding: 2px 4px; }
.title-btn:hover .title { color: var(--accent); }
.title-input { width: 180px; padding: 2px 6px; font-size: 13px; font-weight: 600; }
.bpm {
  display: inline-flex; align-items: stretch; gap: 0;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  overflow: hidden; height: 26px;
}
.bpm-step {
  border: none; background: var(--bg-elevated); color: var(--text-dim);
  padding: 0 8px; font-size: 15px; line-height: 1; border-radius: 0;
}
.bpm-step:hover:not(:disabled) { color: var(--accent); background: var(--bg); }
.bpm-step:disabled { opacity: 0.35; }
.bpm-val {
  display: flex; align-items: baseline; gap: 3px; border: none;
  background: transparent; padding: 0 8px; cursor: ns-resize;
  border-left: 1px solid var(--border); border-right: 1px solid var(--border);
}
.bpm-val:hover { background: var(--bg-elevated); }
.bpm-num { font-size: 14px; font-weight: 600; font-family: 'Consolas', monospace; color: var(--text); }
.bpm-unit { font-size: 9px; letter-spacing: 0.05em; color: var(--text-dim); }
.bpm-input {
  width: 52px; padding: 0 6px; font-size: 14px; text-align: center;
  border: none; border-left: 1px solid var(--border);
  border-right: 1px solid var(--border); border-radius: 0;
  font-family: 'Consolas', monospace;
}
.bpm-tap {
  border: none; background: var(--bg-elevated); color: var(--text-dim);
  padding: 0 9px; font-size: 10px; font-weight: 600; letter-spacing: 0.06em;
  border-radius: 0; border-left: 1px solid var(--border);
}
.bpm-tap:hover { color: var(--accent); background: var(--bg); }
.meta-select {
  border: none; background: transparent; color: var(--text-dim);
  font-size: 13px; padding: 2px 2px; cursor: pointer;
}
.meta-select:hover { color: var(--accent); }
button.active { border-color: var(--accent); color: var(--accent); }
</style>
