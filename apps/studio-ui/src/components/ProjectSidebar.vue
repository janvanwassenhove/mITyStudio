<script setup lang="ts">
import { ref } from 'vue'
import { useStudioStore } from '../stores/studio'

const studio = useStudioStore()
const newTitle = ref('')
const creating = ref(false)

async function create() {
  if (!newTitle.value.trim()) return
  creating.value = true
  try {
    await studio.createProject(newTitle.value.trim())
    newTitle.value = ''
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <div class="sidebar-content">
    <h3>{{ $t('sidebar.projects') }}</h3>
    <div class="new-project">
      <input v-model="newTitle" :placeholder="$t('sidebar.newProject')" @keyup.enter="create" />
      <button class="primary" :disabled="creating || !newTitle.trim()" @click="create">+</button>
    </div>
    <div v-if="!studio.projects.length" class="dim empty">
      {{ $t('sidebar.empty') }}
    </div>
    <div
      v-for="p in studio.projects" :key="p.id"
      class="project-item" :class="{ active: studio.project?.id === p.id }"
      @click="studio.openProject(p.id)"
    >
      <div class="p-title">{{ p.title }}</div>
      <div class="dim small">{{ p.bpm }} BPM · {{ $t('sidebar.trackCount', { n: p.track_count }) }}</div>
    </div>
  </div>
</template>

<style scoped>
.sidebar-content { padding: 12px; }
h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); }
.new-project { display: flex; gap: 6px; margin-bottom: 12px; }
.new-project input { flex: 1; min-width: 0; }
.empty { font-size: 12px; }
.project-item { padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; }
.project-item:hover { background: var(--bg-elevated); }
.project-item.active { background: var(--bg-elevated); outline: 1px solid var(--accent); }
.p-title { font-size: 13px; font-weight: 600; }
.small { font-size: 11px; }
</style>
