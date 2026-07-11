import { ref, type Ref } from 'vue'

// Shared count-in state: a single CountdownOverlay (mounted in App.vue) renders
// whatever runCountdown sets here, so any recording flow can trigger it.
// Backed by a globalThis singleton so the overlay and the recording flows
// always share ONE ref even if the module is duplicated (Vite HMR can create
// dual instances otherwise, leaving the overlay bound to a stale ref).
const _g = globalThis as unknown as { __mityCountdown?: Ref<number | null> }
export const countdownValue: Ref<number | null> =
  _g.__mityCountdown ?? (_g.__mityCountdown = ref<number | null>(null))   // null = hidden, 0 = "go"

let runToken = 0
const delay = (ms: number) => new Promise<void>((r) => window.setTimeout(r, ms))

let ctx: AudioContext | null = null
function beep(accent: boolean) {
  try {
    if (!ctx) ctx = new AudioContext()
    const t = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.frequency.value = accent ? 1320 : 880
    gain.gain.setValueAtTime(0.25, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12)
    osc.connect(gain).connect(ctx.destination)
    osc.start(t)
    osc.stop(t + 0.13)
  } catch { /* no audio available — the visual count-in still runs */ }
}

/** Visual + audible count-in (3 · 2 · 1 · go). Resolves when it finishes so
 *  callers can `await runCountdown()` right before starting the recorder.
 *  A newer call supersedes an in-flight one; `finally` guarantees the overlay
 *  is always dismissed. */
export async function runCountdown(from = 3, stepMs = 750): Promise<void> {
  const token = ++runToken
  try {
    for (let n = from; n > 0; n--) {
      if (token !== runToken) return          // superseded by a newer count-in
      countdownValue.value = n
      beep(n === from)
      await delay(stepMs)
    }
    if (token !== runToken) return
    countdownValue.value = 0                   // brief "go" flash
    beep(true)
    await delay(300)
  } finally {
    if (token === runToken) countdownValue.value = null
  }
}
