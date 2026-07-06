<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStudioStore } from '../stores/studio'
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

const studio = useStudioStore()
const rightTab = ref<'chat' | 'export'>('chat')
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

onMounted(() => studio.refreshProjects())
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
          <div class="resize-handle" title="drag to resize" @pointerdown="startResize" />
          <div class="tabs">
            <button :class="{ active: bottomTab === 'mixer' }" @click="bottomTab = 'mixer'">Mixer</button>
            <button :class="{ active: bottomTab === 'track' }" @click="bottomTab = 'track'">Track</button>
            <button :class="{ active: bottomTab === 'editor' }" @click="bottomTab = 'editor'">Editor</button>
            <button :class="{ active: bottomTab === 'samples' }" @click="bottomTab = 'samples'">Samples</button>
            <button :class="{ active: bottomTab === 'lyrics' }" @click="bottomTab = 'lyrics'">Lyrics</button>
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
          <button :class="{ active: rightTab === 'chat' }" @click="rightTab = 'chat'">Chat</button>
          <button :class="{ active: rightTab === 'export' }" @click="rightTab = 'export'">Export</button>
        </div>
        <ChatPanel v-if="rightTab === 'chat'" />
        <ExportPanel v-else />
      </aside>
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
.rightbar { width: 340px; flex: none; display: flex; flex-direction: column; overflow: hidden; }
.tabs { display: flex; gap: 4px; padding: 6px; border-bottom: 1px solid var(--border); flex: none; }
.tabs button { padding: 4px 10px; font-size: 12px; border: none; background: transparent; color: var(--text-dim); }
.tabs button.active { color: var(--text); background: var(--bg-elevated); border-radius: 4px; }
</style>
