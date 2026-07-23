"""Release packaging guards.

Auto-update silently broke because the installer's filename contained
spaces: GitHub rewrites those to dots when it stores the asset, while
electron-builder writes them as hyphens into latest.yml. The updater then
requested a file that did not exist and every update failed with a generic
"update failed". These assertions keep that from coming back.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

DESKTOP_PKG = (Path(__file__).resolve().parents[3]
               / "apps" / "desktop" / "package.json")


@pytest.fixture(scope="module")
def build_cfg() -> dict:
    if not DESKTOP_PKG.exists():
        pytest.skip("desktop package.json not present")
    return json.loads(DESKTOP_PKG.read_text(encoding="utf-8"))["build"]


def test_installer_filename_has_no_spaces(build_cfg):
    """A space anywhere in artifactName desynchronises latest.yml from the
    uploaded asset name, which 404s every auto-update."""
    names = [build_cfg.get("artifactName"),
             build_cfg.get("nsis", {}).get("artifactName")]
    assert any(names), "artifactName must be set explicitly — the " \
        "electron-builder default contains spaces"
    for n in filter(None, names):
        assert " " not in n, f"artifactName {n!r} contains a space"
        assert "${version}" in n and "${ext}" in n, \
            f"artifactName {n!r} must stay version/extension templated"
    # both places must agree, or which one wins depends on the target
    set_names = {n for n in names if n}
    assert len(set_names) == 1, f"conflicting artifactName values: {set_names}"


def test_publishes_to_github_so_latest_yml_is_generated(build_cfg):
    publish = build_cfg.get("publish")
    provider = (publish or {}).get("provider") if isinstance(publish, dict) \
        else (publish or [{}])[0].get("provider")
    assert provider == "github"


def test_updates_preserve_the_workspace(build_cfg):
    """In-place updates must never wipe the user's projects/assets."""
    assert build_cfg.get("nsis", {}).get("deleteAppDataOnUninstall") is False
