<script setup lang="ts">
/**
 * Photo + face identification for one voice profile.
 *
 * Two clearly separated things, because they carry different weight:
 *  - a PHOTO is decoration (an avatar next to the profile);
 *  - face RECOGNITION is biometric, so it needs its own explicit consent,
 *    stores a template locally, and can be deleted in one click.
 * Camera frames never leave the machine — matching runs in the backend via
 * OpenCV, never through the vision LLM.
 */
import { computed, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Camera, ScanFace, Trash2, Upload } from 'lucide-vue-next'
import type { VoiceProfile } from '../api/types'

const props = defineProps<{ profile: VoiceProfile; modelsReady: boolean }>()
const emit = defineEmits<{ changed: [VoiceProfile] }>()

const { t } = useI18n()
const busy = ref(false)
const error = ref('')
const info = ref('')
const photoBust = ref(Date.now())
const camOpen = ref(false)
const camFor = ref<'photo' | 'enroll'>('photo')
const videoEl = ref<HTMLVideoElement | null>(null)
let stream: MediaStream | null = null

const photoUrl = computed(() =>
  props.profile.photo_path
    ? `/api/voice/profiles/${props.profile.id}/photo?v=${photoBust.value}`
    : '')

function stopCam() {
  stream?.getTracks().forEach((tr) => tr.stop())
  stream = null
  camOpen.value = false
}
onUnmounted(stopCam)

async function openCam(mode: 'photo' | 'enroll') {
  error.value = ''
  camFor.value = mode
  camOpen.value = true
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true })
    await new Promise((r) => setTimeout(r, 60))   // let the <video> mount
    if (videoEl.value) {
      videoEl.value.srcObject = stream
      await videoEl.value.play()
    }
  } catch (e) {
    error.value = t('voices.face.cameraFailed') + ' ' + String(e)
    camOpen.value = false
  }
}

function grabFrame(): Promise<Blob | null> {
  const v = videoEl.value
  if (!v || !v.videoWidth) return Promise.resolve(null)
  const c = document.createElement('canvas')
  c.width = v.videoWidth
  c.height = v.videoHeight
  c.getContext('2d')?.drawImage(v, 0, 0)
  return new Promise((res) => c.toBlob((b) => res(b), 'image/jpeg', 0.92))
}

async function post(path: string, blob: Blob) {
  const fd = new FormData()
  fd.append('file', blob, 'frame.jpg')
  const r = await fetch(path, { method: 'POST', body: fd })
  const body = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(body.detail ?? r.statusText)
  return body
}

async function shoot() {
  const blob = await grabFrame()
  if (!blob) return
  const mode = camFor.value
  stopCam()
  await submit(blob, mode)
}

async function submit(blob: Blob, mode: 'photo' | 'enroll') {
  busy.value = true
  error.value = ''
  info.value = ''
  try {
    if (mode === 'photo') {
      const p = await post(`/api/voice/profiles/${props.profile.id}/photo`, blob)
      photoBust.value = Date.now()
      emit('changed', p as VoiceProfile)
    } else {
      await post(`/api/voice/profiles/${props.profile.id}/face-enroll`, blob)
      info.value = t('voices.face.enrolled')
      emit('changed', { ...props.profile, face_enrolled: true })
    }
  } catch (e) {
    error.value = String(e instanceof Error ? e.message : e)
  } finally {
    busy.value = false
  }
}

async function pickFile(ev: Event, mode: 'photo' | 'enroll') {
  const f = (ev.target as HTMLInputElement).files?.[0]
  if (f) await submit(f, mode)
  ;(ev.target as HTMLInputElement).value = ''
}

async function toggleConsent(ev: Event) {
  const on = (ev.target as HTMLInputElement).checked
  busy.value = true
  error.value = ''
  try {
    const r = await fetch(`/api/voice/profiles/${props.profile.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ face_consent: on }),
    })
    if (!r.ok) throw new Error(await r.text())
    emit('changed', await r.json())
  } catch (e) {
    error.value = String(e)
  } finally {
    busy.value = false
  }
}

async function removeEnrolment() {
  busy.value = true
  try {
    await fetch(`/api/voice/profiles/${props.profile.id}/face-enroll`,
                { method: 'DELETE' })
    info.value = t('voices.face.removed')
    emit('changed', { ...props.profile, face_enrolled: false })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="face-panel">
    <div class="row">
      <div class="avatar" :class="{ empty: !photoUrl }">
        <img v-if="photoUrl" :src="photoUrl" alt="" />
        <Camera v-else :size="18" class="dim" />
      </div>
      <div class="controls">
        <div class="btn-row">
          <button class="small-btn" :disabled="busy" @click="openCam('photo')">
            <Camera class="icon" :size="12" /> {{ t('voices.face.takePhoto') }}
          </button>
          <label class="small-btn file">
            <Upload class="icon" :size="12" /> {{ t('voices.face.upload') }}
            <input type="file" accept="image/*" hidden
                   @change="(e) => pickFile(e, 'photo')" />
          </label>
        </div>

        <label class="consent">
          <input type="checkbox" :checked="profile.face_consent" :disabled="busy"
                 @change="toggleConsent" />
          <span>
            {{ t('voices.face.consent') }}
            <span class="dim block small">{{ t('voices.face.consentHint') }}</span>
          </span>
        </label>

        <div v-if="profile.face_consent" class="btn-row">
          <button class="small-btn" :disabled="busy || !modelsReady"
                  :title="modelsReady ? '' : t('voices.face.modelsMissing')"
                  @click="openCam('enroll')">
            <ScanFace class="icon" :size="12" />
            {{ profile.face_enrolled ? t('voices.face.reEnroll') : t('voices.face.enroll') }}
          </button>
          <label v-if="modelsReady" class="small-btn file">
            <Upload class="icon" :size="12" /> {{ t('voices.face.enrollFromFile') }}
            <input type="file" accept="image/*" hidden
                   @change="(e) => pickFile(e, 'enroll')" />
          </label>
          <button v-if="profile.face_enrolled" class="del-btn" :disabled="busy"
                  :title="t('voices.face.removeTip')" @click="removeEnrolment">
            <Trash2 class="icon" :size="12" />
          </button>
          <span v-if="profile.face_enrolled" class="ok-chip">
            ✓ {{ t('voices.face.enrolledChip') }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="camOpen" class="cam">
      <video ref="videoEl" playsinline muted />
      <div class="btn-row">
        <button class="small-btn primary" :disabled="busy" @click="shoot">
          {{ camFor === 'enroll' ? t('voices.face.captureEnroll') : t('voices.face.capture') }}
        </button>
        <button class="small-btn" @click="stopCam">{{ t('common.cancel') }}</button>
      </div>
    </div>

    <div v-if="info" class="dim small">{{ info }}</div>
    <div v-if="error" class="err-text small">{{ error }}</div>
  </div>
</template>

<style scoped>
.face-panel { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.row { display: flex; gap: 12px; align-items: flex-start; }
.avatar {
  width: 56px; height: 56px; border-radius: 50%; overflow: hidden; flex: none;
  background: var(--bg-elevated); border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.controls { display: flex; flex-direction: column; gap: 8px; flex: 1; min-width: 0; }
.btn-row { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.file { display: inline-flex; align-items: center; gap: 4px; cursor: pointer; }
.consent { display: flex; gap: 8px; align-items: flex-start; font-size: 12px; }
.block { display: block; }
.small { font-size: 11px; }
.ok-chip { font-size: 11px; color: var(--ok); }
.cam { display: flex; flex-direction: column; gap: 6px; }
.cam video { width: 100%; max-width: 320px; border-radius: var(--radius-sm); background: #000; }
.err-text { color: var(--err); }
</style>
