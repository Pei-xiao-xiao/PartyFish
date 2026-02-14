from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QWidget,
    QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor, QFont, QPainter
from qfluentwidgets import (
    SubtitleLabel,
    BodyLabel,
    StrongBodyLabel,
    PushButton,
    CardWidget,
    qconfig,
    LineEdit,
)
from src.pokedex import pokedex, QUALITIES
from src.gui.components import QUALITY_COLORS


class QualityDot(QFrame):
    """品质圆点，可点击切换收集状态 - 优化视觉效果"""

    clicked = Signal()

    def __init__(self, quality: str, parent=None):
        super().__init__(parent)
        self.quality = quality
        self.is_collected = False

        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

        self._update_style()

    def set_status(self, is_collected: bool):
        """设置收集状态"""
        self.is_collected = is_collected
        self._update_style()

    def _update_style(self):
        """更新样式 - 添加悬停效果"""
        theme_val = qconfig.theme.value
        is_dark = (
            theme_val.name == "DARK"
            if hasattr(theme_val, "name")
            else theme_val == "Dark"
        )
        color_pair = QUALITY_COLORS.get(self.quality, (QColor("#666"), QColor("#999")))
        color = color_pair[1] if is_dark else color_pair[0]

        if self.is_collected:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {color.name()};
                    border: none;
                    border-radius: 16px;
                }}
                QFrame:hover {{
                    background-color: {color.lighter(110).name()};
                }}
            """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: transparent;
                    border: 3px solid {color.name()};
                    border-radius: 16px;
                }}
                QFrame:hover {{
                    background-color: {color.name()}33;
                }}
            """
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class FishDetailDialog(QDialog):
    """鱼类详情弹窗 - 现代化设计 优化版"""

    collection_changed = Signal()

    def __init__(self, fish_data: dict, parent=None):
        super().__init__(parent)
        self.fish_data = fish_data
        self.fish_name = fish_data.get("name", "未知")

        self.setWindowTitle(self.fish_name)
        # 无边框全屏窗口
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        # 获取顶级父窗口
        self.main_window = parent.window() if parent else None

        if self.main_window:
            self.resize(self.main_window.size())
        else:
            self.resize(1000, 700)

        self._init_ui()
        self._load_collection_status()

    def _init_ui(self):
        from src.config import cfg

        # 主容器（居中显示）
        self.container = QFrame(self)
        self.container.setFixedSize(420, 540)
        self.container.setObjectName("dialogContainer")
        self.container.setStyleSheet(
            """
            QFrame#dialogContainer {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FAFBFC, stop:1 #F5F7FA);
                border-radius: 24px;
                border: 1px solid #E8ECF0;
            }
        """
        )

        # 添加阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 10)
        self.container.setGraphicsEffect(shadow)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ============ 顶部栏（标题 + 关闭按钮）============
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet(
            """
            QFrame {
                background-color: transparent;
                border-bottom: none;
            }
        """
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 12, 20, 12)

        title = SubtitleLabel(self.fish_name)
        title.setFont(QFont(cfg.get_ui_font(), 16, QFont.Bold))
        title.setStyleSheet("color: #8B7355; background: transparent; border: none;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # 关闭按钮 - 优化设计
        close_btn = QLabel("×")
        close_btn.setFixedSize(36, 36)
        close_btn.setAlignment(Qt.AlignCenter)
        close_btn.setFont(QFont("Arial", 24))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(
            """
            QLabel {
                color: #A0826D;
                background: transparent;
                border: none;
                border-radius: 18px;
            }
            QLabel:hover {
                background-color: #F5E6D3;
                color: #8B7355;
            }
        """
        )
        close_btn.mousePressEvent = lambda e: self.close()
        header_layout.addWidget(close_btn)

        main_layout.addWidget(header)

        # ============ 内容区 ============
        content = QFrame()
        content.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 0, 24, 24)
        content_layout.setSpacing(20)

        # 1. 鱼图和名称卡片
        fish_card = QFrame()
        fish_card.setFixedHeight(160)
        fish_card.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 2px solid #F5E6D3;
            }
        """
        )

        # 为鱼图卡片添加轻微阴影
        fish_shadow = QGraphicsDropShadowEffect(fish_card)
        fish_shadow.setBlurRadius(15)
        fish_shadow.setColor(QColor(0, 0, 0, 20))
        fish_shadow.setOffset(0, 4)
        fish_card.setGraphicsEffect(fish_shadow)

        fish_layout = QVBoxLayout(fish_card)
        fish_layout.setContentsMargins(20, 20, 20, 20)
        fish_layout.setSpacing(12)

        # 鱼图
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedHeight(80)

        image_path = pokedex.get_fish_image_path(self.fish_name)
        if image_path and image_path.exists():
            pixmap = QPixmap(str(image_path))
            # HiDPI 优化: 以 2x 尺寸缩放并设置 devicePixelRatio 使图片清晰锐利
            scaled = pixmap.scaled(
                240, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            scaled.setDevicePixelRatio(2.0)
            image_label.setPixmap(scaled)
        else:
            image_label.setText("🐟")
            image_label.setFont(QFont("Segoe UI Emoji", 48))
        image_label.setStyleSheet("background: transparent; border: none;")

        fish_layout.addWidget(image_label)

        # 标签行
        tags_row = QHBoxLayout()
        tags_row.setSpacing(10)
        tags_row.setAlignment(Qt.AlignCenter)

        locations = self.fish_data.get("locations", [])
        all_loc_names = []
        for loc in locations:
            raw_loc = loc.get("location", "")
            if isinstance(raw_loc, list):
                all_loc_names.extend([x for x in raw_loc if x])
            elif raw_loc:
                all_loc_names.append(raw_loc)
        max_badges = 1
        for location_name in all_loc_names[:max_badges]:
            loc_badge = self._create_badge(
                cfg._get_base_path()
                / "resources"
                / "location"
                / f"{location_name}.png",
                location_name,
                "#2D5016",
                "#D4E7C5",
            )
            tags_row.addWidget(loc_badge)
        if len(all_loc_names) > max_badges:
            more_lbl = QLabel(f"+{len(all_loc_names) - max_badges}")
            more_lbl.setStyleSheet(
                "color: #2D5016; font-size: 12px; font-weight: 600; background: #D4E7C5; border-radius: 8px; padding: 2px 6px;"
            )
            more_lbl.setToolTip(", ".join(all_loc_names[max_badges:]))
            tags_row.addWidget(more_lbl)

        fish_type = self.fish_data.get("type", "")
        if fish_type:
            rod_badge = self._create_badge(
                cfg._get_base_path() / "resources" / "rod" / f"{fish_type}.png",
                fish_type,
                "#8B4513",
                "#F4E4D7",
            )
            tags_row.addWidget(rod_badge)

        fish_layout.addLayout(tags_row)

        content_layout.addWidget(fish_card)

        # 2. 条件卡片
        for loc in locations:
            conditions = loc.get("conditions", [])
            if not conditions:
                continue
            cond = conditions[0]

            cond_frame = QFrame()
            cond_frame.setStyleSheet(
                """
                QFrame {
                    background-color: white;
                    border-radius: 16px;
                    border: 2px solid #F5E6D3;
                }
            """
            )
            cond_layout = QHBoxLayout(cond_frame)
            cond_layout.setContentsMargins(0, 16, 0, 16)
            cond_layout.setSpacing(0)

            raw_loc = loc.get("location", "")
            loc_name = ", ".join(raw_loc) if isinstance(raw_loc, list) else raw_loc
            if len(locations) > 1 and loc_name:
                cond_layout.addWidget(self._create_cell("地点", loc_name), 1)
                cond_layout.addWidget(self._separator())

            season = cond.get("season", [])
            if season:
                cond_layout.addWidget(self._create_cell("季节", ", ".join(season)), 1)
                cond_layout.addWidget(self._separator())

            time_of_day = cond.get("time_of_day", [])
            if time_of_day:
                cond_layout.addWidget(
                    self._create_cell("时间", ", ".join(time_of_day)), 1
                )
                cond_layout.addWidget(self._separator())

            weather = cond.get("weather", [])
            if weather:
                cond_layout.addWidget(self._create_weather_cell(weather, cfg), 1)

            content_layout.addWidget(cond_frame)

        # 3. 品质区域
        quality_frame = QFrame()
        quality_frame.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 2px solid #F5E6D3;
            }
        """
        )
        quality_main_layout = QVBoxLayout(quality_frame)
        quality_main_layout.setContentsMargins(20, 16, 20, 16)
        quality_main_layout.setSpacing(12)

        # 品质标题与圆点行
        quality_header = QHBoxLayout()
        quality_header.setSpacing(12)

        quality_label = StrongBodyLabel("品质")
        quality_label.setStyleSheet(
            "color: #8B7355; font-size: 14px; background: transparent; border: none;"
        )
        quality_header.addWidget(quality_label)

        quality_header.addSpacing(10)

        # 品质圆点 - 直接放在 Header 行
        self.quality_dots = {}
        for quality in QUALITIES:
            dot = QualityDot(quality)
            dot.clicked.connect(lambda q=quality: self._on_quality_clicked(q))
            dot.setToolTip(quality)
            self.quality_dots[quality] = dot
            quality_header.addWidget(dot)

        quality_header.addStretch()

        # 功能按钮 (全选/清空)
        self.action_btn = PushButton("全选")
        self.action_btn.setFixedSize(64, 32)
        self.action_btn.setStyleSheet(
            """
            PushButton {
                background-color: #E8DCC8;
                color: #8B7355;
                border: none;
                border-radius: 16px;
                font-size: 13px;
                font-weight: bold;
            }
            PushButton:hover {
                background-color: #D4C5B0;
            }
            PushButton:pressed {
                background-color: #C4B5A0;
            }
        """
        )
        self.action_btn.clicked.connect(self._on_action_clicked)
        quality_header.addWidget(self.action_btn)

        quality_main_layout.addLayout(quality_header)

        content_layout.addWidget(quality_frame)

        # 4. 最大重量
        weight_frame = QFrame()
        weight_frame.setStyleSheet(
            """
            QFrame {
                background-color: white;
                border-radius: 16px;
                border: 2px solid #F5E6D3;
            }
        """
        )
        weight_layout = QHBoxLayout(weight_frame)
        weight_layout.setContentsMargins(20, 16, 20, 16)
        weight_layout.setSpacing(16)

        weight_label = StrongBodyLabel("最大重量")
        weight_label.setStyleSheet(
            "color: #8B7355; font-size: 14px; background: transparent; border: none;"
        )
        weight_layout.addWidget(weight_label)
        weight_layout.addStretch()

        self.weight_input = LineEdit()
        self.weight_input.setPlaceholderText("输入kg")
        self.weight_input.setFixedWidth(100)
        self.weight_input.setAlignment(Qt.AlignCenter)
        self.weight_input.setStyleSheet(
            """
            LineEdit {
                background-color: #FFFAF0;
                border: 2px solid #E8DCC8;
                border-radius: 12px;
                padding: 8px 12px;
                font-size: 14px;
                color: #8B7355;
            }
            LineEdit:focus {
                border: 2px solid #D4C5B0;
            }
        """
        )
        weight_layout.addWidget(self.weight_input)

        kg_label = BodyLabel("kg")
        kg_label.setStyleSheet(
            "color: #A0826D; font-size: 14px; background: transparent; border: none;"
        )
        weight_layout.addWidget(kg_label)

        content_layout.addWidget(weight_frame)

        # 5. 说明文字区域（如果有）
        description = self.fish_data.get("description", "")
        if description:
            desc_frame = QFrame()
            desc_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #FFF9F0;
                    border-radius: 16px;
                    border: 1px solid #F5E6D3;
                }
            """
            )
            desc_layout = QVBoxLayout(desc_frame)
            desc_layout.setContentsMargins(16, 12, 16, 12)

            desc_label = BodyLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet(
                "color: #A0826D; font-size: 13px; line-height: 1.6; background: transparent; border: none;"
            )
            desc_layout.addWidget(desc_label)

            content_layout.addWidget(desc_frame)

        content_layout.addStretch()

        main_layout.addWidget(content, 1)

    def _create_badge(
        self, icon_path, text: str, text_color: str, bg_color: str
    ) -> QFrame:
        """创建图标+文字徽章 - 优化设计"""
        badge = QFrame()
        layout = QHBoxLayout(badge)
        layout.setContentsMargins(10, 6, 12, 6)
        layout.setSpacing(6)

        if icon_path.exists():
            icon = QLabel()
            pixmap = QPixmap(str(icon_path))
            # HiDPI 优化: 以 2x 尺寸缩放并设置 devicePixelRatio 使图标清晰锐利
            scaled = pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2.0)
            icon.setPixmap(scaled)
            icon.setFixedSize(18, 18)
            icon.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(icon)

        label = QLabel(text)
        label.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(label)

        badge.setStyleSheet(
            f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 16px;
            }}
        """
        )

        return badge

    def _create_cell(self, title: str, value: str) -> QWidget:
        """创建信息单元格"""
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        t = BodyLabel(title)
        t.setStyleSheet(
            "color: #A0826D; font-size: 12px; background: transparent; border: none;"
        )
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)

        v = StrongBodyLabel(value)
        v.setStyleSheet(
            "color: #5D4E37; font-size: 14px; font-weight: bold; background: transparent; border: none;"
        )
        v.setAlignment(Qt.AlignCenter)
        layout.addWidget(v)

        return cell

    def _create_weather_cell(self, weather_list: list, cfg) -> QWidget:
        """创建天气单元格"""
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        t = BodyLabel("天气")
        t.setStyleSheet(
            "color: #A0826D; font-size: 12px; background: transparent; border: none;"
        )
        t.setAlignment(Qt.AlignCenter)
        layout.addWidget(t)

        icons = QHBoxLayout()
        icons.setSpacing(6)
        icons.setAlignment(Qt.AlignCenter)

        for w in weather_list:
            path = cfg._get_base_path() / "resources" / "weather" / f"{w}.png"
            if path.exists():
                item = QHBoxLayout()
                item.setSpacing(4)

                icon = QLabel()
                pixmap = QPixmap(str(path))
                scaled = pixmap.scaled(
                    48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                scaled.setDevicePixelRatio(2.0)
                icon.setPixmap(scaled)
                icon.setFixedSize(24, 24)
                icon.setStyleSheet("background:transparent;border:none;")
                item.addWidget(icon)

                text = QLabel(w)
                text.setStyleSheet(
                    "color: #5D4E37; font-size: 14px; font-weight: bold; background: transparent; border: none;"
                )
                item.addWidget(text)

                icons.addLayout(item)

        layout.addLayout(icons)
        return cell

    def _separator(self) -> QFrame:
        """分隔线"""
        s = QFrame()
        s.setFixedWidth(1)
        s.setFixedHeight(40)
        s.setStyleSheet("background-color: #F5E6D3;")
        return s

    def _load_collection_status(self):
        """加载收集状态"""
        status = pokedex.get_collection_status(self.fish_name)
        collected_count = 0
        for quality, weight in status.items():
            if quality in self.quality_dots:
                is_collected = weight is not None
                self.quality_dots[quality].set_status(is_collected)
                if is_collected:
                    collected_count += 1

        # 更新按钮文本: 全收齐了显示"清空"，否则显示"全选"
        if collected_count == len(QUALITIES):
            self.action_btn.setText("清空")
        else:
            self.action_btn.setText("全选")

        max_weight = max((w for w in status.values() if w), default=0)
        if max_weight > 0:
            self.weight_input.setText(f"{max_weight:.1f}")
        else:
            self.weight_input.clear()

    def _on_quality_clicked(self, quality: str):
        """品质点击事件"""
        pokedex.toggle_quality(self.fish_name, quality)
        self._load_collection_status()
        self.collection_changed.emit()

    def _on_action_clicked(self):
        """处理 按钮点击 (全选/清空)"""
        if self.action_btn.text() == "清空":
            pokedex.clear_all(self.fish_name)
        else:
            pokedex.mark_all_caught(self.fish_name)

        self._load_collection_status()
        self.collection_changed.emit()

    def resizeEvent(self, event):
        """窗口大小变化时调整子控件"""
        super().resizeEvent(event)
        # 容器居中
        if hasattr(self, "container"):
            x = (self.width() - self.container.width()) // 2
            y = (self.height() - self.container.height()) // 2
            self.container.move(x, y)

    def showEvent(self, event):
        """显示时居中容器并覆盖主窗口"""
        super().showEvent(event)

        # 确保覆盖主窗口
        if self.main_window:
            # 获取主窗口的几何信息（相对于屏幕）
            geo = self.main_window.geometry()
            self.setGeometry(geo)

        # 容器居中
        if hasattr(self, "container"):
            self.resizeEvent(None)  # 复用居中逻辑

    def paintEvent(self, event):
        """绘制背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 绘制几乎透明的背景以捕获点击事件
        # Alpha=1 (1/255) 几乎不可见，但足以让窗口接收鼠标事件
        painter.setBrush(QColor(0, 0, 0, 1))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

    def mousePressEvent(self, event):
        """点击窗口外部关闭"""
        # 检查是否点击在主内容区域外（考虑阴影边距）
        if hasattr(self, "container"):
            container_rect = self.container.geometry().adjusted(10, 10, -10, -10)
            if not container_rect.contains(event.pos()):
                self.close()
        super().mousePressEvent(event)
