<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/client'

interface LlmSettings {
  provider: string
  model: string
  base_url: string
  temperature: number
  max_tokens: number
  providers: string[]
  api_keys_set: Record<string, boolean>
  api_key_sources: Record<string, string | null>
  api_key_set: boolean
}

const PROVIDER_INFO: Record<string, { label: string; modelHint: string; urlHint?: string; keyEnv?: string }> = {
  mock: { label: 'Mock (no API key needed)', modelHint: 'keyword planner — no model' },
  anthropic: { label: 'Anthropic (Claude)', modelHint: 'e.g. claude-sonnet-5', keyEnv: 'ANTHROPIC_API_KEY' },
  openai: { label: 'OpenAI (GPT)', modelHint: 'e.g. gpt-5.2', keyEnv: 'OPENAI_API_KEY' },
  custom: {
    label: 'Custom — any OpenAI-compatible API',
    modelHint: 'model id as your provider names it',
    urlHint: 'e.g. https://openrouter.ai/api/v1, https://api.groq.com/openai/v1, http://localhost:11434/v1 (Ollama)',
    keyEnv: 'MITY_LLM_API_KEY',
  },
}

const settings = ref<LlmSettings | null>(null)
const apiKey = ref('')
const testResult = ref('')
const saving = ref(false)
const models = ref<string[]>([])
const modelsSource = ref('')
const loadingModels = ref(false)
const customModel = ref(false)  // manual entry when the list lacks the model

async function loadModels() {
  const s = settings.value
  if (!s || s.provider === 'mock') { models.value = []; return }
  loadingModels.value = true
  try {
    const r = await api.get<{ models: string[]; source: string }>(
      `/settings/llm/models?provider=${s.provider}&base_url=${encodeURIComponent(s.base_url)}`)
    models.value = r.models
    modelsSource.value = r.source
    customModel.value = models.value.length === 0 ||
      (!!s.model && !models.value.includes(s.model))
    if (!s.model && models.value.length) s.model = models.value[0]
  } catch {
    models.value = []
    customModel.value = true
  } finally {
    loadingModels.value = false
  }
}

const info = computed(() => PROVIDER_INFO[settings.value?.provider ?? 'mock'] ?? PROVIDER_INFO.mock)
const needsKey = computed(() => settings.value != null && settings.value.provider !== 'mock')
const needsUrl = computed(() => settings.value?.provider === 'custom')
const keySet = computed(() =>
  settings.value?.api_keys_set?.[settings.value.provider] ?? false)
const keySource = computed(() =>
  settings.value?.api_key_sources?.[settings.value.provider] ?? null)
const keyStatusText = computed(() => {
  if (!keySet.value) return '○ no key found'
  if (keySource.value === 'stored') return '● key stored in local_settings.json'
  return `● using key from environment variable ${keySource.value}`
})

async function load() {
  settings.value = await api.get<LlmSettings>('/settings/llm')
  await loadModels()
}

async function save() {
  if (!settings.value) return
  saving.value = true
  try {
    settings.value = await api.put<LlmSettings>('/settings/llm', {
      provider: settings.value.provider,
      model: settings.value.model,
      base_url: settings.value.base_url,
      temperature: settings.value.temperature,
      max_tokens: settings.value.max_tokens,
      ...(apiKey.value ? { api_key: apiKey.value } : {}),
    })
    apiKey.value = ''
    testResult.value = 'saved'
  } catch (e) {
    testResult.value = String(e)
  } finally {
    saving.value = false
  }
}

async function testConnection() {
  testResult.value = 'testing…'
  try {
    const r = await api.post<{ ok: boolean; message: string }>('/settings/llm/test')
    testResult.value = (r.ok ? '✓ ' : '✗ ') + r.message
  } catch (e) {
    testResult.value = '✗ ' + String(e)
  }
}

function onProviderChange() {
  if (!settings.value) return
  settings.value.model = ''
  testResult.value = ''
  customModel.value = false
  void loadModels()
}

onMounted(load)
</script>

<template>
  <div class="settings">
    <h2>Settings</h2>
    <div v-if="settings" class="panel form">
      <h3>LLM provider</h3>
      <p class="dim small">
        Used by the chat panel to plan song changes. The LLM only produces
        structured operations — it never writes files or audio directly.
        Keys are stored per provider in a git-ignored local file and are
        never returned by the API.
      </p>
      <label>Provider
        <select v-model="settings.provider" @change="onProviderChange">
          <option v-for="p in settings.providers" :key="p" :value="p">
            {{ PROVIDER_INFO[p]?.label ?? p }}
          </option>
        </select>
      </label>
      <label v-if="needsUrl">Base URL
        <input v-model="settings.base_url" :placeholder="info.urlHint" @change="loadModels" />
        <span class="dim tiny">{{ info.urlHint }}</span>
      </label>
      <label v-if="settings.provider !== 'mock'">
        Model
        <span class="dim tiny">
          <template v-if="loadingModels">loading model list…</template>
          <template v-else-if="modelsSource === 'live'">{{ models.length }} models fetched from provider</template>
          <template v-else-if="models.length">known models (no live list available)</template>
        </span>
        <div class="model-row">
          <select v-if="!customModel && models.length" v-model="settings.model" style="flex: 1">
            <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
          </select>
          <input v-else v-model="settings.model" :placeholder="info.modelHint" style="flex: 1" />
          <button v-if="models.length" class="tiny-toggle" type="button"
                  @click="customModel = !customModel">
            {{ customModel ? 'pick from list' : 'type manually' }}
          </button>
          <button class="tiny-toggle" type="button" :disabled="loadingModels" @click="loadModels">↻</button>
        </div>
      </label>
      <label v-if="needsKey">
        API key
        <span class="key-status" :class="{ set: keySet }">
          {{ keyStatusText }}
          <template v-if="!keySet && info.keyEnv"> · also checks env var {{ info.keyEnv }}</template>
        </span>
        <input v-model="apiKey" type="password"
               :placeholder="keySet ? '•••••• (enter to replace, blank keeps current)' : settings.provider === 'custom' ? 'optional — env vars and local servers work without one' : 'paste API key'" />
      </label>
      <div class="row2">
        <label>Temperature
          <input v-model.number="settings.temperature" type="number" min="0" max="1" step="0.1" style="width: 90px" />
        </label>
        <label>Max tokens
          <input v-model.number="settings.max_tokens" type="number" min="256" max="64000" style="width: 110px" />
        </label>
      </div>
      <div class="row-btns">
        <button class="primary" :disabled="saving" @click="save">Save</button>
        <button @click="testConnection">Test connection</button>
        <span class="dim small">{{ testResult }}</span>
      </div>
      <div class="dim tiny keys-overview">
        Keys found:
        <span v-for="(set, p) in settings.api_keys_set" :key="p" class="key-chip" :class="{ set }"
              :title="settings.api_key_sources[p] ? `source: ${settings.api_key_sources[p]}` : 'no key stored or in environment'">
          {{ p }} {{ set ? (settings.api_key_sources[p] === 'stored' ? '✓ file' : '✓ env') : '—' }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings { padding: 24px; max-width: 620px; }
.form { padding: 18px; display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
h3 { margin: 0; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.row2 { display: flex; gap: 16px; }
.row-btns { display: flex; gap: 8px; align-items: center; }
.small { font-size: 11px; }
.tiny { font-size: 10px; }
.key-status { font-size: 11px; }
.key-status.set { color: var(--ok); }
.keys-overview { display: flex; gap: 8px; align-items: center; border-top: 1px solid var(--border); padding-top: 10px; }
.key-chip { background: var(--bg-elevated); border-radius: 4px; padding: 1px 7px; }
.key-chip.set { color: var(--ok); }
.model-row { display: flex; gap: 6px; }
.tiny-toggle { padding: 2px 8px; font-size: 11px; }
</style>
