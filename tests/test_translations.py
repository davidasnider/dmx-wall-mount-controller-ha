import json
from pathlib import Path

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "dmx_diodeled"


def _load(relative_path: str) -> dict:
    return json.loads((COMPONENT_DIR / relative_path).read_text(encoding="utf-8"))


def test_english_translations_match_strings() -> None:
    """Home Assistant only reads translations/<lang>.json for custom
    integrations, so it must stay in sync with strings.json."""
    assert _load("translations/en.json") == _load("strings.json")


def test_translations_cover_config_flow() -> None:
    config = _load("translations/en.json")["config"]

    assert {"user", "discovery_confirm"} <= set(config["step"])
    assert "already_configured" in config["abort"]
    assert "{host}" in config["step"]["discovery_confirm"]["description"]
