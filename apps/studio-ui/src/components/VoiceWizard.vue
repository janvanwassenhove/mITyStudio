<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Dumbbell, Ear, Play, Wand2 } from 'lucide-vue-next'
import { api } from '../api/client'
import type { Asset } from '../api/types'
import { currentLocale } from '../i18n'

const { t, te } = useI18n()
const emit = defineEmits<{ close: [created: boolean] }>()

type Step = 'consent' | 'setup' | 'takes' | 'finish'
const step = ref<Step>('consent')
const error = ref('')

// ---------------- device (honest expectations up front) ----------------
interface DeviceInfo { device: string; name: string; message: string; recommended_tier: string; tiers: Record<string, number> }
const device = ref<DeviceInfo | null>(null)

// localized device banner; falls back to the backend's English message
const deviceMessage = computed(() => {
  const d = device.value
  if (!d) return ''
  const key = `wizard.device.${d.device}`
  return te(key) ? t(key, { name: d.name }) : d.message
})

// ---------------- shared recorder ----------------
const recording = ref(false)
const recSeconds = ref(0)
let mediaRecorder: MediaRecorder | null = null
let mediaStream: MediaStream | null = null
let chunks: Blob[] = []
let recTimer: ReturnType<typeof setInterval> | null = null

// live pitch meter
const pitchCanvas = ref<HTMLCanvasElement | null>(null)
const currentNote = ref('—')
let audioCtx: AudioContext | null = null
let analyser: AnalyserNode | null = null
let pitchRaf = 0
const pitchHistory: number[] = []

const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

function detectPitch(buf: Float32Array, rate: number): number {
  let rms = 0
  for (const v of buf) rms += v * v
  if (Math.sqrt(rms / buf.length) < 0.015) return 0
  const lo = Math.floor(rate / 600), hi = Math.floor(rate / 60)
  let best = 0, bestLag = 0
  for (let lag = lo; lag < Math.min(hi, buf.length / 2); lag++) {
    let s = 0
    for (let i = 0; i < buf.length - lag; i++) s += buf[i] * buf[i + lag]
    if (s > best) { best = s; bestLag = lag }
  }
  let norm = 0
  for (const v of buf) norm += v * v
  return best > 0.3 * norm && bestLag ? rate / bestLag : 0
}

function pitchLoop() {
  if (!analyser || !audioCtx) return
  const buf = new Float32Array(2048)
  analyser.getFloatTimeDomainData(buf)
  const f = detectPitch(buf, audioCtx.sampleRate)
  const midi = f > 0 ? 69 + 12 * Math.log2(f / 440) : 0
  currentNote.value = f > 0 ? `${NOTE_NAMES[Math.round(midi) % 12]}${Math.floor(Math.round(midi) / 12) - 1}` : '—'
  pitchHistory.push(midi)
  if (pitchHistory.length > 160) pitchHistory.shift()
  const cv = pitchCanvas.value
  if (cv) {
    const ctx2 = cv.getContext('2d')!
    ctx2.clearRect(0, 0, cv.width, cv.height)
    ctx2.strokeStyle = '#31363f'
    for (const m of [48, 55, 60, 67, 72]) { // C3 G3 C4 G4 C5 gridlines
      const y = cv.height - ((m - 40) / 40) * cv.height
      ctx2.beginPath(); ctx2.moveTo(0, y); ctx2.lineTo(cv.width, y); ctx2.stroke()
    }
    ctx2.strokeStyle = '#4f9cf9'
    ctx2.lineWidth = 2.5
    ctx2.beginPath()
    pitchHistory.forEach((m, i) => {
      if (m <= 0) return
      const x = (i / 160) * cv.width
      const y = cv.height - ((m - 40) / 40) * cv.height
      ctx2.lineTo(x, y)
    })
    ctx2.stroke()
    ctx2.lineWidth = 1
  }
  pitchRaf = requestAnimationFrame(pitchLoop)
}

async function startRecording() {
  error.value = ''
  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  chunks = []
  mediaRecorder = new MediaRecorder(mediaStream)
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data)
  mediaRecorder.start()
  recording.value = true
  recSeconds.value = 0
  recTimer = setInterval(() => recSeconds.value++, 1000)
  // live pitch
  audioCtx = audioCtx ?? new AudioContext()
  const src = audioCtx.createMediaStreamSource(mediaStream)
  analyser = audioCtx.createAnalyser()
  analyser.fftSize = 2048
  src.connect(analyser)
  pitchHistory.length = 0
  pitchLoop()
}

function stopRecording(): Promise<Blob> {
  return new Promise((resolve) => {
    if (!mediaRecorder) return resolve(new Blob())
    mediaRecorder.onstop = () => {
      mediaStream?.getTracks().forEach((t) => t.stop())
      cancelAnimationFrame(pitchRaf)
      recording.value = false
      if (recTimer) clearInterval(recTimer)
      resolve(new Blob(chunks, { type: mediaRecorder?.mimeType || 'audio/webm' }))
    }
    mediaRecorder.stop()
  })
}

async function uploadBlob(blob: Blob, name: string, tags: string): Promise<Asset> {
  return api.upload<Asset>('/voice/recordings/upload', blob, name,
    { source: 'live_recording', tags })
}

onBeforeUnmount(() => {
  mediaStream?.getTracks().forEach((t) => t.stop())
  cancelAnimationFrame(pitchRaf)
})

// ---------------- step 1: consent ----------------
const consentChecked = ref(false)
const performerName = ref('')
const consentAssetId = ref('')
const consentBusy = ref(false)

const consentText = computed(() =>
  t('wizard.consentStatement', { name: performerName.value || '<name>' }))

async function recordConsent() {
  if (recording.value) {
    consentBusy.value = true
    const blob = await stopRecording()
    try {
      const asset = await uploadBlob(blob, `consent-${Date.now()}.webm`, 'wizard,consent')
      consentAssetId.value = asset.id
    } catch (e) { error.value = String(e) }
    consentBusy.value = false
  } else {
    await startRecording()
  }
}

// ---------------- step 2: setup + range test ----------------
const profileName = ref('')
const language = ref(currentLocale())
const rangeResult = ref<{ vocal_range: string } | null>(null)
const rangeAssetId = ref('')
const rangeBusy = ref(false)

function playRangeGuide() {
  void new Audio('/api/voice/wizard/guide/range_scale').play()
}

async function recordRange() {
  if (recording.value) {
    rangeBusy.value = true
    const blob = await stopRecording()
    try {
      const asset = await uploadBlob(blob, `range-${Date.now()}.webm`, 'wizard,range')
      rangeAssetId.value = asset.id
      rangeResult.value = await api.post(`/voice/recordings/${asset.id}/range-test`)
    } catch (e) {
      error.value = String(e)
      rangeResult.value = null
    }
    rangeBusy.value = false
  } else {
    await startRecording()
  }
}

// ---------------- step 3: takes ----------------
interface Exercise { id: string; title: string; coach: string; seconds: number }
interface TakeState { asset_id?: string; qa?: { verdict: string; issues: string[]; tips: string[]; issue_codes?: string[]; duration?: number }; practicing?: string }

// exercise titles/coaching live in the locale files, keyed by exercise id;
// the backend's English text is the fallback for unknown ids
const exTitle = (e: Exercise) => te(`wizard.ex.${e.id}.title`) ? t(`wizard.ex.${e.id}.title`) : e.title
const exCoach = (e: Exercise) => te(`wizard.ex.${e.id}.coach`) ? t(`wizard.ex.${e.id}.coach`) : e.coach
const qaIssues = (qa: TakeState['qa']) => (qa?.issue_codes?.length
  ? qa.issue_codes.map((c) => te(`wizard.qa.${c}.issue`) ? t(`wizard.qa.${c}.issue`) : c).join(', ')
  : qa?.issues.join(', ') ?? '')
const qaTips = (qa: TakeState['qa']) => (qa?.issue_codes?.length
  ? qa.issue_codes.map((c) => te(`wizard.qa.${c}.tip`) ? t(`wizard.qa.${c}.tip`) : '').filter(Boolean).join('; ')
  : qa?.tips.join('; ') ?? '')
const exercises = ref<Exercise[]>([])
const exIndex = ref(0)
const takes = ref<Record<string, TakeState>>({})
const takeBusy = ref(false)
const practiceUrl = ref('')

// EVERY good take feeds the profile — re-recording an exercise adds material
// instead of replacing it. More minutes = better clone.
const allTakes = ref<{ id: string; seconds: number }[]>([])
const totalMinutes = computed(() =>
  allTakes.value.reduce((s, tk) => s + tk.seconds, 0) / 60)
const MINUTES_GOAL = 10

const currentEx = computed(() => exercises.value[exIndex.value])
const doneCount = computed(() =>
  exercises.value.filter((e) => takes.value[e.id]?.qa?.verdict === 'pass'
    || takes.value[e.id]?.qa?.verdict === 'warn').length)

function playGuide() {
  if (!currentEx.value) return
  void new Audio(`/api/voice/wizard/guide/${currentEx.value.id}`).play()
}

async function doPractice() {
  if (recording.value) {
    const blob = await stopRecording()
    practiceUrl.value = URL.createObjectURL(blob)   // local only, never saved
  } else {
    practiceUrl.value = ''
    await startRecording()
  }
}

async function doTake() {
  const ex = currentEx.value
  if (!ex) return
  if (recording.value) {
    takeBusy.value = true
    const blob = await stopRecording()
    try {
      const asset = await uploadBlob(blob, `wizard-${ex.id}-${Date.now()}.webm`,
        `wizard,${ex.id}`)
      const qa = await api.post<TakeState['qa']>(`/voice/recordings/${asset.id}/qa`)
      takes.value[ex.id] = { asset_id: asset.id, qa }
      if (qa?.verdict !== 'fail') {
        allTakes.value.push({ id: asset.id, seconds: qa?.duration ?? 0 })
      }
    } catch (e) { error.value = String(e) }
    takeBusy.value = false
  } else {
    practiceUrl.value = ''
    await startRecording()
  }
}

// ---------------- step 4: finish ----------------
const creating = ref(false)
const createdProfileId = ref('')
const confidence = ref<{ score: number; minutes: number; notes: string[]; note_codes?: string[]; vocal_range?: string } | null>(null)
const trainMsg = ref('')

const confidenceNotes = computed(() => {
  const c = confidence.value
  if (!c) return []
  if (!c.note_codes?.length) return c.notes
  return c.note_codes.map((code) => te(`wizard.conf.${code}`)
    ? t(`wizard.conf.${code}`, { range: c.vocal_range ?? '' })
    : c.notes[c.note_codes!.indexOf(code)] ?? code)
})

async function finish() {
  creating.value = true
  error.value = ''
  try {
    const ids = [...new Set([rangeAssetId.value,
      ...allTakes.value.map((tk) => tk.id),
      ...Object.values(takes.value).map((tk) => tk.asset_id)])].filter(Boolean) as string[]
    const p = await api.post<{ id: string }>('/voice/profiles', {
      name: profileName.value.trim(),
      source_recording_ids: ids,
      consent_confirmed: true,
      consent_notes: consentText.value,
      consent_recording_id: consentAssetId.value || null,
      language_notes: language.value,
      vocal_range: rangeResult.value?.vocal_range ?? '',
    })
    createdProfileId.value = p.id
    confidence.value = await api.get(`/voice/profiles/${p.id}/confidence`)
    step.value = 'finish'
  } catch (e) { error.value = String(e) }
  creating.value = false
}

async function startTraining(tier: string) {
  try {
    const r = await api.post<{ message: string }>(
      `/voice/profiles/${createdProfileId.value}/train?tier=${tier}`)
    trainMsg.value = r.message
  } catch (e) { trainMsg.value = String(e) }
}

onMounted(async () => {
  device.value = await api.get<DeviceInfo>('/voice/device')
  exercises.value = await api.get<Exercise[]>('/voice/wizard/exercises')
})
</script>

<template>
  <div class="overlay" @click.self="emit('close', !!createdProfileId)">
    <div class="wiz panel">
      <div class="head">
        <h3><Wand2 class="icon" :size="17" /> {{ t('wizard.title') }}</h3>
        <span class="dim small steps">{{ ['consent', 'setup', 'takes', 'finish'].indexOf(step) + 1 }} / 4</span>
        <button class="close" @click="emit('close', !!createdProfileId)">✕</button>
      </div>
      <div v-if="device" class="device dim small">{{ deviceMessage }}</div>

      <!-- 1: consent -->
      <div v-if="step === 'consent'" class="body">
        <p>{{ t('wizard.consentIntro') }}</p>
        <label class="field">{{ t('wizard.performerName') }}
          <input v-model="performerName" :placeholder="t('wizard.performerPh')" />
        </label>
        <blockquote class="consent-text">“{{ consentText }}”</blockquote>
        <div class="row">
          <button @click="recordConsent" :disabled="consentBusy || !performerName.trim()">
            {{ recording ? `■ ${t('common.stop')} (${recSeconds}s)` : consentAssetId ? '✓ ' + t('wizard.reRecordConsent') : '● ' + t('wizard.readAloud') }}
          </button>
          <span v-if="consentAssetId" class="ok small">✓ {{ t('wizard.consentRecorded') }}</span>
        </div>
        <label class="checkline">
          <input type="checkbox" v-model="consentChecked" />
          {{ t('wizard.consentCheck') }}
        </label>
        <div class="nav">
          <button class="primary" :disabled="!consentChecked || !performerName.trim()"
                  @click="step = 'setup'">{{ t('common.continue') }} →</button>
        </div>
      </div>

      <!-- 2: setup + range -->
      <div v-else-if="step === 'setup'" class="body">
        <div class="row">
          <label class="field" style="flex:1">{{ t('wizard.voiceName') }}
            <input v-model="profileName" :placeholder="t('wizard.voiceNamePh', { name: performerName })" />
          </label>
          <label class="field">{{ t('wizard.language') }}
            <select v-model="language">
              <option value="en">English</option><option value="nl">Nederlands</option>
              <option value="fr">Français</option><option value="de">Deutsch</option>
            </select>
          </label>
        </div>
        <h4>{{ t('wizard.rangeCheck') }}</h4>
        <p class="dim small">{{ t('wizard.rangeBlurb') }}</p>
        <div class="row">
          <button @click="playRangeGuide"><Play class="icon" :size="12" /> {{ t('wizard.playGuide') }}</button>
          <button :class="{ reclive: recording }" :disabled="rangeBusy" @click="recordRange">
            {{ recording ? `■ ${t('common.stop')} (${recSeconds}s)` : '● ' + t('wizard.recordScale') }}
          </button>
          <span v-if="rangeBusy" class="dim small">{{ t('wizard.analysing') }}</span>
          <span v-else-if="rangeResult" class="ok">✓ {{ t('wizard.yourRange') }}: <strong>{{ rangeResult.vocal_range }}</strong></span>
        </div>
        <div class="meter">
          <canvas ref="pitchCanvas" width="420" height="90" />
          <span class="note">{{ currentNote }}</span>
        </div>
        <div class="nav">
          <button @click="step = 'consent'">{{ t('common.back') }}</button>
          <button class="primary" :disabled="!profileName.trim() && !performerName.trim()"
                  @click="profileName = profileName.trim() || t('wizard.voiceNamePh', { name: performerName }); step = 'takes'">
            {{ t('common.continue') }} →</button>
        </div>
      </div>

      <!-- 3: takes -->
      <div v-else-if="step === 'takes'" class="body">
        <div class="ex-tabs">
          <button v-for="(e, i) in exercises" :key="e.id" class="ex-tab"
                  :class="{ on: i === exIndex, done: takes[e.id]?.qa && takes[e.id].qa!.verdict !== 'fail' }"
                  @click="exIndex = i">
            {{ takes[e.id]?.qa && takes[e.id].qa!.verdict !== 'fail' ? '✓ ' : '' }}{{ exTitle(e) }}
          </button>
        </div>
        <template v-if="currentEx">
          <p class="coach">🎤 {{ exCoach(currentEx) }}</p>
          <div class="row">
            <button @click="playGuide"><Play class="icon" :size="12" /> {{ t('wizard.hearGuide') }}</button>
            <button :disabled="takeBusy" @click="doPractice"
                    :class="{ reclive: recording && !takeBusy }">
              <template v-if="recording">■ {{ t('common.stop') }} ({{ recSeconds }}s)</template>
              <template v-else><Ear class="icon" :size="12" /> {{ t('wizard.practice') }}</template>
            </button>
            <button class="primary" :disabled="takeBusy" @click="doTake">
              {{ recording ? `■ ${t('wizard.stopTake')} (${recSeconds}s)` : '● ' + t('wizard.take') }}
            </button>
          </div>
          <audio v-if="practiceUrl" :src="practiceUrl" controls style="width: 100%; height: 30px" />
          <div class="meter">
            <canvas ref="pitchCanvas" width="420" height="90" />
            <span class="note">{{ currentNote }}</span>
          </div>
          <div v-if="takes[currentEx.id]?.qa" class="qa" :class="takes[currentEx.id].qa!.verdict">
            <template v-if="takes[currentEx.id].qa!.verdict === 'pass'">✓ {{ t('wizard.qaPass') }}</template>
            <template v-else-if="takes[currentEx.id].qa!.verdict === 'warn'">
              ⚠ {{ t('wizard.qaWarn') }}: {{ qaIssues(takes[currentEx.id].qa) }} —
              {{ qaTips(takes[currentEx.id].qa) }} {{ t('wizard.qaWarnSuffix') }}
            </template>
            <template v-else>
              ✗ {{ t('wizard.qaFail') }}: {{ qaIssues(takes[currentEx.id].qa) }} —
              {{ qaTips(takes[currentEx.id].qa) }}
            </template>
          </div>
        </template>
        <div class="minutes">
          <div class="conf-bar"><div :style="{ width: Math.min(totalMinutes / MINUTES_GOAL, 1) * 100 + '%' }" /></div>
          <span class="dim small">{{ t('wizard.minutesMeter', { m: totalMinutes.toFixed(1), goal: MINUTES_GOAL }) }}</span>
        </div>
        <div class="nav">
          <button @click="step = 'setup'">{{ t('common.back') }}</button>
          <span class="dim small">{{ t('wizard.exercisesDone', { done: doneCount, total: exercises.length }) }}</span>
          <button class="primary" :disabled="doneCount < 3 || creating" @click="finish">
            {{ creating ? t('wizard.creating') : doneCount < exercises.length ? t('wizard.finishWith', { n: doneCount }) : t('wizard.createProfile') }}
          </button>
        </div>
      </div>

      <!-- 4: finish -->
      <div v-else class="body">
        <h4>🎉 {{ t('wizard.ready', { name: profileName }) }}</h4>
        <div v-if="confidence" class="conf">
          <div class="conf-bar"><div :style="{ width: confidence.score * 100 + '%' }" /></div>
          <div class="dim small">{{ t('wizard.expectedQuality', { pct: Math.round(confidence.score * 100), min: confidence.minutes }) }}</div>
          <ul class="small dim">
            <li v-for="n in confidenceNotes" :key="n">{{ n }}</li>
          </ul>
        </div>
        <p class="dim small">{{ t('wizard.nextTraining') }}</p>
        <div class="row" v-if="device">
          <button class="primary" @click="startTraining(device.recommended_tier)">
            <Dumbbell class="icon" :size="13" /> {{ t('wizard.startTier', { tier: t('wizard.tier.' + device.recommended_tier), epochs: device.tiers[device.recommended_tier] }) }}
          </button>
          <button @click="startTraining(device.recommended_tier === 'full' ? 'quick' : 'full')">
            {{ t('wizard.tierInstead', { tier: t('wizard.tier.' + (device.recommended_tier === 'full' ? 'quick' : 'full')) }) }}
          </button>
        </div>
        <div v-if="trainMsg" class="ok small">{{ trainMsg }}</div>
        <div class="nav">
          <button class="primary" @click="emit('close', true)">{{ t('common.done') }}</button>
        </div>
      </div>

      <div v-if="error" class="err small">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 55; }
.wiz { width: 620px; max-width: 94vw; max-height: 90vh; overflow-y: auto; padding: 18px 22px; }
.head { display: flex; align-items: center; gap: 12px; }
.head h3 { margin: 0; flex: 1; }
.close { border: none; background: transparent; }
.device { padding: 6px 0 0; }
.small { font-size: 12px; }
.body { display: flex; flex-direction: column; gap: 12px; padding-top: 12px; }
.field { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.consent-text { border-left: 3px solid var(--accent); margin: 0; padding: 8px 12px; font-size: 13px; background: var(--bg-elevated); border-radius: 0 6px 6px 0; }
.checkline { display: flex; gap: 8px; font-size: 13px; align-items: center; color: var(--warn); }
.nav { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-top: 8px; }
.ok { color: var(--ok); }
.err { color: var(--err); }
.reclive { background: var(--err) !important; border-color: var(--err) !important; color: #fff !important; }
.meter { position: relative; background: rgba(0,0,0,0.3); border-radius: 8px; }
.meter canvas { display: block; width: 100%; height: 90px; }
.note { position: absolute; right: 10px; top: 6px; font-family: monospace; font-size: 15px; color: var(--accent); }
.ex-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.ex-tab { font-size: 11px; padding: 3px 9px; }
.ex-tab.on { border-color: var(--accent); color: var(--accent); }
.ex-tab.done { border-color: var(--ok); }
.coach { font-size: 13.5px; background: var(--bg-elevated); border-radius: 8px; padding: 10px 14px; margin: 0; }
.qa { font-size: 12.5px; border-radius: 6px; padding: 8px 12px; }
.qa.pass { border: 1px solid var(--ok); color: var(--ok); }
.qa.warn { border: 1px solid var(--warn); color: var(--warn); }
.qa.fail { border: 1px solid var(--err); color: var(--err); }
.minutes { display: flex; align-items: center; gap: 10px; }
.minutes .conf-bar { flex: 1; }
.conf-bar { height: 10px; background: var(--bg-elevated); border-radius: 5px; overflow: hidden; }
.conf-bar div { height: 100%; background: linear-gradient(90deg, var(--accent), var(--ok)); }
ul { margin: 4px 0 0; padding-left: 18px; }
h4 { margin: 4px 0 0; }
</style>
