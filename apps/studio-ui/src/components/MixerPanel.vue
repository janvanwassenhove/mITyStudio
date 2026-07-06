<script setup lang="ts">
import { computed, ref } from 'vue'
import { useStudioStore } from '../stores/studio'

const studio = useStudioStore()
const saving = ref(false)
const tracks = computed(() => studio.project?.tracks ?? [])

let saveTimer: ReturnType<typeof setTimeout> | null = null
function queueSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    saving.value = true
    try { await studio.saveProject() } finally { saving.value = false }
  }, 500)
}
</script>

<template>
  <div class="mixer">
    <div v-if="!tracks.length" class="dim empty">No tracks yet.</div>
    <div v-for="t in tracks" :key="t.id" class="strip">
      <div class="strip-name" :title="t.name">{{ t.name }}</div>
      <input
        class="fader" type="range" min="0" max="1.5" step="0.01"
        :value="t.volume"
        @input="t.volume = Number(($event.target as HTMLInputElement).value); queueSave()"
      />
      <div class="dim tiny">{{ (20 * Math.log10(t.volume || 0.001)).toFixed(1) }} dB</div>
      <input
        class="pan" type="range" min="-1" max="1" step="0.05"
        :value="t.pan"
        @input="t.pan = Number(($event.target as HTMLInputElement).value); queueSave()"
        title="pan"
      />
      <div class="btns">
        <button :class="{ on: t.mute }" title="mute" @click="t.mute = !t.mute; queueSave()">M</button>
        <button :class="{ on: t.solo, solo: t.solo }" title="solo" @click="t.solo = !t.solo; queueSave()">S</button>
      </div>
      <div class="dim tiny">{{ (t.effects?.effects ?? []).filter(e => e.enabled).length }} fx</div>
    </div>
    <div v-if="studio.project" class="strip master">
      <div class="strip-name">Master</div>
      <input
        class="fader" type="range" min="0" max="1.5" step="0.01"
        :value="studio.project.mix_settings.master_volume"
        @input="studio.project!.mix_settings.master_volume = Number(($event.target as HTMLInputElement).value); queueSave()"
      />
      <div class="dim tiny">{{ (20 * Math.log10(studio.project.mix_settings.master_volume || 0.001)).toFixed(1) }} dB</div>
      <label class="tiny opt"><input type="checkbox" v-model="studio.project.mix_settings.normalize" @change="queueSave()" /> norm</label>
      <label class="tiny opt"><input type="checkbox" v-model="studio.project.mix_settings.limiter" @change="queueSave()" /> limit</label>
      <div class="dim tiny">{{ (studio.project.mix_settings.master_effects?.effects ?? []).length }} fx</div>
    </div>
    <div v-if="saving" class="dim tiny saving">saving…</div>
  </div>
</template>

<style scoped>
.mixer { display: flex; gap: 8px; padding: 10px; overflow-x: auto; height: 100%; align-items: stretch; }
.empty { align-self: center; margin: auto; }
.strip { display: flex; flex-direction: column; align-items: center; gap: 6px; width: 80px; flex: none; background: var(--bg-elevated); border-radius: 6px; padding: 8px 4px; }
.strip-name { font-size: 11px; font-weight: 600; max-width: 72px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fader { writing-mode: vertical-lr; direction: rtl; flex: 1; width: 22px; min-height: 60px; }
.pan { width: 64px; }
.btns { display: flex; gap: 4px; }
.btns button { padding: 2px 8px; font-size: 11px; }
.btns button.on { background: var(--warn); color: #000; border-color: var(--warn); }
.btns button.on.solo { background: var(--ok); border-color: var(--ok); }
.tiny { font-size: 10px; }
.master { border: 1px solid var(--accent-2); margin-left: auto; }
.opt { display: flex; gap: 3px; align-items: center; color: var(--text-dim); }
.saving { position: absolute; right: 12px; bottom: 6px; }
</style>
