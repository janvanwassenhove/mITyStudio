import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { PlaybackManifest, ProjectSummary, SongProject } from '../api/types'

export const useStudioStore = defineStore('studio', () => {
  const projects = ref<ProjectSummary[]>([])
  const project = ref<SongProject | null>(null)
  const manifest = ref<PlaybackManifest | null>(null)
  const selectedTrackId = ref<string | null>(null)
  const selectedClip = ref<{ trackId: string; clipId: string } | null>(null)
  const editorRequest = ref(0)     // bumped to open the clip editor tab
  const inspectorRequest = ref(0)  // bumped to open the track inspector tab
  const timeMode = ref<'bars' | 'seconds'>('bars')

  function openTrackInspector(trackId: string) {
    selectedTrackId.value = trackId
    inspectorRequest.value++
  }
  const loading = ref(false)
  const error = ref('')

  function openClipEditor(trackId: string, clipId: string) {
    selectedTrackId.value = trackId
    selectedClip.value = { trackId, clipId }
    editorRequest.value++
  }

  async function refreshProjects() {
    projects.value = await api.get<ProjectSummary[]>('/projects')
  }

  async function openProject(id: string) {
    loading.value = true
    error.value = ''
    try {
      project.value = await api.get<SongProject>(`/projects/${id}`)
      manifest.value = await api.get<PlaybackManifest>(`/projects/${id}/playback-manifest`)
    } catch (e) {
      error.value = String(e)
    } finally {
      loading.value = false
    }
  }

  async function reloadCurrent() {
    if (project.value) await openProject(project.value.id)
  }

  async function createProject(title: string, style = '', bpm = 120) {
    const p = await api.post<SongProject>('/projects', { title, style, bpm })
    await refreshProjects()
    await openProject(p.id)
    return p
  }

  async function saveProject() {
    if (!project.value) return
    project.value = await api.put<SongProject>(`/projects/${project.value.id}`, project.value)
    manifest.value = await api.get<PlaybackManifest>(`/projects/${project.value.id}/playback-manifest`)
  }

  return {
    projects, project, manifest, selectedTrackId, selectedClip, editorRequest,
    inspectorRequest, timeMode, loading, error, openClipEditor,
    openTrackInspector,
    refreshProjects, openProject, reloadCurrent, createProject, saveProject,
  }
})
