from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtCore import Qt, Signal, Property
from PySide6.QtGui import QColor, QFont
from qfluentwidgets import (
    StrongBodyLabel,
    BodyLabel,
    PushButton,
    FlowLayout,
    Theme,
    isDarkTheme,
    FluentIcon,
    themeColor,
)


class FilterGroup(QWidget):
    """筛选分组组件"""

    optionChanged = Signal()  # 选项变更信号

    def __init__(self, title: str, options: list, parent=None):
        super().__init__(parent)
        self.title = title
        self.options = options
        self.buttons = {}
        self.title_label = None
        # 为了支持多选，我们不使用 QButtonGroup (它是单选的)
        # 如果需要单选，可以在逻辑层控制，或者由 FilterPanel 传入参数
        # 这里默认全部视为"可切换状态"，即 Toggle

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(10)

        # 标题 (使用稍小的带颜色字体)
        self.title_label = BodyLabel(self.title)
        self.title_label.setStyleSheet("color: #666666; font-weight: 600;")
        layout.addWidget(self.title_label)

        # 选项容器
        container = QWidget()
        self.flow_layout = FlowLayout(container, needAni=False)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setHorizontalSpacing(8)
        self.flow_layout.setVerticalSpacing(8)

        # 创建选项按钮
        for opt in self.options:
            # 使用 PushButton 并设置为 checkable 来模拟 Chip
            btn = PushButton(opt)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.PointingHandCursor)

            # 设置样式
            self._update_btn_style(btn)

            # 连接信号
            btn.toggled.connect(lambda c, b=btn: self._on_btn_toggled(b))

            self.buttons[opt] = btn
            self.flow_layout.addWidget(btn)

        layout.addWidget(container)

    def _update_btn_style(self, btn):
        # 动态生成颜色
        c = themeColor()
        light_bg = c.name()
        is_dark = isDarkTheme()

        # 定义样式表
        # Normal: 浅灰背景, 黑字
        # Checked: 主题色背景, 白字
        # Hover: 稍深灰 或 稍浅主题色

        # 注意：QSS 中无法直接引用变量，我们用 f-string
        # 为了美观，未选中态用 #f0f0f0 (亮色模式)

        if is_dark:
            normal_bg = "#3A424D"
            normal_text = "#E5E7EB"
            hover_bg = "#4A5563"
            checked_bg = light_bg
            checked_hover = c.lighter(110).name()
        else:
            normal_bg = "#f5f5f5"
            normal_text = "#333333"
            hover_bg = "#e0e0e0"
            checked_bg = light_bg
            checked_hover = c.lighter(110).name()

        style = f"""
            QPushButton {{
                background-color: {normal_bg};
                color: {normal_text};
                border: none;
                border-radius: 15px;
                padding: 0 16px;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
            QPushButton:checked {{
                background-color: {checked_bg};
                color: white;
            }}
            QPushButton:checked:hover {{
                background-color: {checked_hover};
            }}
        """
        btn.setStyleSheet(style)

    def apply_theme_styles(self):
        title_color = "#cbd5e1" if isDarkTheme() else "#666666"
        if self.title_label:
            self.title_label.setStyleSheet(f"color: {title_color}; font-weight: 600;")
        for btn in self.buttons.values():
            self._update_btn_style(btn)

    def _on_btn_toggled(self, btn):
        self.optionChanged.emit()

    def get_checked_options(self) -> list:
        """获取选中的选项列表"""
        return [opt for opt, btn in self.buttons.items() if btn.isChecked()]

    def set_checked_options(self, options: list):
        """设置选中的选项"""
        if not options:
            return
        for opt in options:
            if opt in self.buttons:
                # 阻塞信号防止批量设置时频繁触发更新
                self.buttons[opt].blockSignals(True)
                self.buttons[opt].setChecked(True)
                self.buttons[opt].blockSignals(False)

    def reset(self):
        """重置所有选项"""
        for btn in self.buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)


class FilterPanel(QWidget):
    """
    多维度筛选面板 (重构版)
    """

    filterChanged = Signal(dict)  # 实时触发

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)  # 确保 QSS 背景色生效
        self.groups = {}
        self.title_label = None
        self.divider_line = None
        self._init_ui()
        self._apply_theme_styles()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. 标题栏 (Header)
        header = QWidget()
        header.setFixedHeight(60)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        title = StrongBodyLabel("筛选")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.title_label = title

        # 重置按钮 (放右上角，小巧的文字按钮)
        self.reset_btn = PushButton("重置")
        self.reset_btn.setFixedSize(60, 28)
        # 用空样式或自定义样式使其看起来像 Text Button
        self.reset_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #666;
                border: 1px solid #ddd;
                border-radius: 14px;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                color: #333;
            }
        """
        )
        self.reset_btn.clicked.connect(self.reset_all)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.reset_btn)

        main_layout.addWidget(header)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #f0f0f0; border: none; max-height: 1px;")
        self.divider_line = line
        main_layout.addWidget(line)

        # 2. 滚动内容 (Scroll Content)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )

        content = QWidget()
        content.setStyleSheet("background-color: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(20)

        # 获取动态筛选条件
        from src.pokedex import pokedex

        options = pokedex.get_filter_options()

        # 添加分组

        # 活跃时间
        self._add_group(
            "active_time",
            "活跃时间",
            ["凌晨", "清晨", "上午", "下午", "黄昏", "深夜"],
            content_layout,
        )

        # 活跃天气
        self._add_group(
            "active_weather", "活跃天气", options["weather"], content_layout
        )

        # 出没地点
        self._add_group("location", "出没地点", options["location"], content_layout)

        # 所需鱼竿
        self._add_group(
            "rod_type", "所需鱼竿", pokedex.get_fish_types(), content_layout
        )

        # 收集状态
        self._add_group(
            "collection_status",
            "收集状态",
            ["只显示未全部解锁", "只显示未解锁"],
            content_layout,
        )

        # 活跃季节
        self._add_group("active_season", "活跃季节", options["season"], content_layout)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        self._apply_theme_styles()

    def _add_group(self, key, title, options, layout):
        group = FilterGroup(title, options)
        # 连接信号实现实时筛选
        group.optionChanged.connect(self.apply_filter)
        self.groups[key] = group
        layout.addWidget(group)

    def _apply_theme_styles(self):
        is_dark = isDarkTheme()

        panel_bg = "#2B313B" if is_dark else "white"
        panel_border = "#495264" if is_dark else "#e5e5e5"
        title_color = "#f1f5f9" if is_dark else "#111827"
        divider_color = "rgba(255, 255, 255, 0.14)" if is_dark else "#f0f0f0"

        reset_bg = "transparent"
        reset_text = "#cbd5e1" if is_dark else "#666666"
        reset_border = "#64748b" if is_dark else "#ddd"
        reset_hover_bg = "rgba(255,255,255,0.08)" if is_dark else "#f0f0f0"
        reset_hover_text = "#f8fafc" if is_dark else "#333"

        self.setStyleSheet(
            f"""
            FilterPanel {{
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 8px;
            }}
        """
        )

        if self.title_label:
            self.title_label.setStyleSheet(
                f"font-size: 20px; font-weight: bold; color: {title_color};"
            )

        self.reset_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {reset_bg};
                color: {reset_text};
                border: 1px solid {reset_border};
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: {reset_hover_bg};
                color: {reset_hover_text};
            }}
        """
        )

        if self.divider_line:
            self.divider_line.setStyleSheet(
                f"background-color: {divider_color}; border: none; max-height: 1px;"
            )

        for group in self.groups.values():
            group.apply_theme_styles()

    def refresh_theme(self):
        self._apply_theme_styles()

    def reset_all(self):
        """重置所有筛选"""
        for group in self.groups.values():
            group.reset()
        self.apply_filter()  # 重置后立即刷新

    def apply_filter(self):
        """应用筛选（实时）"""
        criteria = self.get_criteria()
        self.filterChanged.emit(criteria)

    def set_criteria(self, criteria: dict):
        """回显筛选条件"""
        if not criteria:
            return

        # 映射后端 key 到前端组件 key
        # active_time -> time
        if "time" in criteria:
            self.groups["active_time"].set_checked_options(criteria["time"])

        if "weather" in criteria:
            self.groups["active_weather"].set_checked_options(criteria["weather"])

        if "location" in criteria:
            self.groups["location"].set_checked_options(criteria["location"])

        if "type" in criteria:
            self.groups["rod_type"].set_checked_options(criteria["type"])

        if "season" in criteria:
            self.groups["active_season"].set_checked_options(criteria["season"])

        if "collection" in criteria:
            mapped_coll = []
            if "hide_completed" in criteria["collection"]:
                mapped_coll.append("只显示未全部解锁")
            if "only_uncaught" in criteria["collection"]:
                mapped_coll.append("只显示未解锁")
            self.groups["collection_status"].set_checked_options(mapped_coll)

    def get_criteria(self) -> dict:
        """获取当前筛选条件"""
        criteria = {}

        # active_time -> time
        time_opts = self.groups["active_time"].get_checked_options()
        if time_opts:
            criteria["time"] = time_opts

        # active_weather -> weather
        weather_opts = self.groups["active_weather"].get_checked_options()
        if weather_opts:
            criteria["weather"] = weather_opts

        # location -> location
        loc_opts = self.groups["location"].get_checked_options()
        if loc_opts:
            criteria["location"] = loc_opts

        # rod_type -> type
        type_opts = self.groups["rod_type"].get_checked_options()
        if type_opts:
            criteria["type"] = type_opts

        # active_season -> season
        season_opts = self.groups["active_season"].get_checked_options()
        if season_opts:
            criteria["season"] = season_opts

        # collection_status -> collection
        coll_opts = self.groups["collection_status"].get_checked_options()
        if coll_opts:
            mapped_coll = []
            if "只显示未全部解锁" in coll_opts:
                mapped_coll.append("hide_completed")
            if "只显示未解锁" in coll_opts:
                mapped_coll.append("only_uncaught")
            criteria["collection"] = mapped_coll

        return criteria
