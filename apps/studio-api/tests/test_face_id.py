"""Face identification for voice profiles.

The privacy properties are the point of most of these tests: separate
consent, templates that never ride along in exports, and deletion that
actually deletes. Model-dependent paths are skipped when the ~37 MB models
are not installed, so the suite stays fast and offline-safe.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services import face_id


def _vec(seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    v = rng.normal(size=128).astype(np.float32)
    return [float(x) for x in v / np.linalg.norm(v)]


def test_match_requires_threshold_and_margin():
    """A confident match must clear the absolute threshold AND beat the
    runner-up — silently picking the wrong person is the failure to avoid."""
    a, b = _vec(1), _vec(2)
    assert face_id.match(a, {"p1": a, "p2": b})["profile_id"] == "p1"

    # a stranger scores low against everyone → defer to the user
    stranger = face_id.match(_vec(9), {"p1": a, "p2": b})
    assert stranger["profile_id"] is None and not stranger["confident"]

    # two near-identical enrolments → ambiguous, so no auto-selection
    twin = [x * 0.99 + y * 0.14 for x, y in zip(a, b)]
    amb = face_id.match(a, {"p1": a, "p2": twin})
    assert amb["confident"] is False
    assert amb["best_profile_id"] == "p1"      # still reported, just not applied

    assert face_id.match(a, {})["profile_id"] is None   # nobody enrolled


def test_cosine_handles_degenerate_input():
    assert face_id.cosine([0.0] * 128, _vec(3)) == 0.0
    v = _vec(4)
    assert face_id.cosine(v, v) == pytest.approx(1.0, abs=1e-5)


def test_template_storage_roundtrip_and_deletion(client, workspace):
    v = _vec(5)
    face_id.save_template("prof-a", np.asarray(v, dtype=np.float32))  # numpy ok
    assert face_id.load_template("prof-a") == pytest.approx(v, abs=1e-6)
    assert "prof-a" in face_id.enrolled_templates()

    assert face_id.delete_template("prof-a") is True
    assert face_id.load_template("prof-a") is None
    assert face_id.enrolled_templates() == {}
    assert face_id.delete_template("prof-a") is False   # idempotent


def _make_profile(name: str = "Face Person"):
    """A persisted profile. create_profile() demands a real source recording,
    which these tests don't need — insert the row directly."""
    from app.db import get_db
    from app.models.voice import VoiceProfile
    p = VoiceProfile(name=name, consent_confirmed=True)
    get_db().execute("INSERT INTO voice_profiles (id, data) VALUES (?, ?)",
                     (p.id, p.model_dump_json()))
    get_db().commit()
    return p


def test_deleting_a_profile_deletes_its_face_template(client, workspace):
    """Biometric data must never outlive the profile it belongs to."""
    from app.services import voice_profiles

    p = _make_profile()
    face_id.save_template(p.id, _vec(6))
    assert face_id.load_template(p.id) is not None

    voice_profiles.delete_profile(p.id)
    assert face_id.load_template(p.id) is None


def test_enrolment_requires_its_own_consent(client, workspace):
    """Consenting to voice cloning is not consenting to face recognition."""
    p = _make_profile("No Face Consent")        # face_consent defaults False

    r = client.post(f"/api/voice/profiles/{p.id}/face-enroll",
                    files={"file": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 403
    assert "consent" in r.json()["detail"].lower()

    # granting face consent gets past the gate (503 = models absent, still
    # not a consent failure)
    from app.services import voice_profiles
    p.face_consent = True
    voice_profiles.update_profile(p)
    r2 = client.post(f"/api/voice/profiles/{p.id}/face-enroll",
                     files={"file": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r2.status_code != 403


def test_status_and_capability_never_raise(client, workspace):
    s = client.get("/api/voice/face/status").json()
    assert {"runtime_available", "models_installed", "available"} <= set(s)
    assert s["threshold"] == face_id.MATCH_THRESHOLD
    # the health probe must survive missing models
    assert "face_id" in client.get("/api/health").json()["capabilities"]


def test_identify_without_enrolments_is_graceful(client, workspace,
                                                  monkeypatch):
    monkeypatch.setattr(face_id, "available", lambda: True)
    monkeypatch.setattr(face_id, "enrolled_templates", dict)
    r = client.post("/api/voice/identify",
                    files={"file": ("f.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 200
    assert r.json()["profile_id"] is None


def test_bundle_import_never_claims_face_enrolment(client, workspace):
    """Templates are excluded from bundles, so an imported profile must not
    come back marked as enrolled (or carry someone's face consent)."""
    import inspect
    from app.services import bundles
    src = inspect.getsource(bundles)
    assert 'pdump["face_enrolled"] = False' in src
    assert 'pdump["face_consent"] = False' in src


def _real_models_dir():
    """Where the models live in the developer's own workspace. The `workspace`
    fixture points MITY_ROOT at a temp dir, so models_installed() must be
    asked about THAT dir — the skip guard cannot be a module-level decorator
    (it would be evaluated against the real root before the fixture runs)."""
    from pathlib import Path
    return Path(__file__).resolve().parents[3] / "models" / "face"


def test_detect_rejects_unusable_photos(client, workspace, monkeypatch):
    import cv2
    real = _real_models_dir()
    if not (real / "face_recognition_sface_2021dec.onnx").exists():
        pytest.skip("face models not installed")
    monkeypatch.setattr(face_id, "models_dir", lambda: real)
    face_id.reset_engines()
    with pytest.raises(face_id.FaceIdError):
        face_id.detect_and_embed(b"definitely not an image")
    blank = cv2.imencode(".jpg", np.zeros((480, 640, 3), np.uint8))[1].tobytes()
    with pytest.raises(face_id.FaceIdError) as e:
        face_id.detect_and_embed(blank)
    assert "no face" in str(e.value).lower()
