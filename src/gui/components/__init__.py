from PySide6.QtWidgets import QLineEdit
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from qfluentwidgets import Theme, qconfig

# 定义品质颜色 (亮色主题, 暗色主题)
QUALITY_COLORS = {
    "标准": (QColor("#606060"), QColor("#D0D0D0")),  # 灰色
    "非凡": (QColor("#1E9E00"), QColor("#2ECC71")),  # 绿色
    "稀有": (QColor("#007ACC"), QColor("#3498DB")),  # 蓝色
    "史诗": (QColor("#8A2BE2"), QColor("#9B59B6")),  # 紫色
    "传奇": (QColor("#FF8C00"), QColor("#F39C12")),  # 橙色
    "传说": (QColor("#FF8C00"), QColor("#F39C12")),  # 传奇的别名
}


class KeyBindingWidget(QLineEdit):
    gamepad_button_captured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("点击后按下按键")
        self.setAlignment(Qt.AlignCenter)
        self.setReadOnly(True)
        self.is_capturing = False
        self.original_text = ""
        self._gamepad_mode = False
        self._gamepad_connection = None

    def set_gamepad_mode(self, enabled: bool):
        self._gamepad_mode = enabled
        if enabled:
            self.setPlaceholderText("点击后按手柄按键")
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
            elif button == Qt.RightButton:
                return
            elif button == Qt.MiddleButton:
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
        if self._gamepad_mode:
            self.setText("请按手柄按键...")
            self._connect_gamepad()
        else:
            self.setText("请按下按键...")
        self.setProperty("isCapturing", True)
        self.update_style()

    def stop_capture(self):
        self.is_capturing = False
        self.setProperty("isCapturing", False)
        self._disconnect_gamepad()
        self.update_style()

    def _connect_gamepad(self):
        if not self._gamepad_mode:
            return
        try:
            from src.gamepad_controller import gamepad_controller

            # 确保 pygame 已初始化
            if not gamepad_controller._pygame_initialized:
                if not gamepad_controller._init_pygame():
                    print("[KeyBindingWidget] Failed to initialize pygame")
                    return

            # 确保手柄控制器正在监听
            if not gamepad_controller._running:
                gamepad_controller.start_listening()
                print("[KeyBindingWidget] Started gamepad listening")

            # 连接信号（使用 UniqueConnection 避免重复连接）
            try:
                gamepad_controller.gamepad_button_pressed.disconnect(
                    self._on_gamepad_button
                )
            except (TypeError, RuntimeError):
                pass  # 信号未连接，忽略

            gamepad_controller.gamepad_button_pressed.connect(
                self._on_gamepad_button, Qt.UniqueConnection
            )
            self._gamepad_connection = True
            print(f"[KeyBindingWidget] Gamepad connected for {self.placeholderText()}")
        except Exception as e:
            print(f"[KeyBindingWidget] Failed to connect gamepad: {e}")
            import traceback

            traceback.print_exc()

    def _disconnect_gamepad(self):
        if self._gamepad_connection:
            try:
                from src.gamepad_controller import gamepad_controller

                gamepad_controller.gamepad_button_pressed.disconnect(
                    self._on_gamepad_button
                )
                print(
                    f"[KeyBindingWidget] Gamepad disconnected for {self.placeholderText()}"
                )
            except Exception:
                pass
            finally:
                self._gamepad_connection = None

    def _on_gamepad_button(self, button_name: str):
        if self.is_capturing and self._gamepad_mode:
            self.setText(button_name)
            self.stop_capture()
            self.editingFinished.emit()
            self.gamepad_button_captured.emit(button_name)

    def update_style(self):
        color = qconfig.themeColor.name
        if self.property("isCapturing"):
            self.setStyleSheet(
                f"border: 2px solid {color}; background-color: rgba(0, 159, 227, 0.1);"
            )
        else:
            self.setStyleSheet("")
        self.style().unpolish(self)
        self.style().polish(self)

    def keyPressEvent(self, event):
        if not self.is_capturing:
            return

        if self._gamepad_mode:
            if event.key() == Qt.Key_Escape:
                self.setText(self.original_text)
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
            self.setText(self.original_text)
            self.stop_capture()

    def focusOutEvent(self, event):
        if self.is_capturing:
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
