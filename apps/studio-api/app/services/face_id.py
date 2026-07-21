"""Face identification for voice profiles — fully local, consent-gated.

Purpose: let the studio recognise WHICH enrolled performer is at the mic and
pre-select their voice profile, and show a photo next to each profile.

Design constraints, deliberately strict because a face template is
biometric data (same category as the voice recordings this app already
consent-gates):

- **Local only.** Detection and matching run through OpenCV's bundled
  YuNet + SFace ONNX models via `cv2.dnn`. A face image is NEVER sent to
  the vision LLM or any other network service.
- **No new heavy runtime.** opencv-python is already a dependency; this
  needs neither torch, onnxruntime nor insightface — only two model files
  (~37 MB total) fetched on demand, like the SVS vocoder.
- **Separate consent.** Consenting to voice cloning is NOT consent to face
  recognition, so enrolment requires its own flag on the profile.
- **Templates stay out of shareable exports.** The embedding lives in
  voices/profiles/<id>.face.json, never in the profile record, so exporting
  or sharing a voice bundle cannot leak someone's face template.
- **Deletable.** Removing enrolment deletes the template file outright.

Matching uses cosine similarity on SFace's 128-d embedding. Two guards keep
a wrong profile from being auto-selected: an absolute threshold, and a
margin the best match must beat the runner-up by.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import get_config

log = logging.getLogger(__name__)

# OpenCV Zoo (Apache-2.0). The raw.githubusercontent URLs serve Git-LFS
# pointer stubs, so the media.* host is required to get the real weights.
_ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
MODELS = {
    "detector": (f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
                 "face_detection_yunet_2023mar.onnx"),
    "recognizer": (f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
                   "face_recognition_sface_2021dec.onnx"),
}

# SFace's published operating point is cosine 0.363; we ask for a little more
# plus a clear margin over the runner-up, because silently picking the WRONG
# person's voice profile is worse than asking the user to choose.
#
# Validated on the LFW benchmark (24 enrolled people, 67 identifications of
# unseen photos): 63 correct, 0 wrong, 4 deferred to the user. Across 1541
# imposter comparisons the highest score was 0.389 — no imposter reached
# 0.40. Keep the threshold above that ceiling if you ever retune it.
MATCH_THRESHOLD = 0.40
MATCH_MARGIN = 0.05
_MIN_FACE_PX = 60
# Detector confidence. Kept deliberately loose: measured on LFW, 0.9 missed
# 1/60 well-framed faces while 0.7 found 60/60, and a false *detection*
# costs nothing — identity is decided by MATCH_THRESHOLD below, not here.
_DETECT_CONF = 0.7


class FaceIdError(Exception):
    pass


def models_dir() -> Path:
    return get_config().root / "models" / "face"


def model_path(kind: str) -> Path:
    return models_dir() / MODELS[kind][1]


def models_installed() -> bool:
    return all(model_path(k).exists() and model_path(k).stat().st_size > 10_000
               for k in MODELS)


def available() -> bool:
    """Cheap probe: OpenCV new enough for the face API + models present."""
    import os
    if os.environ.get("MITY_DISABLE_FACE_ID"):
        return False
    try:
        import cv2
    except Exception:  # noqa: BLE001
        return False
    if not (hasattr(cv2, "FaceDetectorYN") and hasattr(cv2, "FaceRecognizerSF")):
        return False
    return models_installed()


def status() -> dict:
    try:
        import cv2
        runtime = (hasattr(cv2, "FaceDetectorYN")
                   and hasattr(cv2, "FaceRecognizerSF"))
        version = cv2.__version__
    except Exception:  # noqa: BLE001
        runtime, version = False, ""
    return {"runtime_available": runtime, "opencv": version,
            "models_installed": models_installed(),
            "available": available(),
            "threshold": MATCH_THRESHOLD, "margin": MATCH_MARGIN}


def install_models() -> dict:
    """One-time download of YuNet (~230 KB) + SFace (~37 MB)."""
    out = models_dir()
    out.mkdir(parents=True, exist_ok=True)
    fetched = []
    for kind, (url, name) in MODELS.items():
        dest = out / name
        if dest.exists() and dest.stat().st_size > 10_000:
            continue
        tmp = dest.with_suffix(".part")
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "mITyStudio-face-models"})
            with urllib.request.urlopen(req, timeout=120) as r, \
                    open(tmp, "wb") as f:
                f.write(r.read())
        except Exception as e:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise FaceIdError(f"could not download the {kind} model: {e}")
        if tmp.stat().st_size < 10_000:      # an LFS stub or an error page
            tmp.unlink(missing_ok=True)
            raise FaceIdError(f"{kind} model download returned no weights")
        tmp.replace(dest)
        fetched.append(name)
    return {"installed": models_installed(), "downloaded": fetched}


# --- engine ---------------------------------------------------------------

_engines: dict = {}


def _engines_for(width: int, height: int):
    import cv2
    if "rec" not in _engines:
        if not models_installed():
            raise FaceIdError(
                "face models are not installed — run the face model install "
                "first")
        _engines["det"] = cv2.FaceDetectorYN.create(
            str(model_path("detector")), "", (320, 320), _DETECT_CONF,
            0.3, 5000)
        _engines["rec"] = cv2.FaceRecognizerSF.create(
            str(model_path("recognizer")), "")
    _engines["det"].setInputSize((width, height))
    return _engines["det"], _engines["rec"]


def reset_engines() -> None:
    """Drop cached engines (after a model (re)install or in tests)."""
    _engines.clear()


@dataclass
class FaceResult:
    embedding: list[float]
    box: tuple[int, int, int, int]      # x, y, w, h
    score: float                        # detector confidence


def detect_and_embed(image_bytes: bytes) -> FaceResult:
    """Find the largest face in the image and return its 128-d template.

    Raises FaceIdError with a user-actionable message when the photo cannot
    be used (no face, several faces, face too small).
    """
    import cv2
    buf = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise FaceIdError("that file is not a readable image")
    h, w = img.shape[:2]
    # keep detection cheap on phone-sized photos
    scale = 1.0
    if max(h, w) > 1024:
        scale = 1024 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
        h, w = img.shape[:2]

    det, rec = _engines_for(w, h)
    _n, faces = det.detect(img)
    if faces is None or len(faces) == 0:
        raise FaceIdError("no face found in the photo")
    # largest face wins; a crowded frame is ambiguous for identification
    faces = sorted(faces, key=lambda f: float(f[2]) * float(f[3]), reverse=True)
    if len(faces) > 1:
        biggest, second = faces[0], faces[1]
        if float(second[2]) * float(second[3]) > 0.5 * float(biggest[2]) * float(biggest[3]):
            raise FaceIdError(
                "more than one face in the photo — use a photo of one person")
    face = faces[0]
    if float(face[2]) < _MIN_FACE_PX or float(face[3]) < _MIN_FACE_PX:
        raise FaceIdError("the face is too small — move closer to the camera")

    aligned = rec.alignCrop(img, face)
    emb = rec.feature(aligned)
    vec = np.asarray(emb, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-6:
        raise FaceIdError("could not read a usable face template")
    vec = vec / norm                      # store normalized: match = dot
    x, y, bw, bh = (int(face[i] / scale) for i in range(4))
    return FaceResult(embedding=[float(v) for v in vec], box=(x, y, bw, bh),
                      score=float(face[-1]))


def cosine(a: list[float] | np.ndarray, b: list[float] | np.ndarray) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na < 1e-6 or nb < 1e-6:
        return 0.0
    return float(va @ vb / (na * nb))


def match(embedding: list[float],
          candidates: dict[str, list[float]]) -> dict:
    """Best enrolled profile for this face.

    Returns {"profile_id", "score", "confident", "runner_up"}; `confident`
    is only true when the score clears the threshold AND beats the runner-up
    by the margin — the caller must not auto-apply an unconfident match.
    """
    scored = sorted(((pid, cosine(embedding, vec))
                     for pid, vec in candidates.items()),
                    key=lambda t: -t[1])
    if not scored:
        return {"profile_id": None, "score": 0.0, "confident": False,
                "runner_up": None}
    best_id, best = scored[0]
    runner = scored[1][1] if len(scored) > 1 else 0.0
    confident = best >= MATCH_THRESHOLD and (best - runner) >= MATCH_MARGIN
    return {"profile_id": best_id if confident else None,
            "best_profile_id": best_id, "score": round(best, 4),
            "confident": confident, "runner_up": round(runner, 4)}


# --- template storage (kept OUT of the profile record and its exports) ----

def _template_path(profile_id: str) -> Path:
    return get_config().voices_dir / "profiles" / f"{profile_id}.face.json"


def save_template(profile_id: str, embedding) -> None:
    # coerce to plain floats: callers may hand us numpy scalars, which json
    # cannot serialize
    vec = [float(v) for v in embedding]
    p = _template_path(profile_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"v": 1, "embedding": vec}), encoding="utf-8")


def load_template(profile_id: str) -> list[float] | None:
    p = _template_path(profile_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["embedding"]
    except (OSError, ValueError, KeyError):
        return None


def delete_template(profile_id: str) -> bool:
    p = _template_path(profile_id)
    existed = p.exists()
    p.unlink(missing_ok=True)
    return existed


def enrolled_templates() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    d = get_config().voices_dir / "profiles"
    if not d.exists():
        return out
    for f in d.glob("*.face.json"):
        pid = f.name[:-len(".face.json")]
        vec = load_template(pid)
        if vec:
            out[pid] = vec
    return out
