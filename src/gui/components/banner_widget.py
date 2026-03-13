"""
Banner 组件 - 负责主页 Banner 区域的 UI 构建和交互逻辑
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QGraphicsDropShadowEffect,
)
from qfluentwidgets import (
    CardWidget,
    CaptionLabel,
    TitleLabel,
    SubtitleLabel,
    ComboBox,
    SwitchButton,
    SegmentedWidget,
    qconfig,
)

from src.config import cfg

try:
    from src._version import __version__
except ImportError:
    __version__ = "DEV"


class BannerWidget(QWidget):
    """Banner 组件 - 包含程序标题、热键提示、控制选项、状态显示"""

    overlay_toggled = Signal(bool)
    account_changed = Signal(str)
    preset_changed = Signal(str)
    sound_toggled = Signal(bool)
    release_mode_changed = Signal(str)
    screenshot_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hotkey_badges = {}
        self._init_ui()

    def _init_ui(self):
        """初始化 Banner UI"""
        self.banner = CardWidget(self)
        self.banner_layout = QHBoxLayout(self.banner)
        self.banner_layout.setContentsMargins(28, 24, 28, 24)
        self.banner_layout.setSpacing(20)

        self._setup_logo()
        self._setup_text_section()
        self._setup_controls()
        self._setup_status()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.banner)

    def _setup_logo(self):
        """设置 Logo"""
        self.logo_label = QLabel(self.banner)
        self.logo_label.setFixedSize(88, 88)
        logo_path = Path(cfg._get_base_path()) / "resources" / "avatar.png"
        if logo_path.exists():
            original_pixmap = QPixmap(str(logo_path))
            rounded_pixmap = self._create_rounded_pixmap(original_pixmap, 88, 18)
            self.logo_label.setPixmap(rounded_pixmap)
        self.logo_label.setScaledContents(False)

        shadow = QGraphicsDropShadowEffect(self.logo_label)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.logo_label.setGraphicsEffect(shadow)
        self.banner_layout.addWidget(self.logo_label)

    def _setup_text_section(self):
        """设置文本部分"""
        self.banner_text_layout = QVBoxLayout()
        self.banner_text_layout.setSpacing(6)

        self.title_label = TitleLabel("PartyFish", self.banner)
        self.title_label.setStyleSheet(
            """
            TitleLabel {
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 1px;
            }
        """
        )

        self.subtitle_label = SubtitleLabel("智能垂钓，轻松收获", self.banner)
        self.subtitle_label.setStyleSheet(
            """
            SubtitleLabel {
                font-size: 14px;
                font-weight: 500;
                color: #6b7280;
            }
        """
        )

        self.hotkey_container = QWidget(self.banner)
        self.hotkey_layout = QHBoxLayout(self.hotkey_container)
        self.hotkey_layout.setContentsMargins(0, 4, 0, 0)
        self.hotkey_layout.setSpacing(16)

        self._add_hotkey_badge("启动", cfg.get_global_setting("hotkey", "F2"))
        self._add_hotkey_badge("UNO", cfg.get_global_setting("uno_hotkey", "F3"))
        self._add_hotkey_badge("卖鱼", cfg.get_global_setting("sell_hotkey", "F4"))
        self._add_hotkey_badge("调试", cfg.get_global_setting("debug_hotkey", "F10"))
        self.hotkey_layout.addStretch(1)

        self.banner_text_layout.addWidget(self.title_label)
        self.banner_text_layout.addWidget(self.subtitle_label)
        self.banner_text_layout.addWidget(self.hotkey_container)
        self.banner_layout.addLayout(self.banner_text_layout)

        self.banner_layout.addStretch(1)

    def _setup_controls(self):
        """设置控制区域"""
        self.controls_container = QWidget(self.banner)
        self.controls_layout = QHBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(20)

        self.control_grid = QGridLayout()
        self.control_grid.setHorizontalSpacing(10)
        self.control_grid.setVerticalSpacing(10)
        self.control_grid.setColumnMinimumWidth(0, 50)

        label_style = "color: #6b7280; font-size: 13px; font-weight: 500;"

        self.overlay_label = CaptionLabel("悬浮窗", self.banner)
        self.overlay_label.setStyleSheet(label_style)
        self.overlay_switch = SwitchButton(self.banner)
        self.overlay_switch.setOnText("开")
        self.overlay_switch.setOffText("关")
        self.overlay_switch.checkedChanged.connect(self.overlay_toggled.emit)
        self.control_grid.addWidget(
            self.overlay_label, 0, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.overlay_switch, 0, 1, Qt.AlignLeft)

        self.account_label = CaptionLabel("账号", self.banner)
        self.account_label.setStyleSheet(label_style)
        self.accountComboBox = ComboBox(self.banner)
        self.accountComboBox.addItems(cfg.get_accounts())
        self.accountComboBox.setCurrentText(cfg.current_account)
        self.accountComboBox.setFixedWidth(130)
        self.accountComboBox.currentTextChanged.connect(self._on_account_combo_changed)
        self.control_grid.addWidget(
            self.account_label, 0, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.accountComboBox, 0, 3)

        self.sound_label = CaptionLabel("启动音效", self.banner)
        self.sound_label.setStyleSheet(label_style)
        self.sound_switch = SwitchButton(self.banner)
        self.sound_switch.setOnText("开")
        self.sound_switch.setOffText("关")
        self.sound_switch.setChecked(
            cfg.get_global_setting("control_sound_enabled", False)
        )
        self.sound_switch.checkedChanged.connect(self.sound_toggled.emit)
        self.control_grid.addWidget(
            self.sound_label, 1, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.sound_switch, 1, 1, Qt.AlignLeft)

        self.preset_label = CaptionLabel("预设", self.banner)
        self.preset_label.setStyleSheet(label_style)
        self.presetComboBox = ComboBox(self.banner)
        self.presetComboBox.addItems(list(cfg.presets.keys()))
        self.presetComboBox.setCurrentText(cfg.current_preset_name)
        self.presetComboBox.setFixedWidth(130)
        self.presetComboBox.currentTextChanged.connect(self._on_preset_combo_changed)
        self.control_grid.addWidget(
            self.preset_label, 1, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.presetComboBox, 1, 3)

        self.release_mode_label = CaptionLabel("放生模式", self.banner)
        self.release_mode_label.setStyleSheet(label_style)
        self.release_mode_segment = SegmentedWidget(self.banner)
        self.release_mode_segment.addItem("off", "关")
        self.release_mode_segment.addItem("single", "单条")
        self.release_mode_segment.addItem("auto", "桶满")
        release_mode = cfg.get_global_setting("release_mode", "off")
        self.release_mode_segment.setCurrentItem(release_mode)
        self.release_mode_segment.currentItemChanged.connect(
            self.release_mode_changed.emit
        )
        self.control_grid.addWidget(
            self.release_mode_label, 2, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.release_mode_segment, 2, 1, Qt.AlignLeft)

        self.screenshot_mode_label = CaptionLabel("截图模式", self.banner)
        self.screenshot_mode_label.setStyleSheet(label_style)
        self.screenshot_mode_segment = SegmentedWidget(self.banner)
        self.screenshot_mode_segment.addItem("wegame", "WeGame")
        self.screenshot_mode_segment.addItem("steam", "Steam")
        screenshot_mode = cfg.get_global_setting("screenshot_mode", "wegame")
        self.screenshot_mode_segment.setCurrentItem(screenshot_mode)
        self.screenshot_mode_segment.currentItemChanged.connect(
            self.screenshot_mode_changed.emit
        )
        self.control_grid.addWidget(
            self.screenshot_mode_label, 2, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.screenshot_mode_segment, 2, 3, Qt.AlignLeft)

        self.controls_layout.addLayout(self.control_grid)
        self.banner_layout.addWidget(self.controls_container)

    def _setup_status(self):
        """设置状态区域"""
        self.status_container = QWidget(self.banner)
        self.status_container.setFixedWidth(130)
        status_layout = QVBoxLayout(self.status_container)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(4)
        status_layout.setAlignment(Qt.AlignCenter)

        status_header_layout = QHBoxLayout()
        status_header_layout.setContentsMargins(0, 0, 0, 0)
        status_header_layout.setSpacing(6)
        status_header_layout.setAlignment(Qt.AlignCenter)

        self.status_dot = QLabel(self.status_container)
        self.status_dot.setFixedSize(12, 12)
        self.status_dot.setStyleSheet(
            """
            QLabel {
                background-color: #8a8a8a;
                border-radius: 6px;
            }
        """
        )

        self.status_text = CaptionLabel("已停止", self.status_container)
        self.status_text.setStyleSheet(
            "color: #8a8a8a; font-size: 12px; font-weight: 500;"
        )

        self.run_time_label = CaptionLabel("运行时间 00:00:00", self.status_container)
        self.run_time_label.setStyleSheet(
            "color: #94a3b8; font-size: 11px; font-family: 'Consolas', 'Monaco', monospace;"
        )

        status_header_layout.addWidget(self.status_dot, 0, Qt.AlignVCenter)
        status_header_layout.addWidget(self.status_text, 0, Qt.AlignVCenter)
        status_layout.addLayout(status_header_layout)
        status_layout.addWidget(self.run_time_label, 0, Qt.AlignCenter)

        self.controls_layout.addWidget(self.status_container)

    def _create_rounded_pixmap(
        self, source: QPixmap, size: int, radius: int
    ) -> QPixmap:
        """创建带圆角的高清头像"""
        scale = 2
        scaled_size = size * scale
        scaled_radius = radius * scale

        scaled_source = source.scaled(
            scaled_size,
            scaled_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

        result = QPixmap(scaled_size, scaled_size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        path = QPainterPath()
        path.addRoundedRect(
            0, 0, scaled_size, scaled_size, scaled_radius, scaled_radius
        )
        painter.setClipPath(path)

        x = (scaled_size - scaled_source.width()) // 2
        y = (scaled_size - scaled_source.height()) // 2
        painter.drawPixmap(x, y, scaled_source)
        painter.end()

        result.setDevicePixelRatio(scale)
        return result

    def _add_hotkey_badge(self, label: str, key: str):
        """添加键盘风格的热键徽章"""
        container = QWidget(self.hotkey_container)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label_widget = CaptionLabel(label, container)
        label_widget.setStyleSheet("color: #9ca3af; font-size: 12px;")

        key_badge = QLabel(key, container)
        key_badge.setObjectName("HotkeyBadge")
        self._update_hotkey_badge_style(key_badge)

        layout.addWidget(label_widget)
        layout.addWidget(key_badge)
        self.hotkey_layout.addWidget(container)

        self._hotkey_badges[label] = key_badge

    def _update_hotkey_badge_style(self, key_badge: QLabel):
        """更新热键徽章样式（主题感知）"""
        is_dark = qconfig.theme.value == "Dark"
        if is_dark:
            key_badge.setStyleSheet(
                """
                QLabel {
                    background-color: #374151;
                    border: 1px solid #4b5563;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: 'Consolas', 'Monaco', monospace;
                    color: #ffffff;
                }
            """
            )
        else:
            key_badge.setStyleSheet(
                """
                QLabel {
                    background-color: #f3f4f6;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                    font-weight: 600;
                    font-family: 'Consolas', 'Monaco', monospace;
                    color: #374151;
                }
            """
            )

    def _on_account_combo_changed(self, account_name: str):
        """账号下拉框变化"""
        self.account_changed.emit(account_name)

    def _on_preset_combo_changed(self, preset_name: str):
        """预设下拉框变化"""
        self.preset_changed.emit(preset_name)

    def set_account_list(self, accounts: list):
        """设置账号列表"""
        current = self.accountComboBox.currentText()
        self.accountComboBox.blockSignals(True)
        self.accountComboBox.clear()
        self.accountComboBox.addItems(accounts)
        if current in accounts:
            self.accountComboBox.setCurrentText(current)
        else:
            self.accountComboBox.setCurrentText(cfg.current_account)
        self.accountComboBox.blockSignals(False)

    def set_current_account(self, account: str):
        """设置当前账号"""
        self.accountComboBox.blockSignals(True)
        self.accountComboBox.setCurrentText(account)
        self.accountComboBox.blockSignals(False)

    def set_current_preset(self, preset: str):
        """设置当前预设"""
        self.presetComboBox.blockSignals(True)
        self.presetComboBox.setCurrentText(preset)
        self.presetComboBox.blockSignals(False)

    def set_release_mode(self, mode: str):
        """设置放生模式"""
        self.release_mode_segment.blockSignals(True)
        self.release_mode_segment.setCurrentItem(mode)
        self.release_mode_segment.blockSignals(False)

    def set_screenshot_mode(self, mode: str):
        """设置截图模式"""
        self.screenshot_mode_segment.blockSignals(True)
        self.screenshot_mode_segment.setCurrentItem(mode)
        self.screenshot_mode_segment.blockSignals(False)

    def set_sound_enabled(self, enabled: bool):
        """设置音效开关"""
        self.sound_switch.blockSignals(True)
        self.sound_switch.setChecked(enabled)
        self.sound_switch.blockSignals(False)

    def update_hotkey_display(self, key: str, hotkey: str):
        """更新热键显示"""
        if key in self._hotkey_badges:
            self._hotkey_badges[key].setText(hotkey)

    def update_run_time(self, time_str: str):
        """更新运行时间显示"""
        self.run_time_label.setText(f"运行时间 {time_str}")

    def update_status(self, status: str):
        """更新状态显示"""
        if status == "运行中":
            self.status_dot.setStyleSheet(
                """
                QLabel {
                    background-color: #52c41a;
                    border-radius: 6px;
                }
            """
            )
            self.status_text.setText("运行中")
            self.status_text.setStyleSheet(
                "color: #52c41a; font-size: 12px; font-weight: 500;"
            )
            self.run_time_label.setStyleSheet(
                "color: #52c41a; font-size: 11px; font-family: 'Consolas', 'Monaco', monospace;"
            )
        elif "暂停" in status:
            self.status_dot.setStyleSheet(
                """
                QLabel {
                    background-color: #faad14;
                    border-radius: 6px;
                }
            """
            )
            self.status_text.setText("已暂停")
            self.status_text.setStyleSheet(
                "color: #faad14; font-size: 12px; font-weight: 500;"
            )
            self.run_time_label.setStyleSheet(
                "color: #faad14; font-size: 11px; font-family: 'Consolas', 'Monaco', monospace;"
            )
        elif "停止" in status:
            self.status_dot.setStyleSheet(
                """
                QLabel {
                    background-color: #8a8a8a;
                    border-radius: 6px;
                }
            """
            )
            self.status_text.setText("已停止")
            self.status_text.setStyleSheet(
                "color: #8a8a8a; font-size: 12px; font-weight: 500;"
            )
            self.run_time_label.setStyleSheet(
                "color: #94a3b8; font-size: 11px; font-family: 'Consolas', 'Monaco', monospace;"
            )

    def apply_theme(self):
        """应用主题样式"""
        for key_badge in self._hotkey_badges.values():
            self._update_hotkey_badge_style(key_badge)

        is_dark = qconfig.theme.value == "Dark"
        title_color = "#ffffff" if is_dark else "#111827"
        self.title_label.setStyleSheet(
            f"""
            TitleLabel {{
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 1px;
                color: {title_color};
            }}
        """
        )

    def refresh_account_controls(self):
        """刷新账号相关控件"""
        self.presetComboBox.blockSignals(True)
        self.presetComboBox.setCurrentText(cfg.current_preset_name)
        self.presetComboBox.blockSignals(False)

        self.release_mode_segment.blockSignals(True)
        self.release_mode_segment.setCurrentItem(
            cfg.get_global_setting("release_mode", "off")
        )
        self.release_mode_segment.blockSignals(False)

        self.sound_switch.blockSignals(True)
        self.sound_switch.setChecked(
            cfg.get_global_setting("control_sound_enabled", False)
        )
        self.sound_switch.blockSignals(False)

        self.screenshot_mode_segment.blockSignals(True)
        self.screenshot_mode_segment.setCurrentItem(
            cfg.get_global_setting("screenshot_mode", "wegame")
        )
        self.screenshot_mode_segment.blockSignals(False)
