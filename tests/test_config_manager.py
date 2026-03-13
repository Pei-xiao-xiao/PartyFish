from types import SimpleNamespace

from src.services.config_manager import ConfigManager


def make_manager():
    return ConfigManager(SimpleNamespace())


def test_normalize_preset_name_handles_legacy_names():
    manager = make_manager()

    assert manager._normalize_preset_name("冰钓轻杆") == "池塘轻竿"
    assert manager._normalize_preset_name("冰钓重杆") == "池塘重竿"


def test_sanitize_presets_removes_deprecated_entries_and_merges_defaults():
    manager = make_manager()

    sanitized = manager._sanitize_presets(
        {
            "智能钓鱼": {"cast_time": 9.9},
            "冰钓轻杆": {
                "cast_time": 0.3,
                "smart_release_angle": 10,
                "smart_release_time": 20,
            },
            "路亚重竿": "invalid-preset",
        }
    )

    assert "智能钓鱼" not in sanitized
    assert sanitized["池塘轻竿"]["cast_time"] == 0.3
    assert "smart_release_angle" not in sanitized["池塘轻竿"]
    assert "smart_release_time" not in sanitized["池塘轻竿"]
    assert isinstance(sanitized["路亚重竿"], dict)
    assert sanitized["路亚重竿"]["reel_in_time"] == 0.8
    assert set(manager.get_default_presets()).issubset(set(sanitized))


def test_sanitize_presets_falls_back_to_defaults_when_empty():
    manager = make_manager()

    assert manager._sanitize_presets({}) == manager.get_default_presets()
