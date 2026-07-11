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

// --- editable BPM: the whole song (stems re-render at the new tempo) -------
const editingBpm = ref(false)
const bpmDraft = ref(120)

function startBpmEdit() {
  if (!studio.project) return
  bpmDraft.value = studio.project.bpm
  editingBpm.value = true
}
async function commitBpm() {
  editingBpm.value = false
  const p = studio.project
  const v = Math.round(Number(bpmDraft.value))
  if (!p || !Number.isFinite(v) || v < 30 || v > 300 || v === p.bpm) return
  p.bpm = v
  await studio.saveProject()   // fingerprints change → re-render on next ▶
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
      <input v-if="editingBpm" v-model.number="bpmDraft" type="number" min="30" max="300"
             class="bpm-input" autofocus
             @blur="commitBpm" @keyup.enter="($event.target as HTMLInputElement).blur()" />
      <button v-else class="bpm-btn dim" :title="t('transport.bpmTip')" @click="startBpmEdit">
        {{ studio.project.bpm }} BPM</button>
      <span class="dim" :title="t('transport.tempoTip')">
        · {{ studio.project.key }} · {{ studio.project.time_signature }}</span>
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
.bpm-btn { border: none; background: transparent; padding: 2px 4px; font-size: 13px; }
.bpm-btn:hover { color: var(--accent); border: none; }
.bpm-input { width: 64px; padding: 2px 6px; font-size: 13px; }
button.active { border-color: var(--accent); color: var(--accent); }
</style>
