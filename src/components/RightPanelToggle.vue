<template>
  <div class="right-panel-container">
    <div class="panel-header">
      <div class="panel-tabs">
        <button 
          class="tab-btn"
          :class="{ 'active': activeView === 'structure' }"
          @click="setActiveView('structure')"
        >
          <FileText class="icon" />
          Structure
        </button>
        <button 
          class="tab-btn"
          :class="{ 'active': activeView === 'ai' }"
          @click="setActiveView('ai')"
        >
          <Bot class="icon" />
          AI Assistant
        </button>
      </div>
    </div>
    
    <div class="panel-content">
      <Transition name="panel-fade" mode="out-in">
        <JSONStructurePanel v-if="activeView === 'structure'" key="structure" />
        <AIChat v-else key="ai" />
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { FileText, Bot } from 'lucide-vue-next'
import JSONStructurePanel from './JSONStructurePanel.vue'
import AIChat from './AIChat.vue'

const activeView = ref<'structure' | 'ai'>('structure')

const setActiveView = (view: 'structure' | 'ai') => {
  activeView.value = view
}
</script>

<style scoped>
.right-panel-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--background);
}

.panel-header {
  flex-shrink: 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.panel-tabs {
  display: flex;
}

.tab-btn {
  flex: 1;
  padding: 0.875rem 1rem;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s ease;
  border-bottom: 2px solid transparent;
}

.tab-btn:hover {
  background: var(--border);
  color: var(--text);
}

.tab-btn.active {
  background: var(--background);
  color: var(--primary);
  border-bottom-color: var(--primary);
}

.tab-btn .icon {
  width: 16px;
  height: 16px;
}

.panel-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* Transition animations */
.panel-fade-enter-active,
.panel-fade-leave-active {
  transition: all 0.3s ease;
}

.panel-fade-enter-from {
  opacity: 0;
  transform: translateX(20px);
}

.panel-fade-leave-to {
  opacity: 0;
  transform: translateX(-20px);
}

@media (max-width: 768px) {
  .tab-btn {
    padding: 0.75rem 0.5rem;
    font-size: 0.8125rem;
  }
  
  .tab-btn .icon {
    width: 14px;
    height: 14px;
  }
}
</style>
