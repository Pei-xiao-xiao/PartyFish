import time

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLineEdit
from qfluentwidgets import qconfig

from src.config import cfg

# Quality colors for light and dark themes.
QUALITY_COLORS = {
    "标准": (QColor("#606060"), QColor("#D0D0D0")),
    "非凡": (QColor("#1E9E00"), QColor("#2ECC71")),
    "稀有": (QColor("#007ACC"), QColor("#3498DB")),
    "史诗": (QColor("#8A2BE2"), QColor("#9B59B6")),
    "传奇": (QColor("#FF8C00"), QColor("#F39C12")),
    "传说": (QColor("#FF8C00"), QColor("#F39C12")),
}


class KeyBindingWidget(QLineEdit):
    gamepad_button_captured = Signal(str)
    gamepad_binding_captured = Signal(str, str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("点击后按下按键")
        self.setAlignment(Qt.AlignCenter)
        self.setReadOnly(True)
        self.is_capturing = False
        self.original_text = ""
        self._gamepad_mode = False
        self._gamepad_connection = None
        self._captured_gamepad_button = None
        self._gamepad_press_started_at = None
        self._gamepad_binding = {
            "button": "",
            "mode": "press",
            "hold_ms": cfg.GAMEPAD_HOLD_MS,
        }
        self._original_gamepad_binding = self._gamepad_binding.copy()
        self._capture_timer = QTimer(self)
        self._capture_timer.setInterval(100)
        self._capture_timer.timeout.connect(self._update_capture_elapsed_text)
        self.update_style()

    def set_gamepad_mode(self, enabled: bool):
        self._gamepad_mode = enabled
        if enabled:
            self.setPlaceholderText("点击后按或按住手柄按键")
        else:
            self.setPlaceholderText("点击后按下按键")

    def mousePressEvent(self, event):
        if not self.is_capturing:
            self.start_capture()
        else:
            button = event.button()
            modifiers = event.modifiers()
            parts = []

            if modifiers & Qt.ControlModifier:
                parts.append("Ctrl")
            if modifiers & Qt.AltModifier:
                parts.append("Alt")
            if modifiers & Qt.ShiftModifier:
                parts.append("Shift")

            if button == Qt.LeftButton:
                return
            if button == Qt.RightButton:
                return
            if button == Qt.MiddleButton:
                parts.append("Mouse3")
            elif button == Qt.XButton1:
                parts.append("Mouse4")
            elif button == Qt.XButton2:
                parts.append("Mouse5")

            hotkey_str = "+ ".join(parts)
            self.setText(hotkey_str)
            self.stop_capture()
            self.editingFinished.emit()
            return
        super().mousePressEvent(event)

    def start_capture(self):
        self.is_capturing = True
        self.original_text = self.text()
        self._original_gamepad_binding = self._gamepad_binding.copy()
        self._reset_gamepad_capture_state()
        if self._gamepad_mode:
            self.setText("请按或按住手柄按键...")
            self._connect_gamepad()
        else:
            self.setText("请按下按键...")
        self.setProperty("isCapturing", True)
        self.update_style()

    def stop_capture(self):
        self.is_capturing = False
        self.setProperty("isCapturing", False)
        self._disconnect_gamepad()
        self._capture_timer.stop()
        self._reset_gamepad_capture_state()
        self.update_style()

    def _reset_gamepad_capture_state(self):
        self._captured_gamepad_button = None
        self._gamepad_press_started_at = None

    def set_gamepad_binding(self, mapping):
        normalized = cfg.normalize_gamepad_mapping("custom", mapping)
        self._gamepad_binding = normalized
        self.setText(self._format_gamepad_binding_text(normalized))

    def get_gamepad_binding(self):
        return self._gamepad_binding.copy()

    def _format_gamepad_binding_text(self, mapping):
        button = mapping.get("button", "")
        if not button:
            return ""
        if mapping.get("mode") == "hold":
            return (
                f"{button} ({mapping.get('hold_ms', cfg.GAMEPAD_HOLD_MS) / 1000:.1f}s)"
            )
        return button

    def _update_capture_elapsed_text(self):
        if not self._captured_gamepad_button or self._gamepad_press_started_at is None:
            return
        elapsed_s = time.monotonic() - self._gamepad_press_started_at
        self.setText(f"{self._captured_gamepad_button} ({elapsed_s:.1f}s)")

    def _connect_gamepad(self):
        if not self._gamepad_mode:
            return

        try:
            from src.gamepad_controller import gamepad_controller

            if not gamepad_controller._pygame_initialized:
                if not gamepad_controller._init_pygame():
                    print("[KeyBindingWidget] Failed to initialize pygame")
                    return

            if not gamepad_controller._running:
                gamepad_controller.start_listening()
                print("[KeyBindingWidget] Started gamepad listening")

            try:
                gamepad_controller.gamepad_button_state_changed.disconnect(
                    self._on_gamepad_button_state_changed
                )
            except (TypeError, RuntimeError):
                pass

            gamepad_controller.gamepad_button_state_changed.connect(
                self._on_gamepad_button_state_changed, Qt.UniqueConnection
            )
            self._gamepad_connection = True
            print(f"[KeyBindingWidget] Gamepad connected for {self.placeholderText()}")
        except Exception as e:
            print(f"[KeyBindingWidget] Failed to connect gamepad: {e}")
            import traceback

            traceback.print_exc()

    def _disconnect_gamepad(self):
        if not self._gamepad_connection:
            return

        try:
            from src.gamepad_controller import gamepad_controller

            gamepad_controller.gamepad_button_state_changed.disconnect(
                self._on_gamepad_button_state_changed
            )
            print(
                f"[KeyBindingWidget] Gamepad disconnected for {self.placeholderText()}"
            )
        except Exception:
            pass
        finally:
            self._gamepad_connection = None

    def _on_gamepad_button_state_changed(self, button_name: str, pressed: bool):
        if not (self.is_capturing and self._gamepad_mode):
            return

        if pressed:
            if self._captured_gamepad_button is None:
                self._captured_gamepad_button = button_name
                self._gamepad_press_started_at = time.monotonic()
                self._capture_timer.start()
                self._update_capture_elapsed_text()
            return

        if button_name != self._captured_gamepad_button:
            return

        started_at = self._gamepad_press_started_at or time.monotonic()
        hold_ms = max(0, int((time.monotonic() - started_at) * 1000))
        mode = "hold" if hold_ms >= cfg.GAMEPAD_HOLD_MS else "press"
        self._gamepad_binding = {
            "button": button_name,
            "mode": mode,
            "hold_ms": cfg.normalize_gamepad_hold_ms(hold_ms),
        }
        self.setText(self._format_gamepad_binding_text(self._gamepad_binding))
        self.stop_capture()
        self.gamepad_binding_captured.emit(button_name, mode, hold_ms)
        self.gamepad_button_captured.emit(button_name)
        self.editingFinished.emit()

    def update_style(self):
        color = qconfig.themeColor.name
        is_dark = qconfig.theme.value == "Dark"
        text_color = "#ffffff" if is_dark else "#000000"
        bg_color = "#374151" if is_dark else "#ffffff"
        border_color = "#4b5563" if is_dark else "#d1d5db"
        
        if self.property("isCapturing"):
            self.setStyleSheet(
                f"border: 2px solid {color}; background-color: rgba(0, 159, 227, 0.1); color: {text_color};"
            )
        else:
            self.setStyleSheet(
                f"background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 4px; color: {text_color};"
            )
        self.style().unpolish(self)
        self.style().polish(self)

    def keyPressEvent(self, event):
        if not self.is_capturing:
            return

        if self._gamepad_mode:
            if event.key() == Qt.Key_Escape:
                self.set_gamepad_binding(self._original_gamepad_binding)
                self.stop_capture()
            return

        key = event.key()

        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        modifiers = event.modifiers()
        parts = []

        if modifiers & Qt.ControlModifier:
            parts.append("Ctrl")
        if modifiers & Qt.AltModifier:
            parts.append("Alt")
        if modifiers & Qt.ShiftModifier:
            parts.append("Shift")

        key_name = self.get_key_name(key)
        if key_name:
            parts.append(key_name)
            hotkey_str = "+".join(parts)
            self.setText(hotkey_str)
            self.stop_capture()
            self.editingFinished.emit()
        elif key == Qt.Key_Escape:
            if self._gamepad_mode:
                self.set_gamepad_binding(self._original_gamepad_binding)
            else:
                self.setText(self.original_text)
            self.stop_capture()

    def focusOutEvent(self, event):
        if self.is_capturing:
            if self._gamepad_mode:
                self.set_gamepad_binding(self._original_gamepad_binding)
            else:
                self.setText(self.original_text)
            self.stop_capture()
        super().focusOutEvent(event)

    def get_key_name(self, key):
        if Qt.Key_F1 <= key <= Qt.Key_F12:
            return f"F{key - Qt.Key_F1 + 1}"

        key_map = {
            Qt.Key_Space: "Space",
            Qt.Key_Tab: "Tab",
            Qt.Key_Enter: "Enter",
            Qt.Key_Return: "Enter",
            Qt.Key_Escape: "Esc",
            Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Delete",
            Qt.Key_Insert: "Insert",
            Qt.Key_Home: "Home",
            Qt.Key_End: "End",
            Qt.Key_PageUp: "PgUp",
            Qt.Key_PageDown: "PgDn",
        }

        if key in key_map:
            return key_map[key]

        if Qt.Key_0 <= key <= Qt.Key_9 or Qt.Key_A <= key <= Qt.Key_Z:
            return chr(key).upper()

        return None


from src.gui.components.filter_panel import FilterPanel
from src.gui.components.filter_drawer import FilterDrawer
from src.gui.components.date_range_picker import (
    DateRangePicker,
    DateRangeDialog,
    DateRangeCalendar,
)
from src.gui.components.banner_widget import BannerWidget
from src.gui.components.dashboard_widget import DashboardWidget
from src.gui.components.fish_preview_widget import FishPreviewWidget
from src.gui.components.log_widget import LogWidget
from src.gui.components.footer_widget import FooterWidget
