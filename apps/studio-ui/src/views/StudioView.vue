<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStudioStore } from '../stores/studio'
import { usePlaybackStore } from '../stores/playback'
import TransportControls from '../components/TransportControls.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import TimelinePanel from '../components/TimelinePanel.vue'
import MixerPanel from '../components/MixerPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ExportPanel from '../components/ExportPanel.vue'
import LyricsKaraokeView from '../components/LyricsKaraokeView.vue'
import TrackInspector from '../components/TrackInspector.vue'
import SampleBrowser from '../components/SampleBrowser.vue'
import ClipEditor from '../components/ClipEditor.vue'

const { t } = useI18n()
const studio = useStudioStore()
const rightTab = ref<'chat' | 'export'>('chat')

// context-aware tab labels: show WHAT the Track/Editor tabs will act on
const selTrackName = computed(() =>
  studio.project?.tracks.find((x) => x.id === studio.selectedTrackId)?.name ?? '')
const selClipTrackName = computed(() => {
  const sel = studio.selectedClip
  if (!sel) return ''
  return studio.project?.tracks.find((x) => x.id === sel.trackId)?.name ?? ''
})
const short = (s: string) => (s.length > 12 ? s.slice(0, 11) + '…' : s)
const bottomTab = ref<'mixer' | 'track' | 'editor' | 'samples' | 'lyrics'>('mixer')

watch(() => studio.editorRequest, () => { bottomTab.value = 'editor' })
watch(() => studio.inspectorRequest, () => { bottomTab.value = 'track' })

// resizable bottom panel
const bottomH = ref(280)
function startResize(e: PointerEvent) {
  const y0 = e.clientY
  const h0 = bottomH.value
  const move = (ev: PointerEvent) => {
    bottomH.value = Math.min(Math.max(h0 + (y0 - ev.clientY), 150),
                             window.innerHeight * 0.75)
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup',
    () => window.removeEventListener('pointermove', move), { once: true })
}

// --- keyboard shortcuts -----------------------------------------------------
const playback = usePlaybackStore()
const showShortcuts = ref(false)

function inTextField(e: KeyboardEvent): boolean {
  const t = e.target as HTMLElement
  return ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName) || t.isContentEditable
}

async function deleteSelectedClip() {
  const p = studio.project
  const sel = studio.selectedClip
  if (!p || !sel) return
  const track = p.tracks.find((t) => t.id === sel.trackId)
  if (!track) return
  track.clips = track.clips.filter((c) => c.id !== sel.clipId)
  studio.selectedClip = null
  await studio.saveProject()
}

function onKeydown(e: KeyboardEvent) {
  if (inTextField(e)) return
  const mod = e.ctrlKey || e.metaKey
  if (e.code === 'Space') {
    e.preventDefault()
    if (studio.manifest) playback.playing ? playback.pause() : void playback.play()
  } else if (mod && !e.shiftKey && e.key.toLowerCase() === 'z') {
    e.preventDefault()
    void studio.undo()
  } else if ((mod && e.shiftKey && e.key.toLowerCase() === 'z') ||
             (mod && e.key.toLowerCase() === 'y')) {
    e.preventDefault()
    void studio.redo()
  } else if ((e.key === 'Delete' || e.key === 'Backspace') && studio.selectedClip) {
    e.preventDefault()
    void deleteSelectedClip()
  } else if (e.key === '?') {
    showShortcuts.value = !showShortcuts.value
  } else if (e.key === 'Escape') {
    showShortcuts.value = false
  }
}

onMounted(async () => {
  await studio.refreshProjects()
  window.addEventListener('keydown', onKeydown)
  // deep link: /?project=<id> opens a project directly (docs, screenshots)
  const wanted = new URLSearchParams(window.location.search).get('project')
  if (wanted) void studio.openProject(wanted)
})
onUnmounted(() => window.removeEventListener('keydown', onKeydown))

const SHORTCUTS = computed(() => [
  ['Space', t('shortcuts.playPause')],
  ['Ctrl+Z', t('shortcuts.undo')],
  ['Ctrl+Shift+Z / Ctrl+Y', t('shortcuts.redo')],
  ['Delete', t('shortcuts.deleteClip')],
  [t('shortcuts.dblClickClip'), t('shortcuts.openClipEditor')],
  [t('shortcuts.dblClickTrack'), t('shortcuts.openInspector')],
  [t('shortcuts.dragRuler'), t('shortcuts.scrub')],
  ['?', t('shortcuts.toggleHelp')],
])
</script>

<template>
  <div class="studio">
    <div class="transport-row">
      <TransportControls />
    </div>
    <div class="body-row">
      <aside class="sidebar panel"><ProjectSidebar /></aside>
      <section class="center">
        <div class="timeline panel"><TimelinePanel /></div>
        <div class="bottom panel" :style="{ height: bottomH + 'px' }">
          <div class="resize-handle" :title="t('studio.dragResize')" @pointerdown="startResize" />
          <div class="tabs">
            <button :class="{ active: bottomTab === 'mixer' }" @click="bottomTab = 'mixer'">{{ t('studio.mixer') }}</button>
            <button :class="{ active: bottomTab === 'track' }" @click="bottomTab = 'track'">
              {{ t('studio.track') }}<span v-if="selTrackName" class="tab-ctx"> · {{ short(selTrackName) }}</span></button>
            <button :class="{ active: bottomTab === 'editor' }" @click="bottomTab = 'editor'">
              {{ t('studio.editor') }}<span v-if="selClipTrackName" class="tab-ctx"> · {{ short(selClipTrackName) }}</span></button>
            <button :class="{ active: bottomTab === 'samples' }" @click="bottomTab = 'samples'">{{ t('studio.samples') }}</button>
            <button :class="{ active: bottomTab === 'lyrics' }" @click="bottomTab = 'lyrics'">{{ t('studio.lyrics') }}</button>
          </div>
          <MixerPanel v-if="bottomTab === 'mixer'" />
          <TrackInspector v-else-if="bottomTab === 'track'" />
          <ClipEditor v-else-if="bottomTab === 'editor'" />
          <SampleBrowser v-else-if="bottomTab === 'samples'" />
          <LyricsKaraokeView v-else />
        </div>
      </section>
      <aside class="rightbar panel">
        <div class="tabs">
          <button :class="{ active: rightTab === 'chat' }" @click="rightTab = 'chat'">{{ t('studio.chat') }}</button>
          <button :class="{ active: rightTab === 'export' }" @click="rightTab = 'export'">{{ t('studio.export') }}</button>
        </div>
        <ChatPanel v-if="rightTab === 'chat'" />
        <ExportPanel v-else />
      </aside>
    </div>

    <!-- keyboard shortcuts reference (press ?) -->
    <div v-if="showShortcuts" class="shortcuts-overlay" @click.self="showShortcuts = false">
      <div class="shortcuts panel">
        <h3>{{ t('shortcuts.title') }}</h3>
        <table>
          <tr v-for="[key, desc] in SHORTCUTS" :key="key">
            <td><kbd>{{ key }}</kbd></td>
            <td>{{ desc }}</td>
          </tr>
        </table>
        <button @click="showShortcuts = false">{{ t('shortcuts.close') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio { display: flex; flex-direction: column; height: 100%; padding: 8px; gap: 8px; }
.transport-row { flex: none; }
.body-row { flex: 1; display: flex; gap: 8px; min-height: 0; }
.sidebar { width: 230px; flex: none; overflow-y: auto; }
.center { flex: 1; display: flex; flex-direction: column; gap: 8px; min-width: 0; }
.timeline { flex: 1; min-height: 0; overflow: hidden; }
.bottom { flex: none; display: flex; flex-direction: column; overflow: hidden; position: relative; }
.resize-handle { height: 5px; cursor: ns-resize; flex: none; background: transparent; }
.resize-handle:hover { background: var(--accent); opacity: 0.5; }
.shortcuts-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 60; }
.shortcuts { padding: 20px 26px; display: flex; flex-direction: column; gap: 12px; }
.shortcuts h3 { margin: 0; }
.shortcuts td { padding: 3px 14px 3px 0; font-size: 13px; }
.shortcuts kbd { background: var(--bg-elevated); border: 1px solid var(--border); border-radius: 4px; padding: 1px 7px; font-size: 12px; }
.rightbar { width: 340px; flex: none; display: flex; flex-direction: column; overflow: hidden; }
.tabs { display: flex; gap: 4px; padding: 6px; border-bottom: 1px solid var(--border); flex: none; }
.tabs button { padding: 4px 10px; font-size: 12px; border: none; background: transparent; color: var(--text-dim); }
.tabs button.active { color: var(--text); background: var(--bg-elevated); border-radius: 4px; }
.tab-ctx { color: var(--accent); font-weight: 600; }
</style>
