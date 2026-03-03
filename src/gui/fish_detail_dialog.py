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
    qconfig,
    LineEdit,
)

from src.pokedex import pokedex, QUALITIES
from src.gui.components import QUALITY_COLORS


class QualityDot(QFrame):
    """品质圆点，可点击切换收集状态。"""

    clicked = Signal()

    def __init__(self, quality: str, parent=None):
        super().__init__(parent)
        self.quality = quality
        self.is_collected = False

        self.setFixedSize(30, 30)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style()

    def set_status(self, is_collected: bool):
        self.is_collected = is_collected
        self._update_style()

    def _update_style(self):
        theme_val = qconfig.theme.value
        is_dark = (
            theme_val.name == "DARK"
            if hasattr(theme_val, "name")
            else theme_val == "Dark"
        )
        color_pair = QUALITY_COLORS.get(self.quality, (QColor("#666"), QColor("#999")))
        color = color_pair[1] if is_dark else color_pair[0]
        idle_bg = "#2F3642" if is_dark else "#FFFFFF"

        if self.is_collected:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {color.name()};
                    border: 2px solid {color.name()};
                    border-radius: 15px;
                }}
                QFrame:hover {{
                    background-color: {color.lighter(108).name()};
                    border-color: {color.lighter(108).name()};
                }}
            """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {idle_bg};
                    border: 3px solid {color.name()};
                    border-radius: 15px;
                }}
                QFrame:hover {{
                    background-color: {color.name()}22;
                }}
            """
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class FishDetailDialog(QDialog):
    """鱼类详情弹窗。"""

    collection_changed = Signal()

    def __init__(self, fish_data: dict, parent=None):
        super().__init__(parent)
        self.fish_data = fish_data
        self.fish_name = fish_data.get("name", "未知")
        self._card_frames = []
        self._badge_specs = []
        self._meta_title_labels = []
        self._meta_value_labels = []
        self._separator_frames = []
        self.empty_location_label = None

        self.setWindowTitle(self.fish_name)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)

        self.main_window = parent.window() if parent else None
        if self.main_window:
            self.resize(self.main_window.size())
        else:
            self.resize(1000, 700)

        self._init_ui()
        self._load_collection_status()
        self._apply_theme_styles()

    def _is_dark_theme(self) -> bool:
        theme_val = qconfig.theme.value
        if hasattr(theme_val, "name"):
            return str(theme_val.name).upper() == "DARK"
        return str(theme_val).lower() == "dark"

    @staticmethod
    def _rgba(color: QColor, alpha: int) -> str:
        return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"

    def _theme_palette(self) -> dict:
        if self._is_dark_theme():
            return {
                "overlay_alpha": 96,
                "container_bg": "#2C333D",
                "container_border": "#4A5564",
                "title_text": "#E5E7EB",
                "close_color": "#DAA164",
                "close_hover_bg": "rgba(218, 161, 100, 0.20)",
                "close_pressed_bg": "rgba(218, 161, 100, 0.30)",
                "section_title": "#D8B38D",
                "card_bg": "#363E49",
                "card_border": "#4B5667",
                "meta_title": "#AAB3C2",
                "meta_value": "#E5E7EB",
                "empty_text": "#98A1AF",
                "action_bg": "#675A4A",
                "action_hover": "#756754",
                "action_pressed": "#564A3C",
                "action_text": "#E7D8C4",
                "input_bg": "#2A313B",
                "input_border": "#5A6676",
                "input_focus": "#7A879A",
                "input_text": "#E5E7EB",
                "unit_text": "#AAB3C2",
                "separator": "rgba(229, 231, 235, 0.18)",
                "rarity_text": "#F8D27A",
                "rarity_bg": "rgba(226, 188, 105, 0.18)",
                "rarity_border": "rgba(226, 188, 105, 0.60)",
            }

        return {
            "overlay_alpha": 28,
            "container_bg": "#EEF1F5",
            "container_border": "#DCE2E8",
            "title_text": "#8B6D4E",
            "close_color": "#A56536",
            "close_hover_bg": "#EFE2D4",
            "close_pressed_bg": "#E5D4C0",
            "section_title": "#8B6D4E",
            "card_bg": "#F8F5F1",
            "card_border": "#E3D4C1",
            "meta_title": "#A0826D",
            "meta_value": "#4E3E2D",
            "empty_text": "#A0826D",
            "action_bg": "#D8CCBA",
            "action_hover": "#CABCA7",
            "action_pressed": "#B9AB95",
            "action_text": "#8B6D4E",
            "input_bg": "#FBF4E8",
            "input_border": "#D8C6AD",
            "input_focus": "#C7B298",
            "input_text": "#8B6D4E",
            "unit_text": "#A0826D",
            "separator": "#E3D4C1",
            "rarity_text": "#D29421",
            "rarity_bg": "#F8EBCF",
            "rarity_border": "#E2BC69",
        }

    def _init_ui(self):
        from src.config import cfg

        self.container = QFrame(self)
        self.container.setFixedSize(402, 616)
        self.container.setObjectName("dialogContainer")
        self.container.setStyleSheet(
            """
            QFrame#dialogContainer {
                background-color: #EEF1F5;
                border-radius: 28px;
                border: 1px solid #DCE2E8;
            }
        """
        )

        container_shadow = QGraphicsDropShadowEffect(self.container)
        container_shadow.setBlurRadius(28)
        container_shadow.setColor(QColor(0, 0, 0, 42))
        container_shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(container_shadow)

        main_layout = QVBoxLayout(self.container)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        locations = self._collect_location_names()
        season_values, time_values, weather_values = self._collect_condition_values()

        top_bar = QFrame()
        top_bar.setFixedHeight(34)
        top_bar.setStyleSheet("background: transparent; border: none;")
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(2, 0, 2, 0)
        top_bar_layout.setSpacing(8)

        name_label = SubtitleLabel(self.fish_name)
        name_label.setFont(QFont(cfg.get_ui_font(), 16, QFont.Bold))
        name_label.setStyleSheet(
            "color: #8B6D4E; background: transparent; border: none;"
        )
        self.name_label = name_label
        top_bar_layout.addWidget(name_label)
        top_bar_layout.addStretch()

        close_btn = PushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFont(QFont("Arial", 24))
        close_btn.setStyleSheet(
            """
            PushButton {
                color: #A56536;
                background-color: transparent;
                border: none;
                border-radius: 14px;
                padding-bottom: 2px;
            }
            PushButton:hover {
                background-color: #EFE2D4;
                color: #8D5D32;
            }
            PushButton:pressed {
                background-color: #E5D4C0;
                color: #8D5D32;
            }
        """
        )
        self.close_btn = close_btn
        close_btn.clicked.connect(self.close)
        top_bar_layout.addWidget(close_btn)
        main_layout.addWidget(top_bar)

        fish_card = self._create_card_frame(fixed_height=154, with_shadow=True)
        fish_layout = QVBoxLayout(fish_card)
        fish_layout.setContentsMargins(20, 14, 20, 16)
        fish_layout.setSpacing(10)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedHeight(78)
        image_path = pokedex.get_fish_image_path(self.fish_name)
        if image_path and image_path.exists():
            pixmap = QPixmap(str(image_path))
            scaled = pixmap.scaled(
                220, 146, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            scaled.setDevicePixelRatio(2.0)
            image_label.setPixmap(scaled)
        else:
            image_label.setText("🐟")
            image_label.setFont(QFont("Segoe UI Emoji", 46))
        image_label.setStyleSheet("background: transparent; border: none;")
        fish_layout.addWidget(image_label, 0, Qt.AlignHCenter)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(10)
        tags_row.setAlignment(Qt.AlignCenter)

        fish_type = self.fish_data.get("type", "")
        if fish_type:
            rod_badge = self._create_badge(
                cfg._get_base_path() / "resources" / "rod" / f"{fish_type}.png",
                self._format_rod_type(fish_type),
                "#A56536",
                "#EFE2D4",
            )
            tags_row.addWidget(rod_badge)

        rarity_badge = self._create_rarity_badge(self._build_rarity_label())
        self.rarity_badge = rarity_badge
        tags_row.addWidget(rarity_badge)

        fish_layout.addLayout(tags_row)
        main_layout.addWidget(fish_card)

        condition_frame = self._create_card_frame(fixed_height=80)
        condition_layout = QHBoxLayout(condition_frame)
        condition_layout.setContentsMargins(10, 12, 10, 12)
        condition_layout.setSpacing(0)

        season_text = ", ".join(season_values) if season_values else "-"
        time_text = ", ".join(time_values) if time_values else "-"

        condition_layout.addWidget(self._create_cell("季节", season_text), 1)
        condition_layout.addWidget(self._separator())
        condition_layout.addWidget(self._create_cell("时间", time_text), 1)
        condition_layout.addWidget(self._separator())
        condition_layout.addWidget(self._create_weather_cell(weather_values, cfg), 1)
        main_layout.addWidget(condition_frame)

        row_count = max(1, (len(locations) + 3) // 4)
        location_frame = self._create_card_frame(fixed_height=84 + (row_count - 1) * 34)
        location_layout = QVBoxLayout(location_frame)
        location_layout.setContentsMargins(16, 12, 16, 12)
        location_layout.setSpacing(10)

        location_title = StrongBodyLabel("出没地点")
        location_title.setStyleSheet(
            "color: #8B6D4E; font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        self.location_title_label = location_title
        location_layout.addWidget(location_title)

        chips_container = QVBoxLayout()
        chips_container.setContentsMargins(0, 0, 0, 0)
        chips_container.setSpacing(8)

        if locations:
            for row_items in self._chunk_items(locations, 4):
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(8)
                for column in range(4):
                    slot = QWidget()
                    slot_layout = QHBoxLayout(slot)
                    slot_layout.setContentsMargins(0, 0, 0, 0)
                    slot_layout.setSpacing(0)
                    slot_layout.setAlignment(Qt.AlignCenter)

                    if column < len(row_items):
                        location_name = row_items[column]
                        badge = self._create_badge(
                            cfg._get_base_path()
                            / "resources"
                            / "location"
                            / f"{location_name}.png",
                            location_name,
                            "#9C5D2C",
                            "#EFE8DF",
                        )
                        slot_layout.addWidget(badge, 0, Qt.AlignCenter)

                    row.addWidget(slot, 1)
                chips_container.addLayout(row)
        else:
            empty_label = QLabel("-")
            empty_label.setStyleSheet("color: #A0826D; font-size: 13px;")
            self.empty_location_label = empty_label
            chips_container.addWidget(empty_label)

        location_layout.addLayout(chips_container)
        main_layout.addWidget(location_frame)

        quality_frame = self._create_card_frame(fixed_height=62)
        quality_layout = QHBoxLayout(quality_frame)
        quality_layout.setContentsMargins(16, 10, 16, 10)
        quality_layout.setSpacing(10)

        quality_label = StrongBodyLabel("品质")
        quality_label.setStyleSheet(
            "color: #8B6D4E; font-size: 14px; background: transparent; border: none;"
        )
        self.quality_label_widget = quality_label
        quality_layout.addWidget(quality_label)
        quality_layout.addSpacing(2)

        self.quality_dots = {}
        for quality in QUALITIES:
            dot = QualityDot(quality)
            dot.clicked.connect(lambda q=quality: self._on_quality_clicked(q))
            dot.setToolTip(quality)
            self.quality_dots[quality] = dot
            quality_layout.addWidget(dot)

        quality_layout.addStretch()

        self.action_btn = PushButton("全选")
        self.action_btn.setFixedSize(66, 32)
        self.action_btn.setStyleSheet(
            """
            PushButton {
                background-color: #D8CCBA;
                color: #8B6D4E;
                border: none;
                border-radius: 16px;
                font-size: 13px;
                font-weight: 700;
            }
            PushButton:hover {
                background-color: #CABCA7;
            }
            PushButton:pressed {
                background-color: #B9AB95;
            }
        """
        )
        self.action_btn.clicked.connect(self._on_action_clicked)
        quality_layout.addWidget(self.action_btn)
        main_layout.addWidget(quality_frame)

        weight_frame = self._create_card_frame(fixed_height=62)
        weight_layout = QHBoxLayout(weight_frame)
        weight_layout.setContentsMargins(18, 10, 18, 10)
        weight_layout.setSpacing(14)

        weight_label = StrongBodyLabel("最大重量")
        weight_label.setStyleSheet(
            "color: #8B6D4E; font-size: 14px; background: transparent; border: none;"
        )
        self.weight_label_widget = weight_label
        weight_layout.addWidget(weight_label)
        weight_layout.addStretch()

        self.weight_input = LineEdit()
        self.weight_input.setPlaceholderText("0.0")
        self.weight_input.setAlignment(Qt.AlignCenter)
        self.weight_input.setFixedSize(104, 36)
        self.weight_input.setStyleSheet(
            """
            LineEdit {
                background-color: #FBF4E8;
                border: 2px solid #D8C6AD;
                border-radius: 13px;
                padding: 6px 10px;
                font-size: 14px;
                color: #8B6D4E;
            }
            LineEdit:focus {
                border: 2px solid #C7B298;
            }
        """
        )
        weight_layout.addWidget(self.weight_input)

        kg_label = BodyLabel("kg")
        kg_label.setStyleSheet(
            "color: #A0826D; font-size: 14px; background: transparent; border: none;"
        )
        self.kg_label = kg_label
        weight_layout.addWidget(kg_label)
        main_layout.addWidget(weight_frame)
        main_layout.addStretch(1)

    def _create_card_frame(self, fixed_height=None, with_shadow=False) -> QFrame:
        frame = QFrame()
        frame.setObjectName("detailCard")
        frame.setProperty("with_shadow", with_shadow)
        if fixed_height is not None:
            frame.setFixedHeight(fixed_height)
        frame.setStyleSheet(
            """
            QFrame#detailCard {
                background-color: #F8F5F1;
                border-radius: 20px;
                border: 2px solid #E3D4C1;
            }
        """
        )

        if with_shadow:
            shadow = QGraphicsDropShadowEffect(frame)
            shadow.setBlurRadius(16)
            shadow.setColor(QColor(0, 0, 0, 28))
            shadow.setOffset(0, 2)
            frame.setGraphicsEffect(shadow)

        self._card_frames.append(frame)
        return frame

    def _collect_location_names(self):
        names = []
        for loc in self.fish_data.get("locations", []):
            raw_loc = loc.get("location", "")
            if isinstance(raw_loc, list):
                names.extend([x for x in raw_loc if x])
            elif raw_loc:
                names.append(raw_loc)
        return list(dict.fromkeys(names))

    def _collect_condition_values(self):
        seasons = []
        times = []
        weathers = []
        for loc in self.fish_data.get("locations", []):
            for cond in loc.get("conditions", []):
                seasons.extend(cond.get("season", []))
                times.extend(cond.get("time_of_day", []))
                weathers.extend(cond.get("weather", []))

        season_order = ["春季", "夏季", "秋季", "冬季"]
        time_order = ["凌晨", "清晨", "上午", "下午", "黄昏", "深夜"]
        weather_order = ["晴天", "雾天", "小雨", "大雨", "小雪", "大雪"]

        unique_seasons = list(dict.fromkeys(seasons))
        unique_times = list(dict.fromkeys(times))
        unique_weathers = list(dict.fromkeys(weathers))

        return (
            self._sort_by_order(unique_seasons, season_order),
            self._sort_by_order(unique_times, time_order),
            self._sort_by_order(unique_weathers, weather_order),
        )

    def _sort_by_order(self, values, order):
        order_map = {name: idx for idx, name in enumerate(order)}
        return sorted(values, key=lambda x: (order_map.get(x, 99), x))

    def _chunk_items(self, items, chunk_size):
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]

    def _format_rod_type(self, fish_type: str) -> str:
        return fish_type.replace("杆", "竿")

    def _build_rarity_label(self) -> str:
        def parse_level(value):
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                text = value.strip()
                if text.isdigit():
                    return int(text)
            return None

        level = parse_level(self.fish_data.get("rarity_level"))
        if level is None:
            # fish_data 缺字段时，回查图鉴主数据，确保与 resources/fish.json 一致
            for item in pokedex.get_all_fish():
                if item.get("name") == self.fish_name:
                    level = parse_level(item.get("rarity_level"))
                    break

        if level is not None:
            return f"{level}级稀有"

        rarity_text = self.fish_data.get("rarity", "")
        if isinstance(rarity_text, str):
            rarity_text = rarity_text.strip()
            if rarity_text.endswith("级稀有"):
                return rarity_text

        return "未知稀有"

    def _create_rarity_badge(self, text: str) -> QLabel:
        badge = QLabel(text)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            """
            QLabel {
                color: #D29421;
                font-size: 14px;
                font-weight: 700;
                background-color: #F8EBCF;
                border: 1px solid #E2BC69;
                border-radius: 15px;
                padding: 5px 14px;
            }
        """
        )
        return badge

    def _create_badge(
        self, icon_path, text: str, text_color: str, bg_color: str
    ) -> QFrame:
        badge = QFrame()
        badge.setObjectName("detailBadge")
        badge.setFixedHeight(30)
        layout = QHBoxLayout(badge)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        if icon_path.exists():
            icon = QLabel()
            pixmap = QPixmap(str(icon_path))
            scaled = pixmap.scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(2.0)
            icon.setPixmap(scaled)
            icon.setFixedSize(17, 17)
            icon.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(icon)

        label = QLabel(text)
        label.setStyleSheet(
            f"color: {text_color}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
        )
        layout.addWidget(label)

        badge.setStyleSheet(
            f"background-color: {bg_color}; border-radius: 15px; border: none;"
        )
        self._badge_specs.append((badge, label, text_color, bg_color))
        return badge

    def _create_cell(self, title: str, value: str) -> QWidget:
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(5)

        title_label = BodyLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "color: #A0826D; font-size: 12px; background: transparent; border: none;"
        )
        self._meta_title_labels.append(title_label)
        layout.addWidget(title_label)

        value_label = StrongBodyLabel(value)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet(
            "color: #4E3E2D; font-size: 14px; font-weight: 700; background: transparent; border: none;"
        )
        self._meta_value_labels.append(value_label)
        layout.addWidget(value_label)

        return cell

    def _create_weather_cell(self, weather_list: list, cfg) -> QWidget:
        cell = QWidget()
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(5)

        title_label = BodyLabel("天气")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            "color: #A0826D; font-size: 12px; background: transparent; border: none;"
        )
        self._meta_title_labels.append(title_label)
        layout.addWidget(title_label)

        icon_row = QHBoxLayout()
        icon_row.setContentsMargins(0, 0, 0, 0)
        icon_row.setSpacing(6)
        icon_row.setAlignment(Qt.AlignCenter)

        if weather_list:
            for weather in weather_list[:3]:
                icon_path = (
                    cfg._get_base_path() / "resources" / "weather" / f"{weather}.png"
                )
                if icon_path.exists():
                    icon = QLabel()
                    pixmap = QPixmap(str(icon_path))
                    scaled = pixmap.scaled(
                        40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    scaled.setDevicePixelRatio(2.0)
                    icon.setPixmap(scaled)
                    icon.setFixedSize(20, 20)
                    icon.setStyleSheet("background: transparent; border: none;")
                    icon_row.addWidget(icon)
                else:
                    fallback = QLabel(weather[:1])
                    fallback.setStyleSheet(
                        "color: #4E3E2D; font-size: 13px; font-weight: 700; background: transparent; border: none;"
                    )
                    self._meta_value_labels.append(fallback)
                    icon_row.addWidget(fallback)
        else:
            empty = QLabel("-")
            empty.setStyleSheet(
                "color: #4E3E2D; font-size: 14px; font-weight: 700; background: transparent; border: none;"
            )
            self._meta_value_labels.append(empty)
            icon_row.addWidget(empty)

        layout.addLayout(icon_row)
        return cell

    def _separator(self) -> QFrame:
        separator = QFrame()
        separator.setFixedWidth(1)
        separator.setFixedHeight(44)
        separator.setStyleSheet("background-color: #E3D4C1;")
        self._separator_frames.append(separator)
        return separator

    def _apply_theme_styles(self):
        palette = self._theme_palette()
        is_dark = self._is_dark_theme()

        self.container.setStyleSheet(
            f"""
            QFrame#dialogContainer {{
                background-color: {palette["container_bg"]};
                border-radius: 28px;
                border: 1px solid {palette["container_border"]};
            }}
        """
        )

        container_shadow = self.container.graphicsEffect()
        if isinstance(container_shadow, QGraphicsDropShadowEffect):
            container_shadow.setColor(QColor(0, 0, 0, 86 if is_dark else 42))

        if hasattr(self, "name_label"):
            self.name_label.setStyleSheet(
                f"color: {palette['title_text']}; background: transparent; border: none;"
            )

        if hasattr(self, "close_btn"):
            self.close_btn.setStyleSheet(
                f"""
                PushButton {{
                    color: {palette["close_color"]};
                    background-color: transparent;
                    border: none;
                    border-radius: 14px;
                    padding-bottom: 2px;
                }}
                PushButton:hover {{
                    background-color: {palette["close_hover_bg"]};
                }}
                PushButton:pressed {{
                    background-color: {palette["close_pressed_bg"]};
                }}
            """
            )

        for frame in self._card_frames:
            frame.setStyleSheet(
                f"""
                QFrame#detailCard {{
                    background-color: {palette["card_bg"]};
                    border-radius: 20px;
                    border: 2px solid {palette["card_border"]};
                }}
            """
            )
            shadow = frame.graphicsEffect()
            if isinstance(shadow, QGraphicsDropShadowEffect):
                shadow.setColor(QColor(0, 0, 0, 82 if is_dark else 28))

        for badge, label, light_text, light_bg in self._badge_specs:
            base_color = QColor(light_text)
            if is_dark:
                text_color = base_color.lighter(175).name()
                bg_color = self._rgba(base_color, 48)
                border_color = self._rgba(base_color, 90)
            else:
                text_color = light_text
                bg_color = light_bg
                border_color = "transparent"

            label.setStyleSheet(
                f"color: {text_color}; font-size: 13px; font-weight: 600; background: transparent; border: none;"
            )
            badge.setStyleSheet(
                f"background-color: {bg_color}; border-radius: 15px; border: 1px solid {border_color};"
            )

        if hasattr(self, "rarity_badge"):
            self.rarity_badge.setStyleSheet(
                f"""
                QLabel {{
                    color: {palette["rarity_text"]};
                    font-size: 14px;
                    font-weight: 700;
                    background-color: {palette["rarity_bg"]};
                    border: 1px solid {palette["rarity_border"]};
                    border-radius: 15px;
                    padding: 5px 14px;
                }}
            """
            )

        if hasattr(self, "location_title_label"):
            self.location_title_label.setStyleSheet(
                f"color: {palette['section_title']}; font-size: 14px; font-weight: 700; background: transparent; border: none;"
            )
        if hasattr(self, "quality_label_widget"):
            self.quality_label_widget.setStyleSheet(
                f"color: {palette['section_title']}; font-size: 14px; background: transparent; border: none;"
            )
        if hasattr(self, "weight_label_widget"):
            self.weight_label_widget.setStyleSheet(
                f"color: {palette['section_title']}; font-size: 14px; background: transparent; border: none;"
            )
        if hasattr(self, "kg_label"):
            self.kg_label.setStyleSheet(
                f"color: {palette['unit_text']}; font-size: 14px; background: transparent; border: none;"
            )
        if self.empty_location_label:
            self.empty_location_label.setStyleSheet(
                f"color: {palette['empty_text']}; font-size: 13px;"
            )

        for title_label in self._meta_title_labels:
            title_label.setStyleSheet(
                f"color: {palette['meta_title']}; font-size: 12px; background: transparent; border: none;"
            )
        for value_label in self._meta_value_labels:
            value_label.setStyleSheet(
                f"color: {palette['meta_value']}; font-size: 14px; font-weight: 700; background: transparent; border: none;"
            )
        for separator in self._separator_frames:
            separator.setStyleSheet(f"background-color: {palette['separator']};")

        if hasattr(self, "action_btn"):
            self.action_btn.setStyleSheet(
                f"""
                PushButton {{
                    background-color: {palette["action_bg"]};
                    color: {palette["action_text"]};
                    border: none;
                    border-radius: 16px;
                    font-size: 13px;
                    font-weight: 700;
                }}
                PushButton:hover {{
                    background-color: {palette["action_hover"]};
                }}
                PushButton:pressed {{
                    background-color: {palette["action_pressed"]};
                }}
            """
            )

        if hasattr(self, "weight_input"):
            self.weight_input.setStyleSheet(
                f"""
                LineEdit {{
                    background-color: {palette["input_bg"]};
                    border: 2px solid {palette["input_border"]};
                    border-radius: 13px;
                    padding: 6px 10px;
                    font-size: 14px;
                    color: {palette["input_text"]};
                }}
                LineEdit:focus {{
                    border: 2px solid {palette["input_focus"]};
                }}
            """
            )

        for dot in self.quality_dots.values():
            dot._update_style()

        self.update()

    def _load_collection_status(self):
        status = pokedex.get_collection_status(self.fish_name)
        collected_count = 0
        for quality, weight in status.items():
            if quality in self.quality_dots:
                is_collected = weight is not None
                self.quality_dots[quality].set_status(is_collected)
                if is_collected:
                    collected_count += 1

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
        pokedex.toggle_quality(self.fish_name, quality)
        self._load_collection_status()
        self.collection_changed.emit()

    def _on_action_clicked(self):
        if self.action_btn.text() == "清空":
            pokedex.clear_all(self.fish_name)
        else:
            pokedex.mark_all_caught(self.fish_name)

        self._load_collection_status()
        self.collection_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "container"):
            x = (self.width() - self.container.width()) // 2
            y = (self.height() - self.container.height()) // 2
            self.container.move(x, y)

    def showEvent(self, event):
        super().showEvent(event)

        if self.main_window:
            geo = self.main_window.geometry()
            self.setGeometry(geo)

        if hasattr(self, "container"):
            self._apply_theme_styles()
            self.resizeEvent(None)

    def refresh_theme(self):
        """Refresh dialog styles after app theme changes."""
        self._apply_theme_styles()

    def paintEvent(self, event):
        palette = self._theme_palette()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, palette["overlay_alpha"]))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

    def mousePressEvent(self, event):
        if hasattr(self, "container"):
            container_rect = self.container.geometry().adjusted(10, 10, -10, -10)
            if not container_rect.contains(event.pos()):
                self.close()
        super().mousePressEvent(event)
