<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Sparkles } from 'lucide-vue-next'
import { api } from '../api/client'
import { currentLocale } from '../i18n'
import { useStudioStore } from '../stores/studio'

const emit = defineEmits<{ close: [] }>()
const { t, te } = useI18n()
const studio = useStudioStore()

const prompt = ref('')
const force = ref(false)
const busy = ref(false)
const error = ref('')
const done = ref(false)

interface PipelineJob {
  status: 'running' | 'done' | 'error'
  stage: string
  progress: number
  log: string[]
  summary?: string
  error?: string
}
const job = ref<PipelineJob | null>(null)

const needsForce = computed(() =>
  (studio.project?.tracks ?? []).some((tr) => tr.clips.length > 0))

function stageLabel(stage: string): string {
  const key = `genSong.stage.${stage}`
  return te(key) ? t(key) : stage
}

let timer: ReturnType<typeof setInterval> | null = null

async function start() {
  const p = studio.project
  if (!p || !prompt.value.trim() || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const res = await api.post<{ job_id: string }>(
      `/projects/${p.id}/generate-song`,
      { prompt: prompt.value.trim(), language: currentLocale(),
        force: force.value })
    poll(p.id, res.job_id)
  } catch (e) {
    error.value = String(e)
    busy.value = false
  }
}

function poll(projectId: string, jobId: string) {
  timer = setInterval(async () => {
    try {
      const j = await api.get<PipelineJob>(
        `/projects/${projectId}/generate-song/${jobId}`)
      job.value = j
      if (j.status === 'done' || j.status === 'error') {
        if (timer) clearInterval(timer)
        timer = null
        busy.value = false
        if (j.status === 'done') {
          done.value = true
          await studio.reloadCurrent()
        } else {
          error.value = j.error ?? t('genSong.failed')
        }
      }
    } catch { /* transient — keep polling */ }
  }, 800)
}

onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="overlay" @click.self="!busy && emit('close')">
    <div class="dialog panel">
      <div class="head">
        <h3><Sparkles class="icon" :size="18" /> {{ t('genSong.title') }}</h3>
        <button class="close" :disabled="busy" @click="emit('close')">✕</button>
      </div>

      <template v-if="!busy && !done">
        <label class="field">
          {{ t('genSong.promptLabel') }}
          <textarea v-model="prompt" rows="3"
                    :placeholder="t('genSong.placeholder')" />
        </label>
        <label v-if="needsForce" class="force-row">
          <input type="checkbox" v-model="force" />
          <span>
            <strong>{{ t('genSong.force') }}</strong>
            <span class="dim block small">{{ t('genSong.forceHint') }}</span>
          </span>
        </label>
        <div class="actions">
          <button class="primary" :disabled="!prompt.trim() || (needsForce && !force)"
                  @click="start">
            {{ t('genSong.start') }}
          </button>
        </div>
      </template>

      <template v-else-if="busy">
        <div class="progress-wrap">
          <div class="stage">{{ stageLabel(job?.stage ?? 'starting') }}</div>
          <div class="bar"><div class="fill"
               :style="{ width: `${Math.round((job?.progress ?? 0) * 100)}%` }" /></div>
          <div v-if="job?.log?.length" class="log dim small">
            <div v-for="(line, i) in job.log.slice(-6)" :key="i">{{ line }}</div>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="ok-box">
          {{ t('genSong.done') }}
          <span v-if="job?.summary" class="dim block small">{{ job.summary }}</span>
        </div>
        <div class="actions">
          <button class="primary" @click="emit('close')">{{ t('common.done') }}</button>
        </div>
      </template>

      <div v-if="error" class="err-box">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 50; }
.dialog { width: 480px; max-width: 92vw; padding: 16px; display: flex; flex-direction: column; gap: 14px; }
.head { display: flex; justify-content: space-between; align-items: center; }
h3 { margin: 0; display: flex; align-items: center; gap: 8px; }
.close { border: none; background: transparent; font-size: 14px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-dim); }
textarea { resize: vertical; }
.force-row { display: flex; gap: 10px; align-items: flex-start; font-size: 13px; }
.block { display: block; margin-top: 2px; }
.small { font-size: 11px; }
.actions { display: flex; justify-content: flex-end; }
.progress-wrap { display: flex; flex-direction: column; gap: 10px; }
.stage { font-size: 13px; }
.bar { height: 8px; border-radius: 4px; background: var(--bg-elevated); overflow: hidden; }
.fill { height: 100%; background: var(--accent); transition: width 0.4s ease; }
.log { display: flex; flex-direction: column; gap: 2px; max-height: 120px; overflow-y: auto; }
.ok-box { border: 1px solid var(--ok); color: var(--ok); border-radius: 6px; padding: 10px; font-size: 13px; }
.err-box { border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; }
</style>
