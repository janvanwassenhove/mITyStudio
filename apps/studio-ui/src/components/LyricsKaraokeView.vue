<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

const studio = useStudioStore()
const playback = usePlaybackStore()

const mode = ref<'full' | 'karaoke'>('full')
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

function wordActive(w: { start_time: number; end_time: number }): boolean {
  return playback.playhead >= w.start_time && playback.playhead < w.end_time
}
function wordPast(w: { end_time: number }): boolean {
  return playback.playhead >= w.end_time
}

// --- full-song sheet: all lyric lines grouped by section --------------------
interface SheetSection { name: string; lines: { id: string; text: string; start: number | null }[] }
const sheet = computed<SheetSection[]>(() => {
  const p = studio.project
  if (!p) return []
  const alignById = new Map(lines.value.map((l) => [l.line_id, l]))
  const bySection = new Map<string, { id: string; text: string; start: number | null }[]>()
  for (const l of p.lyrics.lines) {
    const arr = bySection.get(l.section_id) ?? []
    arr.push({ id: l.id, text: l.text, start: alignById.get(l.id)?.start_time ?? null })
    bySection.set(l.section_id, arr)
  }
  const out: SheetSection[] = []
  for (const s of [...p.sections].sort((a, b) => a.start_bar - b.start_bar)) {
    const secLines = bySection.get(s.id)
    if (secLines) out.push({ name: s.name, lines: secLines })
    bySection.delete(s.id)
  }
  for (const [sid, rest] of bySection) out.push({ name: sid ? 'Other' : 'Unassigned', lines: rest })
  return out
})

const activeLineId = computed(() => currentLine.value?.line_id ?? null)

function seekToLine(start: number | null) {
  if (start != null) playback.seek(start)
}
</script>

<template>
  <div class="lyrics-root">
    <div class="mode-bar">
      <button :class="{ active: mode === 'full' }" @click="mode = 'full'">Full song</button>
      <button :class="{ active: mode === 'karaoke' }" @click="mode = 'karaoke'">Karaoke</button>
      <span class="dim small" style="margin-left: auto">
        {{ lines.length ? 'timing from rendered vocals — click a line to jump there' : 'render vocals (press ▶) to enable timing' }}
      </span>
    </div>

    <!-- full-song sheet -->
    <div v-if="mode === 'full'" class="sheet">
      <div v-if="!sheet.length" class="dim center-msg">
        No lyrics yet — ask the chat: “add lyrics about … for the whole song”,
        or add a Voice track (＋ Add Track → 🎤).
      </div>
      <div v-for="sec in sheet" :key="sec.name" class="sheet-section">
        <div class="sec-name">{{ sec.name }}</div>
        <div
          v-for="l in sec.lines" :key="l.id" class="sheet-line"
          :class="{ active: l.id === activeLineId, clickable: l.start != null }"
          @click="seekToLine(l.start)"
        >{{ l.text }}</div>
      </div>
    </div>

    <!-- karaoke -->
    <div v-else class="karaoke">
      <div v-if="!lines.length" class="dim center-msg">
        No lyric timing yet — press ▶ (vocals render automatically) to enable karaoke.
      </div>
      <template v-else>
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
  </div>
</template>

<style scoped>
.lyrics-root { display: flex; flex-direction: column; height: 100%; }
.mode-bar { display: flex; gap: 4px; padding: 6px 10px; border-bottom: 1px solid var(--border); flex: none; align-items: center; }
.mode-bar button { padding: 3px 10px; font-size: 12px; border: none; background: transparent; color: var(--text-dim); }
.mode-bar button.active { color: var(--text); background: var(--bg-elevated); border-radius: 4px; }
.small { font-size: 11px; }
.center-msg { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 13px; padding: 20px; text-align: center; }
.sheet { flex: 1; overflow-y: auto; padding: 12px 20px; columns: 2; column-gap: 40px; }
.sheet-section { break-inside: avoid; margin-bottom: 14px; }
.sec-name { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent-2); margin-bottom: 4px; }
.sheet-line { font-size: 13px; line-height: 1.6; color: var(--text-dim); border-radius: 4px; padding: 0 6px; }
.sheet-line.clickable { cursor: pointer; }
.sheet-line.clickable:hover { background: var(--bg-elevated); }
.sheet-line.active { color: var(--accent); font-weight: 700; background: var(--bg-elevated); }
.karaoke { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 12px; }
.current { font-size: 24px; font-weight: 700; text-align: center; min-height: 32px; }
.word { color: var(--text-dim); transition: color 0.1s; }
.word.past { color: var(--text); }
.word.active { color: var(--accent); }
.next { font-size: 14px; text-align: center; }
</style>
