import ctypes
from pathlib import Path
import sys
import os
import shutil

from src.configs.display_config import DisplayConfig
from src.configs.game_config import GameConfig
from src.configs.region_config import RegionConfig


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Config(metaclass=SingletonMeta):
    def __init__(self):
        # 初始化配置子模块
        self._display_config = DisplayConfig()
        self._game_config = GameConfig()
        self._region_config = RegionConfig()

        # 暴露 DisplayConfig 属性（保持向后兼容）
        self.BASE_SCREEN_WIDTH = self._display_config.BASE_SCREEN_WIDTH
        self.BASE_SCREEN_HEIGHT = self._display_config.BASE_SCREEN_HEIGHT
        self.window_offset_x = self._display_config.window_offset_x
        self.window_offset_y = self._display_config.window_offset_y
        self.screen_width = self._display_config.screen_width
        self.screen_height = self._display_config.screen_height
        self.scale_x = self._display_config.scale_x
        self.scale_y = self._display_config.scale_y
        self.scale = self._display_config.scale

        # 暴露 GameConfig 属性（保持向后兼容）
        self.game_window_titles = self._game_config.game_window_titles
        self.BAIT_PRICES = self._game_config.BAIT_PRICES
        self.current_bait = self._game_config.current_bait
        self.BAIT_CROP_WIDTH1_BASE = self._game_config.BAIT_CROP_WIDTH1_BASE
        self.BTN_JIASHI_NO = self._game_config.BTN_JIASHI_NO
        self.BTN_JIASHI_YES = self._game_config.BTN_JIASHI_YES

        # 暴露 RegionConfig 属性（保持向后兼容）
        self.REGIONS = self._region_config.REGIONS

        # game_hwnd 属性（运行时设置）
        self.game_hwnd = self._game_config.game_hwnd

        # 初始化窗口服务
        from src.services.window_service import WindowService

        self.window_service = WindowService(self)

        # 初始化坐标服务
        from src.services.coordinate_service import CoordinateService

        self.coordinate_service = CoordinateService(self)

        # 计算缩放因子
        self.coordinate_service.recalculate_scale()

        # 初始化账号服务
        from src.services.account_service import AccountService

        self.account_service = AccountService(self)

        # 初始化数据加载服务
        from src.services.data_loader_service import DataLoaderService

        self.data_loader_service = DataLoaderService(self)

        # 初始化配置管理服务
        from src.services.config_manager import ConfigManager

        self.config_manager = ConfigManager(self)

        # 配置存储
        self.current_preset_name = "路亚轻杆"
        self.presets = {}
        self.global_settings = {}
        self.qfluent_settings = {}

        # 多账号支持
        self.current_account = "默认账号"

        # 鱼类名称列表
        self.fish_names_list = []
        self.protected_fish_list = []

        # 启动时的错误信息，将在 GUI 中显示
        self.startup_errors = []

        # 这将在启动时由 main.py 设置，但在此初始化以避免 AttributeError
        self._base_path = None
        self._application_path = None

        # 用户数据目录 (APPDATA/Partyfish)
        self.user_data_dir = Path(os.environ.get("APPDATA")) / "Partyfish"
        self._ensure_user_data()

        self.config_manager.load_config_from_json()

    def set_base_path(self, resources_path, application_path):
        """设置应用程序的基础路径。应在启动时调用一次。"""
        self._base_path = resources_path
        self._application_path = application_path
        # 路径设置后重新加载配置 (配置可能在用户目录，但 fish.json 依赖基础路径)
        self.config_manager.load_config_from_json()
        self._load_fish_data()
        # 重新运行迁移检查，以防基础路径对查找旧数据至关重要？
        # 通常 __init__ 通过回退找到它，但为了安全起见。
        self._ensure_user_data()

    def _ensure_user_data(self):
        """
        确保用户数据目录存在并在必要时迁移数据。
        """
        if not self.user_data_dir.exists():
            try:
                self.user_data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.startup_errors.append(f"创建用户数据目录失败: {e}")

        # 1. Config Migration
        target_config = self.user_data_dir / "config.json"
        if not target_config.exists():
            # 尝试查找本地配置以进行迁移
            local_config = self._get_application_path() / "config" / "config.json"
            if local_config.exists():
                try:
                    shutil.copy2(local_config, target_config)
                    print(f"[Config] 已迁移配置文件到: {target_config}")
                except Exception as e:
                    self.startup_errors.append(f"迁移配置文件失败: {e}")

        # 2. Data Migration - 迁移到"默认账号"目录（兼容多账号结构）
        default_account_data_dir = self.user_data_dir / "accounts" / "默认账号" / "data"

        # 确保默认账号目录存在
        if not default_account_data_dir.exists():
            try:
                default_account_data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.startup_errors.append(f"创建默认账号数据目录失败: {e}")

        # 从旧的根目录 data/ 迁移
        for filename in ["records.csv", "sales.csv"]:
            target_file = default_account_data_dir / filename
            if not target_file.exists():
                # 优先从旧的 APPDATA/Autofish/data/ 迁移（如果之前迁移过）
                old_appdata_file = self.user_data_dir / "data" / filename
                local_file = self._get_application_path() / "data" / filename

                source_file = None
                if old_appdata_file.exists():
                    source_file = old_appdata_file
                elif local_file.exists():
                    source_file = local_file

                if source_file:
                    try:
                        shutil.copy2(source_file, target_file)
                        print(f"[Config] 已迁移 {filename} 到默认账号: {target_file}")
                    except Exception as e:
                        self.startup_errors.append(f"迁移 {filename} 失败: {e}")

    @property
    def records_file(self):
        return self.account_service.get_records_file()

    @property
    def sales_file(self):
        return self.account_service.get_sales_file()

    def _get_account_data_dir(self):
        return self.account_service.get_account_data_dir()

    def get_accounts(self):
        return self.account_service.get_accounts()

    def switch_account(self, account_name):
        return self.account_service.switch_account(account_name)

    def create_account(self, account_name, server_region="CN"):
        return self.account_service.create_account(account_name, server_region)

    def delete_account(self, account_name):
        return self.account_service.delete_account(account_name)

    def get_current_account_server_region(self):
        """获取当前账号的区服设置"""
        return self.account_service.get_account_server_region()

    def set_current_account_server_region(self, region):
        """设置当前账号的区服"""
        self.account_service.set_account_server_region(region)

    def _get_base_path(self):
        """获取应用程序的基础路径。由 main.py 设置。"""
        if self._base_path is None:
            # 在未调用 set_base_path 的情况下的回退方案（例如测试）
            if getattr(sys, "frozen", False):
                return Path(sys._MEIPASS)
            else:
                return Path(__file__).parent.parent
        return self._base_path

    def _get_application_path(self):
        """获取应用程序路径（可执行文件目录）用于用户数据。"""
        if self._application_path is None:
            # 在未调用 set_base_path 的情况下的回退方案（例如测试）
            if getattr(sys, "frozen", False):
                return Path(sys.executable).parent
            else:
                return Path(__file__).parent.parent
        return self._application_path

    def _recalculate_scale(self):
        self.coordinate_service.recalculate_scale()

    def update_game_window(self):
        return self.window_service.update_game_window()

    def activate_game_window(self):
        return self.window_service.activate_game_window()

    def get_top_center_rect(self, coords):
        return self.coordinate_service.get_top_center_rect(coords)

    def get_bottom_center_rect(self, coords):
        return self.coordinate_service.get_bottom_center_rect(coords)

    def get_bottom_right_rect(self, coords):
        return self.coordinate_service.get_bottom_right_rect(coords)

    def get_center_anchored_rect(self, coords):
        return self.coordinate_service.get_center_anchored_rect(coords)

    def get_center_anchored_pos(self, coords):
        return self.coordinate_service.get_center_anchored_pos(coords)

    def get_bottom_right_pos(self, coords):
        return self.coordinate_service.get_bottom_right_pos(coords)

    def __getattr__(self, name):
        """
        动态从当前预设或全局设置获取属性。
        这确保了与使用 cfg.attribute 的代码的向后兼容性。
        """
        # 首先，尝试从当前预设的设置中获取
        current_preset = self.get_current_preset()
        if current_preset and name in current_preset:
            return current_preset[name]

        # 如果不在预设中，尝试从全局设置中获取
        if name in self.global_settings:
            return self.global_settings[name]

        # 如果仍未找到，抛出 AttributeError
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        """
        允许设置属性。
        如果属性存在于当前预设中，则在那里更新它。
        如果它存在于 global_settings 中，则在那里更新它。
        否则，将其设置为普通实例属性。
        """
        # 避免对 __init__ 中定义的实例属性进行递归
        if name in [
            "_display_config",
            "_game_config",
            "_region_config",
            "BASE_SCREEN_WIDTH",
            "BASE_SCREEN_HEIGHT",
            "screen_width",
            "screen_height",
            "scale_x",
            "scale_y",
            "scale",
            "current_preset_name",
            "presets",
            "global_settings",
            "qfluent_settings",
            "REGIONS",
            "_instances",
            "window_offset_x",
            "window_offset_y",
            "game_window_titles",
            "current_account",
            "window_service",
            "coordinate_service",
            "account_service",
            "data_loader_service",
            "config_manager",
            "fish_names_list",
            "startup_errors",
            "_base_path",
            "user_data_dir",
            "BAIT_CROP_WIDTH1_BASE",
            "BTN_JIASHI_NO",
            "BTN_JIASHI_YES",
            "BAIT_PRICES",
            "current_bait",
            "game_hwnd",
            "protected_fish_list",
        ]:
            super().__setattr__(name, value)
            return

        # 检查是否为预设设置
        current_preset = self.get_current_preset()
        if current_preset and name in current_preset:
            current_preset[name] = value
            return

        # 检查是否为全局设置
        if hasattr(self, "global_settings") and name in self.global_settings:
            self.global_settings[name] = value
            return

        # 其他属性的默认行为
        super().__setattr__(name, value)

    def _get_default_presets(self):
        return self.config_manager.get_default_presets()

    def _load_fish_data(self):
        self.data_loader_service.load_fish_data()

    def _load_protected_fish(self):
        self.data_loader_service.load_protected_fish()

    def is_fish_protected(self, fish_name, quality):
        return self.data_loader_service.is_fish_protected(fish_name, quality)

    def _load_config_from_json(self):
        self.config_manager.load_config_from_json()

    def save(self):
        self.config_manager.save()

    def get_current_preset(self):
        return self.config_manager.get_current_preset()

    def load_preset(self, name):
        self.config_manager.load_preset(name)

    def get_ui_font(self):
        """
        返回适合当前系统的UI字体名称。
        台湾/香港用户使用微软正黑体，大陆用户使用微软雅黑。
        """
        import locale

        try:
            lang = locale.getdefaultlocale()[0]
            if lang in ["zh_TW", "zh_HK"]:
                return "Microsoft JhengHei"
        except Exception:
            pass
        return "Microsoft YaHei"

    def get_rect(self, name):
        return self.coordinate_service.get_rect(name)


# Instantiate the singleton
cfg = Config()
