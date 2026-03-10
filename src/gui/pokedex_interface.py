"""
图鉴主界面
展示鱼类卡片网格，支持筛选、搜索和收集管理
优化版：品质圆点可点击，居中对齐
"""

from copy import deepcopy

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QFont, QColor
from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    StrongBodyLabel,
    ComboBox,
    SearchLineEdit,
    PushButton,
    CheckBox,
    ToggleButton,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    qconfig,
    FlowLayout,
    RoundMenu,
    Action,
)
from src.config import cfg
from src.pokedex import pokedex, QUALITIES
from src.gui.fish_detail_dialog import FishDetailDialog
from src.gui.components import QUALITY_COLORS
from src.gui.components.filter_panel import FilterPanel


class SortOption(QLabel):
    """排序选项标签"""

    clicked = Signal(str)

    def __init__(self, text: str, key: str, parent=None):
        super().__init__(text, parent)
        self.key = key
        self.is_active = False
        self.is_reverse = False

        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("is_active", False)  # 用于样式控制

        # 字体设置
        font = self.font()
        font.setPointSize(10)
        self.setFont(font)

    def set_active(self, active: bool, reverse: bool = False):
        self.is_active = active
        self.is_reverse = reverse
        self.setProperty("is_active", active)

        # 更新显示文本（添加箭头）
        base_text = self.text().split(" ")[0]
        if active and self.key in ["progress", "weight"]:
            # reverse=True (Desc) -> ↓ (High to Low)
            # reverse=False (Asc) -> ↑ (Low to High)
            arrow = "↓" if reverse else "↑"
            self.setText(f"{base_text} {arrow}")
        else:
            self.setText(base_text)

        self.setStyle(self.style())  # 强制重新应用样式
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.key)


class SortBar(QWidget):
    """排序工具栏"""

    sortChanged = Signal(str, bool)  # key, reverse

    def __init__(self, parent=None):
        super().__init__(parent)

        self.h_layout = QHBoxLayout(self)
        self.h_layout.setContentsMargins(0, 0, 0, 0)
        # 紧凑化: 15 -> 8
        self.h_layout.setSpacing(8)

        # 标签 "排序："
        label = BodyLabel("排序:")
        label.setStyleSheet("color: #666;")
        self.h_layout.addWidget(label)

        self.options = {}
        # 定义选项：显示文本, 键值
        items = [
            ("默认", "default"),
            ("名称", "name"),
            ("进度", "progress"),
            ("重量", "weight"),
        ]

        for text, key in items:
            opt = SortOption(text, key)
            opt.clicked.connect(self._on_option_clicked)
            self.h_layout.addWidget(opt)
            self.options[key] = opt

        self.current_key = "default"
        self.current_reverse = False

        # 初始化样式
        self._update_styles()
        self.options["default"].set_active(True)

    def _on_option_clicked(self, key: str):
        if self.current_key == key:
            # 如果是当前项，且支持反转（进度/重量），则切换顺序
            if key in ["progress", "weight"]:
                self.current_reverse = not self.current_reverse
        else:
            # 切换新项
            self.current_key = key
            # 默认顺序：
            # 重量: 默认降序 (↓) (Heaviest first)
            # 进度: 默认升序 (↑) (Uncaught first, 0->5)
            # 其他: 默认升序
            self.current_reverse = True if key in ["weight"] else False

        self._update_styles()
        self.sortChanged.emit(self.current_key, self.current_reverse)

    def _update_styles(self):
        """更新所有选项的样式与状态"""
        from qfluentwidgets import themeColor

        c = themeColor()

        for key, opt in self.options.items():
            is_selected = key == self.current_key
            opt.set_active(is_selected, self.current_reverse)

            if is_selected:
                # 选中样式：主题色背景 + 文字
                # 类似截图中的浅色背景 + 深色文字
                rgb = c.name()  # #RRGGBB
                # 使用透明度背景
                # 紧凑化 padding: 4px 12px -> 4px 8px
                opt.setStyleSheet(
                    f"""
                    QLabel {{
                        color: {rgb};
                        background-color: {rgb}1A; /* 10% opacity */
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: bold;
                    }}
                """
                )
            else:
                # 未选中样式：灰色文字
                # 紧凑化 padding: 4px 12px -> 4px 8px
                opt.setStyleSheet(
                    """
                    QLabel {
                        color: #666;
                        background-color: transparent;
                        padding: 4px 8px;
                        border-radius: 4px;
                        font-weight: normal;
                    }
                    QLabel:hover {
                        color: #333;
                        background-color: rgba(0, 0, 0, 0.05);
                    }
                """
                )


class ClickableQualityBadge(QFrame):
    """可点击的品质徽章 - 空心/实心圆环设计"""

    clicked = Signal(str)

    def __init__(self, quality: str, parent=None):
        super().__init__(parent)
        self.quality = quality
        self.is_collected = False

        self.setFixedSize(26, 26)  # 容器26px，由于margin:1px，实际圆圈24px
        self.setCursor(Qt.PointingHandCursor)
        self._update_display()

    def set_collected(self, is_collected: bool):
        self.is_collected = is_collected
        self._update_display()

    def _update_display(self):
        theme_val = qconfig.theme.value
        is_dark = (
            theme_val.name == "DARK"
            if hasattr(theme_val, "name")
            else theme_val == "Dark"
        )
        color_pair = QUALITY_COLORS.get(self.quality, (QColor("#666"), QColor("#999")))
        color = color_pair[1] if is_dark else color_pair[0]
        c_name = color.name()

        if self.is_collected:
            # 实心 24px (26px container - 2px margin)
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {c_name};
                    border: none;
                    border-radius: 12px;
                    min-width: 24px;
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                    margin: 1px;
                    padding: 0px;
                }}
            """
            )
        else:
            # 空心环 24px
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: transparent;
                    border: 2px solid {c_name};
                    border-radius: 12px;
                    min-width: 20px;
                    min-height: 20px;
                    max-width: 24px;
                    max-height: 24px;
                    margin: 1px;
                    padding: 0px;
                }}
            """
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.quality)
            event.accept()
        else:
            super().mousePressEvent(event)


class FishCard(CardWidget):
    """鱼类卡片组件 - 优化版 Scheme B"""

    fish_clicked = Signal(dict)
    collection_changed = Signal()

    def __init__(self, fish_data: dict, parent=None):
        super().__init__(parent)
        self.fish_data = fish_data
        self.fish_name = fish_data.get("name", "未知")

        # 加大卡片尺寸
        self.setFixedSize(160, 240)
        self.setCursor(Qt.PointingHandCursor)

        # 主布局
        self.v_layout = QVBoxLayout(self)
        # 减小左右边距以容纳5个圆点 (160 - 16 = 144px avail)
        self.v_layout.setContentsMargins(8, 12, 8, 12)
        self.v_layout.setSpacing(8)

        # 1. 顶部区域：图片 + 右上角地点标签
        # 使用 QFrame 作为图片容器
        self.img_container = QFrame()
        self.img_container.setFixedSize(136, 100)
        # 移除背景色，保持透明
        self.img_container.setStyleSheet("background-color: transparent;")

        # 图片
        self.image_label = QLabel(self.img_container)
        self.image_label.setAlignment(Qt.AlignCenter)
        img_path = pokedex.get_fish_image_path(self.fish_name)
        if img_path and img_path.exists():
            pix = QPixmap(str(img_path))
            # HiDPI 优化: 以 2x 尺寸缩放并设置 devicePixelRatio 使图片清晰锐利
            self.origin_pixmap = pix.scaled(
                240, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.origin_pixmap.setDevicePixelRatio(2.0)
            self.image_label.setPixmap(self.origin_pixmap)
            # image_label 的大小应基于 pixmap 的逻辑尺寸
            self.image_label.setFixedSize(120, 80)
        else:
            self.origin_pixmap = None
            self.image_label.setText("🐟")
            self.image_label.setFont(QFont("Segoe UI Emoji", 32))
            self.image_label.adjustSize()

        # 居中图片
        self._center_image()

        # 右上角地点标签 (覆盖在图片容器上)
        locs = fish_data.get("locations", [])
        loc_names = []
        for l in locs:
            raw = l.get("location", "")
            if isinstance(raw, list):
                loc_names.extend([x for x in raw if x])
            elif raw:
                loc_names.append(raw)
        if loc_names:
            loc_name = loc_names[0]
            loc_display = " · ".join(loc_names[:2]) + (
                f" +{len(loc_names) - 2}" if len(loc_names) > 2 else ""
            )
            if loc_name:
                # 定义一个容器QWidget作为标签，包含图标和文字
                self.loc_tag = QWidget(self.img_container)
                # 动态适配主题颜色
                from qfluentwidgets import qconfig, themeColor

                theme = qconfig.theme.value
                is_dark = (
                    theme.name == "DARK" if hasattr(theme, "name") else theme == "Dark"
                )

                if is_dark:
                    bg_color = "rgba(0, 0, 0, 0.6)"
                    txt_color = "#FFFFFF"
                    border_color = "rgba(255, 255, 255, 0.1)"
                else:
                    bg_color = "rgba(255, 255, 255, 0.65)"
                    txt_color = "#333333"
                    border_color = "rgba(0, 0, 0, 0.05)"

                # 样式优化: 适配深浅色
                self.loc_tag.setStyleSheet(
                    f"""
                    QWidget {{
                        background-color: {bg_color};
                        border: 1px solid {border_color};
                        border-radius: 6px;
                    }}
                    QLabel {{
                        background-color: transparent;
                        color: {txt_color};
                        font-family: 'Segoe UI', 'Microsoft YaHei UI';
                        font-size: 11px;
                        font-weight: 600;
                        border: none;
                    }}
                """
                )

                tag_layout = QHBoxLayout(self.loc_tag)
                tag_layout.setContentsMargins(6, 3, 6, 3)
                tag_layout.setSpacing(4)

                # 加载地点图标
                from src.config import cfg

                icon_path = (
                    cfg._get_base_path() / "resources" / "location" / f"{loc_name}.png"
                )
                if icon_path.exists():
                    icon_lbl = QLabel()
                    pix = QPixmap(str(icon_path))
                    scaled_icon = pix.scaled(
                        36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    scaled_icon.setDevicePixelRatio(2.0)
                    icon_lbl.setPixmap(scaled_icon)
                    icon_lbl.setFixedSize(18, 18)

                    tag_layout.addWidget(icon_lbl)

                # 地点文字
                txt_lbl = QLabel(loc_display)
                txt_lbl.setAlignment(Qt.AlignVCenter)
                tag_layout.addWidget(txt_lbl)

                self.loc_tag.adjustSize()
                # 放置在右上角
                self.loc_tag.move(136 - self.loc_tag.width() - 4, 4)

        self.v_layout.addWidget(self.img_container)

        # 2. 名称行 (左侧名称，右侧类型)
        name_row = QHBoxLayout()
        name_row.setSpacing(4)

        self.name_label = BodyLabel(self.fish_name)
        font = self.name_label.font()
        font.setPixelSize(16)
        font.setBold(True)
        self.name_label.setFont(font)
        name_row.addWidget(self.name_label)

        name_row.addStretch()

        # 优化 Rod 标识: [Icon] [Text]
        f_type = fish_data.get("type", "")

        rod_container = QWidget()
        rod_layout = QHBoxLayout(rod_container)
        rod_layout.setContentsMargins(0, 0, 0, 0)
        rod_layout.setSpacing(4)

        # 1. 尝试加载图标
        from src.config import cfg

        rod_icon_path = cfg._get_base_path() / "resources" / "rod" / f"{f_type}.png"

        if rod_icon_path.exists():
            icon_lbl = QLabel()
            pix = QPixmap(str(rod_icon_path))
            # HiDPI: 20x20 display -> 40x40 logical
            scaled = pix.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2.0)
            icon_lbl.setPixmap(scaled)
            icon_lbl.setFixedSize(20, 20)
            # 图片可能有自带阴影或边缘，保留透明背景
            icon_lbl.setStyleSheet("background: transparent;")
            rod_layout.addWidget(icon_lbl)
        else:
            # Fallback: 使用旧的色块逻辑
            type_char = f_type[2] if len(f_type) >= 3 else "竿"
            type_color = (
                "#5698c3"
                if "轻" in f_type
                else ("#ed9d51" if "中" in f_type else "#c24848")
            )
            fallback_badge = QLabel(type_char)
            fallback_badge.setAlignment(Qt.AlignCenter)
            fallback_badge.setFixedSize(20, 20)
            fallback_badge.setStyleSheet(
                f"""
                background-color: {type_color}; 
                color: white; 
                border-radius: 10px; 
                font-size: 11px; 
                font-weight: bold;
            """
            )
            rod_layout.addWidget(fallback_badge)

        # 2. 添加文字标签 (路亚/池塘)
        label_text = ""
        if "路亚" in f_type:
            label_text = "路亚"
        elif "池塘" in f_type:
            label_text = "池塘"

        if label_text:
            txt_lbl = QLabel(label_text)
            # 动态适配字体颜色
            # 这里的 parent (FishCard) 背景是透明的，所以参考主窗口背景
            # 我们直接用 themeColor 或者简单的灰黑色
            # 因为卡片本身在ScrollArea里，ScrollArea透明，底色是主窗口底色

            # 使用 fluent widgets 主题感知
            from qfluentwidgets import themeColor, isDarkTheme

            # isDarkTheme() 有时需要 app 实例，这里简单用 qconfig
            from qfluentwidgets import qconfig

            theme = qconfig.theme.value
            is_dark = (
                theme.name == "DARK" if hasattr(theme, "name") else theme == "Dark"
            )

            txt_c = "#BBBBBB" if is_dark else "#888888"

            txt_lbl.setStyleSheet(
                f"""
                color: {txt_c};
                font-size: 11px;
                font-weight: 600;
                font-family: 'Segoe UI', 'Microsoft YaHei';
            """
            )
            txt_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            rod_layout.addWidget(txt_lbl)

        name_row.addWidget(rod_container)

        self.v_layout.addLayout(name_row)

        # 3. 信息标签行 (时间 & 天气)
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        conds = locs[0].get("conditions", []) if locs else []
        times = set()
        weathers = set()
        if conds:
            for c in conds:
                times.update(c.get("time_of_day", []))
                weathers.update(c.get("weather", []))

        # 时间 Chips
        time_row = QHBoxLayout()
        time_row.setSpacing(4)
        sorted_times = sorted(
            list(times),
            key=lambda x: (
                ["凌晨", "清晨", "上午", "下午", "黄昏", "深夜"].index(x)
                if x in ["凌晨", "清晨", "上午", "下午", "黄昏", "深夜"]
                else 99
            ),
        )
        for i, t in enumerate(sorted_times):
            if i > 1:
                break
            lbl = QLabel(t)
            lbl.setStyleSheet(
                "background-color: rgba(0,0,0,0.05); color: #888; border-radius: 3px; padding: 1px 4px; font-size: 10px;"
            )
            time_row.addWidget(lbl)
        time_row.addStretch()
        info_layout.addLayout(time_row)

        # 天气 Icons
        weather_row = QHBoxLayout()
        weather_row.setSpacing(6)
        sorted_weathers = sorted(list(weathers))

        # Ensure cfg is available (it might be imported locally in other scopes)
        from src.config import cfg

        for i, w in enumerate(sorted_weathers):
            if i > 4:
                break  # 限制图标数量避免溢出

            icon_path = cfg._get_base_path() / "resources" / "weather" / f"{w}.png"
            if icon_path.exists():
                icon_lbl = QLabel()
                pix = QPixmap(str(icon_path))
                scaled = pix.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                scaled.setDevicePixelRatio(2.0)
                icon_lbl.setPixmap(scaled)
                icon_lbl.setFixedSize(16, 16)
                icon_lbl.setStyleSheet("background:transparent;border:none;")
                weather_row.addWidget(icon_lbl)

                text_lbl = QLabel(w)
                text_lbl.setStyleSheet(
                    "color: #666; font-size: 11px; background:transparent;"
                )
                weather_row.addWidget(text_lbl)
            else:
                lbl = QLabel(f"{w}")
                lbl.setStyleSheet("color: #999; font-size: 11px;")
                weather_row.addWidget(lbl)

        weather_row.addStretch()
        info_layout.addLayout(weather_row)

        self.v_layout.addLayout(info_layout)

        self.v_layout.addStretch()

        # 4. 底部品质圆点
        self.dots_container = QWidget()
        dots_layout = QHBoxLayout(self.dots_container)
        dots_layout.setContentsMargins(0, 0, 0, 0)
        # 减小圆点间距 4->2 以容纳 26px 的容器(实际显示24px)
        dots_layout.setSpacing(2)
        dots_layout.setAlignment(Qt.AlignLeft)

        self.quality_dots = {}
        for quality in QUALITIES:
            dot = ClickableQualityBadge(quality)
            dot.clicked.connect(self._on_dot_clicked)
            self.quality_dots[quality] = dot
            dots_layout.addWidget(dot)

        self.v_layout.addWidget(self.dots_container)

        self.update_collection_status()

    def _center_image(self):
        """居中图片"""
        self.image_label.move(
            (136 - self.image_label.width()) // 2,
            (100 - self.image_label.height()) // 2,
        )

    def enterEvent(self, event):
        """鼠标悬停动画"""
        img_path = pokedex.get_fish_image_path(self.fish_name)
        if img_path and img_path.exists():
            pix = QPixmap(str(img_path))
            # 放大 1.1 倍 (逻辑尺寸 132x88, 采样 264x176)
            scaled = pix.scaled(264, 176, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2.0)
            self.image_label.setPixmap(scaled)
            self.image_label.setFixedSize(132, 88)
            self._center_image()
        super().enterEvent(event)

    def leaveEvent(self, event):
        """鼠标离开复原"""
        if self.origin_pixmap:
            self.image_label.setPixmap(self.origin_pixmap)
            self.image_label.setFixedSize(120, 80)
            self._center_image()
        super().leaveEvent(event)

    def _on_dot_clicked(self, quality: str):
        """点击品质圆点"""
        pokedex.toggle_quality(self.fish_name, quality)
        self.update_collection_status()
        self.collection_changed.emit()

    def update_collection_status(self):
        """更新收集状态显示"""
        status = pokedex.get_collection_status(self.fish_name)
        for quality, dot in self.quality_dots.items():
            is_collected = status.get(quality) is not None
            dot.set_collected(is_collected)

    def mousePressEvent(self, event):
        # 检查是否点击在圆点区域
        if self.childAt(event.pos()) in self.quality_dots.values():
            return super().mousePressEvent(event)

        if event.button() == Qt.LeftButton:
            self.fish_clicked.emit(self.fish_data)
        super().mousePressEvent(event)


class PokedexInterface(QWidget):
    """图鉴主界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pokedexInterface")

        self.fish_cards = []

        # 筛选条件缓存
        self.current_filter_criteria = deepcopy(
            cfg.global_settings.get("pokedex_filter_criteria", {})
        )
        self.current_sort_key = "default"
        self.current_sort_reverse = False

        self._init_ui()
        self._sync_filter_button_state()
        self._load_fish_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(15)

        # 1. 顶部工具栏
        toolbar = QHBoxLayout()
        toolbar.setSpacing(15)

        # 进度标签 (胶囊样式: 55/56 | 248/280)
        self.progress_label = QLabel("0/0 | 0/0")
        self.progress_label.setObjectName("progressLabel")

        # 样式: 使用主题色作为文字颜色, 浅色背景
        from qfluentwidgets import themeColor

        c = themeColor()

        # 动态生成样式
        self.progress_label.setStyleSheet(
            f"""
            QLabel#progressLabel {{
                background-color: {c.name()}1A;  /* 主题色 10% 透明度 */
                color: {c.name()};               /* 主题色文字 */
                border-radius: 6px;
                padding: 6px 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 14px;
                font-weight: bold;
            }}
        """
        )
        toolbar.addWidget(self.progress_label)

        # 排序条 (插入到中间)
        toolbar.addStretch()
        self.sort_bar = SortBar()
        self.sort_bar.sortChanged.connect(self._on_sort_changed)
        toolbar.addWidget(self.sort_bar)

        toolbar.addStretch()

        from qfluentwidgets import TransparentToolButton

        # 筛选按钮 (图标化)
        self.filter_btn = TransparentToolButton(FluentIcon.FILTER, self)
        self.filter_btn.setToolTip("筛选")
        self.filter_btn.clicked.connect(self._on_filter_clicked)
        toolbar.addWidget(self.filter_btn)

        # 仅显示当前时段 ToggleButton
        self.time_filter_btn = ToggleButton("当前可钓")
        self.time_filter_btn.setCheckable(True)
        self.time_filter_btn.toggled.connect(self._on_time_filter_changed)
        self._update_time_filter_style(False)  # 初始化样式
        toolbar.addWidget(self.time_filter_btn)

        # 同步按钮 (图标化)
        self.sync_btn = TransparentToolButton(FluentIcon.SYNC, self)
        self.sync_btn.setToolTip("同步钓鱼记录")
        self.sync_btn.clicked.connect(self._on_sync_clicked)
        toolbar.addWidget(self.sync_btn)

        # 图鉴管理按钮（点击弹出菜单）
        self.pokedex_manage_btn = PushButton("图鉴管理", self)
        self.pokedex_manage_btn.setIcon(FluentIcon.EDIT)
        self.pokedex_manage_btn.setToolTip("图鉴操作菜单")
        self.pokedex_manage_btn.clicked.connect(self._show_pokedex_menu)
        toolbar.addWidget(self.pokedex_manage_btn)

        # 生成进度图按钮 (图标化)
        self.generate_image_btn = TransparentToolButton(FluentIcon.CAMERA, self)
        self.generate_image_btn.setToolTip("生成进度图")
        self.generate_image_btn.clicked.connect(self._on_generate_image_clicked)
        toolbar.addWidget(self.generate_image_btn)

        # 搜索框
        self.search_box = SearchLineEdit()
        self.search_box.setPlaceholderText("搜索鱼类...")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_box)

        layout.addLayout(toolbar)

        # 2. 卡片网格（滚动区域）
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )  # 隐藏滚动条但保留滚动功能

        # FlowLayout 容器（直接作为滚动区域内容）
        self.grid_container = QWidget()
        self.grid_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.grid_layout = FlowLayout(self.grid_container, needAni=False)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setHorizontalSpacing(12)
        self.grid_layout.setVerticalSpacing(12)

        scroll_area.setWidget(self.grid_container)

        # 3. 样式优化：透明背景
        # 移除 ScrollArea 和 Container 的背景色，使其透出主窗口背景
        scroll_area.setStyleSheet(
            "QScrollArea { background-color: transparent; border: none; }"
        )
        self.grid_container.setStyleSheet("QWidget { background-color: transparent; }")

        layout.addWidget(scroll_area)

    def _load_fish_list(self):
        """加载鱼类列表"""
        # 加载卡片
        self._refresh_cards()
        self._sync_filter_button_state()

    def _refresh_cards(self, fish_list=None):
        """刷新卡片显示"""
        # 清空现有卡片
        for card in self.fish_cards:
            self.grid_layout.removeWidget(card)
            card.deleteLater()
        self.fish_cards.clear()

        # 获取鱼类列表
        if fish_list is None:
            # 使用多条件筛选
            all_fish = pokedex.get_all_fish()

            # 1. 搜索优先 (基于全部鱼类)
            search_text = self.search_box.text().strip()
            if search_text:
                all_fish = pokedex.search_fish(search_text)

            # 2. 多条件筛选
            fish_list = pokedex.filter_fish_multi(
                all_fish, self.current_filter_criteria
            )

        # 应用时段筛选 (快捷按钮)
        if self.time_filter_btn.isChecked():
            current_time = pokedex.get_current_game_time()
            fish_list = pokedex.filter_by_time(fish_list, current_time)

        # 应用排序
        fish_list = pokedex.sort_fish(
            fish_list, self.current_sort_key, self.current_sort_reverse
        )

        # 创建卡片
        for fish in fish_list:
            card = FishCard(fish)
            card.fish_clicked.connect(self._on_card_clicked)
            card.collection_changed.connect(self._on_collection_changed)
            self.fish_cards.append(card)
            self.grid_layout.addWidget(card)

        # 触发一次布局更新以居中
        self._adjust_grid_centering()

    def resizeEvent(self, event):
        """窗口大小改变时，调整网格居中"""
        super().resizeEvent(event)
        self._adjust_grid_centering()

    def showEvent(self, event):
        """页面显示时，强制重新计算居中（解决初始尺寸不对的问题）"""
        super().showEvent(event)
        # 延迟执行以确保布局已完成
        QTimer.singleShot(50, self._adjust_grid_centering)

    def _adjust_grid_centering(self):
        """计算并设置网格边距以实现居中"""
        # 卡片宽度 160 + 间距 12
        CARD_WIDTH = 160
        SPACING = 12

        # 获取 scroll_area 的视口宽度 (减去滚动条可能的宽度)
        # self.grid_container 是 scroll_area 的 widget
        # 我们应该基于 scroll_area 的 viewport 宽度来计算
        # 但这里 self 是 PokedexInterface，它包含了 scroll_area

        # 找到 scroll_area
        scroll_area = self.findChild(QScrollArea)
        if not scroll_area:
            return

        viewport_width = scroll_area.viewport().width()

        # 计算能容纳的最大列数
        # width = n * card + (n-1) * spacing
        # width + spacing = n * (card + spacing)
        # n = (width + spacing) // (card + spacing)

        item_width_with_space = CARD_WIDTH + SPACING
        available_width = viewport_width

        # 至少 1 列
        n_columns = max(1, (available_width + SPACING) // item_width_with_space)

        # 计算内容实际占用的宽度
        content_width = n_columns * CARD_WIDTH + (n_columns - 1) * SPACING

        # 剩余空间
        remaining_space = available_width - content_width

        # 左右边距
        margin = max(0, remaining_space // 2)

        # 设置 grid_layout 的边距
        # 注意 FlowLayout 的 contentsMargins (left, top, right, bottom)
        # 保持原本的 top/bottom margin (虽然原本是0)
        self.grid_layout.setContentsMargins(margin, 0, 0, 0)
        # 只设置左边距即可推挤内容，或者左右都设置
        # 如果 FlowLayout 内部是左对齐的，设置左边距就能居中
        self.grid_layout.setContentsMargins(margin, 0, 0, 0)

        # 更新进度
        self._update_progress()

    def _update_progress(self):
        """更新收集进度"""
        # unpacked 4 values
        c_fish, t_fish, c_qual, t_qual = pokedex.get_progress()

        # Format: "55/56 | 248/280"
        text = f"{c_fish}/{t_fish} | {c_qual}/{t_qual}"
        self.progress_label.setText(text)

    def _on_time_filter_changed(self, checked):
        """时段筛选变化"""
        self._update_time_filter_style(checked)
        self._refresh_cards()

    def _update_time_filter_style(self, checked):
        """更新按钮样式 - 现代胶囊风格"""
        from qfluentwidgets import themeColor

        c = themeColor()

        # 通用圆角和字体设置
        base_style = """
            ToggleButton {
                border-radius: 6px;
                padding: 5px 12px;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-weight: 500;
            }
        """

        if checked:
            # 激活状态：实心主题色 + 阴影效果
            self.time_filter_btn.setStyleSheet(
                base_style
                + f"""
                ToggleButton {{
                    background-color: {c.name()};
                    color: white;
                    border: 1px solid {c.name()};
                }}
                ToggleButton:hover {{
                    background-color: {c.lighter(110).name()};
                }}
                ToggleButton:pressed {{
                    background-color: {c.darker(110).name()};
                }}
            """
            )
        else:
            # 未激活状态：透明背景 + 边框 + 文字颜色
            # 使用主题色作为文字和边框颜色，使其看起来像 outline button
            self.time_filter_btn.setStyleSheet(
                base_style
                + f"""
                ToggleButton {{
                    background-color: transparent;
                    color: {c.name()};
                    border: 1px solid {c.name()};
                }}
                ToggleButton:hover {{
                    background-color: {c.name()}1a;  /* 10% 透明度背景 */
                }}
                ToggleButton:pressed {{
                    background-color: {c.name()}33;  /* 20% 透明度背景 */
                }}
            """
            )

    def _on_filter_clicked(self):
        """点击筛选按钮"""
        # 使用 FilterDrawer 侧边抽屉
        # parent 设为 self.window() 以确保覆盖全屏（包括标题栏下方的内容区域）
        from src.gui.components import FilterDrawer

        self.filter_drawer = FilterDrawer(self.window(), self.current_filter_criteria)
        self.filter_drawer.filterChanged.connect(self._on_multi_filter_changed)

    def _on_multi_filter_changed(self, criteria):
        """筛选条件变化"""
        self.current_filter_criteria = criteria
        cfg.global_settings["pokedex_filter_criteria"] = deepcopy(criteria)
        cfg.save()
        self._refresh_cards()

        # 更新筛选按钮状态（如果有筛选，高亮显示）
        # 更新筛选按钮状态（如果有筛选，高亮显示）
        if criteria:
            count = sum(len(v) for v in criteria.values())
            # 图标按钮不要设置文字，改为更新 Tooltip
            self.filter_btn.setToolTip(f"筛选 ({count})")
            # 设置选中状态以高亮
            self.filter_btn.setChecked(True)
        else:
            self.filter_btn.setToolTip("筛选")
            self.filter_btn.setChecked(False)

    def _sync_filter_button_state(self):
        """Sync filter button state from saved criteria."""
        criteria = self.current_filter_criteria or {}
        if criteria:
            count = sum(len(v) for v in criteria.values())
            self.filter_btn.setToolTip(f"Filter ({count})")
            self.filter_btn.setChecked(True)
            return

        self.filter_btn.setToolTip("Filter")
        self.filter_btn.setChecked(False)

    def _update_filter_button_state(self):
        """同步筛选按钮高亮和提示。"""
        criteria = self.current_filter_criteria or {}
        if criteria:
            count = sum(len(v) for v in criteria.values())
            self.filter_btn.setToolTip(f"绛涢€?({count})")
            self.filter_btn.setChecked(True)
            return

        self.filter_btn.setToolTip("绛涢€?")
        self.filter_btn.setChecked(False)

    def _on_search_changed(self, text):
        """搜索变化"""
        self._refresh_cards()

    def _on_card_clicked(self, fish_data):
        """点击卡片"""
        dialog = FishDetailDialog(fish_data, self)
        dialog.collection_changed.connect(self._on_collection_changed)
        dialog.exec()

    def _on_collection_changed(self):
        """收集状态变化"""
        # 刷新所有卡片状态
        for card in self.fish_cards:
            card.update_collection_status()
        self._update_progress()

    def _on_sync_clicked(self):
        """同步钓鱼记录"""
        new_count = pokedex.sync_from_records()

        # 刷新显示
        for card in self.fish_cards:
            card.update_collection_status()
        self._update_progress()

        # 显示提示
        if new_count > 0:
            InfoBar.success(
                title="同步成功",
                content=f"从钓鱼记录中新增了 {new_count} 条收集记录",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        else:
            InfoBar.info(
                title="同步完成",
                content="没有发现新的收集记录",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def _show_pokedex_menu(self):
        """显示图鉴操作菜单"""
        menu = RoundMenu(parent=self)

        # 添加"一键全图鉴"选项
        action1 = Action(FluentIcon.COMPLETED, "一键全图鉴")
        action1.triggered.connect(self._on_fill_all_clicked)
        menu.addAction(action1)

        # 添加"清空全图鉴"选项
        action2 = Action(FluentIcon.DELETE, "清空全图鉴")
        action2.triggered.connect(self._on_clear_all_clicked)
        menu.addAction(action2)

        # 在按钮下方弹出菜单
        button_pos = self.pokedex_manage_btn.mapToGlobal(
            self.pokedex_manage_btn.rect().bottomLeft()
        )
        menu.exec(button_pos)

    def _on_fill_all_clicked(self):
        """一键点满图鉴"""
        w = MessageBox(
            "确认一键全图鉴",
            "将把当前账号图鉴全部标记为已收集（重量记为 0），是否继续？",
            self.window(),
        )
        w.yesButton.setText("确认点满")
        w.cancelButton.setText("取消")

        if not w.exec():
            return

        changed_count = pokedex.mark_all_pokedex_caught()
        self._on_collection_changed()

        if changed_count > 0:
            InfoBar.success(
                title="操作成功",
                content=f"已点满 {changed_count} 个鱼种的图鉴",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        else:
            InfoBar.info(
                title="无需操作",
                content="当前图鉴已经全部点满",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def _on_clear_all_clicked(self):
        """一键清空图鉴"""
        w = MessageBox(
            "确认清空全图鉴",
            "将清空当前账号图鉴全部收集状态，此操作不可恢复，是否继续？",
            self.window(),
        )
        w.yesButton.setText("确认清空")
        w.cancelButton.setText("取消")

        if not w.exec():
            return

        changed_count = pokedex.clear_all_pokedex()
        self._on_collection_changed()

        if changed_count > 0:
            InfoBar.success(
                title="操作成功",
                content=f"已清空 {changed_count} 个鱼种的图鉴状态",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )
        else:
            InfoBar.info(
                title="无需操作",
                content="当前图鉴已经是清空状态",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self,
            )

    def _on_generate_image_clicked(self):
        """生成进度图"""
        from src.pokedex_image_generator import pokedex_image_generator
        from pathlib import Path
        from qfluentwidgets import FluentIcon
        from PySide6.QtWidgets import (
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QFrame,
            QPushButton,
            QGraphicsDropShadowEffect,
        )
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("选择图鉴类型")
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        dialog.setAttribute(Qt.WA_TranslucentBackground)
        dialog.setFixedSize(400, 250)

        # 主容器
        container = QFrame(dialog)
        container.setFixedSize(400, 250)
        container.setObjectName("dialogContainer")
        container.setStyleSheet(
            """
            QFrame#dialogContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FAFBFC, stop:1 #F5F7FA);
                border-radius: 16px;
                border: 1px solid #E8ECF0;
            }
        """
        )

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(container)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 8)
        container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 顶部栏（标题 + 关闭按钮）
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet("background-color: transparent;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 10, 20, 10)

        title = QLabel("选择图鉴类型")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setStyleSheet("color: #8B7355; background: transparent;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(36, 36)
        close_btn.setFont(QFont("Arial", 24))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QPushButton {
                color: #A0826D;
                background: transparent;
                border: none;
                border-radius: 18px;
            }
            QPushButton:hover {
                background-color: #F5E6D3;
                color: #8B7355;
            }
            QPushButton:pressed {
                background-color: #D4C5B0;
            }
        """
        )
        close_btn.clicked.connect(dialog.reject)
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # 内容区
        content = QFrame()
        content.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 20, 30, 30)
        content_layout.setSpacing(20)

        # 提示文字
        hint = QLabel("请选择要生成的图鉴类型：")
        hint.setFont(QFont("Microsoft YaHei", 13))
        hint.setStyleSheet("color: #666666; background: transparent;")
        hint.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(hint)

        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # 全部图鉴按钮
        all_btn = QPushButton("全部图鉴")
        all_btn.setFixedSize(150, 45)
        all_btn.setFont(QFont("Microsoft YaHei", 13))
        all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #E8DCC8;
                color: #8B7355;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D4C5B0;
            }
            QPushButton:pressed {
                background-color: #C4B5A0;
            }
        """
        )
        all_btn.clicked.connect(lambda: self._generate_and_close(dialog, "all"))
        button_layout.addWidget(all_btn)

        # 未收集图鉴按钮
        uncollected_btn = QPushButton("未收集图鉴")
        uncollected_btn.setFixedSize(150, 45)
        uncollected_btn.setFont(QFont("Microsoft YaHei", 13))
        uncollected_btn.setCursor(Qt.PointingHandCursor)
        uncollected_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #E8DCC8;
                color: #8B7355;
                border: none;
                border-radius: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #D4C5B0;
            }
            QPushButton:pressed {
                background-color: #C4B5A0;
            }
        """
        )
        uncollected_btn.clicked.connect(
            lambda: self._generate_and_close(dialog, "uncollected")
        )
        button_layout.addWidget(uncollected_btn)

        content_layout.addLayout(button_layout)
        main_layout.addWidget(content)

        # 居中显示
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(container)

        dialog.exec()

    def _generate_and_close(self, dialog: QDialog, image_type: str):
        """生成图鉴并关闭对话框"""
        from src.pokedex_image_generator import pokedex_image_generator

        dialog.accept()

        try:
            if image_type == "all":
                path = pokedex_image_generator.generate_pokedex_image("all")
                content = f"全部图鉴已生成: {path.name}"
            else:
                path = pokedex_image_generator.generate_pokedex_image("uncollected")
                content = f"未收集图鉴已生成: {path.name}"

            InfoBar.success(
                title="生成成功",
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self,
            )
        except Exception as e:
            InfoBar.error(
                title="生成失败",
                content=f"生成进度图时出错: {str(e)}",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self,
            )

    def _on_sort_changed(self, key, reverse):
        """排序变化"""
        self.current_sort_key = key
        self.current_sort_reverse = reverse
        self._refresh_cards()

    def reload_data(self):
        """重新加载数据（账号切换时调用）"""
        pokedex.reload()
        self.current_filter_criteria = deepcopy(
            cfg.global_settings.get("pokedex_filter_criteria", {})
        )
        self._sync_filter_button_state()
        self._refresh_cards()
