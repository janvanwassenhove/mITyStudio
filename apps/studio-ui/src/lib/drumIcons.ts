// monochrome drum-piece glyphs (GarageBand-style), keyed by lane label
export const DRUM_SVG: Record<string, string> = {
  Kick: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3"/></svg>',
  Snare: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="8" ry="3"/><path d="M4 8v6c0 1.7 3.6 3 8 3s8-1.3 8-3V8"/><path d="M4 11h16" stroke-width="1"/></svg>',
  'Hi-Hat': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="9" ry="2"/><ellipse cx="12" cy="11" rx="9" ry="2"/><path d="M12 12.5V21"/></svg>',
  'Open Hat': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="6" rx="9" ry="2" transform="rotate(-8 12 6)"/><ellipse cx="12" cy="12" rx="9" ry="2" transform="rotate(6 12 12)"/><path d="M12 14V21"/></svg>',
  Ride: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="10" ry="2.6"/><circle cx="12" cy="7.4" r="1.2"/><path d="M12 10.5V21"/></svg>',
  Crash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="7" rx="9.5" ry="2.4" transform="rotate(-14 12 7)"/><path d="M12 9.5V21"/><path d="M8 21h8"/></svg>',
  Toms: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="7.5" cy="9" rx="5" ry="2"/><path d="M2.5 9v5c0 1.1 2.2 2 5 2s5-.9 5-2V9"/><ellipse cx="17.5" cy="8" rx="4" ry="1.7"/><path d="M13.5 8v4.5c0 .9 1.8 1.6 4 1.6s4-.7 4-1.6V8"/></svg>',
  Clap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M9 12 4 7m5 9-6-3m7 7-5-1"/><path d="M12 11c1-3 3-5 6-5 2 0 3 1.5 2 3.5S16 14 14 17c-1.4 2-4 2.5-5.5 1"/></svg>',
  Shaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="8" y="4" width="8" height="16" rx="4"/><circle cx="11" cy="9" r="0.7" fill="currentColor"/><circle cx="13.5" cy="12" r="0.7" fill="currentColor"/><circle cx="11.5" cy="15" r="0.7" fill="currentColor"/></svg>',
  'Lo Tom': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="12" cy="8" rx="7" ry="2.4"/><path d="M5 8v7c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V8"/></svg>',
}
