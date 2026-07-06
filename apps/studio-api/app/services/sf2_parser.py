"""Minimal SoundFont2 parser: reads the RIFF INFO name and the preset
headers (pdta→phdr) without loading sample data. Pure stdlib.

Used to inventory the preset names/banks/programs of every .sf2 in the
library so tracks can be matched to a SoundFont that actually contains a
suitable instrument (e.g. a bass preset for a bass track, bank 128 for drums).
"""
from __future__ import annotations

import json
import logging
import struct
from pathlib import Path

from ..db import get_db

log = logging.getLogger(__name__)


class Sf2ParseError(Exception):
    pass


def _read_chunk_header(f) -> tuple[bytes, int]:
    hdr = f.read(8)
    if len(hdr) < 8:
        raise Sf2ParseError("unexpected end of file")
    cid, size = struct.unpack("<4sI", hdr)
    return cid, size


def parse_sf2(path: Path) -> dict:
    """Returns {"name": str, "presets": [{"name", "bank", "program"}]}."""
    with open(path, "rb") as f:
        cid, _ = _read_chunk_header(f)
        if cid != b"RIFF":
            raise Sf2ParseError("not a RIFF file")
        if f.read(4) != b"sfbk":
            raise Sf2ParseError("not a SoundFont (sfbk) file")

        bank_name = ""
        presets: list[dict] = []
        while True:
            try:
                cid, size = _read_chunk_header(f)
            except Sf2ParseError:
                break
            if cid != b"LIST":
                f.seek(size + (size & 1), 1)
                continue
            list_type = f.read(4)
            list_end = f.tell() + size - 4
            if list_type == b"INFO":
                while f.tell() < list_end:
                    sub_id, sub_size = _read_chunk_header(f)
                    data = f.read(sub_size + (sub_size & 1))[:sub_size]
                    if sub_id == b"INAM":
                        bank_name = data.split(b"\0")[0].decode("latin-1",
                                                                "replace").strip()
                f.seek(list_end)
            elif list_type == b"pdta":
                while f.tell() < list_end:
                    sub_id, sub_size = _read_chunk_header(f)
                    if sub_id == b"phdr":
                        raw = f.read(sub_size + (sub_size & 1))[:sub_size]
                        # 38-byte records; last record is the EOP terminator
                        for off in range(0, len(raw) - 38, 38):
                            name, program, bank = struct.unpack_from(
                                "<20sHH", raw, off)
                            presets.append({
                                "name": name.split(b"\0")[0]
                                .decode("latin-1", "replace").strip(),
                                "program": program,
                                "bank": bank,
                            })
                    else:
                        f.seek(sub_size + (sub_size & 1), 1)
                f.seek(list_end)
            else:
                f.seek(list_end)
        return {"name": bank_name, "presets": presets}


# --- preset inventory cache (SQLite settings table) ------------------------

def get_preset_inventory(asset_id: str, path: Path) -> dict | None:
    key = f"sf2_presets:{asset_id}"
    row = get_db().execute("SELECT value FROM settings WHERE key=?",
                           (key,)).fetchone()
    if row:
        return json.loads(row["value"])
    try:
        info = parse_sf2(path)
    except (Sf2ParseError, OSError, struct.error) as e:
        log.warning("cannot parse %s: %s", path.name, e)
        info = {"name": "", "presets": [], "error": str(e)}
    get_db().execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(info)))
    get_db().commit()
    return info


# --- smart matching --------------------------------------------------------

# keywords that indicate a preset suits a track type
_TRACK_KEYWORDS: dict[str, list[str]] = {
    "drums": ["drum", "kit", "standard", "percussion"],
    "bass": ["bass"],
    "guitar": ["guitar", "gtr", "nylon", "steel", "strat", "les paul", "clean",
               "overdrive", "distort"],
    "keys": ["piano", "rhodes", "organ", "keys", "clav", "harpsi", "e.piano",
             "epiano", "wurl"],
    "synth": ["synth", "lead", "saw", "square", "pad", "poly"],
    "strings": ["string", "violin", "cello", "viola", "ensemble", "orchestra"],
    "brass": ["brass", "trumpet", "sax", "trombone", "horn", "tuba"],
    "fx": ["fx", "effect", "atmosphere", "goblin", "sweep"],
    "lead_vocal": ["voice", "choir", "aah", "ooh", "vox", "vocal"],
    "backing_vocal": ["voice", "choir", "aah", "ooh", "vox", "vocal"],
}

# General MIDI program ranges per track type (fallback scoring)
_TRACK_GM_RANGES: dict[str, tuple[int, int]] = {
    "keys": (0, 23), "guitar": (24, 31), "bass": (32, 39),
    "strings": (40, 55), "brass": (56, 79), "synth": (80, 103),
    "fx": (96, 103), "lead_vocal": (52, 54), "backing_vocal": (52, 54),
}


def score_soundfont_for_track(inventory: dict, track_type: str,
                              filename: str) -> tuple[float, dict | None]:
    """Score how well a SoundFont suits a track type.
    Returns (score, best_preset)."""
    presets = inventory.get("presets", [])
    if not presets:
        return 0.0, None
    keywords = _TRACK_KEYWORDS.get(track_type, [])
    best: tuple[float, dict | None] = (0.0, None)

    if track_type == "drums":
        drum_presets = [p for p in presets if p["bank"] == 128]
        if drum_presets:
            named = next((p for p in drum_presets
                          if any(k in p["name"].lower() for k in keywords)),
                         drum_presets[0])
            return 10.0, named
        # fall through to keyword scan (some fonts keep kits in bank 0)

    fname = filename.lower()
    for p in presets:
        pname = p["name"].lower()
        score = 0.0
        if any(k in pname for k in keywords):
            score += 6.0
        if any(k in fname for k in keywords):
            score += 2.0
        gm = _TRACK_GM_RANGES.get(track_type)
        if gm and p["bank"] == 0 and gm[0] <= p["program"] <= gm[1]:
            score += 3.0
        if p["bank"] == 128 and track_type != "drums":
            score = 0.0  # never give a melodic track a drum kit
        if score > best[0]:
            best = (score, p)
    # a big GM-style bank is a decent generic fallback
    if best[0] == 0 and len(presets) > 100:
        gm = _TRACK_GM_RANGES.get(track_type)
        if gm:
            candidate = next((p for p in presets if p["bank"] == 0
                              and gm[0] <= p["program"] <= gm[1]), None)
            if candidate:
                best = (1.5, candidate)
    return best


def find_best_soundfont(track_type: str) -> tuple[object, dict] | None:
    """Search the whole registry for the best (asset, preset) for a track
    type. Returns None if nothing suitable exists."""
    from . import asset_repo
    best_score = 0.0
    best: tuple[object, dict] | None = None
    for asset in asset_repo.list_assets("soundfont", include_missing=False):
        if asset.extension not in (".sf2",):
            continue
        inv = get_preset_inventory(asset.id, Path(asset.original_path))
        score, preset = score_soundfont_for_track(inv, track_type, asset.filename)
        if score > best_score and preset is not None:
            best_score = score
            best = (asset, preset)
    return best
