import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { api } from '../api/client'
import type { PlaybackManifest } from '../api/types'
import * as synth from '../lib/synth'
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

  // Persistent per-track gain/pan chains + master gain. Sources plug into
  // these, so mixer changes (volume/pan/mute/solo/master) apply LIVE during
  // playback instead of only on the next play.
  let trackChains = new Map<string, { gain: GainNode; pan: StereoPannerNode }>()
  let masterGain: GainNode | null = null

  function ensureMaster(): GainNode {
    if (!masterGain) {
      masterGain = ctx!.createGain()
      masterGain.connect(ctx!.destination)
    }
    return masterGain
  }

  function ensureChain(trackId: string) {
    let c = trackChains.get(trackId)
    if (!c) {
      const gain = ctx!.createGain()
      const pan = ctx!.createStereoPanner()
      gain.connect(pan).connect(ensureMaster())
      c = { gain, pan }
      trackChains.set(trackId, c)
    }
    return c
  }

  /** Current mixer state, live from the project being edited (mixer faders
   *  write there immediately), falling back to the manifest snapshot. */
  function mixerTracks(): { id: string; volume: number; pan: number;
                            mute: boolean; solo: boolean }[] {
    const p = studio.project
    if (p) return p.tracks.map((t) => ({ id: t.id, volume: t.volume,
      pan: t.pan, mute: t.mute, solo: t.solo }))
    return (studio.manifest?.tracks ?? []).map((t) => ({ id: t.track_id,
      volume: t.volume, pan: t.pan, mute: t.mute, solo: t.solo }))
  }

  /** Push mixer state into the running audio graph. Smoothed by default to
   *  avoid zipper noise while dragging faders. */
  function applyMixer(smooth = true) {
    if (!ctx) return
    const tracks = mixerTracks()
    const anySolo = tracks.some((t) => t.solo)
    const now = ctx.currentTime
    const T = 0.03
    for (const [trackId, chain] of trackChains) {
      const t = tracks.find((x) => x.id === trackId)
      if (!t) continue
      const target = (anySolo ? t.solo : !t.mute) ? t.volume : 0
      if (smooth) {
        chain.gain.gain.setTargetAtTime(target, now, T)
        chain.pan.pan.setTargetAtTime(t.pan, now, T)
      } else {
        chain.gain.gain.value = target
        chain.pan.pan.value = t.pan
      }
    }
    const mv = studio.project?.mix_settings.master_volume
      ?? studio.manifest?.mix_settings?.master_volume ?? 1
    if (masterGain) {
      if (smooth) masterGain.gain.setTargetAtTime(mv, now, T)
      else masterGain.gain.value = mv
    }
  }

  // live-follow mixer edits (Mixer panel + track-header M/S/volume all write
  // to studio.project) while the song is playing
  watch(
    () => {
      const p = studio.project
      if (!p) return ''
      return p.tracks.map((t) =>
        `${t.id}:${t.volume}:${t.pan}:${t.mute}:${t.solo}`).join('|')
        + `#${p.mix_settings.master_volume}`
    },
    () => { if (playing.value) applyMixer() },
  )

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
    stopLiveSynth()
  }

  // --- live synth: instrument tracks with no rendered stem yet play through
  //     the built-in WebAudio synth so there is sound before/without a render
  let liveVoices: synth.Voice[] = []

  function stopLiveSynth() {
    if (!ctx) { liveVoices = []; return }
    const now = ctx.currentTime
    for (const v of liveVoices) { try { v.stop(now) } catch { /* done */ } }
    liveVoices = []
  }

  async function scheduleLiveSynth(m: PlaybackManifest) {
    const p = studio.project
    if (!ctx || !p) return
    await synth.loadPatches()
    const spb = 60 / m.bpm
    for (const track of p.tracks) {
      if (!synth.isSynthTrack(track) || buffers.has(track.id)) continue
      const spec = synth.getPatch(synth.patchIdForTrack(track))
      if (!spec) continue
      const gain = ensureChain(track.id).gain
      for (const clip of track.clips) {
        if (clip.clip_type !== 'midi') continue
        for (const note of clip.note_events) {
          const songT = (clip.start_beat + note.start_beat) * spb
          if (songT < playhead.value - 0.01) continue
          const when = startedAtCtxTime + (songT - startedAtSongTime)
          liveVoices.push(synth.playVoice(ctx, gain, spec, note.midi_note,
            when, note.duration_beats * spb, note.velocity))
        }
      }
    }
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
    if (!m || playing.value || preparing.value) return
    // start INSTANTLY: existing stems play, and any instrument track without a
    // fresh stem sounds live via the built-in synth — no wait for a render
    await startPlayback(m)
    // then refresh stems in the background and hand off to them when ready, so
    // the final sound is the true render without ever blocking playback
    if (m.clips.length > 0) {
      preparing.value = true
      try {
        const res = await api.post<{ changed: boolean; errors: string[]; warnings: string[] }>(
          `/projects/${m.project_id}/render/auto`)
        renderWarnings.value = [...(res.errors ?? []), ...(res.warnings ?? [])]
        if (res.changed && playing.value) {
          buffers = new Map()
          stemsLoaded.value = 0
          await studio.reloadCurrent()
          const m2 = studio.manifest
          if (playing.value && m2) await startPlayback(m2)  // swap to stems
        }
      } catch { /* rendering unavailable — the live synth keeps playing */ }
      finally { preparing.value = false }
    }
  }

  /** Start WebAudio playback from the current playhead WITHOUT the
   *  auto-render check — used by play() after rendering and by seek(),
   *  where a render round-trip would make every jump feel like a hang. */
  async function startPlayback(m: PlaybackManifest) {
    if (!ctx) ctx = new AudioContext()
    await ctx.resume()
    if (buffers.size === 0 && manifestStems(m).length > 0) await loadStems()

    stopSources()
    // start EVERY buffered track; mute/solo act through the gain nodes, so
    // toggling them mid-song is instant and stays sample-synced
    for (const [trackId, buf] of buffers) {
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(ensureChain(trackId).gain)
      src.start(0, Math.min(playhead.value, buf.duration))
      sources.push(src)
    }
    applyMixer(false)
    startedAtCtxTime = ctx.currentTime
    startedAtSongTime = playhead.value
    playing.value = true
    // instrument tracks lacking a rendered stem sound live via the synth
    void scheduleLiveSynth(m)
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
    // drop the old project's track chains so stale ids don't accumulate
    for (const c of trackChains.values()) {
      try { c.gain.disconnect(); c.pan.disconnect() } catch { /* detached */ }
    }
    trackChains = new Map()
  })

  return { playing, playhead, duration, stemsLoaded, preparing, renderWarnings,
           metronome, play, pause, stop, seek, loadStems }
})
