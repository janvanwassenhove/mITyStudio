/**
 * Real-time WebAudio synth — the browser-side twin of the backend's
 * render/synth_engine.py. Instrument tracks play instantly through this
 * (before/without a rendered stem), and the interactive play surfaces share
 * it so auditioning uses the selected patch's true sound.
 *
 * The DSP parameters are NOT duplicated here: they are fetched once from
 * GET /api/assets/synth-patches (the backend is the single source of truth),
 * so the live sound tracks any change to the engine's patches.
 */
import type { Track } from '../api/types'

export interface PatchSpec {
  id: string
  label: string
  category: string
  kind: 'osc' | 'fm' | 'pluck' | 'organ' | 'drums'
  osc: 'sine' | 'saw' | 'square' | 'triangle'
  voices: number
  detune: number
  sub: number
  adsr: [number, number, number, number]
  cutoff: number
  vibrato: number
  fm_ratio: number
  fm_index: number
  gain: number
  track_types: string[]
}

// mirrors render/synth_engine.DEFAULT_PATCH — the one-per-track-type default
const DEFAULT_PATCH: Record<string, string> = {
  drums: 'drum_kit', bass: 'bass_synth', guitar: 'guitar_pluck',
  keys: 'keys_epiano', synth: 'synth_saw_lead', strings: 'strings_ensemble',
  brass: 'brass_synth', fx: 'synth_pad_warm',
}

const OSC_TYPE: Record<string, OscillatorType> = {
  sine: 'sine', saw: 'sawtooth', square: 'square', triangle: 'triangle',
}

let patches: Record<string, PatchSpec> | null = null
let loading: Promise<void> | null = null

export async function loadPatches(): Promise<void> {
  if (patches) return
  if (!loading) {
    loading = fetch('/api/assets/synth-patches')
      .then((r) => (r.ok ? r.json() : []))
      .then((list: PatchSpec[]) => {
        patches = {}
        for (const p of list) patches[p.id] = p
      })
      .catch(() => { patches = {} })
  }
  return loading
}

export function getPatch(id: string): PatchSpec | undefined {
  return patches?.[id]
}

/** The patch id a track should play with (explicit choice, else the default
 *  for its track type). Drum tracks always use the drum kit. */
export function patchIdForTrack(track: Track): string {
  const cfg = track.instrument_config
  if (cfg?.is_drum_kit || track.track_type === 'drums') return 'drum_kit'
  return cfg?.synth_patch || DEFAULT_PATCH[track.track_type] || 'synth_saw_lead'
}

const INSTRUMENT_TYPES = new Set(
  ['drums', 'bass', 'guitar', 'keys', 'synth', 'strings', 'brass', 'fx'])

export function isSynthTrack(track: Track): boolean {
  return INSTRUMENT_TYPES.has(track.track_type)
}

function midiToFreq(midi: number): number {
  return 440 * 2 ** ((midi - 69) / 12)
}

// one shared white-noise buffer per context (drums, snare, hats)
const noiseBuffers = new WeakMap<BaseAudioContext, AudioBuffer>()
function noise(ctx: BaseAudioContext): AudioBuffer {
  let buf = noiseBuffers.get(ctx)
  if (!buf) {
    buf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate)
    const d = buf.getChannelData(0)
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1
    noiseBuffers.set(ctx, buf)
  }
  return buf
}

export interface Voice { stop(at: number): void }

/** Schedule a single note; returns a handle to cut it short (pause/seek). */
export function playVoice(ctx: AudioContext, dest: AudioNode, spec: PatchSpec,
                          midi: number, when: number, durSec: number,
                          velocity: number): Voice {
  const nodes: { stop: (t: number) => void }[] = []
  const amp = Math.pow(velocity / 127, 1.1) * spec.gain
  const freq = midiToFreq(midi)

  if (spec.kind === 'drums') return drumVoice(ctx, dest, midi, when, amp)

  const [a, d, s, r] = spec.adsr
  const gateEnd = Math.max(when + durSec, when + a + 0.01)
  const env = ctx.createGain()
  env.gain.setValueAtTime(0, when)
  env.gain.linearRampToValueAtTime(amp, when + a)
  env.gain.linearRampToValueAtTime(amp * s, when + a + d)
  env.gain.setValueAtTime(amp * s, gateEnd)
  env.gain.linearRampToValueAtTime(0, gateEnd + r)
  const end = gateEnd + r + 0.03

  let sink: AudioNode = env
  if (spec.cutoff > 0) {
    const lp = ctx.createBiquadFilter()
    lp.type = 'lowpass'
    lp.frequency.value = spec.cutoff
    env.connect(lp).connect(dest)
    sink = env
  } else {
    env.connect(dest)
  }

  const startStop = (n: OscillatorNode | AudioBufferSourceNode) => {
    n.start(when); n.stop(end)
    nodes.push({ stop: (t) => { try { n.stop(t) } catch { /* done */ } } })
  }

  if (spec.kind === 'fm') {
    const carrier = ctx.createOscillator()
    carrier.frequency.value = freq
    const mod = ctx.createOscillator()
    mod.frequency.value = freq * spec.fm_ratio
    const modGain = ctx.createGain()
    modGain.gain.setValueAtTime(spec.fm_index * freq, when)
    modGain.gain.exponentialRampToValueAtTime(Math.max(1, freq * 0.01),
                                              when + Math.max(0.05, d))
    mod.connect(modGain).connect(carrier.frequency)
    carrier.connect(sink)
    startStop(carrier); startStop(mod)
  } else if (spec.kind === 'organ') {
    for (const [mult, g] of [[1, 1], [2, 0.6], [3, 0.4], [4, 0.25]]) {
      const o = ctx.createOscillator()
      o.type = 'sine'; o.frequency.value = freq * mult
      const og = ctx.createGain(); og.gain.value = g / 2.25
      o.connect(og).connect(sink)
      startStop(o)
    }
  } else if (spec.kind === 'pluck') {
    // approximation of Karplus-Strong: a bright triangle with a fast decay
    const o = ctx.createOscillator()
    o.type = 'triangle'; o.frequency.value = freq
    o.connect(sink); startStop(o)
    const n = ctx.createBufferSource()
    n.buffer = noise(ctx)
    const ng = ctx.createGain()
    ng.gain.setValueAtTime(amp * 0.5, when)
    ng.gain.exponentialRampToValueAtTime(0.001, when + 0.04)
    n.connect(ng).connect(sink); startStop(n)
  } else {
    // osc: unison of detuned voices (+ optional sub octave), vibrato LFO
    const voices = Math.max(1, spec.voices)
    let lfo: OscillatorNode | null = null
    for (let v = 0; v < voices; v++) {
      const o = ctx.createOscillator()
      o.type = OSC_TYPE[spec.osc] ?? 'sawtooth'
      o.frequency.value = freq
      o.detune.value = voices > 1 ? spec.detune * (v / (voices - 1) - 0.5) : 0
      const vg = ctx.createGain(); vg.gain.value = 1 / voices
      o.connect(vg).connect(sink)
      startStop(o)
      if (spec.vibrato > 0) {
        if (!lfo) { lfo = ctx.createOscillator(); lfo.frequency.value = 5 }
        const depth = ctx.createGain(); depth.gain.value = spec.vibrato
        lfo.connect(depth).connect(o.detune)
      }
    }
    if (lfo) startStop(lfo)
    if (spec.sub > 0) {
      const sub = ctx.createOscillator()
      sub.type = 'sine'; sub.frequency.value = freq / 2
      const sg = ctx.createGain(); sg.gain.value = spec.sub
      sub.connect(sg).connect(sink)
      startStop(sub)
    }
  }

  return { stop: (t) => { for (const n of nodes) n.stop(t) } }
}

function drumVoice(ctx: AudioContext, dest: AudioNode, midi: number,
                   when: number, amp: number): Voice {
  const stops: ((t: number) => void)[] = []
  const g = ctx.createGain(); g.connect(dest)
  const hit = (decay: number, level: number) => {
    g.gain.setValueAtTime(level * amp, when)
    g.gain.exponentialRampToValueAtTime(0.0008, when + decay)
  }
  const oscHit = (f0: number, f1: number, decay: number, level: number) => {
    const o = ctx.createOscillator()
    o.frequency.setValueAtTime(f0, when)
    o.frequency.exponentialRampToValueAtTime(Math.max(20, f1), when + decay * 0.5)
    o.connect(g); o.start(when); o.stop(when + decay + 0.02)
    stops.push((t) => { try { o.stop(t) } catch { /* done */ } })
    hit(decay, level)
  }
  const noiseHit = (type: BiquadFilterType, freq: number, decay: number,
                    level: number) => {
    const n = ctx.createBufferSource(); n.buffer = noise(ctx)
    const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq
    n.connect(f).connect(g); n.start(when); n.stop(when + decay + 0.02)
    stops.push((t) => { try { n.stop(t) } catch { /* done */ } })
    hit(decay, level)
  }
  if (midi === 35 || midi === 36) oscHit(140, 45, 0.18, 1.0)
  else if (midi === 38 || midi === 40) { oscHit(190, 150, 0.12, 0.5); noiseHit('highpass', 1500, 0.14, 0.9) }
  else if (midi === 42 || midi === 44) noiseHit('highpass', 7000, 0.04, 0.6)
  else if (midi === 46) noiseHit('highpass', 6500, 0.2, 0.6)
  else if ([49, 51, 57, 59].includes(midi)) noiseHit('lowpass', 9000, 0.6, 0.5)
  else if (midi >= 41 && midi <= 50) oscHit(180, 110, 0.22, 0.9)
  else noiseHit('highpass', 3000, 0.06, 0.6)
  return { stop: (t) => { for (const s of stops) s(t) } }
}
