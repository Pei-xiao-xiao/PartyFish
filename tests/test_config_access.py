from types import SimpleNamespace

from src.config import Config


def make_config(global_settings=None, presets=None, current_preset_name="路亚轻竿"):
    config = object.__new__(Config)
    object.__setattr__(config, "global_settings", global_settings or {})
    object.__setattr__(config, "presets", presets or {})
    object.__setattr__(config, "current_preset_name", current_preset_name)

    default_presets = {
        "路亚轻竿": {
            "cast_time": 0.1,
            "cycle_interval": 0.1,
        }
    }
    default_global_settings = {
        "theme": "Light",
        "hotkey": "F2",
        "fish_filter_mode": "all",
    }

    manager = SimpleNamespace()
    manager.get_default_presets = lambda: default_presets
    manager._get_default_global_settings = lambda: default_global_settings
    manager.get_current_preset = lambda: config.presets.get(config.current_preset_name)
    object.__setattr__(config, "config_manager", manager)
    return config


def test_explicit_global_setting_api_uses_current_then_default():
    config = make_config(global_settings={"theme": "Dark"})

    assert config.get_global_setting("theme") == "Dark"
    assert config.get_global_setting("hotkey") == "F2"
    assert config.get_global_setting("missing", "fallback") == "fallback"


def test_explicit_preset_api_uses_current_then_default():
    config = make_config(
        presets={"路亚轻竿": {"cast_time": 0.3}},
    )

    assert config.get_preset_value("cast_time") == 0.3
    assert config.get_preset_value("cycle_interval") == 0.1


def test_bulk_global_setting_update_is_explicit_and_stable():
    config = make_config(global_settings={"theme": "Dark"})

    config.update_global_settings(
        {
            "theme": "Light",
            "control_sound_enabled": True,
        }
    )

    assert config.get_global_setting("theme") == "Light"
    assert config.get_global_setting("control_sound_enabled") is True


def test_named_preset_access_and_creation_use_explicit_api():
    config = make_config(presets={})

    assert config.get_preset_value_for("璺簹杞荤", "cycle_interval") == 0.1

    config.set_preset_value_for("custom_preset", "cast_time", 0.8)

    assert config.presets["custom_preset"]["cast_time"] == 0.8


def test_compatibility_magic_access_routes_to_explicit_storage():
    config = make_config(
        global_settings={"theme": "Dark"},
        presets={"路亚轻竿": {"cast_time": 0.3}},
    )

    assert config.theme == "Dark"
    assert config.cast_time == 0.3

    config.theme = "Light"
    config.cast_time = 0.5

    assert config.global_settings["theme"] == "Light"
    assert config.presets["路亚轻竿"]["cast_time"] == 0.5


def test_set_preset_value_creates_missing_current_preset():
    config = make_config(presets={}, current_preset_name="路亚轻竿")

    config.set_preset_value("cast_time", 0.6)

    assert config.presets["路亚轻竿"]["cast_time"] == 0.6
