"""
窗口管理服务
负责游戏窗口检测、激活和屏幕分辨率管理
"""

import ctypes


class WindowService:
    """窗口管理服务类"""

    def __init__(self, config):
        """
        初始化窗口服务

        Args:
            config: Config 实例引用
        """
        self.config = config
        self._setup_dpi_awareness()
        self._init_screen_resolution()

    def _setup_dpi_awareness(self):
        """设置 Per-Monitor DPI Aware V2，支持多显示器不同 DPI 缩放"""
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

    def _init_screen_resolution(self):
        """初始化屏幕分辨率"""
        try:
            user32 = ctypes.windll.user32
            self.config.screen_width = user32.GetSystemMetrics(0)
            self.config.screen_height = user32.GetSystemMetrics(1)
        except Exception:
            self.config.screen_width = self.config.BASE_SCREEN_WIDTH
            self.config.screen_height = self.config.BASE_SCREEN_HEIGHT

    def update_game_window(self):
        """
        检测游戏窗口并更新分辨率和偏移量。
        如果找到游戏窗口，使用其客户区尺寸；否则 fallback 到全屏模式。
        返回 True 表示找到窗口，False 表示使用 fallback。
        """
        try:
            user32 = ctypes.windll.user32

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
            for title in self.config.game_window_titles:
                hwnd = user32.FindWindowW(None, title)
                if hwnd:
                    break

            if not hwnd:
                print("[WindowService] 未找到游戏窗口，使用全屏模式")
                self.config.window_offset_x = 0
                self.config.window_offset_y = 0
                self.config.game_hwnd = None
                self.config.screen_width = user32.GetSystemMetrics(0)
                self.config.screen_height = user32.GetSystemMetrics(1)
                self.config._recalculate_scale()
                return False

            self.config.game_hwnd = hwnd

            client_rect = RECT()
            user32.GetClientRect(hwnd, ctypes.byref(client_rect))

            point = POINT(0, 0)
            user32.ClientToScreen(hwnd, ctypes.byref(point))

            self.config.window_offset_x = point.x
            self.config.window_offset_y = point.y
            self.config.screen_width = client_rect.right - client_rect.left
            self.config.screen_height = client_rect.bottom - client_rect.top

            self.config._recalculate_scale()
            return True

        except Exception as e:
            print(f"[WindowService] 检测游戏窗口失败: {e}，使用全屏模式")
            self.config.window_offset_x = 0
            self.config.window_offset_y = 0
            self.config.game_hwnd = None
            self.config._recalculate_scale()
            return False

    def activate_game_window(self):
        """
        激活游戏窗口，确保按键能发送到游戏。
        将鼠标移动到游戏窗口中心即可转移焦点。
        """
        try:
            if not hasattr(self.config, "game_hwnd") or not self.config.game_hwnd:
                self.update_game_window()

            if not self.config.game_hwnd:
                return False

            user32 = ctypes.windll.user32
            user32.SetForegroundWindow(self.config.game_hwnd)

            center_x = self.config.window_offset_x + self.config.screen_width // 2
            center_y = self.config.window_offset_y + self.config.screen_height // 2
            user32.SetCursorPos(center_x, center_y)

            return True
        except Exception as e:
            print(f"[WindowService] 激活游戏窗口失败: {e}")
            return False
