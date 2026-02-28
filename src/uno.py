"""
UNO 识别管理器模块

负责自动检测游戏中的 UNO 卡牌并自动点击
支持牌数统计、倒计时显示和日志记录
"""
import threading
import time
from pynput import mouse
from PySide6.QtCore import QObject, Signal
from src.vision import vision
from src.config import cfg


class UnoManager(QObject):
    """UNO 识别管理器 - 自动检测并点击 UNO 卡牌"""

    # 信号定义
    cards_updated = Signal(int, int)  # 当前牌数, 最大牌数
    log_message = Signal(str)  # 日志消息
    status_changed = Signal(str)  # 状态变化
    countdown_updated = Signal(int)  # 倒计时更新（秒数）

    def __init__(self):
        super().__init__()
        self.current_cards = 7
        self.max_cards = cfg.global_settings.get("uno_max_cards", 35)
        self.running = False
        self.thread = None
        self.mouse_controller = mouse.Controller()
        self.last_click_pos = None
        self.waited_after_max = False  # 是否已在最大牌数后等待过

    def start(self):
        """启动 UNO 识别"""
        if not self.running:
            self.current_cards = 7
            self.last_click_pos = None
            self.waited_after_max = False
            self.running = True
            self.thread = threading.Thread(target=self._recognition_loop, daemon=True)
            self.thread.start()
            self.status_changed.emit("运行中")
            self.log_message.emit("UNO识别已启动")
            return True
        return False

    def stop(self):
        """停止 UNO 识别"""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1.0)
            self.status_changed.emit("已停止")
            self.log_message.emit("UNO识别已停止")
            return True
        return False

    def _recognition_loop(self):
        """持续识别循环"""
        while self.running:
            try:
                if vision.find_uno_card():
                    # 判断是否达到最大牌数且未等待过
                    if self.current_cards == self.max_cards and not self.waited_after_max:
                        self.log_message.emit(f"UNO 识别：已经达到最大牌数 {self.max_cards}，等待 5 秒后点击")
                        # 等待 5 秒，每秒更新倒计时
                        for i in range(5, 0, -1):
                            if not self.running:
                                return
                            self.countdown_updated.emit(i)
                            time.sleep(1)
                        self.countdown_updated.emit(0)  # 倒计时结束
                        # 使用上次位置点击
                        if self.last_click_pos:
                            self._click_at_position(self.last_click_pos)
                            self.log_message.emit(f"UNO 识别：使用上次位置点击 ({self.last_click_pos[0]}, {self.last_click_pos[1]})")
                        self.waited_after_max = True
                    else:
                        # 正常点击并保存位置
                        click_pos = self._click_uno_position()
                        if click_pos:
                            self.last_click_pos = click_pos

                    self.current_cards += 1

                    # 发射信号更新 UI
                    self.cards_updated.emit(self.current_cards, self.max_cards)
                    self.log_message.emit(f"UNO 识别：检测到卡牌，当前 {self.current_cards}/{self.max_cards}")

                time.sleep(0.5)
            except KeyboardInterrupt:
                # 用户中断，优雅退出
                self.log_message.emit("UNO 识别：收到用户中断信号")
                break
            except Exception as e:
                error_msg = f"UNO 识别错误：{type(e).__name__}: {e}"
                print(f"[UnoManager] {error_msg}")
                self.log_message.emit(error_msg)

    def _click_uno_position(self):
        """点击 UNO 位置（右下角，基于 2560x1440），返回点击位置"""
        base_x, base_y = 2381, 1353
        click_pos = cfg.get_bottom_right_pos((base_x, base_y))
        final_x = click_pos[0] + cfg.window_offset_x
        final_y = click_pos[1] + cfg.window_offset_y
        self.mouse_controller.position = (final_x, final_y)
        self.mouse_controller.click(mouse.Button.left, 1)
        return (final_x, final_y)

    def _click_at_position(self, pos):
        """在指定位置点击"""
        self.mouse_controller.position = pos
        self.mouse_controller.click(mouse.Button.left, 1)


# 全局单例
uno_manager = UnoManager()
