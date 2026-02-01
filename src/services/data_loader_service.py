"""
数据加载服务
负责加载鱼类数据和保护鱼配置
"""

import json


class DataLoaderService:
    """数据加载服务类"""

    def __init__(self, config):
        """
        初始化数据加载服务

        Args:
            config: Config 实例引用
        """
        self.config = config

    def load_fish_data(self):
        """加载鱼类数据"""
        base_path = self.config._get_base_path()
        fish_config_path = base_path / "resources" / "fish.json"

        if not fish_config_path.exists():
            self.config.startup_errors.append(
                f"⚠️ 关键配置文件缺失: resources/fish.json，鱼名匹配功能将不可用"
            )
            self.config.fish_names_list = []
            return

        try:
            with open(fish_config_path, "r", encoding="utf-8") as f:
                fish_data = json.load(f)
                self.config.fish_names_list = [
                    item["name"] for item in fish_data if "name" in item
                ]
        except Exception as e:
            self.config.startup_errors.append(f"⚠️ 加载 fish.json 失败: {e}")
            self.config.fish_names_list = []

        self.load_protected_fish()

    def load_protected_fish(self):
        """加载保护鱼配置文件"""
        base_path = self.config._get_application_path()
        protected_fish_path = base_path / "data" / "protected_fish.json"

        if not protected_fish_path.exists():
            self.config.protected_fish_list = []
            return

        try:
            with open(protected_fish_path, "r", encoding="utf-8") as f:
                self.config.protected_fish_list = json.load(f)
        except Exception as e:
            self.config.startup_errors.append(f"⚠️ 加载 protected_fish.json 失败: {e}")
            self.config.protected_fish_list = []

    def is_fish_protected(self, fish_name, quality):
        """检查鱼是否在保护列表中"""
        if not hasattr(self.config, "protected_fish_list"):
            return False

        for fish in self.config.protected_fish_list:
            if fish.get("name") == fish_name and fish.get("quality") == quality:
                return True
        return False
