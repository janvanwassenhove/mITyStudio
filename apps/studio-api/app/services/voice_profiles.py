"""Voice profile management. Consent is mandatory: a profile cannot be
created without consent_confirmed=True, and recordings never become profiles
automatically."""
from __future__ import annotations

from ..db import get_db
from ..models.voice import CreateVoiceProfileRequest, VoiceProfile
from . import asset_repo


class ConsentRequired(Exception):
    pass


class InvalidSourceRecording(Exception):
    pass


def create_profile(req: CreateVoiceProfileRequest) -> VoiceProfile:
    if not req.consent_confirmed:
        raise ConsentRequired(
            "creating a voice profile requires explicit consent "
            "(consent_confirmed must be true)")
    for rid in req.source_recording_ids:
        asset = asset_repo.get_asset(rid)
        if asset is None or asset.asset_type != "voice_recording":
            raise InvalidSourceRecording(
                f"{rid} is not a registered voice recording")
    profile = VoiceProfile(**req.model_dump())
    get_db().execute(
        "INSERT INTO voice_profiles (id, data) VALUES (?, ?)",
        (profile.id, profile.model_dump_json()))
    get_db().commit()

    # register as an asset so it shows up in the Asset Library
    from ..models.asset import Asset
    asset_repo.upsert_asset(Asset(
        id=profile.id, asset_type="voice_profile", filename=profile.name,
        original_path="", relative_path=f"voices/profiles/{profile.id}",
        extension="", source="upload",
        user_description=f"voice profile ({profile.performer_alias or 'unnamed performer'})",
        license_notes=profile.usage_restrictions))
    return profile


def get_profile(profile_id: str) -> VoiceProfile | None:
    row = get_db().execute("SELECT data FROM voice_profiles WHERE id=?",
                           (profile_id,)).fetchone()
    return VoiceProfile.model_validate_json(row["data"]) if row else None


def list_profiles() -> list[VoiceProfile]:
    rows = get_db().execute("SELECT data FROM voice_profiles").fetchall()
    return [VoiceProfile.model_validate_json(r["data"]) for r in rows]


def update_profile(profile: VoiceProfile) -> None:
    get_db().execute("UPDATE voice_profiles SET data=? WHERE id=?",
                     (profile.model_dump_json(), profile.id))
    get_db().commit()


def delete_profile(profile_id: str) -> bool:
    """Remove a voice profile (and its asset-library mirror). Source
    recordings are never touched. Tracks referencing it fall back to the
    default voice at render time."""
    cur = get_db().execute("DELETE FROM voice_profiles WHERE id=?",
                           (profile_id,))
    get_db().execute("DELETE FROM assets WHERE id=? AND asset_type='voice_profile'",
                     (profile_id,))
    get_db().commit()
    return cur.rowcount > 0
