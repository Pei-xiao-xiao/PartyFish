import ctypes
import json
from pathlib import Path
import sys
import os
import shutil


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Config(metaclass=SingletonMeta):
    def __init__(self):
        # 设置 Per-Monitor DPI Aware V2，支持多显示器不同 DPI 缩放
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(
                2
            )  # PROCESS_PER_MONITOR_DPI_AWARE_V2
        except AttributeError:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(
                    1
                )  # Fallback to system aware
            except AttributeError:
                ctypes.windll.user32.SetProcessDPIAware()

        # Base resolution
        self.BASE_SCREEN_WIDTH = 2560
        self.BASE_SCREEN_HEIGHT = 1440

        # Get current screen resolution
        try:
            user32 = ctypes.windll.user32
            self.screen_width = user32.GetSystemMetrics(0)
            self.screen_height = user32.GetSystemMetrics(1)
        except Exception:
            self.screen_width = self.BASE_SCREEN_WIDTH
            self.screen_height = self.BASE_SCREEN_HEIGHT

        # 游戏窗口偏移（用于截图定位）
        self.window_offset_x = 0
        self.window_offset_y = 0

        # 游戏窗口标题列表（按优先级尝试，包含简体、繁体和英文）
        self.game_window_titles = ["猛兽派对", "猛獸派對", "Party Animals"]

        # Calculate scaling factors
        self._recalculate_scale()

        # Configuration storage
        self.current_preset_name = "路亚轻杆"
        self.presets = {}
        self.global_settings = {}
        self.qfluent_settings = {}

        # 多账号支持
        self.current_account = "默认账号"

        # Fish names list
        self.fish_names_list = []

        # 启动时的错误信息，将在 GUI 中显示
        self.startup_errors = []

        # This will be set by main.py at startup, but init it here to avoid AttributeError
        self._base_path = None

        # User Data Directory (APPDATA/Partyfish)
        self.user_data_dir = Path(os.environ.get("APPDATA")) / "Partyfish"
        self._ensure_user_data()

        # Predefined regions based on 2560x1440
        # 注意：检测区域需要比模板稍大，给模板匹配留出缓冲空间（约+10像素）
        self.REGIONS = {
            "cast_rod": {"coords": (1087, 1318, 35, 42), "anchor": "bottom_center"},
            "cast_rod_ice": {"coords": (1198, 1318, 35, 42), "anchor": "bottom_center"},
            "wait_bite": {"coords": (975, 1318, 35, 42), "anchor": "bottom_center"},
            "shangyu": {"coords": (1143, 1313, 25, 28), "anchor": "bottom_center"},
            "reel_in_star": {"coords": (1167, 160, 44, 44), "anchor": "top_center"},
            "bait_count": {"coords": (2316, 1294, 32, 26), "anchor": "bottom_right"},
            "jiashi_popup": {
                "coords": (1237, 669, 40, 40),
                "anchor": "center",
            },  # 保留旧配置兼容
            "afk_popup": {
                "coords": (1147, 678, 40, 40),
                "anchor": "center",
            },  # 保留旧配置兼容
            "popup_exclamation": {
                "coords": (1250, 420, 60, 110),
                "anchor": "center",
            },  # 统一弹窗检测区域（感叹号位置）
            "ocr_area": {"coords": (915, 75, 725, 150), "anchor": "top_center"},
            "sell_price_area": {
                "coords": (2030, 1045, 200, 50),
                "anchor": "bottom_right",
            },
            "uno_card": {
                "coords": (2242, 1314, 80, 40),
                "anchor": "bottom_right",
            },  # UNO 卡片检测区域
            "fish_name_tooltip": {
                "coords": (1819, 436, 235, 96),
                "anchor": "bottom_right",
            },  # 鱼名提示区域
            "fish_inventory": {
                "anchor": "bottom_right",
                "zones": [
                    {
                        "id": 1,
                        "coords": (1857, 521, 608, 603),
                        "grid": {
                            "rows": 4,
                            "cols": 4,
                            "cell_width": 152,
                            "cell_height": 151,
                            "star_offset": (58, 112),
                            "star_size": (47, 33),
                        },
                    },
                ],
                "release_button_offset": (200, 107),
                "single_release_button_offset": (80, 150),
                "single_release_fish_pos": (1933, 600),
            },
        }

        # Constants
        self.BAIT_CROP_WIDTH1_BASE = 15
        self.BTN_JIASHI_NO = (1175, 778)  # Relative to 2560x1440
        self.BTN_JIASHI_YES = (1390, 778)  # Relative to 2560x1440

        self.BAIT_PRICES = {"蔓越莓": 1, "蓝莓": 2, "橡果": 3, "蘑菇": 4, "蜂巢蜜": 5}
        self.current_bait = "蔓越莓"  # Default bait

        self._load_config_from_json()

    def set_base_path(self, path):
        """Sets the base path for the application. Should be called once at startup."""
        self._base_path = path
        # 路径设置后重新加载配置 (Config might be in user dir, but fish.json relies on base path)
        self._load_config_from_json()
        self._load_fish_data()
        # Re-run migration check in case base path was crucial for finding old data?
        # Typically __init__ found it via fallback, but let's be safe.
        self._ensure_user_data()

    def _ensure_user_data(self):
        """
        Ensures the user data directory exists and migrates data if necessary.
        """
        if not self.user_data_dir.exists():
            try:
                self.user_data_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.startup_errors.append(f"创建用户数据目录失败: {e}")

        # 1. Config Migration
        target_config = self.user_data_dir / "config.json"
        if not target_config.exists():
            # Try to find local config to migrate
            local_config = self._get_base_path() / "config" / "config.json"
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
                local_file = self._get_base_path() / "data" / filename

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
        return self._get_account_data_dir() / "records.csv"

    @property
    def sales_file(self):
        return self._get_account_data_dir() / "sales.csv"

    def _get_account_data_dir(self):
        """返回当前账号的数据目录"""
        return self.user_data_dir / "accounts" / self.current_account / "data"

    def get_accounts(self):
        """获取所有账号列表"""
        accounts_dir = self.user_data_dir / "accounts"
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
        self.current_account = account_name
        # 确保账号数据目录存在
        account_dir = self._get_account_data_dir()
        account_dir.mkdir(parents=True, exist_ok=True)
        self.save()
        return True

    def create_account(self, account_name):
        """
        创建新账号
        :param account_name: 新账号名
        :return: True 如果创建成功，False 如果账号已存在
        """
        if not account_name or account_name.strip() == "":
            return False

        account_name = account_name.strip()
        account_dir = self.user_data_dir / "accounts" / account_name / "data"

        if account_dir.exists():
            return False  # 账号已存在

        account_dir.mkdir(parents=True, exist_ok=True)
        return True

    def delete_account(self, account_name):
        """
        删除账号
        :param account_name: 要删除的账号名
        :return: True 如果删除成功
        """
        if account_name == self.current_account:
            return False  # 不能删除当前正在使用的账号

        account_dir = self.user_data_dir / "accounts" / account_name
        if account_dir.exists():
            shutil.rmtree(account_dir)
            return True
        return False

    def _get_base_path(self):
        """Gets the base path for the application. It's set by main.py."""
        if self._base_path is None:
            # Fallback for cases where set_base_path was not called (e.g., testing)
            if getattr(sys, "frozen", False):
                return Path(sys.executable).parent
            else:
                return Path(__file__).parent.parent
        return self._base_path

    def _recalculate_scale(self):
        """重新计算缩放因子，基于当前 screen_width 和 screen_height"""
        self.scale_x = self.screen_width / self.BASE_SCREEN_WIDTH
        self.scale_y = self.screen_height / self.BASE_SCREEN_HEIGHT
        # 使用 scale_y 作为主缩放因子（锚定逻辑基于高度计算偏移）
        self.scale = self.scale_y

    def update_game_window(self):
        """
        检测游戏窗口并更新分辨率和偏移量。
        如果找到游戏窗口，使用其客户区尺寸；否则 fallback 到全屏模式。
        返回 True 表示找到窗口，False 表示使用 fallback。
        """
        try:
            user32 = ctypes.windll.user32

            # 定义 Win32 结构体
            class RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class POINT(ctypes.Structure):
                _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

            hwnd = None
            # 尝试查找游戏窗口
            for title in self.game_window_titles:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    break

            if not hwnd:
                # 未找到窗口，fallback 到全屏
                print("[Config] 未找到游戏窗口，使用全屏模式")
                self.window_offset_x = 0
                self.window_offset_y = 0
                self.game_hwnd = None
                self.screen_width = user32.GetSystemMetrics(0)
                self.screen_height = user32.GetSystemMetrics(1)
                self._recalculate_scale()
                return False

            # 保存窗口句柄
            self.game_hwnd = hwnd

            # 获取客户区尺寸
            client_rect = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))

            # 获取客户区左上角的屏幕坐标
            point = POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(point))

            # 更新分辨率和偏移量
            self.window_offset_x = point.x
            self.window_offset_y = point.y
            self.screen_width = client_rect.right - client_rect.left
            self.screen_height = client_rect.bottom - client_rect.top

            self._recalculate_scale()
            return True

        except Exception as e:
            print(f"[Config] 检测游戏窗口失败: {e}，使用全屏模式")
            self.window_offset_x = 0
            self.window_offset_y = 0
            self.game_hwnd = None
            self._recalculate_scale()
            return False

    def activate_game_window(self):
        """
        激活游戏窗口，确保按键能发送到游戏。
        将鼠标移动到游戏窗口中心即可转移焦点。
        """
        try:
            if not hasattr(self, "game_hwnd") or not self.game_hwnd:
                # 尝试重新查找窗口
                self.update_game_window()

            if not self.game_hwnd:
                return False

            user32 = ctypes.windll.user32

            # 将游戏窗口设为前台
            user32.SetForegroundWindow(self.game_hwnd)

            # 将鼠标移动到游戏窗口中心（焦点会自动转移，无需点击）
            center_x = self.window_offset_x + self.screen_width // 2
            center_y = self.window_offset_y + self.screen_height // 2
            user32.SetCursorPos(center_x, center_y)

            return True
        except Exception as e:
            print(f"[Config] 激活游戏窗口失败: {e}")
            return False

    def get_top_center_rect(self, coords):
        """
        Calculates coordinates for a top-center anchored region.
        Scales based on height (self.scale) to maintain aspect ratio.
        """
        base_x, base_y, base_w, base_h = coords

        # Calculate center offset from base resolution center
        base_center_x = base_x + (base_w / 2)
        offset_from_center_x = base_center_x - (self.BASE_SCREEN_WIDTH / 2)

        # Calculate new dimensions
        new_w = int(base_w * self.scale)
        new_h = int(base_h * self.scale)

        # Calculate new center position
        new_center_x = (self.screen_width / 2) + (offset_from_center_x * self.scale)

        # Calculate new top-left position
        new_x = int(new_center_x - (new_w / 2))
        new_y = int(base_y * self.scale)

        return (new_x, new_y, new_w, new_h)

    def get_bottom_center_rect(self, coords):
        """
        Calculates coordinates for a bottom-center anchored region.
        """
        base_x, base_y, base_w, base_h = coords

        # Calculate center offset from base resolution center
        base_center_x = base_x + (base_w / 2)
        offset_from_center_x = base_center_x - (self.BASE_SCREEN_WIDTH / 2)

        # Calculate offset from bottom
        offset_from_bottom = self.BASE_SCREEN_HEIGHT - base_y

        # Calculate new dimensions
        new_w = int(base_w * self.scale)
        new_h = int(base_h * self.scale)

        # Calculate new center position X
        new_center_x = (self.screen_width / 2) + (offset_from_center_x * self.scale)

        # Calculate new Y (from bottom)
        new_y = int(self.screen_height - (offset_from_bottom * self.scale))

        # Calculate new top-left X
        new_x = int(new_center_x - (new_w / 2))

        return (new_x, new_y, new_w, new_h)

    def get_bottom_right_rect(self, coords):
        """
        Calculates coordinates for a bottom-right anchored region.
        """
        base_x, base_y, base_w, base_h = coords

        # Calculate offsets from bottom-right corner
        offset_from_right = self.BASE_SCREEN_WIDTH - base_x
        offset_from_bottom = self.BASE_SCREEN_HEIGHT - base_y

        # Calculate new dimensions
        new_w = int(base_w * self.scale)
        new_h = int(base_h * self.scale)

        # Calculate new top-left position
        new_x = int(self.screen_width - (offset_from_right * self.scale))
        new_y = int(self.screen_height - (offset_from_bottom * self.scale))

        return (new_x, new_y, new_w, new_h)

    def get_center_anchored_rect(self, coords):
        """
        Calculates coordinates for a center-center anchored region.
        弹窗 UI 保持宽高比，所以偏移缩放使用 min(scale_x, scale_y)。
        """
        base_x, base_y, base_w, base_h = coords

        base_center_x = base_x + (base_w / 2)
        base_center_y = base_y + (base_h / 2)

        offset_from_center_x = base_center_x - (self.BASE_SCREEN_WIDTH / 2)
        offset_from_center_y = base_center_y - (self.BASE_SCREEN_HEIGHT / 2)

        # 弹窗保持宽高比，使用较小的缩放因子
        popup_scale = min(self.scale_x, self.scale_y)

        new_w = int(base_w * popup_scale)
        new_h = int(base_h * popup_scale)

        new_center_x = (self.screen_width / 2) + (offset_from_center_x * popup_scale)
        new_center_y = (self.screen_height / 2) + (offset_from_center_y * popup_scale)

        new_x = int(new_center_x - (new_w / 2))
        new_y = int(new_center_y - (new_h / 2))

        return (new_x, new_y, new_w, new_h)

    def get_center_anchored_pos(self, coords):
        """
        Calculates coordinates for a center-center anchored point (x, y).
        弹窗 UI 保持宽高比，所以偏移缩放使用 min(scale_x, scale_y)。
        """
        base_x, base_y = coords

        offset_from_center_x = base_x - (self.BASE_SCREEN_WIDTH / 2)
        offset_from_center_y = base_y - (self.BASE_SCREEN_HEIGHT / 2)

        # 弹窗保持宽高比，使用较小的缩放因子
        popup_scale = min(self.scale_x, self.scale_y)

        new_x = int((self.screen_width / 2) + (offset_from_center_x * popup_scale))
        new_y = int((self.screen_height / 2) + (offset_from_center_y * popup_scale))

        return (new_x, new_y)

    def __getattr__(self, name):
        """
        Dynamically get attributes from the current preset or global settings.
        This ensures backward compatibility with code that uses cfg.attribute.
        """
        # First, try to get from the current preset's settings
        current_preset = self.get_current_preset()
        if current_preset and name in current_preset:
            return current_preset[name]

        # If not in preset, try to get from global settings
        if name in self.global_settings:
            return self.global_settings[name]

        # If still not found, raise an AttributeError
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        """
        Allows setting attributes.
        If the attribute exists in the current preset, update it there.
        If it exists in global_settings, update it there.
        Otherwise, set it as a normal instance attribute.
        """
        # Avoid recursion for instance attributes defined in __init__
        if name in [
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
        ]:
            super().__setattr__(name, value)
            return

        # Check if it's a preset setting
        current_preset = self.get_current_preset()
        if current_preset and name in current_preset:
            current_preset[name] = value
            return

        # Check if it's a global setting
        if hasattr(self, "global_settings") and name in self.global_settings:
            self.global_settings[name] = value
            return

        # Default behavior for other attributes
        super().__setattr__(name, value)

    def _get_default_presets(self):
        """Returns a dictionary of default presets."""
        return {
            "路亚轻杆": {
                "cast_time": 1.8,
                "reel_in_time": 2.0,
                "release_time": 1.0,
                "max_pulls": 30,
                "cycle_interval": 0.2,
            },
            "路亚重杆": {
                "cast_time": 2.5,
                "reel_in_time": 2.0,
                "release_time": 1.0,
                "max_pulls": 30,
                "cycle_interval": 0.2,
            },
            "冰钓轻杆": {
                "cast_time": 0.1,
                "reel_in_time": 0.2,
                "release_time": 0.1,
                "max_pulls": 100,
                "cycle_interval": 0.1,
            },
            "冰钓重杆": {
                "cast_time": 0.1,
                "reel_in_time": 0.4,
                "release_time": 0.2,
                "max_pulls": 100,
                "cycle_interval": 0.1,
            },
        }

    def _load_fish_data(self):
        base_path = self._get_base_path()
        # fish.json is now in resources
        fish_config_path = base_path / "resources" / "fish.json"
        if not fish_config_path.exists():
            self.startup_errors.append(
                f"⚠️ 关键配置文件缺失: resources/fish.json，鱼名匹配功能将不可用"
            )
            self.fish_names_list = []
            return

        try:
            with open(fish_config_path, "r", encoding="utf-8") as f:
                fish_data = json.load(f)
                # 提取所有鱼名
                self.fish_names_list = [
                    item["name"] for item in fish_data if "name" in item
                ]
        except Exception as e:
            self.startup_errors.append(f"⚠️ 加载 fish.json 失败: {e}")
            self.fish_names_list = []

        # 加载保护鱼配置
        self._load_protected_fish()

    def _load_protected_fish(self):
        """加载保护鱼配置文件"""
        base_path = self._get_base_path()
        protected_fish_path = base_path / "resources" / "protected_fish.json"

        if not protected_fish_path.exists():
            self.protected_fish_list = []
            return

        try:
            with open(protected_fish_path, "r", encoding="utf-8") as f:
                self.protected_fish_list = json.load(f)
        except Exception as e:
            self.startup_errors.append(f"⚠️ 加载 protected_fish.json 失败: {e}")
            self.protected_fish_list = []

    def is_fish_protected(self, fish_name, quality):
        """检查鱼是否在保护列表中"""
        if not hasattr(self, "protected_fish_list"):
            return False

        for fish in self.protected_fish_list:
            if fish.get("name") == fish_name and fish.get("quality") == quality:
                return True
        return False

    def _load_config_from_json(self):
        # Load from user data directory
        config_path = self.user_data_dir / "config.json"
        if not config_path.exists():
            # If config file doesn't exist, create it with default values
            self.presets = self._get_default_presets()
            self.global_settings = {
                "hotkey": "F2",
                "debug_hotkey": "F10",
                "sell_hotkey": "F4",
                "auto_click_sell": True,  # New setting
                "enable_jiashi": True,
                "jitter_range": 0,
                "theme": "Light",
                "enable_anti_afk": True,
                "enable_sound_alert": False,
                "enable_fish_recognition": True,  # 鱼类识别开关
                "server_region": "CN",
                "overlay_visible": False,
                "overlay_position": None,  # [x, y] 或 None
                "welcome_dialog_shown": False,  # 欢迎窗口是否已显示
                "hardware_info": {},  # 保存的硬件信息
                "uno_hotkey": "F3",  # UNO 功能热键
                "uno_current_cards": 7,  # UNO 当前牌数
                "uno_max_cards": 35,  # UNO 最大牌数
            }
            self.qfluent_settings = {"ThemeMode": "Light"}
            self.save()
            return

        with open(config_path, "r", encoding="utf-8") as f:
            try:
                config_data = json.load(f)
            except json.JSONDecodeError:
                # Handle corrupted JSON file
                self.presets = self._get_default_presets()
                self.global_settings = {
                    "hotkey": "F2",
                    "debug_hotkey": "F10",
                    "sell_hotkey": "F4",
                    "auto_click_sell": True,
                    "enable_jiashi": True,
                    "jitter_range": 0,
                    "theme": "Light",
                    "enable_anti_afk": True,
                    "enable_sound_alert": False,
                    "server_region": "CN",
                }
                self.qfluent_settings = {"ThemeMode": "Light"}
                self.save()
                return

        self.current_preset_name = config_data.get("current_preset", "路亚轻杆")
        self.presets = config_data.get("presets", self._get_default_presets())

        # Load global settings with defaults for missing keys
        default_global_settings = {
            "hotkey": "F2",
            "debug_hotkey": "F10",
            "sell_hotkey": "F4",
            "auto_click_sell": True,
            "enable_jiashi": True,
            "jitter_range": 0,
            "theme": "Light",
            "enable_anti_afk": True,
            "enable_sound_alert": False,
            "enable_record": True,  # 钓鱼记录开关
            "server_region": "CN",
            "overlay_visible": False,
            "overlay_position": None,
            "fish_filter_mode": "all",  # all, lure, ice
            "welcome_dialog_shown": False,  # 欢迎窗口是否已显示
            "hardware_info": {},  # 保存的硬件信息
            "uno_hotkey": "F3",  # UNO 功能热键
            "uno_current_cards": 7,  # UNO 当前牌数
            "uno_max_cards": 35,  # UNO 最大牌数
            "auto_release_enabled": False,
            "enable_fish_name_protection": False,
            "release_standard": True,
            "release_uncommon": False,
            "release_rare": False,
            "release_epic": False,
            "release_legendary": False,
            "single_release_standard": False,
            "single_release_uncommon": False,
            "single_release_rare": False,
            "single_release_epic": False,
            "single_release_legendary": False,
        }
        loaded_global_settings = config_data.get("global_settings", {})
        default_global_settings.update(loaded_global_settings)
        self.global_settings = default_global_settings

        # Load current bait if saved, otherwise default
        self.current_bait = config_data.get("current_bait", "蔓越莓")

        # 加载当前账号
        self.current_account = config_data.get("current_account", "默认账号")
        # 确保账号数据目录存在
        self._get_account_data_dir().mkdir(parents=True, exist_ok=True)

        self.qfluent_settings = config_data.get(
            "QFluentWidgets", {"ThemeMode": "Light"}
        )

    def save(self):
        """
        Saves the entire configuration structure to config.json in user data directory.
        """
        config_path = self.user_data_dir / "config.json"

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = {}

        config_data = {
            "current_preset": self.current_preset_name,
            "current_bait": self.current_bait,
            "current_account": self.current_account,
            "presets": self.presets,
            "global_settings": self.global_settings,
            "QFluentWidgets": self.qfluent_settings,
        }

        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)

    def get_current_preset(self):
        """Returns the dictionary for the currently active preset."""
        return self.presets.get(self.current_preset_name)

    def load_preset(self, name):
        """Switches the current preset by name."""
        if name in self.presets:
            self.current_preset_name = name
        else:
            raise ValueError(f"Preset '{name}' not found.")

    def get_rect(self, name):
        """
        Calculates the scaled rectangle for a predefined region using an anchor-based dispatcher.
        """
        if name not in self.REGIONS:
            raise KeyError(f"Region '{name}' not defined in Config.")

        region_info = self.REGIONS[name]
        coords = region_info["coords"]
        anchor_type = region_info.get("anchor", "default")  # Default to simple scaling

        # Dispatcher to select the correct anchor calculation method
        dispatcher = {
            "top_center": self.get_top_center_rect,
            "bottom_center": self.get_bottom_center_rect,
            "bottom_right": self.get_bottom_right_rect,
            "center": self.get_center_anchored_rect,
        }

        calculation_method = dispatcher.get(anchor_type)

        if calculation_method:
            return calculation_method(coords)
        else:  # "default" or any other undefined anchor
            x, y, w, h = coords
            scaled_x = int(x * self.scale_x)
            scaled_y = int(y * self.scale_y)
            scaled_w = int(w * self.scale_x)
            scaled_h = int(h * self.scale_y)
            return (scaled_x, scaled_y, scaled_w, scaled_h)


# Instantiate the singleton
cfg = Config()
