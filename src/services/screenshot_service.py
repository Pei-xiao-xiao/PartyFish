"""
截图服务
负责线程安全的屏幕截图和特殊截图功能
"""

import time
import mss
import mss.tools
import cv2
import numpy as np
import threading
from pathlib import Path
from src.config import cfg


class ScreenshotService:
    """截图服务类"""

    def __init__(self):
        """初始化截图服务"""
        # 线程锁，用于保护截图操作的线程安全
        self._screenshot_lock = threading.Lock()
        # 使用 threading.local() 来存储每个线程独立的 mss 实例
        self._thread_local = threading.local()

    def screenshot(self, region=None):
        """
        线程安全的屏幕截图

        Args:
            region: 截图区域 (x, y, width, height)，None 表示截取整个游戏窗口

        Returns:
            numpy.ndarray: BGR 格式的图像
        """
        with self._screenshot_lock:
            cfg.update_game_window()

            max_retries = 5
            for attempt in range(max_retries):
                try:
                    if (
                        not hasattr(self._thread_local, "sct")
                        or self._thread_local.sct is None
                    ):
                        self._thread_local.sct = mss.mss()

                    if region is None:
                        monitor = {
                            "left": cfg.window_offset_x,
                            "top": cfg.window_offset_y,
                            "width": cfg.screen_width,
                            "height": cfg.screen_height,
                        }
                    else:
                        monitor = {
                            "left": region[0] + cfg.window_offset_x,
                            "top": region[1] + cfg.window_offset_y,
                            "width": region[2],
                            "height": region[3],
                        }

                    sct_img = self._thread_local.sct.grab(monitor)
                    img = np.array(sct_img)
                    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                except Exception as e:
                    try:
                        if (
                            hasattr(self._thread_local, "sct")
                            and self._thread_local.sct
                        ):
                            self._thread_local.sct.close()
                    except:
                        pass
                    self._thread_local.sct = None

                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    raise e

    @staticmethod
    def capture_first_catch(fish_name: str) -> tuple[bool, str]:
        """
        首次捕获截图

        Args:
            fish_name: 鱼名

        Returns:
            (成功标志, 消息或文件路径)
        """
        try:
            with mss.mss() as sct:
                monitor = {
                    "left": cfg.window_offset_x,
                    "top": cfg.window_offset_y,
                    "width": cfg.screen_width,
                    "height": cfg.screen_height,
                }
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = (
                    cfg._get_application_path()
                    / "screenshots"
                    / f"first_catch_{fish_name.replace(':', '_')}_{timestamp}.png"
                )
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(filename))
                return True, str(filename)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def capture_legendary(fish_name: str) -> tuple[bool, str]:
        """
        传奇品质截图

        Args:
            fish_name: 鱼名

        Returns:
            (成功标志, 消息或文件路径)
        """
        try:
            with mss.mss() as sct:
                monitor = {
                    "left": cfg.window_offset_x,
                    "top": cfg.window_offset_y,
                    "width": cfg.screen_width,
                    "height": cfg.screen_height,
                }
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = (
                    cfg._get_application_path()
                    / "screenshots"
                    / f"legendary_{fish_name.replace(':', '_')}_{timestamp}.png"
                )
                sct_img = sct.grab(monitor)
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(filename))
                return True, str(filename)
        except Exception as e:
            return False, str(e)
