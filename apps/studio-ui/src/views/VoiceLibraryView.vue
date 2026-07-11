<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, Dumbbell, Mic, PackageOpen, Play, Trash2, Wand2 } from 'lucide-vue-next'
import { api } from '../api/client'
import type { Asset, VoiceProfile } from '../api/types'
import VoiceWizard from '../components/VoiceWizard.vue'
import { runCountdown } from '../composables/countdown'

const { t } = useI18n()

const recordings = ref<Asset[]>([])
const profiles = ref<VoiceProfile[]>([])
const error = ref('')
const showWizard = ref(false)

async function wizardClosed(created: boolean) {
  showWizard.value = false
  if (created) {
    await load()
    await loadRvcStatus()
  }
}

// --- upload ---
const fileInput = ref<HTMLInputElement | null>(null)
async function uploadFile() {
  const f = fileInput.value?.files?.[0]
  if (!f) return
  error.value = ''
  try {
    await api.upload('/voice/recordings/upload', f, f.name)
    if (fileInput.value) fileInput.value.value = ''
    await load()
  } catch (e) {
    error.value = String(e)
  }
}

// --- live recording ---
const recording = ref(false)
const recordSeconds = ref(0)
let mediaRecorder: MediaRecorder | null = null
let chunks: Blob[] = []
let timer: ReturnType<typeof setInterval> | null = null

async function startRecording() {
  error.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    await runCountdown()
    chunks = []
    mediaRecorder = new MediaRecorder(stream)
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      const blob = new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' })
      const ext = (mediaRecorder?.mimeType || '').includes('ogg') ? 'ogg' : 'webm'
      try {
        await api.upload('/voice/recordings/upload', blob,
          `live-recording-${Date.now()}.${ext}`, { source: 'live_recording' })
        await load()
      } catch (e) {
        error.value = String(e)
      }
    }
    mediaRecorder.start()
    recording.value = true
    recordSeconds.value = 0
    timer = setInterval(() => recordSeconds.value++, 1000)
  } catch (e) {
    error.value = t('transport.micUnavailable') + String(e)
  }
}

function stopRecording() {
  mediaRecorder?.stop()
  recording.value = false
  if (timer) clearInterval(timer)
}

onUnmounted(() => { if (recording.value) stopRecording() })

// --- profile creation (consent-gated) ---
const showProfileForm = ref(false)
const profileName = ref('')
const performerAlias = ref('')
const selectedRecordings = ref<string[]>([])
const consentConfirmed = ref(false)
const consentNotes = ref('')
const usageRestrictions = ref('')

function startProfileFrom(r: Asset) {
  showProfileForm.value = true
  selectedRecordings.value = [r.id]
  profileName.value = r.filename.replace(/\.[^.]+$/, '') + ' voice'
  consentNotes.value = ''
  consentConfirmed.value = false
}

const canCreateProfile = computed(() =>
  profileName.value.trim() !== '' && selectedRecordings.value.length > 0 && consentConfirmed.value)

async function createProfile() {
  error.value = ''
  try {
    await api.post('/voice/profiles', {
      name: profileName.value.trim(),
      source_recording_ids: selectedRecordings.value,
      consent_confirmed: consentConfirmed.value,
      consent_notes: consentNotes.value,
      performer_alias: performerAlias.value,
      usage_restrictions: usageRestrictions.value,
    })
    showProfileForm.value = false
    profileName.value = ''
    selectedRecordings.value = []
    consentConfirmed.value = false
    consentNotes.value = ''
    await load()
  } catch (e) {
    error.value = String(e)
  }
}

async function load() {
  recordings.value = await api.get<Asset[]>('/assets/voice-recordings')
  profiles.value = await api.get<VoiceProfile[]>('/voice/profiles')
}

const testingId = ref('')
const testResults = ref<Record<string, { url: string; rvc: boolean }>>({})

// --- live RVC training status (async training runs in the background) ---
interface RvcModel {
  profile_id: string
  stage: string | null
  current_epoch: number
  total_epochs: number
  training_active: boolean
  ready: boolean
}
const rvcModels = ref<Record<string, RvcModel>>({})
let rvcTimer: ReturnType<typeof setInterval> | null = null

async function loadRvcStatus() {
  try {
    const r = await api.get<{ models: RvcModel[] }>('/voice/rvc-status')
    rvcModels.value = Object.fromEntries(r.models.map((m) => [m.profile_id, m]))
  } catch { /* backend without rvc — badges just hide */ }
}

function rvcBadge(p: VoiceProfile): { text: string; cls: string; canTrain?: boolean } | null {
  const m = rvcModels.value[p.id]
  if (!m) return null
  if (m.stage === 'complete' || (m.ready && !m.training_active)) {
    return { text: '🎓 ' + t('voices.modelReady'), cls: 'ok' }
  }
  if (m.stage === 'failed') return { text: '⚠ ' + t('voices.trainingFailed'), cls: 'err', canTrain: true }
  if (m.training_active || ['preprocess', 'extract', 'train', 'index', 'preparing'].includes(m.stage ?? '')) {
    const detail = m.stage === 'train' || m.current_epoch > 0
      ? t('voices.epoch', { n: m.current_epoch, total: m.total_epochs })
      : m.stage
    return { text: `🏋 ${t('voices.training')} ${detail}${m.ready ? ' ' + t('voices.checkpointInUse') : ''}`, cls: 'busy' }
  }
  return { text: '⏳ ' + t('voices.notTrained'), cls: 'dim', canTrain: true }
}

const anyTraining = computed(() =>
  Object.values(rvcModels.value).some((m) => m.training_active))
const trainMsg = ref('')

async function startTraining(p: VoiceProfile) {
  trainMsg.value = ''
  try {
    const r = await api.post<{ started: boolean; message: string }>(
      `/voice/profiles/${p.id}/train`)
    trainMsg.value = r.message
    setTimeout(loadRvcStatus, 3000)
  } catch (e) {
    trainMsg.value = String(e)
  }
}

// --- training log, on demand (no console window anymore) --------------------
const showLog = ref(false)
const logLines = ref<string[]>([])
let logTimer: ReturnType<typeof setInterval> | null = null

async function refreshLog() {
  const r = await api.get<{ lines: string[] }>('/voice/training-log?lines=120')
  logLines.value = r.lines
}
function toggleLog() {
  showLog.value = !showLog.value
  if (showLog.value) {
    void refreshLog()
    logTimer = setInterval(refreshLog, 5000)
  } else if (logTimer) {
    clearInterval(logTimer)
    logTimer = null
  }
}
onUnmounted(() => { if (logTimer) clearInterval(logTimer) })

// --- portable voice bundles ---------------------------------------------------
function exportVoice(p: VoiceProfile) {
  window.open(`/api/voice/profiles/${p.id}/export`, '_blank')
}

const voiceImportInput = ref<HTMLInputElement | null>(null)
async function importVoice() {
  const f = voiceImportInput.value?.files?.[0]
  if (!f) return
  error.value = ''
  trainMsg.value = t('voices.importing')
  try {
    const r = await api.upload<{ profile_id: string; name: string; warnings: string[] }>(
      '/voice/profiles/import', f, f.name)
    trainMsg.value = r.warnings.length ? r.warnings.join('; ')
      : t('voices.imported', { name: r.name })
    await load()
    await loadRvcStatus()
  } catch (e) {
    error.value = String(e)
    trainMsg.value = ''
  } finally {
    if (voiceImportInput.value) voiceImportInput.value.value = ''
  }
}

onMounted(() => {
  void loadRvcStatus()
  rvcTimer = setInterval(loadRvcStatus, 30000)
})
onUnmounted(() => { if (rvcTimer) clearInterval(rvcTimer) })

async function testVoice(p: VoiceProfile) {
  testingId.value = p.id
  error.value = ''
  try {
    const res = await fetch(`/api/voice/profiles/${p.id}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText)
    const rvc = res.headers.get('X-RVC-Applied') === 'True'
    const blob = await res.blob()
    testResults.value[p.id] = { url: URL.createObjectURL(blob), rvc }
  } catch (e) {
    error.value = String(e)
  } finally {
    testingId.value = ''
  }
}

async function deleteProfile(p: VoiceProfile) {
  if (!confirm(t('voices.deleteConfirm', { name: p.name }))) return
  try {
    await api.del(`/voice/profiles/${p.id}`)
    await load()
  } catch (e) {
    error.value = String(e)
  }
}

onMounted(load)
</script>

<template>
  <div class="voices">
    <div class="col panel">
      <h3>{{ t('voices.recordings') }}</h3>
      <div class="actions">
        <input ref="fileInput" type="file" accept="audio/*" @change="uploadFile" />
        <button v-if="!recording" @click="startRecording">● {{ t('voices.recordLive') }}</button>
        <button v-else class="rec" @click="stopRecording">■ {{ t('common.stop') }} ({{ recordSeconds }}s)</button>
      </div>
      <p class="dim small">
        {{ t('voices.recordingsBlurb') }}
      </p>
      <div v-for="r in recordings" :key="r.id" class="rec-item">
        <div class="fname">{{ r.filename }} <span v-if="r.is_missing" class="err-text">({{ t('assets.missing') }})</span></div>
        <audio v-if="!r.is_missing" controls :src="`/api/assets/${r.id}/file`" style="width: 100%; height: 32px" />
        <div class="rec-actions">
          <button v-if="!r.is_missing" class="small-btn"
                  :title="t('voices.makeVoiceTip')"
                  @click="startProfileFrom(r)"><Mic class="icon" :size="12" /> {{ t('voices.makeVoice') }}</button>
          <label v-if="showProfileForm" class="small">
            <input type="checkbox" :value="r.id" v-model="selectedRecordings" /> {{ t('voices.useForProfile') }}
          </label>
        </div>
      </div>
      <div v-if="!recordings.length" class="dim small">{{ t('voices.noRecordings') }}</div>
    </div>

    <div class="col panel">
      <h3>{{ t('voices.profiles') }}</h3>
      <p class="dim small">
        {{ t('voices.profilesBlurb') }}
      </p>
      <div class="create-row">
        <button class="primary" @click="showWizard = true"
                :title="t('voices.wizardTip')">
          <Wand2 class="icon" :size="13" /> {{ t('voices.guidedSetup') }}</button>
        <button v-if="!showProfileForm" @click="showProfileForm = true"
                :title="t('voices.fromExistingTip')">
          + {{ t('voices.fromExisting') }}</button>
        <input ref="voiceImportInput" type="file" accept=".zip" style="display: none" @change="importVoice" />
        <button :title="t('voices.importTip')" @click="voiceImportInput?.click()">
          <PackageOpen class="icon" :size="12" /> {{ t('voices.importVoice') }}</button>
      </div>
      <div class="log-row">
        <button class="small-btn" @click="toggleLog">
          {{ showLog ? '▾' : '▸' }} {{ t('voices.trainingLog') }}</button>
        <pre v-if="showLog" class="train-log">{{ logLines.join('\n') || t('voices.noLog') }}</pre>
      </div>
      <div v-if="showProfileForm" class="profile-form">
        <label>{{ t('voices.profileName') }} <input v-model="profileName" /></label>
        <label>{{ t('voices.performerAlias') }} <input v-model="performerAlias" /></label>
        <div class="small dim">{{ t('voices.selectSources', { n: selectedRecordings.length }) }}</div>
        <label>{{ t('voices.usageRestrictions') }} <input v-model="usageRestrictions" :placeholder="t('voices.restrictionsPh')" /></label>
        <label class="consent">
          <input type="checkbox" v-model="consentConfirmed" />
          <span>{{ t('voices.consentCheck') }}</span>
        </label>
        <label>{{ t('voices.consentNotes') }} <textarea v-model="consentNotes" rows="2" :placeholder="t('voices.consentNotesPh')" /></label>
        <div class="row-btns">
          <button class="primary" :disabled="!canCreateProfile" @click="createProfile">{{ t('voices.createProfile') }}</button>
          <button @click="showProfileForm = false">{{ t('common.cancel') }}</button>
        </div>
      </div>

      <div v-for="p in profiles" :key="p.id" class="profile-item">
        <div class="profile-head">
          <div class="fname">{{ p.name }} <span class="dim small">({{ p.status }})</span></div>
          <div class="profile-actions">
            <button class="small-btn" :disabled="testingId === p.id"
                    :title="t('voices.testTip')"
                    @click="testVoice(p)">
              <template v-if="testingId === p.id">⏳ {{ t('voices.synthesizing') }}</template>
              <template v-else><Play class="icon" :size="11" /> {{ t('voices.testVoice') }}</template>
            </button>
            <button class="small-btn" :title="t('voices.exportTip')"
                    @click="exportVoice(p)"><Download class="icon" :size="12" /></button>
            <button class="del-btn" :title="t('voices.deleteTip')"
                    @click="deleteProfile(p)"><Trash2 class="icon" :size="12" /></button>
          </div>
        </div>
        <div v-if="testResults[p.id]" class="test-result">
          <audio controls autoplay :src="testResults[p.id].url" style="width: 100%; height: 32px" />
          <span class="dim small">{{ testResults[p.id].rvc ? '✓ ' + t('voices.rvcApplied') : t('voices.zeroShot') }}</span>
        </div>
        <div v-if="rvcBadge(p)" class="badge-row">
          <span class="rvc-badge" :class="rvcBadge(p)!.cls">{{ rvcBadge(p)!.text }}</span>
          <button v-if="rvcBadge(p)!.canTrain" class="small-btn train-btn"
                  :disabled="anyTraining"
                  :title="anyTraining ? t('voices.oneAtATime') : t('voices.trainTip')"
                  @click="startTraining(p)"><Dumbbell class="icon" :size="12" /> {{ t('voices.startTraining') }}</button>
        </div>
        <div v-if="trainMsg" class="dim small">{{ trainMsg }}</div>
        <div class="dim small">
          {{ t('voices.sourceCount', { n: p.source_recording_ids.length }) }}
          <span v-if="p.performer_alias"> · {{ p.performer_alias }}</span>
        </div>
        <div v-if="p.usage_restrictions" class="dim small">{{ t('voices.restrictions') }}: {{ p.usage_restrictions }}</div>
      </div>
      <div v-if="!profiles.length && !showProfileForm" class="dim small">{{ t('voices.noProfiles') }}</div>
    </div>
    <div v-if="error" class="err-box">{{ error }}</div>
    <VoiceWizard v-if="showWizard" @close="wizardClosed" />
  </div>
</template>

<style scoped>
.voices { display: flex; gap: 8px; padding: 8px; height: 100%; position: relative; }
.col { flex: 1; padding: 14px; overflow-y: auto; }
h3 { margin: 0 0 8px; }
.actions { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.small { font-size: 11px; }
.rec-item { padding: 8px 0; border-bottom: 1px solid var(--border); }
.rec-actions { display: flex; gap: 10px; align-items: center; margin-top: 4px; }
.small-btn { font-size: 11px; padding: 2px 8px; }
.fname { font-size: 13px; margin-bottom: 4px; }
.rec { background: var(--err); border-color: var(--err); color: #fff; }
.profile-form { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--border); border-radius: 8px; padding: 12px; margin: 8px 0; }
.profile-form label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.consent { flex-direction: row !important; align-items: flex-start; gap: 8px !important; color: var(--warn) !important; }
.profile-item { padding: 8px 0; border-bottom: 1px solid var(--border); }
.profile-head { display: flex; justify-content: space-between; align-items: center; }
.profile-actions { display: flex; gap: 6px; }
.create-row { display: flex; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
.log-row { margin-bottom: 8px; }
.train-log { font-size: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; padding: 8px; max-height: 180px; overflow: auto; white-space: pre-wrap; margin: 6px 0 0; }
.badge-row { display: flex; gap: 8px; align-items: center; margin: 3px 0; }
.train-btn { border-color: var(--accent); }
.rvc-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; display: inline-block; }
.rvc-badge.ok { color: var(--ok); border: 1px solid var(--ok); }
.rvc-badge.busy { color: var(--warn); border: 1px solid var(--warn); }
.rvc-badge.err { color: var(--err); border: 1px solid var(--err); }
.rvc-badge.dim { color: var(--text-dim); border: 1px solid var(--border); }
.test-result { margin: 6px 0; }
.del-btn { padding: 1px 7px; font-size: 12px; border-color: var(--err); }
.row-btns { display: flex; gap: 8px; }
.err-box { position: absolute; bottom: 12px; left: 12px; right: 12px; border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; background: var(--bg-panel); }
.err-text { color: var(--err); }
</style>
