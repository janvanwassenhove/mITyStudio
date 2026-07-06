<script setup lang="ts">
import { computed } from 'vue'
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
</script>

<template>
  <div class="transport panel">
    <button title="Stop" @click="playback.stop()">⏹</button>
    <button class="primary" :title="playback.playing ? 'Pause' : 'Play'"
            :disabled="!studio.manifest"
            @click="playback.playing ? playback.pause() : playback.play()">
      {{ playback.playing ? '⏸' : '▶' }}
    </button>
    <span class="time">{{ timeDisplay }}</span>
    <span class="dim">bar {{ barBeat }}</span>
    <span class="spacer" />
    <template v-if="studio.project">
      <span class="title">{{ studio.project.title }}</span>
      <span class="dim">{{ studio.project.bpm }} BPM · {{ studio.project.key }} · {{ studio.project.time_signature }}</span>
      <span v-if="studio.manifest && studio.manifest.stems.length" class="dim">
        · {{ playback.stemsLoaded }}/{{ studio.manifest.stems.length }} stems loaded
      </span>
    </template>
    <span v-else class="dim">no project open</span>
  </div>
</template>

<style scoped>
.transport { display: flex; align-items: center; gap: 12px; padding: 8px 12px; }
.time { font-family: 'Consolas', monospace; font-size: 16px; min-width: 64px; }
.title { font-weight: 600; }
.spacer { flex: 1; }
</style>
