"""Vision score import: PDF / JPG / PNG chord sheets, lead sheets and tabs
→ structured song data via a vision LLM (OpenAI, using the configured key).

The model reads the image and returns chords/lyrics/structure as JSON; the
studio then builds real tracks (strummed chords + bass roots) from it. The
LLM never produces audio — same architecture as chat planning.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)


class ScoreVisionError(Exception):
    pass


# --- chord symbols → midi notes --------------------------------------------

_ROOTS = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5,
          "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10,
          "BB": 10, "B": 11}


def chord_to_midis(symbol: str, base: int = 48) -> list[int] | None:
    """'Em7' → [52, 55, 59, 62]. Returns None for unparseable symbols."""
    m = re.match(
        r"^([A-G][#b]?)\s*(maj7|maj|min7|min|m7|m(?!aj)|dim7|dim|aug|sus2|sus4|7|6|9|add9)?",
        symbol.strip())
    if not m or not m.group(1):
        return None
    root = _ROOTS.get(m.group(1).upper().replace("B#", "C"))
    if root is None:
        return None
    q = m.group(2) or ""
    if q in ("m", "min"):
        iv = [0, 3, 7]
    elif q in ("m7", "min7"):
        iv = [0, 3, 7, 10]
    elif q in ("dim", "dim7"):
        iv = [0, 3, 6]
    elif q == "aug":
        iv = [0, 4, 8]
    elif q == "sus2":
        iv = [0, 2, 7]
    elif q == "sus4":
        iv = [0, 5, 7]
    elif q == "7":
        iv = [0, 4, 7, 10]
    elif q in ("maj7", "maj"):
        iv = [0, 4, 7, 11] if q == "maj7" else [0, 4, 7]
    elif q == "6":
        iv = [0, 4, 7, 9]
    elif q in ("9", "add9"):
        iv = [0, 4, 7, 14]
    else:
        iv = [0, 4, 7]
    return [base + root + i for i in iv]


# --- image loading -----------------------------------------------------------

def _load_image_bytes(path: Path) -> tuple[bytes, str]:
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        return path.read_bytes(), "image/jpeg"
    if ext == ".png":
        return path.read_bytes(), "image/png"
    if ext == ".pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(path))
        try:
            page = pdf[0]
            bitmap = page.render(scale=2.2)
            pil = bitmap.to_pil()
            buf = io.BytesIO()
            pil.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
        finally:
            pdf.close()
    raise ScoreVisionError(f"unsupported image/score format {ext!r}")


# --- vision extraction --------------------------------------------------------

_VISION_PROMPT = """You are reading a photographed/scanned music document: it may
be a chord sheet, lead sheet, guitar tab, or sheet music. Extract the song
structure and return ONLY one JSON object, no prose:

{"title": "...", "bpm": 120 or null, "key": "E minor" or null,
 "time_signature": "4/4",
 "sections": [{"name": "Verse", "chords": ["Em","G","D","A"],
               "lyrics": ["line 1", "line 2"]}]}

Rules:
- chords: one symbol per bar in playing order (repeat a symbol for repeated bars);
  standard notation (Em, C, G7, Am7, F#m, Bb, Dsus4...).
- If the document shows tab numbers instead of chord names, infer the chords.
- lyrics: transcribe EVERY lyric line VERBATIM and COMPLETELY — do not skip,
  summarize or paraphrase any line; include repeated choruses each time they
  appear. [] only if the section truly has no words.
- Create sections as marked (Intro/Verse/Chorus...); if unmarked, split
  sensibly into 1-4 sections. If the key isn't marked, infer it from the chords.
- If the image is NOT readable music, return {"error": "reason"}."""


def _vision_backends() -> list[tuple[str, str | None, list[str]]]:
    """(api_key, base_url, models) options in preference order — any
    OpenAI-compatible vision endpoint the user has a key for."""
    import os

    from .llm.settings import get_api_key, load_settings
    settings = load_settings()
    out: list[tuple[str, str | None, list[str]]] = []
    openai_key = get_api_key("openai")
    if openai_key:
        models = []
        if settings.provider == "openai" and settings.model:
            models.append(settings.model)
        out.append((openai_key, None, models + ["gpt-4o", "gpt-4o-mini"]))
    if os.environ.get("GEMINI_API_KEY"):
        out.append((os.environ["GEMINI_API_KEY"],
                    "https://generativelanguage.googleapis.com/v1beta/openai/",
                    ["gemini-2.5-flash", "gemini-2.0-flash"]))
    if os.environ.get("OPENROUTER_API_KEY"):
        out.append((os.environ["OPENROUTER_API_KEY"],
                    "https://openrouter.ai/api/v1",
                    ["google/gemini-3.5-flash", "anthropic/claude-sonnet-5",
                     "openai/gpt-4o"]))
    return out


def extract_song_data(image_bytes: bytes, mime: str) -> dict:
    from .llm.provider import LlmProviderError, _extract_json

    backends = _vision_backends()
    if not backends:
        raise ScoreVisionError(
            "score reading needs a vision-capable LLM — add an OpenAI API "
            "key in Settings (or OPENAI_API_KEY / GEMINI_API_KEY / "
            "OPENROUTER_API_KEY)")
    from openai import OpenAI

    b64 = base64.b64encode(image_bytes).decode()
    content = [
        {"type": "text", "text": _VISION_PROMPT},
        {"type": "image_url",
         "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ]
    last: Exception | None = None
    for key, base_url, models in backends:
        client = OpenAI(api_key=key, base_url=base_url, timeout=90)
        for model in dict.fromkeys(models):
            try:
                kwargs: dict = {"model": model,
                                "messages": [{"role": "user", "content": content}]}
                try:
                    resp = client.chat.completions.create(
                        max_completion_tokens=3000, **kwargs)
                except Exception:
                    resp = client.chat.completions.create(max_tokens=3000, **kwargs)
                return _extract_json(resp.choices[0].message.content or "")
            except (LlmProviderError, Exception) as e:  # noqa: BLE001
                last = e
                msg = str(e).lower()
                if "quota" in msg or "429" in msg or "401" in msg:
                    break  # this backend is unusable, try the next one
    raise ScoreVisionError(f"vision extraction failed: {last}")


# --- build import result -------------------------------------------------------

def import_score_vision(asset) -> "object":
    from .score_import import DetectedTrack, ScoreImportResult

    result = ScoreImportResult(source_asset_id=asset.id, format="vision")
    try:
        image, mime = _load_image_bytes(Path(asset.original_path))
        data = extract_song_data(image, mime)
    except (ScoreVisionError, Exception) as e:  # noqa: BLE001
        result.supported = False
        result.warnings.append(str(e))
        return result

    if data.get("error"):
        result.supported = False
        result.warnings.append(f"could not read the document: {data['error']}")
        return result

    sections = data.get("sections") or []
    if not sections:
        result.supported = False
        result.warnings.append("no sections/chords found in the document")
        return result

    result.detected_tempo = float(data["bpm"]) if data.get("bpm") else 100.0
    result.detected_key = data.get("key")
    result.time_signature = data.get("time_signature") or "4/4"
    if data.get("title"):
        result.warnings.append(f"title detected: {data['title']}")
    num, den = (int(x) for x in result.time_signature.split("/"))
    bpb = num * 4.0 / den

    chord_notes: list[dict] = []
    bass_notes: list[dict] = []
    out_sections: list[dict] = []
    bar = 0
    for sec in sections:
        chords = [c for c in (sec.get("chords") or []) if isinstance(c, str)]
        length = max(len(chords), 2)
        out_sections.append({"name": sec.get("name") or f"Section {len(out_sections) + 1}",
                             "start_bar": bar, "length_bars": length,
                             "lyrics": sec.get("lyrics") or []})
        for i, sym in enumerate(chords):
            midis = chord_to_midis(sym)
            if midis is None:
                result.warnings.append(f"unreadable chord symbol {sym!r}")
                continue
            start = (bar + i) * bpb
            for hit in (0.0, bpb / 2):
                for j, mnote in enumerate(midis):
                    chord_notes.append({"midi_note": mnote + 12,
                                        "start_beat": start + hit + j * 0.02,
                                        "duration_beats": bpb / 2 - 0.1,
                                        "velocity": 92 - j * 3})
            for b in range(int(bpb)):
                bass_notes.append({"midi_note": midis[0] - 12,
                                   "start_beat": start + b,
                                   "duration_beats": 0.9, "velocity": 100})
        bar += length

    if chord_notes:
        result.detected_tracks.append(DetectedTrack(
            name="Chords", suggested_track_type="guitar", program=25,
            note_count=len(chord_notes), notes=chord_notes))
        result.detected_tracks.append(DetectedTrack(
            name="Bass", suggested_track_type="bass", program=33,
            note_count=len(bass_notes), notes=bass_notes))
    result.sections = out_sections
    if not result.detected_tracks:
        result.supported = False
        result.warnings.append("no playable chords could be extracted")
    return result
