import ctypes
import time
import random
from pynput import keyboard, mouse
from PySide6.QtCore import QObject, Signal, QTimer
from src.config import cfg

# 鼠标事件常量
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


class InputController(QObject):
    toggle_script_signal = Signal()
    debug_screenshot_signal = Signal()
    sell_hotkey_signal = Signal()
    uno_hotkey_signal = Signal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.keyboard_listener = None
        self._hotkey_handler = None
        self._debug_hotkey_handler = None
        self._sell_hotkey_handler = None
        self._uno_hotkey_handler = None
        self.is_mouse_down = False

        self._main_hotkey_str = cfg.hotkey
        self._debug_hotkey_str = cfg.global_settings.get("debug_hotkey", "F10")
        self._sell_hotkey_str = cfg.global_settings.get("sell_hotkey", "F4")
        self._uno_hotkey_str = cfg.global_settings.get("uno_hotkey", "F3")

        self._update_hotkey_handler()
        self._update_debug_hotkey_handler()
        self._update_sell_hotkey_handler()
        self._update_uno_hotkey_handler()

        self._gamepad_controller = None
        self._gamepad_hold_timers = {}
        self._active_gamepad_buttons = set()
        self._init_gamepad()

    def _parse_hotkey_string(self, hotkey_string):
        """辅助函数，将热键字符串解析为 pynput 格式。"""
        raw = hotkey_string.lower()
        parts = raw.split("+")
        formatted_parts = []

        special_keys = {
            "ctrl",
            "alt",
            "shift",
            "win",
            "cmd",
            "f1",
            "f2",
            "f3",
            "f4",
            "f5",
            "f6",
            "f7",
            "f8",
            "f9",
            "f10",
            "f11",
            "f12",
            "space",
            "tab",
            "enter",
            "esc",
            "backspace",
            "delete",
            "insert",
            "home",
            "end",
            "pgup",
            "pgdn",
            "up",
            "down",
            "left",
            "right",
        }

        # 鼠标侧键映射
        mouse_buttons = {
            "mouse1": "Button.left",
            "mouse2": "Button.right",
            "mouse3": "Button.middle",
            "mouse4": "Button.x1",  # 侧键1
            "mouse5": "Button.x2",  # 侧键2
            "x1": "Button.x1",  # 侧键1 (简化写法)
            "x2": "Button.x2",  # 侧键2 (简化写法)
            "侧键1": "Button.x1",
            "侧键2": "Button.x2",
        }

        for p in parts:
            p = p.strip()
            if p in special_keys:
                formatted_parts.append(f"<{p}>")
            elif p in mouse_buttons:
                formatted_parts.append(mouse_buttons[p])
            else:
                formatted_parts.append(p)

        return "+".join(formatted_parts)

    def _update_hotkey_handler(self):
        """
        从配置解析主热键并创建 pynput HotKey 处理器。
        """
        self._main_hotkey_str = cfg.hotkey

        # 鼠标按钮跳过 keyboard.HotKey
        if self._main_hotkey_str in ["Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5"]:
            self._hotkey_handler = None
            return

        try:
            formatted_hotkey = self._parse_hotkey_string(cfg.hotkey)
            self._hotkey_handler = keyboard.HotKey(
                keyboard.HotKey.parse(formatted_hotkey), self.toggle_script_signal.emit
            )
        except Exception as e:
            print(f"Error parsing hotkey '{cfg.hotkey}': {e}")
            self._hotkey_handler = None

    def _update_debug_hotkey_handler(self):
        """
        从配置解析调试热键并创建 pynput HotKey 处理器。
        """
        self._debug_hotkey_str = cfg.global_settings.get("debug_hotkey", "F10")

        # 鼠标按钮跳过 keyboard.HotKey
        if self._debug_hotkey_str in ["Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5"]:
            self._debug_hotkey_handler = None
            return

        try:
            formatted_hotkey = self._parse_hotkey_string(self._debug_hotkey_str)
            self._debug_hotkey_handler = keyboard.HotKey(
                keyboard.HotKey.parse(formatted_hotkey),
                self.debug_screenshot_signal.emit,
            )
        except Exception as e:
            print(f"Error parsing debug hotkey '{self._debug_hotkey_str}': {e}")
            self._debug_hotkey_handler = None

    def _update_sell_hotkey_handler(self):
        """
        从配置解析卖鱼热键并创建 pynput HotKey 处理器。
        """
        self._sell_hotkey_str = cfg.global_settings.get("sell_hotkey", "F4")

        # 鼠标按钮跳过 keyboard.HotKey
        if self._sell_hotkey_str in ["Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5"]:
            self._sell_hotkey_handler = None
            return

        try:
            formatted_hotkey = self._parse_hotkey_string(self._sell_hotkey_str)
            self._sell_hotkey_handler = keyboard.HotKey(
                keyboard.HotKey.parse(formatted_hotkey), self.sell_hotkey_signal.emit
            )
        except Exception as e:
            print(f"Error parsing sell hotkey '{self._sell_hotkey_str}': {e}")
            self._sell_hotkey_handler = None

    def _update_uno_hotkey_handler(self):
        """
        从配置解析 UNO 热键并创建 pynput HotKey 处理器。
        """
        self._uno_hotkey_str = cfg.global_settings.get("uno_hotkey", "F3")

        if self._uno_hotkey_str in ["Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5"]:
            self._uno_hotkey_handler = None
            return

        try:
            formatted_hotkey = self._parse_hotkey_string(self._uno_hotkey_str)
            self._uno_hotkey_handler = keyboard.HotKey(
                keyboard.HotKey.parse(formatted_hotkey), self.uno_hotkey_signal.emit
            )
        except Exception as e:
            print(f"Error parsing uno hotkey '{self._uno_hotkey_str}': {e}")
            self._uno_hotkey_handler = None

    def _init_gamepad(self):
        """
        如果启用，初始化手柄控制器。
        """
        if not cfg.global_settings.get("enable_gamepad", False):
            return

        try:
            from src.gamepad_controller import gamepad_controller

            self._gamepad_controller = gamepad_controller
            try:
                self._gamepad_controller.gamepad_button_state_changed.disconnect(
                    self._on_gamepad_button_state_changed
                )
            except Exception:
                pass
            self._gamepad_controller.gamepad_button_state_changed.connect(
                self._on_gamepad_button_state_changed
            )
            if self.running:
                self._gamepad_controller.start_listening()
        except Exception as e:
            print(f"Failed to initialize gamepad controller: {e}")
            self._gamepad_controller = None
        except ImportError as e:
            print(f"Gamepad controller module not found: {e}")
            self._gamepad_controller = None

    def _reinit_gamepad(self):
        """
        重新初始化手柄控制器（当手柄设置更改时调用）。
        """
        if self._gamepad_controller:
            self._gamepad_controller.stop_listening()
            try:
                self._gamepad_controller.gamepad_button_state_changed.disconnect(
                    self._on_gamepad_button_state_changed
                )
            except Exception:
                pass
            self._gamepad_controller = None

        self._clear_gamepad_hold_state()
        self._init_gamepad()

    def _on_gamepad_button(self, button_name):
        """
        处理手柄按钮按下事件。
        """
        mappings = cfg.normalize_gamepad_mappings(
            cfg.global_settings.get("gamepad_mappings", {})
        )

        for action_name, mapping in mappings.items():
            if mapping.get("button") == button_name and mapping.get("mode") == "press":
                self._emit_gamepad_action(action_name)

    def _emit_gamepad_action(self, action_name):
        if action_name == "toggle":
            self.toggle_script_signal.emit()
        elif action_name == "debug":
            self.debug_screenshot_signal.emit()
        elif action_name == "sell":
            self.sell_hotkey_signal.emit()
        elif action_name == "uno":
            self.uno_hotkey_signal.emit()

    def _cancel_gamepad_hold(self, action_name):
        timer = self._gamepad_hold_timers.pop(action_name, None)
        if timer:
            timer.stop()
            timer.deleteLater()

    def _clear_gamepad_hold_state(self):
        for action_name in list(self._gamepad_hold_timers):
            self._cancel_gamepad_hold(action_name)
        self._active_gamepad_buttons.clear()

    def _on_gamepad_hold_timeout(self, action_name, button_name):
        mapping = cfg.get_gamepad_mapping(action_name)
        if (
            mapping.get("mode") == "hold"
            and mapping.get("button") == button_name
            and button_name in self._active_gamepad_buttons
        ):
            self._emit_gamepad_action(action_name)
        self._cancel_gamepad_hold(action_name)

    def _start_gamepad_hold(self, action_name, button_name, hold_ms):
        self._cancel_gamepad_hold(action_name)
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(
            lambda action=action_name, button=button_name: self._on_gamepad_hold_timeout(
                action, button
            )
        )
        self._gamepad_hold_timers[action_name] = timer
        timer.start(cfg.normalize_gamepad_hold_ms(hold_ms))

    def _on_gamepad_button_state_changed(self, button_name, pressed):
        """Handle gamepad button state changes for press/hold mappings."""
        if pressed:
            self._active_gamepad_buttons.add(button_name)
        else:
            self._active_gamepad_buttons.discard(button_name)

        mappings = cfg.normalize_gamepad_mappings(
            cfg.global_settings.get("gamepad_mappings", {})
        )
        cfg.global_settings["gamepad_mappings"] = mappings

        for action_name, mapping in mappings.items():
            if mapping.get("button") != button_name:
                continue

            if mapping.get("mode") == "hold":
                if pressed:
                    self._start_gamepad_hold(
                        action_name,
                        button_name,
                        mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
                    )
                else:
                    self._cancel_gamepad_hold(action_name)
            elif pressed:
                self._emit_gamepad_action(action_name)

    def add_jitter(self, base_time):
        jitter_range = cfg.jitter_range
        if jitter_range <= 0:
            return base_time

        multiplier = random.uniform(1 - jitter_range / 100, 1 + jitter_range / 100)
        jittered_time = round(base_time * multiplier, 3)

        return max(0.01, jittered_time)

    @staticmethod
    def press_key(key_name):
        """
        使用虚拟键码模拟按下和释放按键。
        """
        key_name = key_name.upper()
        # 常用虚拟键码和扫描码
        vk_map = {
            "F1": (0x70, 0x3B),
            "F2": (0x71, 0x3C),
            "F3": (0x72, 0x3D),
            "F4": (0x73, 0x3E),
            "F12": (0x7B, 0x58),
            "E": (0x45, 0x12),
            "R": (0x52, 0x13),
            "SPACE": (0x20, 0x39),
            "ESC": (0x1B, 0x01),
        }
        key_info = vk_map.get(key_name)
        if key_info:
            vk, scan = key_info
            ctypes.windll.user32.keybd_event(vk, scan, 0, 0)  # 按下
            time.sleep(random.uniform(0.05, 0.1))
            ctypes.windll.user32.keybd_event(vk, scan, 2, 0)  # 释放
        else:
            print(f"Unknown key for simulation: {key_name}")

    @staticmethod
    def jitter_click(x, y):
        """
        模拟更像人类的鼠标点击，带有随机延迟。
        """
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(random.uniform(0.05, 0.12))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def click(self, x, y):
        """
        在给定坐标模拟鼠标左键点击。
        """
        self.jitter_click(x, y)

    @staticmethod
    def double_click(x, y):
        """
        在给定坐标模拟双击。
        """
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(random.uniform(0.05, 0.08))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(random.uniform(0.05, 0.08))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(random.uniform(0.05, 0.08))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def press_mouse_button(self):
        """模拟按下鼠标左键但不释放。"""
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.is_mouse_down = True

    def release_mouse_button(self):
        """模拟释放鼠标左键。"""
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_mouse_down = False

    def hold_mouse(self, duration):
        """
        模拟按住鼠标左键指定时长。
        """
        actual_duration = self.add_jitter(duration)
        self.press_mouse_button()
        time.sleep(actual_duration)
        self.release_mouse_button()

    def left_click(self):
        """
        模拟鼠标左键点击。
        """
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.is_mouse_down = True
        time.sleep(0.1)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_mouse_down = False

    def ensure_mouse_up(self):
        """
        确保鼠标左键已释放（如果当前按下）。
        """
        if self.is_mouse_down:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_mouse_down = False

    def _on_press(self, key):
        """
        键盘按下事件回调。
        """
        if self._hotkey_handler:
            try:
                self._hotkey_handler.press(self.keyboard_listener.canonical(key))
            except Exception:
                pass

        if self._debug_hotkey_handler:
            try:
                self._debug_hotkey_handler.press(self.keyboard_listener.canonical(key))
            except Exception:
                pass

        if self._sell_hotkey_handler:
            try:
                self._sell_hotkey_handler.press(self.keyboard_listener.canonical(key))
            except Exception:
                pass

        if self._uno_hotkey_handler:
            try:
                self._uno_hotkey_handler.press(self.keyboard_listener.canonical(key))
            except Exception:
                pass

    def _on_release(self, key):
        """
        键盘释放事件回调。
        """
        if self._hotkey_handler:
            try:
                self._hotkey_handler.release(self.keyboard_listener.canonical(key))
            except Exception:
                pass

        if self._debug_hotkey_handler:
            try:
                self._debug_hotkey_handler.release(
                    self.keyboard_listener.canonical(key)
                )
            except Exception:
                pass

        if self._sell_hotkey_handler:
            try:
                self._sell_hotkey_handler.release(self.keyboard_listener.canonical(key))
            except Exception:
                pass

        if self._uno_hotkey_handler:
            try:
                self._uno_hotkey_handler.release(self.keyboard_listener.canonical(key))
            except Exception:
                pass

    def start_listening(self):
        """
        启动键盘监听器。
        """
        if self.running:
            return

        self._update_hotkey_handler()
        self._update_debug_hotkey_handler()
        self._update_sell_hotkey_handler()
        self._update_uno_hotkey_handler()
        self._init_gamepad()
        self.running = True
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self.keyboard_listener.start()

        self.mouse_listener = mouse.Listener(on_click=self._on_mouse_click)
        self.mouse_listener.start()

        if self._gamepad_controller:
            self._gamepad_controller.start_listening()

    def stop_listening(self):
        """
        停止键盘和鼠标监听器。
        """
        if not self.running:
            return

        self.running = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        if hasattr(self, "mouse_listener") and self.mouse_listener:
            self.mouse_listener.stop()
            self.mouse_listener = None
        if self._gamepad_controller:
            self._gamepad_controller.stop_listening()
        self._clear_gamepad_hold_state()

    @staticmethod
    def hold_key(key_name):
        """按住按键"""
        key_name = key_name.upper()
        vk_map = {"C": 0x43, "ESC": 0x1B}
        vk = vk_map.get(key_name)
        if vk:
            ctypes.windll.user32.keybd_event(vk, 0, 0, 0)

    def _on_mouse_click(self, x, y, button, pressed):
        """
        鼠标点击事件处理，支持侧键热键
        """
        if not pressed:
            return

        button_str = ""
        if button == mouse.Button.left:
            button_str = "Mouse1"
        elif button == mouse.Button.right:
            button_str = "Mouse2"
        elif button == mouse.Button.middle:
            button_str = "Mouse3"
        elif button == mouse.Button.x1:
            button_str = "Mouse4"
        elif button == mouse.Button.x2:
            button_str = "Mouse5"

        if not button_str:
            return

        if button_str == self._main_hotkey_str:
            self.toggle_script_signal.emit()
        elif button_str == self._debug_hotkey_str:
            self.debug_screenshot_signal.emit()
        elif button_str == self._sell_hotkey_str:
            self.sell_hotkey_signal.emit()
        elif button_str == self._uno_hotkey_str:
            self.uno_hotkey_signal.emit()

    @staticmethod
    def release_key(key_name):
        """释放按键"""
        key_name = key_name.upper()
        vk_map = {"C": 0x43, "ESC": 0x1B}
        vk = vk_map.get(key_name)
        if vk:
            ctypes.windll.user32.keybd_event(vk, 0, 2, 0)

    @staticmethod
    def scroll_wheel(clicks):
        """滚动鼠标滚轮"""
        for _ in range(abs(clicks)):
            delta = WHEEL_DELTA if clicks > 0 else -WHEEL_DELTA
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            time.sleep(0.1)

    @staticmethod
    def switch_bait(scroll_count):
        """
        切换鱼饵：按住B键，滚动鼠标滚轮，然后松开B键

        Args:
            scroll_count: 滚动次数，正数向上滚动，负数向下滚动
        """
        VK_B = 0x42
        # 按住B键
        ctypes.windll.user32.keybd_event(VK_B, 0, 0, 0)
        time.sleep(0.8)

        # 滚动鼠标滚轮
        for _ in range(abs(scroll_count)):
            delta = WHEEL_DELTA if scroll_count > 0 else -WHEEL_DELTA
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            time.sleep(0.5)

        time.sleep(0.8)
        # 松开B键
        ctypes.windll.user32.keybd_event(VK_B, 0, 2, 0)
