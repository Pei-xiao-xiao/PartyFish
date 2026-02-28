import ctypes
import time
import random
from pynput import keyboard, mouse
from PySide6.QtCore import QObject, Signal
from src.config import cfg

# Constants for mouse_event
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120


class InputController(QObject):
    toggle_script_signal = Signal()
    debug_screenshot_signal = Signal()
    sell_hotkey_signal = Signal()
    uno_hotkey_signal = Signal()
    record_only_hotkey_signal = Signal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.keyboard_listener = None
        self._hotkey_handler = None
        self._debug_hotkey_handler = None
        self._sell_hotkey_handler = None
        self._uno_hotkey_handler = None
        self._record_only_hotkey_handler = None
        self.is_mouse_down = False

        self._main_hotkey_str = cfg.hotkey
        self._debug_hotkey_str = cfg.global_settings.get("debug_hotkey", "F10")
        self._sell_hotkey_str = cfg.global_settings.get("sell_hotkey", "F4")
        self._uno_hotkey_str = cfg.global_settings.get("uno_hotkey", "F3")
        self._record_only_hotkey_str = cfg.global_settings.get("record_only_hotkey", "F5")

        self._update_hotkey_handler()
        self._update_debug_hotkey_handler()
        self._update_sell_hotkey_handler()
        self._update_uno_hotkey_handler()
        self._update_record_only_hotkey_handler()

        self._gamepad_controller = None
        self._init_gamepad()

    def _parse_hotkey_string(self, hotkey_string):
        """Helper function to parse a hotkey string into pynput format."""
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
        Parses the main hotkey from config and creates a pynput HotKey handler.
        """
        self._main_hotkey_str = cfg.hotkey

        # Skip keyboard.HotKey for mouse buttons
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
        Parses the debug hotkey from config and creates a pynput HotKey handler.
        """
        self._debug_hotkey_str = cfg.global_settings.get("debug_hotkey", "F10")

        # Skip keyboard.HotKey for mouse buttons
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
        Parses the sell hotkey from config and creates a pynput HotKey handler.
        """
        self._sell_hotkey_str = cfg.global_settings.get("sell_hotkey", "F4")

        # Skip keyboard.HotKey for mouse buttons
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
        Parses the uno hotkey from config and creates a pynput HotKey handler.
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

    def _update_record_only_hotkey_handler(self):
        """
        Parses the record only hotkey from config and creates a pynput HotKey handler.
        """
        self._record_only_hotkey_str = cfg.global_settings.get("record_only_hotkey", "F5")

        if self._record_only_hotkey_str in ["Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5"]:
            self._record_only_hotkey_handler = None
            return

        try:
            formatted_hotkey = self._parse_hotkey_string(self._record_only_hotkey_str)
            self._record_only_hotkey_handler = keyboard.HotKey(
                keyboard.HotKey.parse(formatted_hotkey), self.record_only_hotkey_signal.emit
            )
        except Exception as e:
            print(f"Error parsing record only hotkey '{self._record_only_hotkey_str}': {e}")
            self._record_only_hotkey_handler = None

    def _init_gamepad(self):
        """
        Initialize gamepad controller if enabled.
        """
        if not cfg.global_settings.get("enable_gamepad", False):
            return

        try:
            from src.gamepad_controller import gamepad_controller
            self._gamepad_controller = gamepad_controller
            self._gamepad_controller.gamepad_button_pressed.connect(self._on_gamepad_button)
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
        Reinitialize gamepad controller (called when gamepad settings change).
        """
        if self._gamepad_controller:
            self._gamepad_controller.stop_listening()
            try:
                self._gamepad_controller.gamepad_button_pressed.disconnect(self._on_gamepad_button)
            except Exception:
                pass
            self._gamepad_controller = None

        self._init_gamepad()

    def _on_gamepad_button(self, button_name):
        """
        Handle gamepad button press events.
        """
        gamepad_mappings = cfg.global_settings.get("gamepad_mappings", {})
        
        if button_name == gamepad_mappings.get("toggle"):
            self.toggle_script_signal.emit()
        elif button_name == gamepad_mappings.get("debug"):
            self.debug_screenshot_signal.emit()
        elif button_name == gamepad_mappings.get("sell"):
            self.sell_hotkey_signal.emit()
        elif button_name == gamepad_mappings.get("uno"):
            self.uno_hotkey_signal.emit()
        elif button_name == gamepad_mappings.get("record_only"):
            self.record_only_hotkey_signal.emit()

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
        Simulates pressing and releasing a key using virtual key codes.
        """
        key_name = key_name.upper()
        # Common virtual key codes and scan codes
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
            ctypes.windll.user32.keybd_event(vk, scan, 0, 0)  # Key Down
            time.sleep(random.uniform(0.05, 0.1))
            ctypes.windll.user32.keybd_event(vk, scan, 2, 0)  # Key Up
        else:
            print(f"Unknown key for simulation: {key_name}")

    @staticmethod
    def jitter_click(x, y):
        """
        Simulates a more human-like mouse click with random delay.
        """
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(random.uniform(0.05, 0.12))
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def click(self, x, y):
        """
        Simulates a left mouse click at the given coordinates.
        """
        self.jitter_click(x, y)

    @staticmethod
    def double_click(x, y):
        """
        Simulates a double click at the given coordinates.
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
        """Simulates pressing the left mouse button down without releasing."""
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.is_mouse_down = True

    def release_mouse_button(self):
        """Simulates releasing the left mouse button."""
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_mouse_down = False

    def hold_mouse(self, duration):
        """
        Simulates holding the left mouse button for a specified duration.
        """
        actual_duration = self.add_jitter(duration)
        self.press_mouse_button()
        time.sleep(actual_duration)
        self.release_mouse_button()

    def left_click(self):
        """
        Simulates a left mouse click.
        """
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        self.is_mouse_down = True
        time.sleep(0.1)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        self.is_mouse_down = False

    def ensure_mouse_up(self):
        """
        Ensures the left mouse button is released if it's currently held down.
        """
        if self.is_mouse_down:
            ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            self.is_mouse_down = False

    def _on_press(self, key):
        """
        Callback for keyboard press events.
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

        if self._record_only_hotkey_handler:
            try:
                self._record_only_hotkey_handler.press(self.keyboard_listener.canonical(key))
            except Exception:
                pass

    def _on_release(self, key):
        """
        Callback for keyboard release events.
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

        if self._record_only_hotkey_handler:
            try:
                self._record_only_hotkey_handler.release(self.keyboard_listener.canonical(key))
            except Exception:
                pass

    def start_listening(self):
        """
        Starts the keyboard listener.
        """
        if self.running:
            return

        self._update_hotkey_handler()
        self._update_debug_hotkey_handler()
        self._update_sell_hotkey_handler()
        self._update_uno_hotkey_handler()
        self._update_record_only_hotkey_handler()
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
        Stops the keyboard and mouse listeners.
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
        elif button_str == self._record_only_hotkey_str:
            self.record_only_hotkey_signal.emit()

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
