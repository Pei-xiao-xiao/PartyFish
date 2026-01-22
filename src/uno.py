import threading
import time
from pynput import mouse
from src.vision import vision
from src.config import cfg


class UnoManager:
    def __init__(self):
        self.current_cards = 7
        self.max_cards = 35
        self.running = False
        self.thread = None
        self.mouse_controller = mouse.Controller()

    def start(self):
        """启动 UNO 识别"""
        if not self.running:
            self.current_cards = 7
            self.running = True
            self.thread = threading.Thread(target=self._recognition_loop, daemon=True)
            self.thread.start()
            return True
        return False

    def stop(self):
        """停止 UNO 识别"""
        if self.running:
            self.running = False
            if self.thread:
                self.thread.join(timeout=1.0)
            return True
        return False

    def _recognition_loop(self):
        """持续识别循环"""
        while self.running:
            try:
                if vision.find_uno_card():
                    self.current_cards += 1
                    self._click_uno_position()

                    if self.current_cards >= self.max_cards:
                        self.running = False
                        break

                time.sleep(0.5)
            except Exception as e:
                print(f"UNO 识别错误: {e}")

    def _click_uno_position(self):
        """点击 UNO 位置（右下角，基于 2560x1440）"""
        base_x, base_y = 2381, 1353
        click_pos = cfg.get_center_anchored_pos((base_x, base_y))
        final_x = click_pos[0] + cfg.window_offset_x
        final_y = click_pos[1] + cfg.window_offset_y
        self.mouse_controller.position = (final_x, final_y)
        self.mouse_controller.click(mouse.Button.left, 1)


uno_manager = UnoManager()
