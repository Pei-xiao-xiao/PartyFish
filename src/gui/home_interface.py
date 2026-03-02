from PySide6.QtCore import Qt, QTimer, Slot, QTime, Signal, QDateTime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QLabel,
    QGraphicsDropShadowEffect,
    QFrame,
)
from PySide6.QtGui import (
    QColor,
    QBrush,
    QPixmap,
    QPainter,
    QPainterPath,
    QFont,
    QLinearGradient,
)
from qfluentwidgets import (
    CardWidget,
    TextEdit,
    StrongBodyLabel,
    TableWidget,
    CaptionLabel,
    TitleLabel,
    SubtitleLabel,
    InfoBadge,
    InfoLevel,
    ComboBox,
    qconfig,
    SwitchButton,
    HyperlinkButton,
    BodyLabel,
    IconWidget,
    PrimaryPushButton,
    ProgressRing,
    SegmentedWidget,
    ToolButton,
)
from qfluentwidgets import FluentIcon as FIF
from src.config import cfg
from .components import QUALITY_COLORS
from pathlib import Path

try:
    from src._version import __version__
except ImportError:
    __version__ = "DEV"


class HomeInterface(QWidget):
    """主页界面"""

    preset_changed_signal = Signal(str)
    toggle_overlay_signal = Signal()
    fishFilterChanged = Signal()
    account_changed_signal = Signal(str)  # 账号切换信号

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("HomeInterface")

        self.run_time = QTime(0, 0, 0)
        self.total_catch = 0
        self.last_fish_info = "暂无"

        self.v_box_layout = QVBoxLayout(self)
        self.v_box_layout.setContentsMargins(40, 40, 40, 20)
        self.v_box_layout.setSpacing(24)

        # 1. Banner Area
        self.init_banner()

        # Create a splitter to divide the main area
        self.main_splitter = QSplitter(Qt.Horizontal, self)

        # Left side widget
        self.left_widget = QWidget(self)
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 20, 0)  # Add right margin
        self.left_layout.setSpacing(24)

        # 2. Real-time data panel
        self.init_dashboard()
        self.left_layout.addLayout(self.dashboard_layout)

        # 3. Session records table
        self.init_session_records()
        self.left_layout.addWidget(self.session_records_container)
        self.left_layout.addStretch(1)

        # Right side widget (Log Area)
        self.init_log_area()  # This now returns the container

        # Add widgets to splitter
        self.main_splitter.addWidget(self.left_widget)
        self.main_splitter.addWidget(self.log_container)

        self.main_splitter.setStretchFactor(
            0, 2
        )  # Give more space to the left side initially (ratio 2:1)
        self.main_splitter.setStretchFactor(1, 1)
        # Removed border style for splitter handle to remove the separator line
        self.main_splitter.setStyleSheet(
            """
            QSplitter::handle {
                background-color: transparent;
                width: 1px;
            }
        """
        )

        self.v_box_layout.addWidget(self.main_splitter, 1)  # Add stretch factor of 1

        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_run_time)

        # 显示启动时的错误信息
        if cfg.startup_errors:
            for error in cfg.startup_errors:
                self.log_output.append(error)

        # 监听信号 (Move from _on_preset_changed)

        self.account_changed_signal.connect(self._on_account_changed)
        self.fishFilterChanged.connect(self._refresh_fish_preview)

        # 监听图鉴数据变化
        from src.pokedex import pokedex

        pokedex.data_changed.connect(self._on_pokedex_data_changed)

        # 4. Footer - Move to bottom
        self.init_footer()

    def init_footer(self):
        """Initialize footer with author info and license."""
        self.footer_container = QWidget(self)
        self.footer_layout = QHBoxLayout(self.footer_container)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(12)

        # Text container for two lines
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        # Line 1: Author & Open Source Declaration
        self.author_label = BodyLabel(
            f"Created by FadedTUMI, MaiDong688, Pei-Xiao-Xiao | {__version__} | 本软件完全免费 如遇售卖 直接举报",
            self,
        )
        self.author_label.setTextColor(QColor(100, 100, 100), QColor(150, 150, 150))

        # Line 2: Disclaimer
        self.disclaimer_label = CaptionLabel(
            "软件仅供学习交流，若因使用此软件导致的任何损失与作者无关",
            self,
        )
        self.disclaimer_label.setTextColor(QColor(150, 150, 150), QColor(120, 120, 120))

        text_layout.addWidget(self.author_label)
        text_layout.addWidget(self.disclaimer_label)

        self.footer_layout.addWidget(text_container)
        self.footer_layout.addStretch(1)

        self.v_box_layout.addWidget(self.footer_container, 0, Qt.AlignBottom)

    def init_banner(self):
        """初始化 Banner"""
        self.banner = CardWidget(self)
        self.banner_layout = QHBoxLayout(self.banner)
        self.banner_layout.setContentsMargins(28, 24, 28, 24)
        self.banner_layout.setSpacing(20)

        # Logo - 使用水豚头像，高清渲染
        self.logo_label = QLabel(self.banner)
        self.logo_label.setFixedSize(88, 88)
        logo_path = Path(cfg._get_base_path()) / "resources" / "avatar.png"
        if logo_path.exists():
            # 高清渲染：加载 2x 大小后缩放，实现 HiDPI 效果
            original_pixmap = QPixmap(str(logo_path))
            # 创建带圆角的头像
            rounded_pixmap = self._create_rounded_pixmap(original_pixmap, 88, 18)
            self.logo_label.setPixmap(rounded_pixmap)
        self.logo_label.setScaledContents(False)
        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self.logo_label)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.logo_label.setGraphicsEffect(shadow)
        self.banner_layout.addWidget(self.logo_label)

        # 文本部分
        self.banner_text_layout = QVBoxLayout()
        self.banner_text_layout.setSpacing(6)

        # 程序名称：现代美观风格
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

        # 副标题：简洁优雅风格
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

        # 热键提示：现代键盘按键风格
        self.hotkey_container = QWidget(self.banner)
        self.hotkey_layout = QHBoxLayout(self.hotkey_container)
        self.hotkey_layout.setContentsMargins(0, 4, 0, 0)
        self.hotkey_layout.setSpacing(16)

        self._add_hotkey_badge("启动", cfg.hotkey)
        self._add_hotkey_badge("UNO", cfg.global_settings.get("uno_hotkey", "F3"))
        self._add_hotkey_badge("卖鱼", cfg.global_settings.get("sell_hotkey", "F4"))
        self._add_hotkey_badge("调试", cfg.global_settings.get("debug_hotkey", "F10"))
        self.hotkey_layout.addStretch(1)

        self.banner_text_layout.addWidget(self.title_label)
        self.banner_text_layout.addWidget(self.subtitle_label)
        self.banner_text_layout.addWidget(self.hotkey_container)
        self.banner_layout.addLayout(self.banner_text_layout)

        self.banner_layout.addStretch(1)

        # Right side controls - 现代简洁风格
        self.controls_container = QWidget(self.banner)
        self.controls_layout = QHBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(20)

        # 控制选项区域 - 使用 Grid 对齐
        self.control_grid = QGridLayout()
        self.control_grid.setHorizontalSpacing(10)
        self.control_grid.setVerticalSpacing(10)
        self.control_grid.setColumnMinimumWidth(0, 50)  # 标签列固定宽度

        # 标签样式
        label_style = "color: #6b7280; font-size: 13px; font-weight: 500;"

        # 0. Overlay Switcher (左侧)
        self.overlay_label = CaptionLabel("悬浮窗", self.banner)
        self.overlay_label.setStyleSheet(label_style)
        self.overlay_switch = SwitchButton(self.banner)
        self.overlay_switch.setOnText("开")
        self.overlay_switch.setOffText("关")
        self.overlay_switch.checkedChanged.connect(
            lambda _: self.toggle_overlay_signal.emit()
        )
        self.control_grid.addWidget(
            self.overlay_label, 0, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.overlay_switch, 0, 1, Qt.AlignLeft)

        # 1. Account Switcher (右侧)
        self.account_label = CaptionLabel("账号", self.banner)
        self.account_label.setStyleSheet(label_style)
        self.accountComboBox = ComboBox(self.banner)
        self.accountComboBox.addItems(cfg.get_accounts())
        self.accountComboBox.setCurrentText(cfg.current_account)
        self.accountComboBox.setFixedWidth(130)
        self.accountComboBox.currentTextChanged.connect(self._on_account_changed)
        self.control_grid.addWidget(
            self.account_label, 0, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.accountComboBox, 0, 3)

        # 2. Sound Switcher (左侧)
        self.sound_label = CaptionLabel("启动音效", self.banner)
        self.sound_label.setStyleSheet(label_style)
        self.sound_switch = SwitchButton(self.banner)
        self.sound_switch.setOnText("开")
        self.sound_switch.setOffText("关")
        self.sound_switch.setChecked(
            cfg.global_settings.get("control_sound_enabled", False)
        )
        self.sound_switch.checkedChanged.connect(self._on_sound_switch_changed)
        self.control_grid.addWidget(
            self.sound_label, 1, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.sound_switch, 1, 1, Qt.AlignLeft)

        # 3. Preset Switcher (右侧)
        self.preset_label = CaptionLabel("预设", self.banner)
        self.preset_label.setStyleSheet(label_style)
        self.presetComboBox = ComboBox(self.banner)
        self.presetComboBox.addItems(list(cfg.presets.keys()))
        self.presetComboBox.setCurrentText(cfg.current_preset_name)
        self.presetComboBox.setFixedWidth(130)
        self.presetComboBox.currentTextChanged.connect(self._on_preset_changed)
        self.control_grid.addWidget(
            self.preset_label, 1, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.presetComboBox, 1, 3)

        # 4. Release Mode Switcher (左侧) - 放生模式三档开关
        self.release_mode_label = CaptionLabel("放生模式", self.banner)
        self.release_mode_label.setStyleSheet(label_style)
        self.release_mode_segment = SegmentedWidget(self.banner)
        self.release_mode_segment.addItem("off", "关")
        self.release_mode_segment.addItem("single", "单条")
        self.release_mode_segment.addItem("auto", "自动")
        # 根据配置设置当前选项
        release_mode = cfg.global_settings.get("release_mode", "off")
        self.release_mode_segment.setCurrentItem(release_mode)
        self.release_mode_segment.currentItemChanged.connect(
            self._on_release_mode_changed
        )
        self.control_grid.addWidget(
            self.release_mode_label, 2, 0, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.release_mode_segment, 2, 1, Qt.AlignLeft)

        # 5. Screenshot Mode Switcher (右侧) - 截图模式选择
        self.screenshot_mode_label = CaptionLabel("截图模式", self.banner)
        self.screenshot_mode_label.setStyleSheet(label_style)
        self.screenshot_mode_segment = SegmentedWidget(self.banner)
        self.screenshot_mode_segment.addItem("wegame", "WeGame")
        self.screenshot_mode_segment.addItem("steam", "Steam")
        # 根据配置设置当前选项
        screenshot_mode = cfg.global_settings.get("screenshot_mode", "wegame")
        self.screenshot_mode_segment.setCurrentItem(screenshot_mode)
        self.screenshot_mode_segment.currentItemChanged.connect(
            self._on_screenshot_mode_changed
        )
        self.control_grid.addWidget(
            self.screenshot_mode_label, 2, 2, Qt.AlignRight | Qt.AlignVCenter
        )
        self.control_grid.addWidget(self.screenshot_mode_segment, 2, 3, Qt.AlignLeft)

        self.controls_layout.addLayout(self.control_grid)

        # 状态指示器 - 简洁竖向卡片
        self.status_container = QWidget(self.banner)
        self.status_container.setFixedWidth(70)
        status_layout = QVBoxLayout(self.status_container)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(4)
        status_layout.setAlignment(Qt.AlignCenter)

        # 状态圆点
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

        # 状态文字
        self.status_text = CaptionLabel("已停止", self.status_container)
        self.status_text.setStyleSheet(
            "color: #8a8a8a; font-size: 12px; font-weight: 500;"
        )

        status_layout.addWidget(self.status_dot, 0, Qt.AlignCenter)
        status_layout.addWidget(self.status_text, 0, Qt.AlignCenter)

        self.controls_layout.addWidget(self.status_container)
        self.banner_layout.addWidget(self.controls_container)

        self.v_box_layout.addWidget(self.banner)

    def _create_control_row(self, label_text: str, control_widget: QWidget) -> QWidget:
        """创建现代风格的控制行"""
        row = QWidget(self.banner)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 标签 - 现代风格
        label = CaptionLabel(label_text, row)
        label.setFixedWidth(50)
        label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        label.setStyleSheet(
            """
            CaptionLabel {
                color: #6b7280;
                font-size: 13px;
                font-weight: 500;
            }
        """
        )

        layout.addWidget(label)
        layout.addWidget(control_widget)
        return row

    def _create_styled_combobox(
        self, items: list, current: str, width: int
    ) -> ComboBox:
        """创建样式化的下拉框"""
        combo = ComboBox(self.banner)
        combo.addItems(items)
        combo.setCurrentText(current)
        combo.setFixedWidth(width)
        return combo

    def _create_rounded_pixmap(
        self, source: QPixmap, size: int, radius: int
    ) -> QPixmap:
        """创建带圆角的高清头像"""
        # HiDPI 缩放：使用 2x 分辨率渲染
        scale = 2
        scaled_size = size * scale
        scaled_radius = radius * scale

        # 缩放原图
        scaled_source = source.scaled(
            scaled_size,
            scaled_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

        # 创建圆角遮罩
        result = QPixmap(scaled_size, scaled_size)
        result.fill(Qt.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 绘制圆角矩形路径
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, scaled_size, scaled_size, scaled_radius, scaled_radius
        )
        painter.setClipPath(path)

        # 居中绘制
        x = (scaled_size - scaled_source.width()) // 2
        y = (scaled_size - scaled_source.height()) // 2
        painter.drawPixmap(x, y, scaled_source)
        painter.end()

        # 设置 devicePixelRatio 实现 HiDPI 效果
        result.setDevicePixelRatio(scale)
        return result

    def _add_hotkey_badge(self, label: str, key: str):
        """添加键盘风格的热键徽章"""
        container = QWidget(self.hotkey_container)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # 功能标签
        label_widget = CaptionLabel(label, container)
        label_widget.setStyleSheet("color: #9ca3af; font-size: 12px;")

        # 按键徽章（键盘按键风格）
        key_badge = QLabel(key, container)
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

        layout.addWidget(label_widget)
        layout.addWidget(key_badge)
        self.hotkey_layout.addWidget(container)

        # 保存引用以便更新
        if not hasattr(self, "_hotkey_badges"):
            self._hotkey_badges = {}
        self._hotkey_badges[label] = key_badge

    def _on_preset_changed(self, preset_name):
        """Handle preset switching from the ComboBox."""
        if preset_name in cfg.presets:
            cfg.load_preset(preset_name)
            cfg.save()
            # 状态重置信号：如果此时脚本正在运行或暂停，我们需要通知Worker重置状态
            # 由于没有直接引用的worker，我们通过一个自定义信号或查找父窗口来通信
            # 或者更简单的，我们定义一个信号，让MainWindow去连接
            if hasattr(self, "preset_changed_signal"):
                self.preset_changed_signal.emit(preset_name)

    def _on_account_changed(self, account_name):
        """Handle account switching from the ComboBox."""
        if account_name and account_name != cfg.current_account:
            # 使用延时更新，避免阻塞下拉框动画，提升流畅度
            def delayed_update():
                cfg.switch_account(account_name)
                # 发送信号通知其他组件（如记录页、收益页）刷新数据
                self.account_changed_signal.emit(account_name)
                # 清空本次会话记录，因为切换了账号
                self.clear_session_table()
                self.total_catch = 0

                # 重新加载图鉴数据
                from src.pokedex import pokedex

                pokedex.reload()

            # 延时 50ms 执行，给 UI 响应时间
            QTimer.singleShot(50, delayed_update)

    def _on_sound_switch_changed(self, checked):
        """处理音效开关变化"""
        cfg.global_settings["control_sound_enabled"] = checked
        cfg.save()

    def _on_release_mode_changed(self, mode):
        """处理放生模式变化"""
        cfg.global_settings["release_mode"] = mode

        # 同步 auto_release_enabled 配置
        if mode == "auto":
            cfg.global_settings["auto_release_enabled"] = True
        else:
            cfg.global_settings["auto_release_enabled"] = False

        cfg.save()

        # 通知设置页面更新开关状态
        self._notify_settings_interface_update(mode)

        # 更新设置页面的开关状态
        mode_text_map = {"off": "关", "single": "单条", "auto": "自动"}
        self.update_log(f"[系统] 放生模式已切换为: {mode_text_map.get(mode, mode)}")

    def _on_screenshot_mode_changed(self, mode):
        """处理截图模式变化"""
        cfg.global_settings["screenshot_mode"] = mode
        cfg.save()
        mode_text_map = {"wegame": "WeGame", "steam": "Steam"}
        self.update_log(f"[系统] 截图模式已切换为: {mode_text_map.get(mode, mode)}")

    def _notify_settings_interface_update(self, mode):
        """通知设置页面更新放生模式"""
        # 通过父窗口查找设置页面
        parent = self.parent()
        while parent:
            if hasattr(parent, "settings_interface"):
                parent.settings_interface.update_release_mode_from_main(mode)
                break
            parent = parent.parent()

    def update_release_mode_segment(self, mode):
        """从设置页面更新放生模式选择器"""
        # 阻止信号避免循环触发
        self.release_mode_segment.blockSignals(True)
        self.release_mode_segment.setCurrentItem(mode)
        self.release_mode_segment.blockSignals(False)

        # 同步配置
        cfg.global_settings["release_mode"] = mode
        if mode == "auto":
            cfg.global_settings["auto_release_enabled"] = True
        else:
            cfg.global_settings["auto_release_enabled"] = False
        cfg.save()

    def refresh_account_list(self):
        """刷新账号下拉框列表"""
        current = self.accountComboBox.currentText()
        self.accountComboBox.blockSignals(True)
        self.accountComboBox.clear()
        self.accountComboBox.addItems(cfg.get_accounts())
        # 恢复选中项
        if current in cfg.get_accounts():
            self.accountComboBox.setCurrentText(current)
        else:
            self.accountComboBox.setCurrentText(cfg.current_account)
        self.accountComboBox.blockSignals(False)

    def update_hotkey_display(self, new_hotkey):
        if hasattr(self, "_hotkey_badges") and "启动" in self._hotkey_badges:
            self._hotkey_badges["启动"].setText(new_hotkey)

    def update_debug_hotkey_display(self, new_hotkey):
        if hasattr(self, "_hotkey_badges") and "调试" in self._hotkey_badges:
            self._hotkey_badges["调试"].setText(new_hotkey)

    def update_sell_hotkey_display(self, new_hotkey):
        if hasattr(self, "_hotkey_badges") and "卖鱼" in self._hotkey_badges:
            self._hotkey_badges["卖鱼"].setText(new_hotkey)

    def init_dashboard(self):
        """初始化数据看板 - 今日销售 + 图鉴进度"""
        self.dashboard_layout = QHBoxLayout()
        self.dashboard_layout.setSpacing(24)

        # 卡片 1 - 今日销售进度
        self.sales_card = CardWidget(self)
        sales_layout = QVBoxLayout(self.sales_card)
        sales_layout.setContentsMargins(20, 16, 20, 16)
        sales_layout.setSpacing(10)

        # 标题行
        sales_header = QHBoxLayout()
        sales_icon = IconWidget(FIF.SHOPPING_CART, self.sales_card)
        sales_icon.setFixedSize(16, 16)
        sales_title = StrongBodyLabel("今日销售", self.sales_card)
        sales_header.addWidget(sales_icon)
        sales_header.addWidget(sales_title)
        sales_header.addStretch(1)
        sales_layout.addLayout(sales_header)

        # 进度条容器
        progress_container = QWidget(self.sales_card)
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(12)

        # 自定义进度条
        self.sales_progress_bar = QWidget(progress_container)
        self.sales_progress_bar.setFixedHeight(12)
        self.sales_progress_bar.setMinimumWidth(200)
        self.sales_progress_bar.setStyleSheet(
            """
            QWidget {
                background-color: #e5e7eb;
                border-radius: 6px;
            }
        """
        )

        # 进度条填充
        self.sales_progress_fill = QWidget(self.sales_progress_bar)
        self.sales_progress_fill.setFixedHeight(12)
        self.sales_progress_fill.setStyleSheet(
            """
            QWidget {
                background-color: #10b981;
                border-radius: 6px;
            }
        """
        )
        self.sales_progress_fill.move(0, 0)

        # 销售金额标签
        self.sales_value_label = BodyLabel("0 / 899", progress_container)
        self.sales_value_label.setStyleSheet("color: #6b7280; font-weight: 500;")

        progress_layout.addWidget(self.sales_progress_bar, 1)
        progress_layout.addWidget(self.sales_value_label)
        sales_layout.addWidget(progress_container)

        self.dashboard_layout.addWidget(self.sales_card, 2)

        # 卡片 2 - 图鉴进度
        self.pokedex_card = CardWidget(self)
        pokedex_layout = QVBoxLayout(self.pokedex_card)
        pokedex_layout.setContentsMargins(20, 16, 20, 16)
        pokedex_layout.setSpacing(10)

        # 标题行
        pokedex_header = QHBoxLayout()
        pokedex_icon = IconWidget(FIF.LIBRARY, self.pokedex_card)
        pokedex_icon.setFixedSize(16, 16)
        pokedex_title = StrongBodyLabel("图鉴进度", self.pokedex_card)
        pokedex_header.addWidget(pokedex_icon)
        pokedex_header.addWidget(pokedex_title)
        pokedex_header.addStretch(1)
        pokedex_layout.addLayout(pokedex_header)

        # 数据显示区域 (左右分栏)
        data_container = QHBoxLayout()
        data_container.setSpacing(0)

        # === 左侧：鱼种解锁 ===
        fish_container = QWidget()
        fish_layout = QVBoxLayout(fish_container)
        fish_layout.setContentsMargins(0, 0, 0, 0)
        fish_layout.setSpacing(6)

        # 环形进度条容器
        fish_ring_box = QWidget()
        fish_ring_box.setFixedSize(60, 60)
        fish_ring_stack = QGridLayout(fish_ring_box)
        fish_ring_stack.setContentsMargins(0, 0, 0, 0)

        self.fish_ring = ProgressRing()
        self.fish_ring.setFixedSize(56, 56)
        self.fish_ring.setStrokeWidth(5)
        self.fish_ring.setTextVisible(False)

        self.fish_collected_label = TitleLabel("0", self.pokedex_card)
        self.fish_collected_label.setStyleSheet(
            "color: #0ea5e9; font-size: 15px; font-weight: bold;"
        )
        self.fish_collected_label.setAlignment(Qt.AlignCenter)

        fish_ring_stack.addWidget(self.fish_ring, 0, 0, Qt.AlignCenter)
        fish_ring_stack.addWidget(self.fish_collected_label, 0, 0, Qt.AlignCenter)

        fish_layout.addWidget(fish_ring_box, 0, Qt.AlignCenter)

        # 底部文字
        fish_text_layout = QVBoxLayout()
        fish_text_layout.setSpacing(2)
        fish_title = CaptionLabel("已解锁鱼种", self.pokedex_card)
        fish_title.setStyleSheet("color: #64748b")
        self.fish_total_label = CaptionLabel("总计 0", self.pokedex_card)
        self.fish_total_label.setStyleSheet("color: #94a3b8")

        fish_text_layout.addWidget(fish_title, 0, Qt.AlignCenter)
        fish_text_layout.addWidget(self.fish_total_label, 0, Qt.AlignCenter)
        fish_layout.addLayout(fish_text_layout)

        # === 分隔线 ===
        line = QFrame(self.pokedex_card)
        line.setFrameShape(QFrame.VLine)
        line.setFixedSize(1, 30)
        line.setStyleSheet("background-color: #e2e8f0; border: none;")

        # === 右侧：全品质收集 ===
        crown_container = QWidget()
        crown_layout = QVBoxLayout(crown_container)
        crown_layout.setContentsMargins(0, 0, 0, 0)
        crown_layout.setSpacing(6)

        # 环形进度条容器
        crown_ring_box = QWidget()
        crown_ring_box.setFixedSize(60, 60)
        crown_ring_stack = QGridLayout(crown_ring_box)
        crown_ring_stack.setContentsMargins(0, 0, 0, 0)

        self.crown_ring = ProgressRing()
        self.crown_ring.setFixedSize(56, 56)
        self.crown_ring.setStrokeWidth(5)
        self.crown_ring.setTextVisible(False)

        self.crown_collected_label = TitleLabel("0", self.pokedex_card)
        self.crown_collected_label.setStyleSheet(
            "color: #8b5cf6; font-size: 15px; font-weight: bold;"
        )
        self.crown_collected_label.setAlignment(Qt.AlignCenter)

        crown_ring_stack.addWidget(self.crown_ring, 0, 0, Qt.AlignCenter)
        crown_ring_stack.addWidget(self.crown_collected_label, 0, 0, Qt.AlignCenter)

        crown_layout.addWidget(crown_ring_box, 0, Qt.AlignCenter)

        # 底部文字
        crown_text_layout = QVBoxLayout()
        crown_text_layout.setSpacing(2)
        crown_title = CaptionLabel("全品质收集", self.pokedex_card)
        crown_title.setStyleSheet("color: #64748b")
        self.crown_total_label = CaptionLabel("总计 0", self.pokedex_card)
        self.crown_total_label.setStyleSheet("color: #94a3b8")

        crown_text_layout.addWidget(crown_title, 0, Qt.AlignCenter)
        crown_text_layout.addWidget(self.crown_total_label, 0, Qt.AlignCenter)
        crown_layout.addLayout(crown_text_layout)

        # 添加到主布局
        data_container.addWidget(fish_container, 1)
        data_container.addWidget(line)
        data_container.addWidget(crown_container, 1)

        pokedex_layout.addLayout(data_container)

        self.dashboard_layout.addWidget(self.pokedex_card, 1)

    def init_session_records(self):
        """初始化当前可钓鱼种预览区域（替代原本次记录）"""
        from src.pokedex import pokedex
        from src.gui.components.home_fish_card import HomeFishCard
        from src.gui.components.draggable_scroll_area import DraggableScrollArea
        from datetime import datetime

        self.session_records_container = CardWidget(self)
        layout = QVBoxLayout(self.session_records_container)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(0)

        # 标题行（显示当前时段）
        header_layout = QHBoxLayout()
        header_icon = IconWidget(FIF.CALORIES, self.session_records_container)
        header_icon.setFixedSize(16, 16)
        self.fish_preview_title = StrongBodyLabel(
            "当前可钓", self.session_records_container
        )
        self.fish_preview_time_label = CaptionLabel("", self.session_records_container)
        self.fish_preview_time_label.setStyleSheet("color: #9ca3af;")

        header_layout.setSpacing(12)

        header_layout.addWidget(header_icon)
        header_layout.addWidget(self.fish_preview_title)
        header_layout.addWidget(self.fish_preview_time_label)

        # 添加过滤选项 (三段式开关)
        self.fish_filter_segment = SegmentedWidget(self.session_records_container)
        self.fish_filter_segment.addItem("all", "全部")
        self.fish_filter_segment.addItem("lure", "路亚")
        self.fish_filter_segment.addItem("ice", "池塘")

        # 加载配置
        current_mode = getattr(cfg, "fish_filter_mode", "all")
        self.fish_filter_segment.setCurrentItem(current_mode)

        self.fish_filter_segment.currentItemChanged.connect(
            self._on_fish_filter_changed
        )
        header_layout.addWidget(self.fish_filter_segment)
        header_layout.addStretch(1)

        layout.addLayout(header_layout)

        # 鱼种卡片滚动区域 - 自定义可拖拽区域
        self.fish_scroll_area = DraggableScrollArea(self.session_records_container)
        self.fish_scroll_area.setWidgetResizable(True)
        self.fish_scroll_area.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """
        )
        self.fish_scroll_area.setFixedHeight(165)

        # 卡片容器
        self.fish_cards_container = QWidget()
        self.fish_cards_layout = QHBoxLayout(self.fish_cards_container)
        self.fish_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.fish_cards_layout.setSpacing(4)
        self.fish_cards_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.fish_scroll_area.setWidget(self.fish_cards_container)
        layout.addWidget(self.fish_scroll_area)

        # 缓存上次检测到的条件，避免每秒重建UI
        self._last_time = None
        self._last_weather = None

        # 定时检测条件变化
        self.fish_preview_timer = QTimer(self)
        self.fish_preview_timer.timeout.connect(self._check_conditions)

        # 延迟初始化（等待 pokedex 加载完成）
        QTimer.singleShot(500, self._check_conditions)

    def _on_fish_filter_changed(self, routeKey):
        """处理鱼种过滤改变"""
        cfg.fish_filter_mode = routeKey
        cfg.save()
        self._refresh_fish_preview()
        self.fishFilterChanged.emit()

    def _check_conditions(self):
        """每秒检测天气和时段，变化时才刷新UI"""
        from src.pokedex import pokedex

        try:
            current_time = pokedex.get_current_game_time()
            current_weather = pokedex.detect_current_weather()

            if current_time != self._last_time or current_weather != self._last_weather:
                self._last_time = current_time
                self._last_weather = current_weather
                self.update_log(
                    f"[天气] 当前: {current_weather or '未识别'} · {current_time}"
                )
                self._refresh_fish_preview()
        except Exception as e:
            print(f"[Home] 检测条件失败: {e}")
        finally:
            self.fish_preview_timer.start(1000)

    def _refresh_fish_preview(self):
        """刷新当前可钓鱼种预览（仅在条件变化时调用）"""
        from src.pokedex import pokedex, QUALITIES
        from src.gui.components.home_fish_card import HomeFishCard

        try:
            # 清空旧卡片
            while self.fish_cards_layout.count():
                item = self.fish_cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            current_time = self._last_time
            current_weather = self._last_weather

            # 更新标签显示
            weather_text = current_weather or "未知"
            season_text = (
                "春季"
                if cfg.global_settings.get("enable_season_filter", True)
                else "春夏秋"
            )
            self.fish_preview_time_label.setText(
                f"({current_time} · {weather_text} · {season_text})"
            )

            # 构建筛选条件：时间 + 天气 + 季节（排除冬季）
            criteria = {"time": [current_time]}
            if current_weather:
                criteria["weather"] = [current_weather]
            if cfg.global_settings.get("enable_season_filter", True):
                criteria["season"] = ["春季"]
            else:
                criteria["season"] = ["春季", "夏季", "秋季"]

            # 获取当前可钓鱼种
            all_fish = pokedex.get_all_fish()
            catchable_fish = pokedex.filter_fish_multi(all_fish, criteria)

            # 过滤掉冰钓鱼种
            catchable_fish = [
                f for f in catchable_fish if "冰钓" not in f.get("type", "")
            ]

            # 应用类型过滤
            filter_mode = getattr(cfg, "fish_filter_mode", "all")
            if filter_mode == "lure":
                catchable_fish = [
                    f for f in catchable_fish if "路亚" in f.get("type", "")
                ]
            elif filter_mode == "ice":
                catchable_fish = [
                    f for f in catchable_fish if "池塘" in f.get("type", "")
                ]

            if not catchable_fish:
                # 显示空状态提示
                empty_label = CaptionLabel(
                    "当前时段暂无可钓鱼种", self.fish_cards_container
                )
                empty_label.setStyleSheet("color: #9ca3af; padding: 20px;")
                self.fish_cards_layout.addWidget(empty_label)
            else:
                # 筛选：仅显示未完全收集的鱼种
                visible_fish = []
                for fish in catchable_fish:
                    # 检查是否完全收集
                    status = pokedex.get_collection_status(fish["name"])
                    is_fully_collected = all(
                        status.get(q) is not None for q in QUALITIES
                    )

                    # 只有未完全收集的才显示（或者根据需求，也可以显示所有但通过半透明区分？）
                    # 用户需求："显示所有用户没有完全收集的"
                    if not is_fully_collected:
                        visible_fish.append(fish)

                if not visible_fish:
                    # 所有可钓的都收集满了！
                    empty_label = CaptionLabel(
                        "当前时段所有鱼种已毕业！", self.fish_cards_container
                    )
                    empty_label.setStyleSheet(
                        "color: #10b981; font-weight: bold; padding: 20px;"
                    )
                    self.fish_cards_layout.addWidget(empty_label)
                else:
                    # 按收集进度排序（未收集优先）
                    sorted_fish = pokedex.sort_fish(
                        visible_fish, sort_key="progress", reverse=False
                    )

                    # 显示卡片（显示所有）
                    for fish in sorted_fish:
                        card = HomeFishCard(fish, self.fish_cards_container)
                        self.fish_cards_layout.addWidget(card)

            self.fish_cards_layout.addStretch(1)

        except Exception as e:
            print(f"[Home] 刷新鱼种预览失败: {e}")

    def update_sales_progress(self, sold: int, limit: int = 899):
        """更新今日销售进度"""
        # 计算进度和差值
        if limit <= 0:
            progress_ratio = 0
            is_overflow = False
            overflow_amount = 0
        else:
            progress_ratio = min(sold / limit, 1.0)
            is_overflow = sold > limit
            overflow_amount = sold - limit

        # 更新标签文字
        if is_overflow:
            # 超额显示风格：899 / 899 (+708 已超额)
            self.sales_value_label.setText(
                f"{limit} / {limit} (<span style='color: #ef4444; font-weight: bold;'>+{overflow_amount} 已超额</span>)"
            )
        else:
            self.sales_value_label.setText(f"{sold} / {limit}")

        # 更新进度条宽度
        # 使用 QTimer.singleShot 确保在布局完成后再计算宽度，
        # 或者在超额时直接尽量给一个大的宽度（如果是容器会自动裁剪的话，但这里是绝对定位子 Widget）
        def do_update_bar():
            bar_width = self.sales_progress_bar.width()
            if is_overflow:
                fill_width = bar_width  # 强制填满
            else:
                fill_width = int(bar_width * progress_ratio)

            # 修复圆角问题
            if fill_width <= 0:
                self.sales_progress_fill.hide()
            else:
                self.sales_progress_fill.show()
                self.sales_progress_fill.setFixedWidth(fill_width)

            # 根据进度改变颜色
            if is_overflow:
                color = "#b91c1c"  # 深红色
            elif progress_ratio >= 0.9:
                color = "#ef4444"
            elif progress_ratio >= 0.7:
                color = "#f59e0b"
            else:
                color = "#10b981"

            self.sales_progress_fill.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {color};
                    border-radius: 6px;
                }}
            """
            )

        # 立即执行一次，并延时执行一次以应对窗口大小变化
        do_update_bar()
        QTimer.singleShot(10, do_update_bar)

    def _on_pokedex_data_changed(self):
        """图鉴数据变化响应"""
        self._refresh_fish_preview()
        self.update_pokedex_progress()

    def update_pokedex_progress(self):
        """更新图鉴进度"""
        from src.pokedex import pokedex

        try:
            collected, total, collected_q, total_q = pokedex.get_progress()

            # 更新鱼种
            self.fish_collected_label.setText(str(collected))
            self.fish_total_label.setText(f"总计 {total}")
            fish_percent = int(collected / total * 100) if total > 0 else 0
            self.fish_ring.setValue(fish_percent)

            # 更新全品质
            self.crown_collected_label.setText(str(collected_q))
            self.crown_total_label.setText(f"总计 {total_q}")
            crown_percent = int(collected_q / total_q * 100) if total_q > 0 else 0
            self.crown_ring.setValue(crown_percent)
        except Exception as e:
            print(f"[Home] 更新图鉴进度失败: {e}")

    # 保留空方法以兼容旧代码调用
    def add_record_to_session_table(self, record):
        """兼容旧代码，现在不做任何事"""
        pass

    def clear_session_table(self):
        """兼容旧代码，现在不做任何事"""
        pass

    def init_log_area(self):
        """初始化日志区域"""
        # 容器 - 使用 CardWidget 保持统一风格
        self.log_container = CardWidget(self)
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(20, 16, 20, 20)
        self.log_layout.setSpacing(12)

        # 头部
        log_header_layout = QHBoxLayout()
        log_icon = IconWidget(FIF.COMMAND_PROMPT, self.log_container)
        log_icon.setFixedSize(16, 16)
        self.log_header_label = StrongBodyLabel("运行日志", self.log_container)

        # 下载日志按钮
        self.download_log_button = ToolButton(self.log_container)
        self.download_log_button.setIcon(FIF.DOWNLOAD)
        self.download_log_button.setToolTip("下载日志到 debug_screenshots 文件夹")
        self.download_log_button.setFixedSize(24, 24)
        self.download_log_button.clicked.connect(self._download_log)

        log_header_layout.addWidget(log_icon)
        log_header_layout.addWidget(self.log_header_label)
        log_header_layout.addStretch(1)
        log_header_layout.addWidget(self.download_log_button)
        self.log_layout.addLayout(log_header_layout)

        # 日志输出框 - 优化样式
        self.log_output = TextEdit(self.log_container)
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("LogOutput")

        # 使用更现代、简洁的样式
        self.log_output.setStyleSheet(
            """
            TextEdit {
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                padding: 8px;
            }
            TextEdit:hover {
                background-color: #f3f4f6;
                border: 1px solid #d1d5db;
            }
        """
        )

        self.log_layout.addWidget(self.log_output)

        # self.v_box_layout.addWidget(self.log_container) NO LONGER ADDED HERE
        # self.v_box_layout.setStretchFactor(self.log_container, 1)

    def _download_log(self):
        """下载日志到 debug_screenshots 文件夹"""
        try:
            # 获取日志内容
            log_content = self.log_output.toPlainText()
            if not log_content.strip():
                self.update_log("[系统] 日志为空，无需保存")
                return

            # 创建 debug_screenshots 目录
            debug_dir = cfg._get_application_path() / "debug_screenshots"
            debug_dir.mkdir(parents=True, exist_ok=True)

            # 生成文件名：app_YYYYMMDD_HHMMSS.log
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
            log_file = debug_dir / f"app_{timestamp}.log"

            # 保存日志
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(log_content)

            self.update_log(f"[系统] 日志已保存到: {log_file}")
        except Exception as e:
            self.update_log(f"[系统] 保存日志失败: {e}")

    @Slot(str)
    def update_log(self, text):
        """追加日志"""
        self.log_output.append(text)

    @Slot(str)
    def update_status(self, status):
        """更新状态"""
        # 更新状态圆点和文字
        if status == "运行中":
            # 绿色运行状态
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

            # 重置计数
            if not self.timer.isActive():
                self.total_catch = 0
                self.run_time = QTime(0, 0, 0)
                self.timer.start(1000)

        elif status == "只记录模式":
            # 蓝色只记录模式状态
            self.status_dot.setStyleSheet(
                """
                QLabel {
                    background-color: #1890ff;
                    border-radius: 6px;
                }
            """
            )
            self.status_text.setText("只记录模式")
            self.status_text.setStyleSheet(
                "color: #1890ff; font-size: 12px; font-weight: 500;"
            )
            # 只记录模式不启动计时器
            self.timer.stop()

        elif "暂停" in status:
            # 橙色暂停状态
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
            self.timer.stop()

        elif "停止" in status:
            # 灰色停止状态
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
            self.timer.stop()

    def update_run_time(self):
        """更新运行时间（兼容旧代码，现在仅更新内部计时）"""
        self.run_time = self.run_time.addSecs(1)

    @Slot(dict)
    def update_catch_info(self, catch_data):
        """更新捕获数据"""
        self.total_catch += 1
        # 更新图鉴进度（可能有新鱼种）
        self.update_pokedex_progress()
        # 刷新可钓鱼种预览（收集状态可能改变）
        self._refresh_fish_preview()

    def refresh_table_colors(self):
        """兼容旧代码，现在不做任何事"""
        pass
