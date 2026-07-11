<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
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

// --- playful "thinking" indicator while the LLM works -----------------------
// Cycling music-themed status phrases so long reasoning waits feel alive.
const THINK_PHASES = ['reading', 'composing', 'harmony', 'instruments',
                      'melody', 'mixing', 'almost'] as const
const thinkTick = ref(0)
const elapsed = ref(0)
let phaseTimer: ReturnType<typeof setInterval> | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null

const thinkingText = computed(() => {
  const n = THINK_PHASES.length
  const i = thinkTick.value < n
    ? thinkTick.value
    : 1 + ((thinkTick.value - n) % (n - 1))   // loop the "working" phases
  return t('chat.think.' + THINK_PHASES[i])
})

function startThinking() {
  thinkTick.value = 0
  elapsed.value = 0
  phaseTimer = setInterval(() => { thinkTick.value++ }, 2600)
  elapsedTimer = setInterval(() => { elapsed.value++ }, 1000)
}
function stopThinking() {
  if (phaseTimer) { clearInterval(phaseTimer); phaseTimer = null }
  if (elapsedTimer) { clearInterval(elapsedTimer); elapsedTimer = null }
}
onUnmounted(stopThinking)

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
  startThinking()
  await nextTick()
  scrollEl.value?.scrollTo({ top: scrollEl.value.scrollHeight })
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
    stopThinking()
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
      <div v-if="busy" class="thinking">
        <span class="eq" aria-hidden="true"><i /><i /><i /><i /><i /></span>
        <span class="think-text">{{ thinkingText }}</span>
        <span v-if="elapsed >= 3" class="think-time dim">· {{ t('chat.elapsedS', { s: elapsed }) }}</span>
      </div>
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

/* animated "thinking" indicator */
.thinking {
  align-self: flex-start; display: flex; align-items: center; gap: 8px;
  background: var(--bg-elevated); border-radius: 8px; padding: 7px 12px;
  font-size: 13px; max-width: 95%;
}
.think-text {
  background: linear-gradient(90deg, var(--text-dim) 0%, var(--text) 50%, var(--text-dim) 100%);
  background-size: 200% 100%;
  -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: think-shimmer 2s linear infinite;
}
.think-time { font-size: 11px; }
@keyframes think-shimmer { to { background-position: -200% 0; } }
.eq { display: inline-flex; align-items: flex-end; gap: 2px; height: 15px; }
.eq i {
  width: 3px; height: 4px; border-radius: 1px;
  background: linear-gradient(var(--accent), var(--accent-2));
  animation: eq-bounce 0.9s ease-in-out infinite;
}
.eq i:nth-child(1) { animation-delay: 0s; }
.eq i:nth-child(2) { animation-delay: 0.15s; }
.eq i:nth-child(3) { animation-delay: 0.3s; }
.eq i:nth-child(4) { animation-delay: 0.45s; }
.eq i:nth-child(5) { animation-delay: 0.6s; }
@keyframes eq-bounce { 0%, 100% { height: 4px; } 50% { height: 15px; } }
@media (prefers-reduced-motion: reduce) {
  .think-text, .eq i { animation: none; }
  .think-text { color: var(--text-dim); }
}
</style>
