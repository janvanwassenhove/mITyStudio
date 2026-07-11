import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api } from '../api/client'
import type { PlaybackManifest } from '../api/types'
import { useStudioStore } from './studio'

/**
 * Playback engine.
 * - If the project has rendered stems, they are played via Web Audio with
 *   per-track gain/pan taken from the manifest mixer state.
 * - Without stems, the transport still runs a synchronized clock so the
 *   playhead, timeline and karaoke view work.
 * All timing comes from the PlaybackManifest; nothing is guessed here.
 */
export const usePlaybackStore = defineStore('playback', () => {
  const studio = useStudioStore()

  const playing = ref(false)
  const playhead = ref(0) // seconds
  const stemsLoaded = ref(0)
  const preparing = ref(false)      // auto-render in progress
  const renderWarnings = ref<string[]>([])
  const metronome = ref(false)

  // --- metronome: lookahead-scheduled clicks via WebAudio ---
  let metroTimer: number | null = null
  let nextBeatIndex = 0

  function metroClick(when: number, accent: boolean) {
    if (!ctx) return
    const osc = ctx.createOscillator()
    const g = ctx.createGain()
    osc.frequency.value = accent ? 1568 : 1046
    g.gain.setValueAtTime(0.22, when)
    g.gain.exponentialRampToValueAtTime(0.001, when + 0.05)
    osc.connect(g).connect(ctx.destination)
    osc.start(when)
    osc.stop(when + 0.06)
  }

  function startMetronome() {
    const m = studio.manifest
    if (!ctx || !m || metroTimer !== null) return
    const spb = 60 / m.bpm
    nextBeatIndex = Math.ceil((playhead.value - 1e-6) / spb)
    metroTimer = window.setInterval(() => {
      if (!ctx || !playing.value || !metronome.value) return
      const songNow = startedAtSongTime + (ctx.currentTime - startedAtCtxTime)
      while (nextBeatIndex * spb < songNow + 0.15) {
        const beatTime = nextBeatIndex * spb
        if (beatTime >= songNow - 0.02) {
          metroClick(startedAtCtxTime + (beatTime - startedAtSongTime),
                     nextBeatIndex % m.beats_per_bar === 0)
        }
        nextBeatIndex++
      }
    }, 60)
  }

  function stopMetronome() {
    if (metroTimer !== null) {
      clearInterval(metroTimer)
      metroTimer = null
    }
  }

  watch(metronome, (on) => {
    if (on && playing.value) startMetronome()
    if (!on) stopMetronome()
  })

  let ctx: AudioContext | null = null
  let sources: AudioBufferSourceNode[] = []
  let buffers = new Map<string, AudioBuffer>() // track_id -> buffer
  let startedAtCtxTime = 0
  let startedAtSongTime = 0
  let raf = 0

  const duration = computed(() => studio.manifest?.duration_seconds ?? 0)

  function manifestStems(m: PlaybackManifest) {
    return m.stems ?? []
  }

  async function loadStems() {
    const m = studio.manifest
    buffers = new Map()
    stemsLoaded.value = 0
    if (!m) return
    if (!ctx) ctx = new AudioContext()
    await Promise.all(manifestStems(m).map(async (s) => {
      try {
        const res = await fetch(`/api/projects/${m.project_id}/stems/${s.track_id}/file`)
        if (!res.ok) return
        const buf = await ctx!.decodeAudioData(await res.arrayBuffer())
        buffers.set(s.track_id, buf)
        stemsLoaded.value = buffers.size
      } catch { /* stem not playable; clock still runs */ }
    }))
  }

  function stopSources() {
    for (const s of sources) { try { s.stop() } catch { /* already stopped */ } }
    sources = []
  }

  function tick() {
    if (!playing.value) return
    const now = ctx ? ctx.currentTime : performance.now() / 1000
    playhead.value = startedAtSongTime + (now - startedAtCtxTime)
    if (duration.value > 0 && playhead.value >= duration.value) {
      pause()
      playhead.value = duration.value
      return
    }
    raf = requestAnimationFrame(tick)
  }

  async function play() {
    let m = studio.manifest
    if (!m || playing.value || preparing.value) return
    // auto-render: make sure every stem is fresh before playing, so the user
    // never has to render manually
    if (m.clips.length > 0) {
      preparing.value = true
      try {
        const res = await api.post<{ changed: boolean; errors: string[]; warnings: string[] }>(
          `/projects/${m.project_id}/render/auto`)
        renderWarnings.value = [...(res.errors ?? []), ...(res.warnings ?? [])]
        if (res.changed) {
          buffers = new Map()
          stemsLoaded.value = 0
          await studio.reloadCurrent()
        }
      } catch { /* rendering unavailable — the clock still runs */ }
      finally { preparing.value = false }
      m = studio.manifest!
      if (!m) return
    }
    await startPlayback(m)
  }

  /** Start WebAudio playback from the current playhead WITHOUT the
   *  auto-render check — used by play() after rendering and by seek(),
   *  where a render round-trip would make every jump feel like a hang. */
  async function startPlayback(m: PlaybackManifest) {
    if (!ctx) ctx = new AudioContext()
    await ctx.resume()
    if (buffers.size === 0 && manifestStems(m).length > 0) await loadStems()

    const anySolo = m.tracks.some((t) => t.solo)
    stopSources()
    for (const [trackId, buf] of buffers) {
      const t = m.tracks.find((x) => x.track_id === trackId)
      if (!t) continue
      const audible = anySolo ? t.solo : !t.mute
      if (!audible) continue
      const src = ctx.createBufferSource()
      src.buffer = buf
      const gain = ctx.createGain()
      gain.gain.value = t.volume
      const pan = ctx.createStereoPanner()
      pan.pan.value = t.pan
      src.connect(gain).connect(pan).connect(ctx.destination)
      src.start(0, Math.min(playhead.value, buf.duration))
      sources.push(src)
    }
    startedAtCtxTime = ctx.currentTime
    startedAtSongTime = playhead.value
    playing.value = true
    if (metronome.value) startMetronome()
    raf = requestAnimationFrame(tick)
  }

  function pause() {
    playing.value = false
    cancelAnimationFrame(raf)
    stopSources()
    stopMetronome()
  }

  function stop() {
    pause()
    playhead.value = 0
  }

  function seek(seconds: number) {
    const wasPlaying = playing.value
    pause()
    playhead.value = Math.max(0, Math.min(seconds, duration.value))
    // resume instantly from loaded buffers — no render/auto round-trip
    if (wasPlaying && studio.manifest) void startPlayback(studio.manifest)
  }

  // reset when switching projects
  watch(() => studio.manifest?.project_id, () => {
    stop()
    buffers = new Map()
    stemsLoaded.value = 0
  })

  return { playing, playhead, duration, stemsLoaded, preparing, renderWarnings,
           metronome, play, pause, stop, seek, loadStems }
})
