import { createI18n } from 'vue-i18n'
import en from './en'
import nl from './nl'
import fr from './fr'
import de from './de'

export const LOCALES = [
  { code: 'en', label: 'English' },
  { code: 'nl', label: 'Nederlands' },
  { code: 'fr', label: 'Français' },
  { code: 'de', label: 'Deutsch' },
] as const
export type LocaleCode = (typeof LOCALES)[number]['code']

const STORAGE_KEY = 'mity-locale'

function initialLocale(): LocaleCode {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved && LOCALES.some(l => l.code === saved)) return saved as LocaleCode
  const nav = navigator.language.slice(0, 2)
  return (LOCALES.some(l => l.code === nav) ? nav : 'en') as LocaleCode
}

export const i18n = createI18n({
  legacy: false,
  globalInjection: true,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { en, nl, fr, de },
  missingWarn: false,
  fallbackWarn: false,
})

document.documentElement.lang = i18n.global.locale.value

export function currentLocale(): LocaleCode {
  return i18n.global.locale.value as LocaleCode
}

export function setLocale(code: LocaleCode) {
  i18n.global.locale.value = code
  localStorage.setItem(STORAGE_KEY, code)
  document.documentElement.lang = code
}
