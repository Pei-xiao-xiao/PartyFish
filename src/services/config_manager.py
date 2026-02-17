"""
配置管理服务
负责配置文件的加载、保存和预设管理
"""

import json


class ConfigManager:
    """配置管理服务类"""

    def __init__(self, config):
        """
        初始化配置管理服务

        Args:
            config: Config 实例引用
        """
        self.config = config

    def get_default_presets(self):
        """返回默认预设字典"""
        return {
            "路亚轻杆": {
                "cast_time": 2.7,
                "reel_in_time": 0.17,
                "release_time": 0.07,
                "max_pulls": 99,
                "cycle_interval": 0.3,
            },
            "路亚重杆": {
                "cast_time": 2.5,
                "reel_in_time": 1.2,
                "release_time": 0.2,
                "max_pulls": 99,
                "cycle_interval": 0.5,
            },
            "池塘轻杆": {
                "cast_time": 0.1,
                "reel_in_time": 0.555,
                "release_time": 0.444,
                "max_pulls": 100,
                "cycle_interval": 0.5,
            },
            "池塘重杆": {
                "cast_time": 0.2,
                "reel_in_time": 0.4,
                "release_time": 0.2,
                "max_pulls": 100,
                "cycle_interval": 0.5,
            },
        }

    def load_config_from_json(self):
        """从 JSON 文件加载配置"""
        config_path = self.config.user_data_dir / "config.json"

        if not config_path.exists():
            self._create_default_config()
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
        except json.JSONDecodeError:
            self._create_default_config()
            return

        self.config.current_preset_name = config_data.get("current_preset", "路亚轻杆")
        self.config.presets = config_data.get("presets", self.get_default_presets())

        # 迁移旧预设名称
        rename_map = {"冰钓轻杆": "池塘轻杆", "冰钓重杆": "池塘重杆"}
        for old_name, new_name in rename_map.items():
            if old_name in self.config.presets:
                self.config.presets[new_name] = self.config.presets.pop(old_name)
                if self.config.current_preset_name == old_name:
                    self.config.current_preset_name = new_name

        default_global_settings = self._get_default_global_settings()
        loaded_global_settings = config_data.get("global_settings", {})
        default_global_settings.update(loaded_global_settings)
        self.config.global_settings = default_global_settings

        self.config.current_bait = config_data.get("current_bait", "蔓越莓")
        self.config.current_account = config_data.get("current_account", "默认账号")

        # 确保账号数据目录存在
        self.config._get_account_data_dir().mkdir(parents=True, exist_ok=True)

        self.config.qfluent_settings = config_data.get(
            "QFluentWidgets", {"ThemeMode": "Light"}
        )

    def _create_default_config(self):
        """创建默认配置"""
        self.config.presets = self.get_default_presets()
        self.config.global_settings = self._get_default_global_settings()
        self.config.qfluent_settings = {"ThemeMode": "Light"}
        self.save()

    def _get_default_global_settings(self):
        """返回默认全局设置"""
        return {
            "hotkey": "F2",
            "debug_hotkey": "F10",
            "sell_hotkey": "F4",
            "auto_click_sell": True,
            "enable_jiashi": True,
            "jitter_range": 0,
            "theme": "Light",
            "enable_anti_afk": True,
            "enable_sound_alert": False,
            "enable_record": True,
            "server_region": "CN",
            "overlay_visible": False,
            "overlay_position": None,
            "fish_filter_mode": "all",
            "welcome_dialog_shown": False,
            "hardware_info": {},
            "uno_hotkey": "F3",
            "uno_current_cards": 7,
            "uno_max_cards": 35,
            "release_mode": "off",
            "auto_release_enabled": False,
            "enable_fish_name_protection": False,
            "release_standard": True,
            "release_uncommon": False,
            "release_rare": False,
            "release_epic": False,
            "release_legendary": False,
            "enable_legendary_screenshot": True,
            "enable_first_catch_screenshot": True,
            "enable_record_only": False,
            "record_only_hotkey": "F5",
            "enable_gamepad": False,
            "gamepad_mappings": {},
        }

    def save(self):
        """保存配置到 JSON 文件"""
        config_path = self.config.user_data_dir / "config.json"

        config_data = {
            "current_preset": self.config.current_preset_name,
            "current_bait": self.config.current_bait,
            "current_account": self.config.current_account,
            "presets": self.config.presets,
            "global_settings": self.config.global_settings,
            "QFluentWidgets": self.config.qfluent_settings,
        }

        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    def get_current_preset(self):
        """返回当前活动预设的字典"""
        return self.config.presets.get(self.config.current_preset_name)

    def load_preset(self, name):
        """切换当前预设"""
        if name in self.config.presets:
            self.config.current_preset_name = name
        else:
            raise ValueError(f"Preset '{name}' not found.")
