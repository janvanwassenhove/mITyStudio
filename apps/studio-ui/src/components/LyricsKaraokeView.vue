<script setup lang="ts">
import { computed } from 'vue'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

const studio = useStudioStore()
const playback = usePlaybackStore()

const lines = computed(() => studio.manifest?.lyrics_alignment ?? [])

const currentIndex = computed(() => {
  const t = playback.playhead
  return lines.value.findIndex((l) => t >= l.start_time && t < l.end_time)
})
const currentLine = computed(() => (currentIndex.value >= 0 ? lines.value[currentIndex.value] : null))
const nextLine = computed(() => {
  const t = playback.playhead
  if (currentIndex.value >= 0) return lines.value[currentIndex.value + 1] ?? null
  return lines.value.find((l) => l.start_time > t) ?? null
})
const sectionName = computed(() => {
  const sid = currentLine.value?.section_id
  if (!sid) return ''
  return studio.manifest?.sections.find((s) => s.section_id === sid)?.name ?? ''
})

function wordActive(w: { start_time: number; end_time: number }): boolean {
  return playback.playhead >= w.start_time && playback.playhead < w.end_time
}
function wordPast(w: { end_time: number }): boolean {
  return playback.playhead >= w.end_time
}
</script>

<template>
  <div class="karaoke">
    <div v-if="!lines.length" class="dim center-msg">
      No lyric timing yet — render a vocal track to enable karaoke.
    </div>
    <template v-else>
      <div class="section dim">{{ sectionName }}</div>
      <div class="current">
        <template v-if="currentLine">
          <span
            v-for="(w, i) in currentLine.words" :key="i" class="word"
            :class="{ active: wordActive(w), past: wordPast(w) }"
          >{{ w.word }}&nbsp;</span>
        </template>
        <span v-else class="dim">♪</span>
      </div>
      <div class="next dim">{{ nextLine?.text ?? '' }}</div>
    </template>
  </div>
</template>

<style scoped>
.karaoke { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 10px; padding: 12px; }
.center-msg { font-size: 13px; }
.section { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; }
.current { font-size: 22px; font-weight: 700; text-align: center; min-height: 30px; }
.word { color: var(--text-dim); transition: color 0.1s; }
.word.past { color: var(--text); }
.word.active { color: var(--accent); }
.next { font-size: 14px; text-align: center; }
</style>
