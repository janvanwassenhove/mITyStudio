<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { countdownValue } from '../composables/countdown'

const { t } = useI18n()
</script>

<template>
  <Teleport to="body">
    <div v-if="countdownValue !== null" class="cd-overlay">
      <div class="cd-ring">
        <div :key="countdownValue" class="cd-num">
          {{ countdownValue && countdownValue > 0 ? countdownValue : t('rec.go') }}
        </div>
      </div>
      <div class="cd-hint">{{ t('rec.getReady') }}</div>
    </div>
  </Teleport>
</template>

<style scoped>
.cd-overlay {
  position: fixed; inset: 0; z-index: 120;
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 18px;
  background: rgba(8, 10, 14, 0.72); backdrop-filter: blur(3px);
}
.cd-ring {
  width: 190px; height: 190px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  border: 3px solid var(--err);
  box-shadow: 0 0 40px rgba(242, 85, 90, 0.5), inset 0 0 30px rgba(242, 85, 90, 0.25);
}
.cd-num {
  font-size: 96px; font-weight: 800; color: #fff; line-height: 1;
  animation: cd-pop 0.7s ease-out;
}
.cd-hint { color: var(--text-dim); font-size: 15px; letter-spacing: 0.04em; }
@keyframes cd-pop {
  0% { transform: scale(0.4); opacity: 0; }
  35% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(1); opacity: 0.85; }
}
@media (prefers-reduced-motion: reduce) {
  .cd-num { animation: none; }
}
</style>
