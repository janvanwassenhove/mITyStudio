<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { api } from '../api/client'
import type { Asset, SongProject } from '../api/types'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

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
    if (!track) { recStatus.value = 'could not create a vocal track'; return }
  }
  studio.selectedTrackId = track.id
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
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
          recStatus.value = 'take saved onto ' + tr.name
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
    recStatus.value = 'Microphone unavailable: ' + String(e)
  }
}

function stopRecord() {
  mediaRecorder?.stop()
  recording.value = false
  if (recTimer) clearInterval(recTimer)
  playback.pause()
}

onUnmounted(() => { if (recording.value) stopRecord() })
</script>

<template>
  <div class="transport panel">
    <button title="Stop" @click="playback.stop()">⏹</button>
    <button class="primary" :title="playback.playing ? 'Pause' : 'Play'"
            :disabled="!studio.manifest || playback.preparing"
            @click="playback.playing ? playback.pause() : playback.play()">
      {{ playback.preparing ? '⏳' : playback.playing ? '⏸' : '▶' }}
    </button>
    <button :class="{ 'rec-on': recording }" :disabled="!studio.project"
            :title="recording ? 'Stop recording' : 'Record a vocal take (sing along from the playhead)'"
            @click="toggleRecord">
      {{ recording ? '■ ' + recSeconds + 's' : '🎙' }}
    </button>
    <button :class="{ active: playback.metronome }" title="Metronome"
            @click="playback.metronome = !playback.metronome">🕐</button>
    <button :disabled="!studio.canUndo" title="Undo (Ctrl+Z)" @click="studio.undo()">↶</button>
    <button :disabled="!studio.canRedo" title="Redo (Ctrl+Shift+Z)" @click="studio.redo()">↷</button>
    <button class="time-toggle" :title="'Switch ruler to ' + (studio.timeMode === 'bars' ? 'seconds' : 'bars')"
            @click="studio.timeMode = studio.timeMode === 'bars' ? 'seconds' : 'bars'">
      <span class="time">{{ studio.timeMode === 'bars' ? 'bar ' + barBeat : timeDisplay }}</span>
      <span class="dim small">{{ studio.timeMode === 'bars' ? timeDisplay : 'bar ' + barBeat }}</span>
    </button>
    <span v-if="playback.preparing" class="preparing">preparing audio…</span>
    <span v-if="recStatus" class="dim small">{{ recStatus }}</span>
    <span class="spacer" />
    <template v-if="studio.project">
      <span class="title">{{ studio.project.title }}</span>
      <span class="dim" title="Tempo (beats per minute) · musical key · time signature — change them via chat: “make it 140 bpm”, “change key to A minor”">
        {{ studio.project.bpm }} BPM · {{ studio.project.key }} · {{ studio.project.time_signature }}</span>
      <span v-if="studio.manifest && studio.manifest.stems.length" class="dim"
            title="Stems are the rendered audio files, one per track. They render automatically when you press play and load here for playback.">
        · {{ playback.stemsLoaded }}/{{ studio.manifest.stems.length }} stems loaded
      </span>
    </template>
    <span v-else class="dim">no project open</span>
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
button.active { border-color: var(--accent); color: var(--accent); }
</style>
