<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileMusic, MessageSquare, Mic, Music2, Repeat } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const emit = defineEmits<{ close: [] }>()
const { t } = useI18n()
const router = useRouter()

const step = ref(0)
const STEPS = [
  { key: 'soundfonts', icon: Music2, route: '/assets' },
  { key: 'samples', icon: Repeat, route: '/assets' },
  { key: 'voice', icon: Mic, route: '/voices' },
  { key: 'scores', icon: FileMusic, route: '/assets' },
  { key: 'chat', icon: MessageSquare, route: '/' },
] as const

function finish(goTo?: string) {
  localStorage.setItem('mity-onboarding-done', '1')
  if (goTo) void router.push(goTo)
  emit('close')
}
</script>

<template>
  <div class="overlay" @click.self="finish()">
    <div class="guide panel">
      <div class="head">
        <h3>{{ t('onboard.title') }}</h3>
        <button class="close" @click="finish()">✕</button>
      </div>
      <p class="dim intro">{{ t('onboard.intro') }}</p>

      <div class="steps-row">
        <button v-for="(s, i) in STEPS" :key="s.key" class="step-dot"
                :class="{ on: step === i, seen: step > i }" @click="step = i">
          <component :is="s.icon" class="icon" :size="15" />
        </button>
      </div>

      <div class="card">
        <component :is="STEPS[step].icon" class="icon big" :size="30" />
        <h4>{{ t(`onboard.${STEPS[step].key}.title`) }}</h4>
        <p>{{ t(`onboard.${STEPS[step].key}.body`) }}</p>
        <button class="goto" @click="finish(STEPS[step].route)">
          {{ t(`onboard.${STEPS[step].key}.action`) }} →
        </button>
      </div>

      <div class="nav">
        <button @click="finish()">{{ t('onboard.skip') }}</button>
        <span class="dim small">{{ step + 1 }} / {{ STEPS.length }}</span>
        <button v-if="step < STEPS.length - 1" class="primary" @click="step++">
          {{ t('common.continue') }} →</button>
        <button v-else class="primary" @click="finish()">{{ t('common.done') }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 70; }
.guide { width: 520px; max-width: 94vw; padding: 18px 22px; display: flex; flex-direction: column; gap: 12px; }
.head { display: flex; align-items: center; justify-content: space-between; }
.head h3 { margin: 0; }
.close { border: none; background: transparent; }
.intro { font-size: 13px; margin: 0; }
.steps-row { display: flex; gap: 6px; justify-content: center; }
.step-dot { padding: 6px 10px; border-radius: 8px; color: var(--text-dim); }
.step-dot.on { border-color: var(--accent); color: var(--accent); }
.step-dot.seen { color: var(--ok); }
.card { display: flex; flex-direction: column; align-items: center; gap: 8px; text-align: center; background: var(--bg-elevated); border-radius: 10px; padding: 18px; min-height: 170px; }
.card .big { color: var(--accent); }
.card h4 { margin: 0; }
.card p { margin: 0; font-size: 13px; color: var(--text-dim); line-height: 1.5; }
.goto { border-color: var(--accent); color: var(--accent); font-size: 12px; }
.nav { display: flex; align-items: center; justify-content: space-between; }
.small { font-size: 11px; }
</style>
