<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api/client'

interface LlmSettings {
  provider: string
  model: string
  api_key_set: boolean
  temperature: number
  max_tokens: number
}

const settings = ref<LlmSettings | null>(null)
const apiKey = ref('')
const testResult = ref('')
const saving = ref(false)

async function load() {
  settings.value = await api.get<LlmSettings>('/settings/llm')
}

async function save() {
  if (!settings.value) return
  saving.value = true
  try {
    settings.value = await api.put<LlmSettings>('/settings/llm', {
      provider: settings.value.provider,
      model: settings.value.model,
      temperature: settings.value.temperature,
      max_tokens: settings.value.max_tokens,
      ...(apiKey.value ? { api_key: apiKey.value } : {}),
    })
    apiKey.value = ''
    testResult.value = 'saved'
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
        Keys are stored locally (never committed to source control).
      </p>
      <label>Provider
        <select v-model="settings.provider">
          <option value="mock">Mock (no API key needed)</option>
          <option value="anthropic">Anthropic (Claude)</option>
        </select>
      </label>
      <label>Model
        <input v-model="settings.model" placeholder="e.g. claude-sonnet-5" />
      </label>
      <label>API key
        <input v-model="apiKey" type="password"
               :placeholder="settings.api_key_set ? '•••••• (already set — enter to replace)' : 'sk-ant-…'" />
      </label>
      <label>Temperature
        <input v-model.number="settings.temperature" type="number" min="0" max="1" step="0.1" style="width: 90px" />
      </label>
      <label>Max tokens
        <input v-model.number="settings.max_tokens" type="number" min="256" max="64000" style="width: 110px" />
      </label>
      <div class="row-btns">
        <button class="primary" :disabled="saving" @click="save">Save</button>
        <button @click="testConnection">Test connection</button>
        <span class="dim small">{{ testResult }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings { padding: 24px; max-width: 560px; }
.form { padding: 18px; display: flex; flex-direction: column; gap: 12px; margin-top: 12px; }
h3 { margin: 0; }
label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-dim); }
.row-btns { display: flex; gap: 8px; align-items: center; }
.small { font-size: 11px; }
</style>
