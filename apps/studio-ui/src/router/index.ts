import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'studio', component: () => import('../views/StudioView.vue') },
    { path: '/assets', name: 'assets', component: () => import('../views/AssetLibraryView.vue') },
    { path: '/voices', name: 'voices', component: () => import('../views/VoiceLibraryView.vue') },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue') },
  ],
})
