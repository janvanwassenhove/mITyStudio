<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { ChatResponse } from '../api/types'
import { currentLocale } from '../i18n'
import { useStudioStore } from '../stores/studio'

const { t } = useI18n()
const studio = useStudioStore()

interface LlmUsage { model: string; input_tokens: number; output_tokens: number; error_kind?: string }
interface ChatMsg {
  role: 'user' | 'assistant'
  text: string
  operations?: ChatResponse['operations']
  usage?: LlmUsage
}

const messages = ref<ChatMsg[]>([])
const input = ref('')
const busy = ref(false)
const scrollEl = ref<HTMLElement | null>(null)
const sessionTokens = ref(0)

const fmtTok = (n: number) => (n >= 1000 ? (n / 1000).toFixed(1) + 'k' : String(n))

async function send() {
  const text = input.value.trim()
  if (!text || busy.value) return
  if (!studio.project) {
    messages.value.push({ role: 'assistant', text: t('chat.noProject') })
    return
  }
  input.value = ''
  messages.value.push({ role: 'user', text })
  busy.value = true
  try {
    const res = await api.post<ChatResponse>(`/projects/${studio.project.id}/chat`,
      { message: text, language: currentLocale() })
    const usage = (res as ChatResponse & { usage?: LlmUsage }).usage
    messages.value.push({ role: 'assistant', text: res.reply,
                          operations: res.operations, usage })
    if (usage) sessionTokens.value += (usage.input_tokens + usage.output_tokens)
    await studio.reloadCurrent()
  } catch (e) {
    messages.value.push({ role: 'assistant', text: `Error: ${String(e)}` })
  } finally {
    busy.value = false
    await nextTick()
    scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight })
  }
}
</script>

<template>
  <div class="chat">
    <div ref="scrollEl" class="messages">
      <div v-if="!messages.length" class="dim hint">
        {{ t('chat.hint') }}
      </div>
      <div v-for="(m, i) in messages" :key="i" class="msg" :class="m.role">
        <div class="bubble" :class="{ 'err-bubble': m.usage?.error_kind }">{{ m.text }}</div>
        <div v-if="m.usage?.error_kind && m.usage.error_kind !== 'error'" class="err-hint">
          {{ t('chat.err.' + m.usage.error_kind) }}
        </div>
        <div v-else-if="m.usage && (m.usage.input_tokens || m.usage.output_tokens)" class="usage dim">
          {{ m.usage.model }} · {{ fmtTok(m.usage.input_tokens) }} → {{ fmtTok(m.usage.output_tokens) }} tokens
        </div>
        <ul v-if="m.operations?.length" class="ops">
          <li v-for="(op, j) in m.operations" :key="j" :class="{ failed: !op.applied }">
            <span class="op-type">{{ op.op_type }}</span> — {{ op.summary }}
            <span v-if="op.error" class="err-text">({{ op.error }})</span>
          </li>
        </ul>
      </div>
      <div v-if="busy" class="dim hint">{{ t('chat.planning') }}</div>
    </div>
    <div v-if="sessionTokens" class="session-usage dim">
      {{ t('chat.sessionTokens', { n: fmtTok(sessionTokens) }) }}
    </div>
    <div class="input-row">
      <textarea
        v-model="input" rows="2" :placeholder="t('chat.placeholder')"
        @keydown.enter.exact.prevent="send"
      />
      <button class="primary" :disabled="busy || !input.trim()" @click="send">{{ t('chat.send') }}</button>
    </div>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.messages { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 8px; }
.hint { font-size: 12px; }
.msg.user { align-self: flex-end; max-width: 90%; }
.msg.assistant { align-self: flex-start; max-width: 95%; }
.bubble { padding: 8px 10px; border-radius: 8px; font-size: 13px; white-space: pre-wrap; }
.msg.user .bubble { background: var(--accent); color: #fff; }
.msg.assistant .bubble { background: var(--bg-elevated); }
.ops { margin: 4px 0 0; padding-left: 18px; font-size: 11px; color: var(--text-dim); }
.ops .op-type { color: var(--accent); font-family: monospace; }
.ops .failed { color: var(--err); }
.err-text { color: var(--err); }
.err-bubble { border: 1px solid var(--err); }
.err-hint { font-size: 11px; color: var(--warn); margin-top: 3px; }
.usage { font-size: 10px; margin-top: 2px; }
.session-usage { font-size: 10px; padding: 2px 10px; text-align: right; flex: none; }
.input-row { display: flex; gap: 6px; padding: 8px; border-top: 1px solid var(--border); flex: none; }
textarea { flex: 1; resize: none; }
</style>
