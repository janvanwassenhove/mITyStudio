import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import * as Tone from 'tone'
import './style.css'
import App from './App.vue'

// Make Tone.js globally available for debugging
;(window as any).Tone = Tone

// Import translations
import en from './locales/en.json'
import es from './locales/es.json'
import nl from './locales/nl.json'
import fr from './locales/fr.json'
import de from './locales/de.json'
import it from './locales/it.json'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  globalInjection: true,
  messages: {
    en,
    es,
    nl,
    fr,
    de,
    it
  }
})

const pinia = createPinia()
const app = createApp(App)

app.use(pinia)
app.use(i18n)

// Add theme transition class to body for smooth transitions
document.body.classList.add('theme-transition')

app.mount('#app')
