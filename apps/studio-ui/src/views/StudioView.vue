<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useStudioStore } from '../stores/studio'
import TransportControls from '../components/TransportControls.vue'
import ProjectSidebar from '../components/ProjectSidebar.vue'
import TimelinePanel from '../components/TimelinePanel.vue'
import MixerPanel from '../components/MixerPanel.vue'
import ChatPanel from '../components/ChatPanel.vue'
import ExportPanel from '../components/ExportPanel.vue'
import LyricsKaraokeView from '../components/LyricsKaraokeView.vue'

const studio = useStudioStore()
const rightTab = ref<'chat' | 'export'>('chat')
const bottomTab = ref<'mixer' | 'karaoke'>('mixer')

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
        <div class="bottom panel">
          <div class="tabs">
            <button :class="{ active: bottomTab === 'mixer' }" @click="bottomTab = 'mixer'">Mixer</button>
            <button :class="{ active: bottomTab === 'karaoke' }" @click="bottomTab = 'karaoke'">Karaoke</button>
          </div>
          <MixerPanel v-if="bottomTab === 'mixer'" />
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
.bottom { height: 240px; flex: none; display: flex; flex-direction: column; overflow: hidden; }
.rightbar { width: 340px; flex: none; display: flex; flex-direction: column; overflow: hidden; }
.tabs { display: flex; gap: 4px; padding: 6px; border-bottom: 1px solid var(--border); flex: none; }
.tabs button { padding: 4px 10px; font-size: 12px; border: none; background: transparent; color: var(--text-dim); }
.tabs button.active { color: var(--text); background: var(--bg-elevated); border-radius: 4px; }
</style>
