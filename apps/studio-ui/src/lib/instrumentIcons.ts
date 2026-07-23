/**
 * Instrument-category → icon, shared by every place that lists SoundFont
 * presets (the Assets library and the track instrument picker).
 *
 * The CATEGORY comes from the backend (sf2_parser classifies each preset),
 * so the classification lives in exactly one place — this file only maps a
 * category name onto a glyph and a colour.
 */
import { Bell, Drum, Guitar, Layers, Mic, Music, Music2, Piano, Sparkles,
         Waves, Wind, Zap } from 'lucide-vue-next'
import { CATEGORY_COLORS } from './trackColors'

const CAT_ICONS: Record<string, unknown> = {
  'piano & keys': Piano, organ: Piano, guitar: Guitar, bass: Guitar,
  strings: Music2, brass: Music2, 'sax & winds': Wind,
  'voice & choir': Mic, 'synth lead': Zap, 'synth pad': Waves,
  'drum kits': Drum, percussion: Bell, fx: Sparkles, 'gm-bank': Layers,
}

export function catIcon(category: string) {
  return CAT_ICONS[(category || '').toLowerCase()] ?? Music
}

export function catColor(category: string): string {
  const hit = Object.entries(CATEGORY_COLORS)
    .find(([k]) => k.toLowerCase() === (category || '').toLowerCase())
  return hit ? hit[1] : CATEGORY_COLORS.Other
}
