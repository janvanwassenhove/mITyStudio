/**
 * Ask-first update detection.
 *
 * Desktop: the Electron main process watches GitHub Releases
 * (electron-updater) and tells us via IPC; nothing downloads until the
 * user clicks. Browser/dev: one GET /api/updates/check (backend-cached)
 * and the action is a link to the release page.
 */
import { ref } from 'vue'
import { isDesktop } from './uiPrefs'

export type UpdatePhase = 'idle' | 'available' | 'downloading' | 'downloaded'
  | 'error'

export const updatePhase = ref<UpdatePhase>('idle')
export const updateVersion = ref('')
export const updateUrl = ref('')
export const updatePercent = ref(0)
export const updateError = ref('')

interface MityUpdater {
  onUpdateAvailable?: (cb: (i: { version: string }) => void) => void
  onUpdateProgress?: (cb: (p: { percent: number }) => void) => void
  onUpdateDownloaded?: (cb: (i: { version: string }) => void) => void
  onUpdateError?: (cb: (e: { message: string }) => void) => void
  downloadUpdate?: () => Promise<{ ok: boolean; error?: string }>
  installUpdate?: () => Promise<void>
}

function bridge(): MityUpdater | undefined {
  return (window as unknown as { mity?: MityUpdater }).mity
}

/** True only inside the real desktop shell (preload bridge present) — a UA
 *  sniff alone misfires in other Electron-embedded browsers. */
export function canSelfUpdate(): boolean {
  return isDesktop && !!bridge()?.downloadUpdate
}

const DISMISS_KEY = 'mity-update-dismissed'

function dismissed(version: string): boolean {
  return localStorage.getItem(DISMISS_KEY) === version
}

export function initUpdateWatcher(): void {
  const m = bridge()
  if (canSelfUpdate() && m?.onUpdateAvailable) {
    m.onUpdateAvailable((i) => {
      if (dismissed(i.version)) return
      updateVersion.value = i.version
      updatePhase.value = 'available'
    })
    m.onUpdateProgress?.((p) => { updatePercent.value = p.percent })
    m.onUpdateDownloaded?.(() => { updatePhase.value = 'downloaded' })
    m.onUpdateError?.((e) => {
      updateError.value = e.message
      updatePhase.value = 'error'
    })
    return
  }
  // browser/dev: one cached check against the backend
  fetch('/api/updates/check')
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      if (!d?.update_available || dismissed(d.latest)) return
      updateVersion.value = d.latest
      updateUrl.value = d.url
      updatePhase.value = 'available'
    })
    .catch(() => { /* offline — the health banner covers that */ })
}

/** User said yes: desktop downloads the release; web opens the page. */
export async function startUpdate(): Promise<void> {
  const m = bridge()
  if (canSelfUpdate() && m?.downloadUpdate) {
    updatePhase.value = 'downloading'
    updatePercent.value = 0
    const res = await m.downloadUpdate()
    if (res && !res.ok) {
      updateError.value = res.error ?? 'download failed'
      updatePhase.value = 'error'
    }
    return
  }
  window.open(updateUrl.value || 'https://github.com/janvanwassenhove/mITyStudio/releases/latest',
              '_blank')
}

/** Always opens the release page in a browser — the escape hatch when the
 *  in-app download fails, where retrying it would just fail again. */
export function openReleasePage(): void {
  window.open(updateUrl.value
    || 'https://github.com/janvanwassenhove/mITyStudio/releases/latest',
    '_blank')
}

export function installUpdate(): void {
  void bridge()?.installUpdate?.()
}

export function dismissUpdate(): void {
  localStorage.setItem(DISMISS_KEY, updateVersion.value)
  updatePhase.value = 'idle'
}
