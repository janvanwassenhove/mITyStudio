<script setup lang="ts">
import { computed } from 'vue'
import {
  AudioWaveform, Drum, Guitar, KeyboardMusic, Megaphone, Mic, Music4,
  Piano, Repeat, Sparkles,
} from 'lucide-vue-next'
import { trackColor } from '../lib/trackColors'

const props = defineProps<{ type: string; size?: number; colored?: boolean }>()

const ICONS: Record<string, unknown> = {
  drums: Drum, bass: AudioWaveform, guitar: Guitar, keys: Piano,
  synth: KeyboardMusic, strings: Music4, brass: Megaphone, sample: Repeat,
  lead_vocal: Mic, backing_vocal: Mic, fx: Sparkles,
}

const icon = computed(() => ICONS[props.type] ?? Sparkles)
const style = computed(() =>
  props.colored ? { color: trackColor(props.type) } : {})
</script>

<template>
  <component :is="icon" class="icon" :size="size ?? 16" :style="style" aria-hidden="true" />
</template>
