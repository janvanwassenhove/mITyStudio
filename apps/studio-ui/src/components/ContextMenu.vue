<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'

export interface MenuItem {
  label: string
  danger?: boolean
  action: () => void
}

const props = defineProps<{ x: number; y: number; items: MenuItem[] }>()
const emit = defineEmits<{ close: [] }>()

// keep the menu inside the viewport
const style = computed(() => ({
  left: Math.min(props.x, window.innerWidth - 200) + 'px',
  top: Math.min(props.y, window.innerHeight - props.items.length * 34 - 12) + 'px',
}))

function pick(item: MenuItem) {
  emit('close')
  item.action()
}
function onDown(e: PointerEvent) {
  if (!(e.target as HTMLElement).closest('.ctx-menu')) emit('close')
}
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => {
  window.addEventListener('pointerdown', onDown, true)
  window.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onDown, true)
  window.removeEventListener('keydown', onKey)
})
</script>

<template>
  <Teleport to="body">
    <div class="ctx-menu panel" :style="style">
      <button v-for="(it, i) in items" :key="i" class="ctx-item"
              :class="{ danger: it.danger }" @click="pick(it)">
        {{ it.label }}
      </button>
    </div>
  </Teleport>
</template>

<style scoped>
.ctx-menu {
  position: fixed; z-index: 90; min-width: 170px; padding: 4px;
  display: flex; flex-direction: column; box-shadow: 0 8px 24px rgba(0,0,0,0.6);
}
.ctx-item {
  border: none; background: transparent; text-align: left;
  padding: 7px 12px; font-size: 13px; border-radius: 5px;
}
.ctx-item:hover { background: var(--bg-elevated); }
.ctx-item.danger { color: var(--err); }
</style>
