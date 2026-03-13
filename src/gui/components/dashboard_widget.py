"""
Dashboard 组件 - 负责主页数据看板的 UI 构建和数据更新
"""

import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QUrl
from PySide6.QtGui import QColor, QPixmap, QPainter, QPainterPath, QPen, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QPushButton,
)
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    CaptionLabel,
    BodyLabel,
    IconWidget,
    ProgressRing,
    FluentIcon,
    qconfig,
)

from src.config import cfg


class DashboardWidget(QWidget):
    """Dashboard 组件 - 包含今日销售进度和图鉴进度"""

    data_directory_requested = Signal()
    screenshot_directory_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化 Dashboard UI"""
        self.dashboard_layout = QHBoxLayout(self)
        self.dashboard_layout.setContentsMargins(0, 0, 0, 0)
        self.dashboard_layout.setSpacing(24)

        self._setup_sales_card()
        self._setup_pokedex_card()

    def _setup_sales_card(self):
        """设置销售卡片"""
        self.sales_card = CardWidget(self)
        sales_layout = QVBoxLayout(self.sales_card)
        sales_layout.setContentsMargins(20, 16, 20, 16)
        sales_layout.setSpacing(10)

        sales_header = QHBoxLayout()
        sales_icon = IconWidget(FluentIcon.SHOPPING_CART, self.sales_card)
        sales_icon.setFixedSize(16, 16)
        sales_title = StrongBodyLabel("今日销售", self.sales_card)
        sales_header.addWidget(sales_icon)
        sales_header.addWidget(sales_title)
        sales_header.addStretch(1)
        sales_layout.addLayout(sales_header)

        progress_container = QWidget(self.sales_card)
        progress_layout = QHBoxLayout(progress_container)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(12)

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

        self.sales_value_label = BodyLabel("0 / 899", progress_container)
        self.sales_value_label.setStyleSheet("color: #6b7280; font-weight: 500;")

        progress_layout.addWidget(self.sales_progress_bar, 1)
        progress_layout.addWidget(self.sales_value_label)
        sales_layout.addWidget(progress_container)

        sales_divider = QFrame(self.sales_card)
        sales_divider.setFrameShape(QFrame.HLine)
        sales_divider.setFixedHeight(1)
        sales_divider.setStyleSheet("background-color: #e5e7eb; border: none;")
        sales_layout.addWidget(sales_divider)

        sales_actions = QHBoxLayout()
        sales_actions.setContentsMargins(0, 0, 0, 0)
        sales_actions.setSpacing(12)

        self.sales_data_dir_button = self._create_dashboard_link_button(
            "打开数据目录", "folder", self.data_directory_requested.emit
        )
        self.sales_screenshot_dir_button = self._create_dashboard_link_button(
            "打开截图目录", "image", self.screenshot_directory_requested.emit
        )
        sales_actions.addWidget(self.sales_data_dir_button)
        sales_actions.addWidget(self.sales_screenshot_dir_button)
        sales_actions.addStretch(1)
        sales_layout.addLayout(sales_actions)

        self.dashboard_layout.addWidget(self.sales_card, 2)

    def _setup_pokedex_card(self):
        """设置图鉴卡片"""
        self.pokedex_card = CardWidget(self)
        pokedex_layout = QVBoxLayout(self.pokedex_card)
        pokedex_layout.setContentsMargins(20, 16, 20, 16)
        pokedex_layout.setSpacing(10)

        pokedex_header = QHBoxLayout()
        pokedex_icon = IconWidget(FluentIcon.LIBRARY, self.pokedex_card)
        pokedex_icon.setFixedSize(16, 16)
        pokedex_title = StrongBodyLabel("图鉴进度", self.pokedex_card)
        pokedex_header.addWidget(pokedex_icon)
        pokedex_header.addWidget(pokedex_title)
        pokedex_header.addStretch(1)
        pokedex_layout.addLayout(pokedex_header)

        data_container = QHBoxLayout()
        data_container.setSpacing(0)

        fish_container = QWidget()
        fish_layout = QVBoxLayout(fish_container)
        fish_layout.setContentsMargins(0, 0, 0, 0)
        fish_layout.setSpacing(6)

        fish_ring_box = QWidget()
        fish_ring_box.setFixedSize(60, 60)
        fish_ring_stack = QGridLayout(fish_ring_box)
        fish_ring_stack.setContentsMargins(0, 0, 0, 0)

        self.fish_ring = ProgressRing()
        self.fish_ring.setFixedSize(56, 56)
        self.fish_ring.setStrokeWidth(5)
        self.fish_ring.setTextVisible(False)

        self.fish_collected_label = QLabel("0", self.pokedex_card)
        self.fish_collected_label.setStyleSheet(
            "color: #0ea5e9; font-size: 15px; font-weight: bold;"
        )
        self.fish_collected_label.setAlignment(Qt.AlignCenter)

        fish_ring_stack.addWidget(self.fish_ring, 0, 0, Qt.AlignCenter)
        fish_ring_stack.addWidget(self.fish_collected_label, 0, 0, Qt.AlignCenter)

        fish_layout.addWidget(fish_ring_box, 0, Qt.AlignCenter)

        fish_text_layout = QVBoxLayout()
        fish_text_layout.setSpacing(2)
        fish_title = CaptionLabel("已解锁鱼种", self.pokedex_card)
        fish_title.setStyleSheet("color: #64748b")
        self.fish_title_label = fish_title
        self.fish_total_label = CaptionLabel("总计 0", self.pokedex_card)
        self.fish_total_label.setStyleSheet("color: #94a3b8")

        fish_text_layout.addWidget(fish_title, 0, Qt.AlignCenter)
        fish_text_layout.addWidget(self.fish_total_label, 0, Qt.AlignCenter)
        fish_layout.addLayout(fish_text_layout)

        line = QFrame(self.pokedex_card)
        line.setFrameShape(QFrame.VLine)
        line.setFixedSize(1, 30)
        line.setStyleSheet("background-color: #e2e8f0; border: none;")
        self.pokedex_divider_line = line

        crown_container = QWidget()
        crown_layout = QVBoxLayout(crown_container)
        crown_layout.setContentsMargins(0, 0, 0, 0)
        crown_layout.setSpacing(6)

        crown_ring_box = QWidget()
        crown_ring_box.setFixedSize(60, 60)
        crown_ring_stack = QGridLayout(crown_ring_box)
        crown_ring_stack.setContentsMargins(0, 0, 0, 0)

        self.crown_ring = ProgressRing()
        self.crown_ring.setFixedSize(56, 56)
        self.crown_ring.setStrokeWidth(5)
        self.crown_ring.setTextVisible(False)

        self.crown_collected_label = QLabel("0", self.pokedex_card)
        self.crown_collected_label.setStyleSheet(
            "color: #8b5cf6; font-size: 15px; font-weight: bold;"
        )
        self.crown_collected_label.setAlignment(Qt.AlignCenter)

        crown_ring_stack.addWidget(self.crown_ring, 0, 0, Qt.AlignCenter)
        crown_ring_stack.addWidget(self.crown_collected_label, 0, 0, Qt.AlignCenter)

        crown_layout.addWidget(crown_ring_box, 0, Qt.AlignCenter)

        crown_text_layout = QVBoxLayout()
        crown_text_layout.setSpacing(2)
        crown_title = CaptionLabel("全品质收集", self.pokedex_card)
        crown_title.setStyleSheet("color: #64748b")
        self.crown_title_label = crown_title
        self.crown_total_label = CaptionLabel("总计 0", self.pokedex_card)
        self.crown_total_label.setStyleSheet("color: #94a3b8")

        crown_text_layout.addWidget(crown_title, 0, Qt.AlignCenter)
        crown_text_layout.addWidget(self.crown_total_label, 0, Qt.AlignCenter)
        crown_layout.addLayout(crown_text_layout)

        data_container.addWidget(fish_container, 1)
        data_container.addWidget(line)
        data_container.addWidget(crown_container, 1)

        pokedex_layout.addLayout(data_container)

        self.dashboard_layout.addWidget(self.pokedex_card, 1)

    def _create_dashboard_link_icon(
        self, icon_kind: str, color: str = "#06b6d4"
    ) -> QIcon:
        """创建链接图标"""
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), 1.4)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)

        if icon_kind == "folder":
            folder_path = QPainterPath()
            folder_path.moveTo(2.5, 6.5)
            folder_path.lineTo(6.2, 6.5)
            folder_path.lineTo(7.8, 4.8)
            folder_path.lineTo(15.5, 4.8)
            folder_path.lineTo(15.5, 13.8)
            folder_path.lineTo(2.5, 13.8)
            folder_path.closeSubpath()
            painter.drawPath(folder_path)
            painter.drawLine(2.5, 6.5, 15.5, 6.5)
        elif icon_kind == "image":
            painter.drawRoundedRect(2.5, 3.5, 13.0, 11.0, 2.0, 2.0)
            painter.drawEllipse(10.6, 6.0, 2.1, 2.1)

            image_path = QPainterPath()
            image_path.moveTo(4.5, 12.2)
            image_path.lineTo(7.7, 9.4)
            image_path.lineTo(9.7, 11.0)
            image_path.lineTo(11.7, 8.3)
            image_path.lineTo(14.0, 12.2)
            painter.drawPath(image_path)

        painter.end()
        return QIcon(pixmap)

    def _create_dashboard_link_button(
        self, text: str, icon_kind: str, handler
    ) -> QPushButton:
        """创建链接按钮"""
        button = QPushButton(text, self.sales_card)
        button.setFlat(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setIcon(self._create_dashboard_link_icon(icon_kind))
        button.setIconSize(QSize(16, 16))
        button.clicked.connect(handler)
        button.setStyleSheet(
            """
            QPushButton {
                color: #06b6d4;
                background: transparent;
                border: none;
                padding: 4px 8px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton:hover {
                color: #0891b2;
            }
            QPushButton:pressed {
                color: #0e7490;
            }
        """
        )
        return button

    def update_sales_progress(self, sold: int, limit: int = 899):
        """更新今日销售进度"""
        if limit <= 0:
            progress_ratio = 0
            is_overflow = False
            overflow_amount = 0
        else:
            progress_ratio = min(sold / limit, 1.0)
            is_overflow = sold > limit
            overflow_amount = sold - limit

        if is_overflow:
            self.sales_value_label.setText(
                f"{limit} / {limit} (<span style='color: #ef4444; font-weight: bold;'>+{overflow_amount} 已超额</span>)"
            )
        else:
            self.sales_value_label.setText(f"{sold} / {limit}")

        def do_update_bar():
            bar_width = self.sales_progress_bar.width()
            if is_overflow:
                fill_width = bar_width
            else:
                fill_width = int(bar_width * progress_ratio)

            if fill_width <= 0:
                self.sales_progress_fill.hide()
            else:
                self.sales_progress_fill.show()
                self.sales_progress_fill.setFixedWidth(fill_width)

            if is_overflow:
                color = "#b91c1c"
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

        do_update_bar()
        QTimer.singleShot(10, do_update_bar)

    def update_pokedex_progress(
        self, collected: int, total: int, collected_q: int, total_q: int
    ):
        """更新图鉴进度"""
        self.fish_collected_label.setText(str(collected))
        self.fish_total_label.setText(f"总计 {total}")
        fish_percent = int(collected / total * 100) if total > 0 else 0
        self.fish_ring.setValue(fish_percent)

        self.crown_collected_label.setText(str(collected_q))
        self.crown_total_label.setText(f"总计 {total_q}")
        crown_percent = int(collected_q / total_q * 100) if total_q > 0 else 0
        self.crown_ring.setValue(crown_percent)

    def apply_theme(self):
        """应用主题样式"""
        is_dark = qconfig.theme.value == "Dark"

        track_color = "rgba(255, 255, 255, 0.16)" if is_dark else "#e5e7eb"
        self.sales_progress_bar.setStyleSheet(
            f"""
            QWidget {{
                background-color: {track_color};
                border-radius: 6px;
            }}
        """
        )

        value_color = "#cbd5e1" if is_dark else "#6b7280"
        self.sales_value_label.setStyleSheet(f"color: {value_color}; font-weight: 500;")

        title_color = "#94a3b8" if is_dark else "#64748b"
        sub_color = "#cbd5e1" if is_dark else "#94a3b8"
        divider_color = "rgba(255, 255, 255, 0.18)" if is_dark else "#e2e8f0"

        self.fish_title_label.setStyleSheet(f"color: {title_color}")
        self.fish_collected_label.setStyleSheet(
            "color: #0ea5e9; font-size: 15px; font-weight: bold;"
        )
        self.fish_total_label.setStyleSheet(f"color: {sub_color}")
        self.crown_title_label.setStyleSheet(f"color: {title_color}")
        self.crown_collected_label.setStyleSheet(
            "color: #8b5cf6; font-size: 15px; font-weight: bold;"
        )
        self.crown_total_label.setStyleSheet(f"color: {sub_color}")
        self.pokedex_divider_line.setStyleSheet(
            f"background-color: {divider_color}; border: none;"
        )
