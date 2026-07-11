<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { History, Mic, Pencil } from 'lucide-vue-next'
import { api } from '../api/client'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'

const { t } = useI18n()
const studio = useStudioStore()
const playback = usePlaybackStore()

// --- "sing these lyrics": lyrics exist but not every lyric section is sung
const hasLyrics = computed(() => (studio.project?.lyrics.lines.length ?? 0) > 0)
const unsungSections = computed(() => {
  const p = studio.project
  if (!p) return 0
  const vocal = p.tracks.filter((t) => ['lead_vocal', 'backing_vocal'].includes(t.track_type))
  const sungSectionIds = new Set(vocal.flatMap((t) => t.clips)
    .filter((c) => c.note_events.length).map((c) => c.section_id))
  const lyricSectionIds = new Set(p.lyrics.lines.map((l) => l.section_id).filter(Boolean))
  return [...lyricSectionIds].filter((id) => !sungSectionIds.has(id)).length
})

const singing = ref(false)
const singMsg = ref('')
async function singLyrics() {
  const p = studio.project
  if (!p) return
  singing.value = true
  singMsg.value = ''
  try {
    const r = await api.post<{ sections_sung: number; errors: string[] }>(
      `/projects/${p.id}/vocals/sing-lyrics`)
    await studio.reloadCurrent()
    singMsg.value = r.errors.length
      ? r.errors.join('; ')
      : t('lyrics.melodyWritten', { n: r.sections_sung })
  } catch (e) {
    singMsg.value = String(e)
  } finally {
    singing.value = false
  }
}

const mode = ref<'full' | 'karaoke'>('full')
const lines = computed(() => studio.manifest?.lyrics_alignment ?? [])

// --- inline editing + version history --------------------------------------
const editMode = ref(false)
const needsRender = ref(false)
const savingLine = ref('')

async function saveLine(lineId: string, ev: Event) {
  const p = studio.project
  if (!p) return
  const text = (ev.target as HTMLInputElement).value.trim()
  savingLine.value = lineId
  try {
    const r = await api.put<{ changed: boolean; needs_render?: boolean }>(
      `/projects/${p.id}/lyrics/lines/${lineId}`, { text })
    if (r.changed) {
      if (r.needs_render) needsRender.value = true
      await studio.reloadCurrent()
    }
  } catch (e) {
    singMsg.value = String(e)
  } finally {
    savingLine.value = ''
  }
}

interface LyricsVersion { id: string; timestamp: string; label: string; line_count: number; preview: string }
const showHistory = ref(false)
const history = ref<LyricsVersion[]>([])

async function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value && studio.project) {
    history.value = await api.get<LyricsVersion[]>(
      `/projects/${studio.project.id}/lyrics/history`)
  }
}

async function restoreVersion(v: LyricsVersion) {
  const p = studio.project
  if (!p) return
  try {
    const r = await api.post<{ needs_render?: boolean }>(
      `/projects/${p.id}/lyrics/restore/${v.id}`)
    if (r.needs_render) needsRender.value = true
    showHistory.value = false
    await studio.reloadCurrent()
  } catch (e) {
    singMsg.value = String(e)
  }
}

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
  for (const [sid, rest] of bySection) out.push({ name: sid ? t('lyrics.other') : t('lyrics.unassigned'), lines: rest })
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
      <button :class="{ active: mode === 'full' }" @click="mode = 'full'">{{ t('lyrics.fullSong') }}</button>
      <button :class="{ active: mode === 'karaoke' }" @click="mode = 'karaoke'">{{ t('lyrics.karaoke') }}</button>
      <button v-if="hasLyrics && unsungSections > 0" class="sing-btn"
              :disabled="singing" @click="singLyrics">
        <template v-if="singing">{{ t('lyrics.writingMelody') }}</template>
        <template v-else><Mic class="icon" :size="12" /> {{ t('lyrics.singThese', { n: unsungSections }) }}</template>
      </button>
      <button v-if="hasLyrics" class="mode-bar-btn" :class="{ active: editMode }"
              :title="t('lyrics.editTip')" @click="editMode = !editMode">
        <Pencil class="icon" :size="12" /> {{ t('lyrics.edit') }}
      </button>
      <button v-if="hasLyrics" class="mode-bar-btn" :class="{ active: showHistory }"
              :title="t('lyrics.historyTip')" @click="toggleHistory">
        <History class="icon" :size="12" /> {{ t('lyrics.history') }}
      </button>
      <span v-if="needsRender" class="render-chip">{{ t('lyrics.needsRender') }}</span>
      <span class="dim small sing-msg">{{ singMsg }}</span>
      <span class="dim small" style="margin-left: auto">
        {{ lines.length ? t('lyrics.timingHint')
           : hasLyrics && unsungSections > 0 ? t('lyrics.melodyFirst')
           : t('lyrics.pressPlay') }}
      </span>
    </div>

    <!-- version history -->
    <div v-if="showHistory" class="history panel">
      <div v-if="!history.length" class="dim small" style="padding: 8px">{{ t('lyrics.noHistory') }}</div>
      <div v-for="v in history" :key="v.id" class="hist-row">
        <span class="dim small">{{ v.timestamp.replace('T', ' ').replace('+00:00', '') }} · {{ t('lyrics.v.' + v.label) }} · {{ v.line_count }}</span>
        <span class="hist-preview dim small">“{{ v.preview }}…”</span>
        <button class="tiny-btn" @click="restoreVersion(v)">{{ t('lyrics.restore') }}</button>
      </div>
    </div>

    <!-- full-song sheet -->
    <div v-if="mode === 'full'" class="sheet" :class="{ editing: editMode }">
      <div v-if="!sheet.length" class="dim center-msg">
        {{ t('lyrics.empty') }}
      </div>
      <div v-for="sec in sheet" :key="sec.name" class="sheet-section">
        <div class="sec-name">{{ sec.name }}</div>
        <template v-if="editMode">
          <input
            v-for="l in sec.lines" :key="l.id" class="sheet-edit"
            :value="l.text" :disabled="savingLine === l.id"
            @keyup.enter="($event.target as HTMLInputElement).blur()"
            @blur="saveLine(l.id, $event)"
          />
        </template>
        <template v-else>
          <div
            v-for="l in sec.lines" :key="l.id" class="sheet-line"
            :class="{ active: l.id === activeLineId, clickable: l.start != null }"
            @click="seekToLine(l.start)"
          >{{ l.text }}</div>
        </template>
      </div>
    </div>

    <!-- karaoke -->
    <div v-else class="karaoke">
      <div v-if="!lines.length" class="dim center-msg">
        {{ hasLyrics && unsungSections > 0 ? t('lyrics.noMelodyYet') : t('lyrics.noTimingYet') }}
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
.sing-btn { background: var(--accent) !important; color: #fff !important; border-radius: 5px !important; margin-left: 10px; padding: 3px 12px !important; }
.sing-msg { max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mode-bar-btn { display: inline-flex; align-items: center; gap: 4px; }
.mode-bar-btn.active { color: var(--accent) !important; }
.render-chip { font-size: 11px; color: var(--warn); border: 1px solid var(--warn); border-radius: 10px; padding: 1px 8px; }
.history { margin: 6px 10px 0; max-height: 160px; overflow-y: auto; }
.hist-row { display: flex; gap: 10px; align-items: center; padding: 4px 10px; border-bottom: 1px solid var(--border); }
.hist-preview { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tiny-btn { font-size: 11px; padding: 1px 8px; }
.sheet-edit { display: block; width: 100%; margin: 2px 0; font-size: 13px; padding: 3px 6px; }
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
