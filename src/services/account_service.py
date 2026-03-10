"""
账号管理服务
负责多账号的创建、切换、删除和数据目录管理
"""

import json
import shutil
from copy import deepcopy


class AccountService:
    """账号管理服务类"""

    ACCOUNT_SPECIFIC_GLOBAL_KEYS = (
        "cast_mode",
        "selected_baits",
        "release_mode",
        "auto_release_enabled",
        "enable_fish_name_protection",
        "release_standard",
        "release_uncommon",
        "release_rare",
        "release_epic",
        "release_legendary",
        "pokedex_filter_criteria",
    )

    DEFAULT_ACCOUNT_SETTINGS = {
        "server_region": "CN",
        "current_preset": "路亚轻杆",
        "current_bait": "蔓越莓",
        "selected_baits": [],
        "release_mode": "off",
        "auto_release_enabled": False,
        "enable_fish_name_protection": False,
        "release_standard": True,
        "release_uncommon": False,
        "release_rare": False,
        "release_epic": False,
        "release_legendary": False,
        "pokedex_filter_criteria": {},
        "cast_mode": "tap",
    }

    def __init__(self, config):
        """
        初始化账号服务

        Args:
            config: Config 实例引用
        """
        self.config = config

    def get_account_data_dir(self):
        """返回当前账号的数据目录"""
        return (
            self.config.user_data_dir
            / "accounts"
            / self.config.current_account
            / "data"
        )

    def get_records_file(self):
        """返回当前账号的钓鱼记录文件路径"""
        return self.get_account_data_dir() / "records.csv"

    def get_sales_file(self):
        """返回当前账号的销售记录文件路径"""
        return self.get_account_data_dir() / "sales.csv"

    def get_accounts(self):
        """获取所有账号列表"""
        accounts_dir = self.config.user_data_dir / "accounts"
        if accounts_dir.exists():
            accounts = [d.name for d in accounts_dir.iterdir() if d.is_dir()]
            if accounts:
                return sorted(accounts)
        return ["默认账号"]

    def switch_account(self, account_name):
        """
        切换账号
        :param account_name: 目标账号名
        :return: True 如果切换成功
        """
        self.persist_current_account_settings()
        self.config.current_account = account_name

        account_dir = self.get_account_data_dir()
        account_dir.mkdir(parents=True, exist_ok=True)

        self.apply_account_settings(account_name)
        self.config.save()
        return True

    def delete_account(self, account_name):
        """
        删除账号
        :param account_name: 要删除的账号名
        :return: True 如果删除成功
        """
        if account_name == self.config.current_account:
            return False

        account_dir = self.config.user_data_dir / "accounts" / account_name
        if account_dir.exists():
            shutil.rmtree(account_dir)
            return True
        return False

    def get_account_settings_file(self, account_name=None):
        """
        返回账号设置文件路径
        :param account_name: 账号名，默认为当前账号
        """
        if account_name is None:
            account_name = self.config.current_account
        return (
            self.config.user_data_dir
            / "accounts"
            / account_name
            / "account_settings.json"
        )

    def _get_default_account_settings(self):
        return deepcopy(self.DEFAULT_ACCOUNT_SETTINGS)

    def _infer_cast_mode(self, settings=None):
        preset_name = self.config.current_preset_name
        if isinstance(settings, dict):
            preset_name = settings.get("current_preset", preset_name)

        preset = self.config.presets.get(preset_name, {})
        cast_time = preset.get("cast_time", 0.1)
        return "far" if cast_time >= 1 else "tap"

    def _normalize_account_settings(self, settings):
        normalized = self._get_default_account_settings()
        if isinstance(settings, dict):
            normalized.update(settings)

        if not isinstance(normalized.get("selected_baits"), list):
            normalized["selected_baits"] = []

        if not isinstance(normalized.get("pokedex_filter_criteria"), dict):
            normalized["pokedex_filter_criteria"] = {}

        normalized["cast_mode"] = self.config.normalize_cast_mode(
            normalized.get("cast_mode", self._infer_cast_mode(normalized))
        )

        return normalized

    def get_account_settings(self, account_name=None):
        """
        获取账号设置
        :param account_name: 账号名，默认为当前账号
        :return: 账号设置字典
        """
        settings_file = self.get_account_settings_file(account_name)
        settings = {}

        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, Exception):
                settings = {}

        return self._normalize_account_settings(settings)

    def save_account_settings(self, settings, account_name=None):
        """
        保存账号设置
        :param settings: 设置字典
        :param account_name: 账号名，默认为当前账号
        """
        settings_file = self.get_account_settings_file(account_name)
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(
                self._normalize_account_settings(settings),
                f,
                indent=2,
                ensure_ascii=False,
            )

    def get_shared_global_settings(self):
        """返回应该写入全局配置文件的共享设置。"""
        return {
            key: deepcopy(value)
            for key, value in self.config.global_settings.items()
            if key not in self.ACCOUNT_SPECIFIC_GLOBAL_KEYS
        }

    def ensure_account_settings_migrated(self):
        """
        将旧版全局配置中的账号相关字段迁移到当前账号。
        """
        settings_file = self.get_account_settings_file()
        if settings_file.exists():
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except (json.JSONDecodeError, Exception):
                settings = {}
        else:
            settings = {}

        changed = False

        if "current_preset" not in settings:
            settings["current_preset"] = self.config.current_preset_name
            changed = True

        if "current_bait" not in settings:
            settings["current_bait"] = self.config.current_bait
            changed = True

        if "cast_mode" not in settings:
            settings["cast_mode"] = self._infer_cast_mode(settings)
            changed = True

        for key in self.ACCOUNT_SPECIFIC_GLOBAL_KEYS:
            if key not in settings and key in self.config.global_settings:
                settings[key] = deepcopy(self.config.global_settings.get(key))
                changed = True

        if changed:
            self.save_account_settings(settings)

    def apply_account_settings(self, account_name=None):
        """将账号私有配置加载到当前运行时配置中。"""
        settings = self.get_account_settings(account_name)

        for key in self.ACCOUNT_SPECIFIC_GLOBAL_KEYS:
            self.config.global_settings[key] = deepcopy(settings.get(key))

        preset_name = settings.get("current_preset", self.config.current_preset_name)
        if preset_name not in self.config.presets:
            preset_name = next(iter(self.config.presets), "路亚轻杆")
        self.config.current_preset_name = preset_name
        self.config.current_bait = settings.get(
            "current_bait", self.config.current_bait
        )
        self.config.apply_cast_mode(settings.get("cast_mode", "tap"))

    def persist_current_account_settings(self):
        """保存当前账号的私有配置。"""
        settings = self.get_account_settings()
        settings["current_preset"] = self.config.current_preset_name
        settings["current_bait"] = self.config.current_bait

        for key in self.ACCOUNT_SPECIFIC_GLOBAL_KEYS:
            settings[key] = deepcopy(self.config.global_settings.get(key))

        self.save_account_settings(settings)

    def get_account_server_region(self, account_name=None):
        """
        获取账号的区服设置
        :param account_name: 账号名，默认为当前账号
        :return: "CN" 或 "Global"
        """
        settings = self.get_account_settings(account_name)
        return settings.get("server_region", "CN")

    def set_account_server_region(self, region, account_name=None):
        """
        设置账号的区服
        :param region: "CN" 或 "Global"
        :param account_name: 账号名，默认为当前账号
        """
        settings = self.get_account_settings(account_name)
        settings["server_region"] = region
        self.save_account_settings(settings, account_name)

    def create_account(self, account_name, server_region="CN"):
        """
        创建新账号
        :param account_name: 新账号名
        :param server_region: 区服设置，"CN" 或 "Global"
        :return: True 如果创建成功，False 如果账号已存在
        """
        if not account_name or account_name.strip() == "":
            return False

        account_name = account_name.strip()
        account_dir = self.config.user_data_dir / "accounts" / account_name / "data"

        if account_dir.exists():
            return False

        account_dir.mkdir(parents=True, exist_ok=True)

        settings = self._get_default_account_settings()
        settings["server_region"] = server_region
        self.save_account_settings(settings, account_name)

        return True
