<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api } from '../api/client'
import type { Asset, VoiceProfile } from '../api/types'

const recordings = ref<Asset[]>([])
const profiles = ref<VoiceProfile[]>([])
const error = ref('')

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
    error.value = 'Microphone unavailable: ' + String(e)
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

onMounted(load)
</script>

<template>
  <div class="voices">
    <div class="col panel">
      <h3>Voice recordings</h3>
      <div class="actions">
        <input ref="fileInput" type="file" accept="audio/*" @change="uploadFile" />
        <button v-if="!recording" @click="startRecording">● Record live</button>
        <button v-else class="rec" @click="stopRecording">■ Stop ({{ recordSeconds }}s)</button>
      </div>
      <p class="dim small">
        Recordings are stored in <code>voices/recordings/</code>. They are never
        modified and never become voice profiles automatically.
      </p>
      <div v-for="r in recordings" :key="r.id" class="rec-item">
        <div class="fname">{{ r.filename }} <span v-if="r.is_missing" class="err-text">(missing)</span></div>
        <audio v-if="!r.is_missing" controls :src="`/api/assets/${r.id}/file`" style="width: 100%; height: 32px" />
        <div class="rec-actions">
          <button v-if="!r.is_missing" class="small-btn"
                  title="Create a consented voice profile from this recording — vocal tracks can then sing with this voice"
                  @click="startProfileFrom(r)">🎙 → Make this my AI voice</button>
          <label v-if="showProfileForm" class="small">
            <input type="checkbox" :value="r.id" v-model="selectedRecordings" /> use for profile
          </label>
        </div>
      </div>
      <div v-if="!recordings.length" class="dim small">No recordings yet — upload a file or record live.</div>
    </div>

    <div class="col panel">
      <h3>Voice profiles</h3>
      <p class="dim small">
        A voice profile is a reusable singing voice. Creating one requires
        explicit consent from the performer. Profiles are only used when you
        assign them to a vocal track.
      </p>
      <button v-if="!showProfileForm" class="primary" @click="showProfileForm = true">+ Create voice profile</button>
      <div v-else class="profile-form">
        <label>Profile name <input v-model="profileName" /></label>
        <label>Performer alias <input v-model="performerAlias" /></label>
        <div class="small dim">Select source recordings in the left column ({{ selectedRecordings.length }} selected)</div>
        <label>Usage restrictions <input v-model="usageRestrictions" placeholder="e.g. personal projects only" /></label>
        <label class="consent">
          <input type="checkbox" v-model="consentConfirmed" />
          <span>I confirm the performer of these recordings has given explicit
          consent to create a reusable singing voice profile from them.</span>
        </label>
        <label>Consent notes <textarea v-model="consentNotes" rows="2" placeholder="who consented, when, how" /></label>
        <div class="row-btns">
          <button class="primary" :disabled="!canCreateProfile" @click="createProfile">Create profile</button>
          <button @click="showProfileForm = false">Cancel</button>
        </div>
      </div>

      <div v-for="p in profiles" :key="p.id" class="profile-item">
        <div class="fname">{{ p.name }} <span class="dim small">({{ p.status }})</span></div>
        <div class="dim small">
          {{ p.source_recording_ids.length }} source recording(s)
          <span v-if="p.performer_alias"> · {{ p.performer_alias }}</span>
        </div>
        <div v-if="p.usage_restrictions" class="dim small">restrictions: {{ p.usage_restrictions }}</div>
      </div>
      <div v-if="!profiles.length && !showProfileForm" class="dim small">No voice profiles yet.</div>
    </div>
    <div v-if="error" class="err-box">{{ error }}</div>
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
.row-btns { display: flex; gap: 8px; }
.err-box { position: absolute; bottom: 12px; left: 12px; right: 12px; border: 1px solid var(--err); color: var(--err); border-radius: 6px; padding: 8px; font-size: 12px; background: var(--bg-panel); }
.err-text { color: var(--err); }
</style>
