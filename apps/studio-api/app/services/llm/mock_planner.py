"""MockLlmProvider planning logic: deterministic keyword → operations.

Good enough to build complete songs without an API key, and a stable target
for tests. The real provider must produce the same operation JSON shape.
"""
from __future__ import annotations

import re

_STYLES = ["punk", "rock", "metal", "pop", "jazz", "blues", "edm", "dance",
           "house", "techno", "folk", "country", "hiphop", "reggae"]

_SECTION_WORDS = ["intro", "verse", "chorus", "bridge", "outro", "drop",
                  "breakdown", "solo"]

_KEY_RE = re.compile(
    r"\b(?:in|to)\s+(?:the\s+key\s+of\s+)?([A-G][#b]?)\s*(minor|major|min|maj)?\b",
    re.IGNORECASE)
_BPM_RE = re.compile(r"(\d{2,3})\s*bpm", re.IGNORECASE)


def _detect_style(msg: str) -> str | None:
    return next((s for s in _STYLES if s in msg), None)


def plan_from_message(system_prompt: str, user_message: str) -> dict:
    msg = user_message.lower()
    ops: list[dict] = []
    replies: list[str] = []

    wants_song = any(w in msg for w in ("create", "make", "write", "new song",
                                        "generate a song", "compose"))
    style = _detect_style(msg)
    key_m = _KEY_RE.search(user_message)
    bpm_m = _BPM_RE.search(msg)

    if wants_song and ("song" in msg or "track" in msg or style):
        params: dict = {}
        title_m = (re.search(r'(?:called|titled|named)\s+["‘’\'"]([^"‘’\'"]+)["‘’\'"]',
                             user_message, re.IGNORECASE)
                   or re.search(r'(?:called|titled|named)\s+(.+?)(?:\s+at\s+|\s+in\s+|[.,]|$)',
                                user_message, re.IGNORECASE))
        if title_m:
            params["title"] = title_m.group(1).strip()
        if style:
            params["style"] = style
        if bpm_m:
            params["bpm"] = int(bpm_m.group(1))
        elif style in ("punk", "metal"):
            params["bpm"] = 170
        elif style in ("edm", "dance", "house", "techno"):
            params["bpm"] = 126
        if key_m:
            qual = (key_m.group(2) or "major").lower()
            params["key"] = f"{key_m.group(1).upper()} {'minor' if qual.startswith('min') else 'major'}"
        ops.append({"op_type": "create_song", "params": params})
        # standard structure
        for name, bars, energy in (("Intro", 4, 0.3), ("Verse 1", 8, 0.5),
                                   ("Chorus", 8, 0.9), ("Verse 2", 8, 0.55),
                                   ("Chorus 2", 8, 0.9), ("Outro", 4, 0.35)):
            ops.append({"op_type": "add_section",
                        "params": {"name": name, "length_bars": bars,
                                   "energy": energy}})
        for section in ("Intro", "Verse 1", "Chorus", "Verse 2", "Chorus 2", "Outro"):
            ops.append({"op_type": "generate_drums", "params": {"section": section}})
            ops.append({"op_type": "generate_bassline", "params": {"section": section}})
            ops.append({"op_type": "generate_chords", "params": {"section": section}})
        for section in ("Verse 1", "Chorus", "Verse 2", "Chorus 2"):
            ops.append({"op_type": "generate_melody",
                        "params": {"section": section, "track_type": "synth",
                                   "track": "Melody"}})
        replies.append("I set up a full song structure (intro, verses, "
                       "choruses, outro) with drums, bass, chords and a melody.")
        return {"reply": " ".join(replies), "operations": ops}

    # --- incremental edits ---
    if bpm_m or "faster" in msg or "slower" in msg or "tempo" in msg:
        if bpm_m:
            ops.append({"op_type": "change_tempo",
                        "params": {"bpm": int(bpm_m.group(1))}})
            replies.append(f"Tempo set to {bpm_m.group(1)} BPM.")
        elif "faster" in msg:
            ops.append({"op_type": "change_tempo", "params": {"bpm": "+15"}})
            replies.append("Sped it up by 15 BPM.")
        elif "slower" in msg:
            ops.append({"op_type": "change_tempo", "params": {"bpm": "-15"}})
            replies.append("Slowed it down by 15 BPM.")

    if key_m and ("key" in msg or "transpose" in msg):
        qual = (key_m.group(2) or "major").lower()
        key = f"{key_m.group(1).upper()} {'minor' if qual.startswith('min') else 'major'}"
        ops.append({"op_type": "change_key", "params": {"key": key}})
        replies.append(f"Key changed to {key}.")

    for word in _SECTION_WORDS:
        if f"add {word}" in msg or f"add a {word}" in msg or f"add an {word}" in msg:
            name = word.title()
            ops.append({"op_type": "add_section",
                        "params": {"name": name,
                                   "energy": 0.9 if word in ("chorus", "drop") else 0.5}})
            for gen in ("generate_drums", "generate_bassline", "generate_chords"):
                ops.append({"op_type": gen, "params": {"section": name}})
            replies.append(f"Added a {word} with drums, bass and chords.")

    if "lyrics" in msg or "sing about" in msg:
        topic_m = re.search(r"(?:lyrics about|sing about|about)\s+(.+?)(?:\.|$)", msg)
        topic = topic_m.group(1).strip() if topic_m else "life"
        lines = [
            f"We're running through the night, chasing {topic}",
            f"Nothing's gonna stop us now",
            f"Hearts on fire, dreaming of {topic}",
            f"We sing it loud, we sing it proud",
        ]
        ops.append({"op_type": "rewrite_lyrics", "params": {"lines": lines}})
        ops.append({"op_type": "generate_melody",
                    "params": {"track_type": "lead_vocal", "track": "Lead Vocal"}})
        replies.append(f"Wrote lyrics about {topic} and set a vocal melody.")

    if "drum" in msg and not any(o["op_type"] == "generate_drums" for o in ops):
        ops.append({"op_type": "generate_drums", "params": {}})
        replies.append("Regenerated the drums.")
    if "bass" in msg and not any(o["op_type"] == "generate_bassline" for o in ops):
        ops.append({"op_type": "generate_bassline", "params": {}})
        replies.append("Regenerated the bassline.")
    if ("chord" in msg or "guitar" in msg or "keys" in msg) \
            and not any(o["op_type"] == "generate_chords" for o in ops):
        ops.append({"op_type": "generate_chords", "params": {}})
        replies.append("Regenerated the chords.")
    if "melody" in msg and not any(o["op_type"] == "generate_melody" for o in ops):
        ops.append({"op_type": "generate_melody", "params": {}})
        replies.append("Regenerated the melody.")

    if not ops:
        return {"reply": ("(mock planner) I can create songs "
                          "('create a punk song at 170 bpm in E minor'), add "
                          "sections ('add a chorus'), change tempo/key, write "
                          "lyrics ('add lyrics about summer'), or regenerate "
                          "drums/bass/chords/melody. Configure a real LLM in "
                          "Settings for free-form requests."),
                "operations": []}
    return {"reply": " ".join(replies), "operations": ops}
