<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { PackageOpen } from 'lucide-vue-next'
import { api } from '../api/client'
import { useStudioStore } from '../stores/studio'
import ContextMenu, { type MenuItem } from './ContextMenu.vue'

const { t } = useI18n()
const studio = useStudioStore()
const newTitle = ref('')
const creating = ref(false)
const busyMsg = ref('')

// inline rename + delete confirm — Electron does NOT support window.prompt()
// (returns null) and confirm() is unreliable, so we use in-app UI instead
const renamingId = ref('')
const renameDraft = ref('')
const renameInput = ref<HTMLInputElement | null>(null)
const confirmDeleteId = ref('')

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

// --- right-click context menu -----------------------------------------------
const menu = ref<{ x: number; y: number; items: MenuItem[] } | null>(null)

function projectMenu(e: MouseEvent, p: { id: string; title: string }) {
  e.preventDefault()
  const isOpen = studio.project?.id === p.id
  menu.value = {
    x: e.clientX, y: e.clientY,
    items: [
      // "Open" is redundant when it's already the open project, so label it
      // honestly and no-op gracefully rather than looking broken
      { label: isOpen ? t('ctx.reload') : t('ctx.open'),
        action: () => void studio.openProject(p.id) },
      { label: t('ctx.rename'), action: () => startRename(p) },
      { label: t('ctx.exportBundle'), action: () => exportBundle(p) },
      { label: t('ctx.delete'), danger: true,
        action: () => { confirmDeleteId.value = p.id } },
    ],
  }
}

function startRename(p: { id: string; title: string }) {
  renamingId.value = p.id
  renameDraft.value = p.title
  void nextTick(() => {
    const el = renameInput.value as HTMLInputElement | HTMLInputElement[] | null
    ;(Array.isArray(el) ? el[0] : el)?.focus()
  })
}

async function commitRename(p: { id: string; title: string }) {
  const title = renameDraft.value.trim()
  renamingId.value = ''
  if (!title || title === p.title) return
  const proj = await api.get<{ [k: string]: unknown }>(`/projects/${p.id}`)
  proj.title = title
  await api.put(`/projects/${p.id}`, proj)
  await studio.refreshProjects()
  if (studio.project?.id === p.id) await studio.reloadCurrent()
}

async function deleteProject(id: string) {
  confirmDeleteId.value = ''
  await api.del(`/projects/${id}`)
  if (studio.project?.id === id) studio.project = null
  await studio.refreshProjects()
}

function exportBundle(p: { id: string }) {
  window.open(`/api/projects/${p.id}/export/bundle`, '_blank')
}

// --- import a portable project bundle ----------------------------------------
const importInput = ref<HTMLInputElement | null>(null)

async function importBundle() {
  const f = importInput.value?.files?.[0]
  if (!f) return
  busyMsg.value = t('ctx.importing')
  try {
    const r = await api.upload<{ project_id: string; title: string; warnings: string[] }>(
      '/projects/import', f, f.name)
    busyMsg.value = r.warnings.length ? r.warnings.join('; ')
      : t('ctx.imported', { name: r.title })
    await studio.refreshProjects()
    await studio.openProject(r.project_id)
  } catch (e) {
    busyMsg.value = String(e)
  } finally {
    if (importInput.value) importInput.value.value = ''
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
    <div class="import-row">
      <input ref="importInput" type="file" accept=".zip" style="display: none" @change="importBundle" />
      <button class="import-btn" :title="$t('ctx.importTip')" @click="importInput?.click()">
        <PackageOpen class="icon" :size="12" /> {{ $t('ctx.importBundle') }}
      </button>
    </div>
    <div v-if="busyMsg" class="dim small">{{ busyMsg }}</div>
    <div v-if="!studio.projects.length" class="dim empty">
      {{ $t('sidebar.empty') }}
    </div>
    <div
      v-for="p in studio.projects" :key="p.id"
      class="project-item" :class="{ active: studio.project?.id === p.id }"
      :title="$t('ctx.rightClickTip')"
      @click="renamingId === p.id ? null : studio.openProject(p.id)"
      @contextmenu="projectMenu($event, p)"
    >
      <input v-if="renamingId === p.id" ref="renameInput" v-model="renameDraft"
             class="rename-input" @click.stop
             @keyup.enter="($event.target as HTMLInputElement).blur()"
             @keyup.esc="renamingId = ''"
             @blur="commitRename(p)" />
      <div v-else class="p-title">{{ p.title }}</div>
      <div class="dim small">{{ p.bpm }} BPM · {{ $t('sidebar.trackCount', { n: p.track_count }) }}</div>
      <div v-if="confirmDeleteId === p.id" class="del-confirm" @click.stop>
        <span class="dim small">{{ $t('ctx.deleteConfirm', { name: p.title }) }}</span>
        <div class="del-btns">
          <button class="danger-btn" @click="deleteProject(p.id)">{{ $t('common.delete') }}</button>
          <button @click="confirmDeleteId = ''">{{ $t('common.cancel') }}</button>
        </div>
      </div>
    </div>
    <ContextMenu v-if="menu" :x="menu.x" :y="menu.y" :items="menu.items" @close="menu = null" />
  </div>
</template>

<style scoped>
.sidebar-content { padding: 12px; }
h3 { margin: 0 0 10px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-dim); }
.new-project { display: flex; gap: 6px; margin-bottom: 6px; }
.new-project input { flex: 1; min-width: 0; }
.import-row { margin-bottom: 10px; }
.import-btn { font-size: 11px; padding: 3px 8px; width: 100%; }
.empty { font-size: 12px; }
.project-item { padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; }
.project-item:hover { background: var(--bg-elevated); }
.rename-input { width: 100%; font-size: 13px; padding: 3px 6px; margin-bottom: 2px; }
.del-confirm { margin-top: 6px; padding: 6px; border: 1px solid var(--err); border-radius: 5px; display: flex; flex-direction: column; gap: 6px; }
.del-btns { display: flex; gap: 6px; }
.del-btns button { font-size: 11px; padding: 3px 10px; }
.danger-btn { border-color: var(--err); color: var(--err); }
.project-item.active { background: var(--bg-elevated); outline: 1px solid var(--accent); }
.p-title { font-size: 13px; font-weight: 600; }
.small { font-size: 11px; }
</style>
