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
        # every generated song gets a singing lead vocal
        profile_m = re.search(r'"voice_profiles":\s*\[\s*\{\s*"id":\s*"([^"]+)"',
                              system_prompt)
        vt_params: dict = {"name": "Lead Vocal", "track_type": "lead_vocal"}
        if profile_m:
            vt_params["voice_profile_id"] = profile_m.group(1)
        ops.append({"op_type": "create_vocal_track", "params": vt_params})
        topic = params.get("title") or style or "tonight"
        for section in ("Chorus", "Chorus 2"):
            ops.append({"op_type": "rewrite_lyrics",
                        "params": {"section": section, "lines": [
                            f"We sing it loud, {topic}",
                            "Hearts wide open, carried by the sound",
                            f"Nothing's gonna stop us now, {topic}",
                            "This is where we're found",
                        ]}})
            ops.append({"op_type": "generate_melody",
                        "params": {"section": section, "track": "Lead Vocal",
                                   "track_type": "lead_vocal"}})
        replies.append("I set up a full song (intro, verses, choruses, outro) "
                       "with drums, bass, chords, a melody and a singing lead "
                       "vocal on the choruses.")
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

    wants_voice = any(w in msg for w in ("add voice", "add vocals", "add a voice",
                                         "add singing", "add a singer",
                                         "vocals", "sing this", "make it sing",
                                         "voice track", "vocal track",
                                         "use my voice", "with my voice"))
    if wants_voice and "lyrics" not in msg:
        # pick a consented voice profile from the planning context if any
        profile_id = None
        m_prof = re.search(r'"voice_profiles":\s*\[\s*\{\s*"id":\s*"([^"]+)"',
                           system_prompt)
        if m_prof:
            profile_id = m_prof.group(1)
        vt_params: dict = {"name": "Lead Vocal", "track_type": "lead_vocal"}
        if profile_id:
            vt_params["voice_profile_id"] = profile_id
        ops.append({"op_type": "create_vocal_track", "params": vt_params})
        topic_m = re.search(r"(?:about|over|on)\s+(.+?)(?:\.|$)", msg)
        topic = topic_m.group(1).strip() if topic_m else "this moment"
        ops.append({"op_type": "rewrite_lyrics", "params": {"lines": [
            f"Here we are, singing about {topic}",
            "Every note is finding its way",
            f"Carry me home to {topic}",
            "We won't let this fade away",
        ]}})
        ops.append({"op_type": "generate_melody",
                    "params": {"track": "Lead Vocal",
                               "track_type": "lead_vocal"}})
        if profile_id:
            replies.append("Added a lead vocal singing with your voice "
                           "profile, with lyrics and a melody.")
        else:
            replies.append("Added a lead vocal with lyrics and a melody "
                           "(synthetic voice — create a voice profile in "
                           "Voices to sing with your own).")

    if "lyrics" in msg or "sing about" in msg:
        topic_m = re.search(r"(?:lyrics about|sing about|about)\s+(.+?)(?:\.|$)", msg)
        topic = topic_m.group(1).strip() if topic_m else "life"
        whole_song = any(w in msg for w in ("whole song", "full song",
                                            "entire song", "every section",
                                            "all sections"))
        lines = [
            f"We're running through the night, chasing {topic}",
            "Nothing's gonna stop us now",
            f"Hearts on fire, dreaming of {topic}",
            "We sing it loud, we sing it proud",
            f"Morning light is calling out for {topic}",
            "Every echo knows our name",
            f"Hold on tight, we're closer to {topic}",
            "Nothing ever stays the same",
        ]
        section = "all" if whole_song else None
        params: dict = {"lines": lines if whole_song else lines[:4]}
        if section:
            params["section"] = section
        ops.append({"op_type": "rewrite_lyrics", "params": params})
        mel_params: dict = {"track_type": "lead_vocal", "track": "Lead Vocal"}
        if section:
            mel_params["section"] = "all"
        ops.append({"op_type": "generate_melody", "params": mel_params})
        replies.append(
            f"Wrote lyrics about {topic} "
            f"{'across the whole song' if whole_song else ''} and set a vocal "
            "melody. Say 'add lyrics about … for the whole song' to fill "
            "every section.")

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

    if any(w in msg for w in ("from my score", "from the score", "from my sheet",
                              "from the sheet", "from my pdf", "from the pdf",
                              "from my tab", "use the score", "use my score",
                              "arrange the score", "import the score")):
        m_score = re.search(r'"scores":\s*\[.*?\{\s*"id":\s*"([^"]+)"',
                            system_prompt, re.DOTALL)
        if m_score:
            ops.append({"op_type": "arrange_from_score",
                        "params": {"score_asset_id": m_score.group(1)}})
            replies.append("Arranging the song from your score — chords, "
                           "bass, sections and any lyrics it contains.")
        else:
            replies.append("I don't see any score assets — upload one in "
                           "Assets → Scores (PDF/photo/MIDI/GP all work).")

    if not ops:
        return {"reply": ("(mock planner) I can create songs "
                          "('create a punk song at 170 bpm in E minor'), add "
                          "sections ('add a chorus'), change tempo/key, write "
                          "lyrics ('add lyrics about summer'), or regenerate "
                          "drums/bass/chords/melody. Configure a real LLM in "
                          "Settings for free-form requests."),
                "operations": []}
    return {"reply": " ".join(replies), "operations": ops}
