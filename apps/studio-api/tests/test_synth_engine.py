"""Built-in synth engine + its exposure to the agent and the render pipeline."""
from __future__ import annotations

import numpy as np

from app.services.render import synth_engine as se


def test_every_patch_renders_finite_audio():
    for pid, patch in se.PATCHES.items():
        midi = 36 if patch.kind == "drums" else 60
        buf = se.render_note(patch, midi, 0.5, 100)
        assert buf.dtype == np.float32, pid
        assert len(buf) > 0, pid
        assert np.isfinite(buf).all(), pid
        assert float(np.max(np.abs(buf))) > 0.01, f"{pid} is silent"


def test_drum_kit_maps_notes_to_distinct_voices():
    kit = se.PATCHES["drum_kit"]
    kick = se.render_note(kit, 36, 0.2, 110)
    snare = se.render_note(kit, 38, 0.2, 110)
    hat = se.render_note(kit, 42, 0.2, 110)
    # different GM notes yield audibly different (different-length) hits
    assert len({len(kick), len(snare), len(hat)}) >= 2
    for buf in (kick, snare, hat):
        assert float(np.max(np.abs(buf))) > 0.01


def test_default_patch_covers_every_instrument_type():
    for tt in ("drums", "bass", "guitar", "keys", "synth", "strings", "brass",
               "fx"):
        pid = se.default_patch(tt)
        assert se.get_patch(pid) is not None, tt
    assert se.default_patch("drums") == "drum_kit"


def test_catalog_and_specs_shape():
    cat = se.synth_catalog()
    assert cat and all("category" in c and c["presets"] for c in cat)
    entry = cat[0]["presets"][0]
    assert entry["asset_id"].startswith("synth:")
    assert entry["synth_patch"] and entry["soundfont"] == "Built-in synth"

    specs = se.synth_patch_specs()
    assert len(specs) == len(se.PATCHES)
    for s in specs:
        assert isinstance(s["adsr"], list) and len(s["adsr"]) == 4
        assert {"id", "kind", "osc", "cutoff", "track_types"} <= set(s)


def test_polyblep_saw_is_band_limited():
    """The PolyBLEP saw must have less aliasing than a naive saw: for a high
    fundamental, energy above Nyquist-folded harmonics should be reduced."""
    sr = 44100
    n = sr
    freq = 2000.0
    dt = np.full(n, freq / sr)
    phase = (np.arange(n) * dt) % 1.0
    naive = 2 * phase - 1
    blep = naive - se._polyblep(phase, dt)
    # crude aliasing proxy: high-band energy ratio should drop
    def hi_energy(x):
        spec = np.abs(np.fft.rfft(x))
        f = np.fft.rfftfreq(n, 1 / sr)
        return float(spec[f > 12000].sum() / (spec.sum() + 1e-9))
    assert hi_energy(blep) < hi_energy(naive)


def test_summary_and_retrieval_expose_builtin_synths(client, workspace):
    """The agent always knows the built-in synth set, even with no SoundFonts
    installed in the workspace."""
    from app.services import asset_retrieval, project_repo
    from tests.test_projects import make_project

    p = make_project(client)
    project = project_repo.load_project(p["id"])

    summary = asset_retrieval.summary()
    assert summary["built_in_synths"] == len(se.PATCHES)
    assert any(c["category"] == "Synth Lead"
               for c in summary["instrument_categories"])

    inst = asset_retrieval.retrieve_instruments(
        "give me a plucked bass and a warm pad", project)
    synth_ids = {e["synth_patch"] for e in inst if e.get("synth_patch")}
    assert synth_ids == set(se.PATCHES)          # every patch is always offered
