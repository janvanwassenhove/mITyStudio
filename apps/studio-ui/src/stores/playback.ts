import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
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
    const m = studio.manifest
    if (!m || playing.value) return
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
    raf = requestAnimationFrame(tick)
  }

  function pause() {
    playing.value = false
    cancelAnimationFrame(raf)
    stopSources()
  }

  function stop() {
    pause()
    playhead.value = 0
  }

  function seek(seconds: number) {
    const wasPlaying = playing.value
    pause()
    playhead.value = Math.max(0, Math.min(seconds, duration.value))
    if (wasPlaying) void play()
  }

  // reset when switching projects
  watch(() => studio.manifest?.project_id, () => {
    stop()
    buffers = new Map()
    stemsLoaded.value = 0
  })

  return { playing, playhead, duration, stemsLoaded, play, pause, stop, seek, loadStems }
})
