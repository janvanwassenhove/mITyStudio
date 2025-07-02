<template>
  <div id="app" class="app-container">
    <AppHeader />
    <main class="main-content">
      <div class="workspace">
        <div class="left-panel">
          <TrackControls />
        </div>
        <div class="center-panel">
          <PlaybackControls />
          <TimelineEditor />
        </div>
        <div class="right-panel">
          <RightPanelToggle />
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAudioStore } from './stores/audioStore'
import AppHeader from './components/AppHeader.vue'
import TrackControls from './components/TrackControls.vue'
import PlaybackControls from './components/PlaybackControls.vue'
import TimelineEditor from './components/TimelineEditor.vue'
import RightPanelToggle from './components/RightPanelToggle.vue'

const audioStore = useAudioStore()

onMounted(() => {
  audioStore.initializeAudio()
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--background);
}

.main-content {
  flex: 1;
  overflow: hidden;
}

.workspace {
  display: grid;
  grid-template-columns: 300px 1fr 350px;
  height: 100%;
  gap: 1px;
  background: var(--border);
}

.left-panel,
.center-panel,
.right-panel {
  background: var(--background);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.left-panel {
  border-right: 1px solid var(--border);
}

.right-panel {
  border-left: 1px solid var(--border);
}

@media (max-width: 1200px) {
  .workspace {
    grid-template-columns: 280px 1fr 320px;
  }
}

@media (max-width: 768px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto;
  }
  
  .left-panel,
  .right-panel {
    border: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>
