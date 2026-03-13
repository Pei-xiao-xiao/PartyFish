"""
Footer 组件 - 负责主页 Footer 区域的 UI 构建
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import BodyLabel, CaptionLabel

try:
    from src._version import __version__
except ImportError:
    __version__ = "DEV"


class FooterWidget(QWidget):
    """Footer 组件 - 显示作者信息和声明"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        """初始化 Footer UI"""
        self.footer_container = QWidget(self)
        self.footer_layout = QHBoxLayout(self.footer_container)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.footer_layout.setSpacing(12)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        self.author_label = BodyLabel(
            f"Created by FadedTUMI, MaiDong688, Pei-Xiao-Xiao | {__version__} | 本软件完全免费 如遇售卖 直接举报",
            self,
        )
        self.author_label.setTextColor(QColor(100, 100, 100), QColor(150, 150, 150))

        self.disclaimer_label = CaptionLabel(
            "软件仅供学习交流，若因使用此软件导致的任何损失与作者无关",
            self,
        )
        self.disclaimer_label.setTextColor(QColor(150, 150, 150), QColor(120, 120, 120))

        text_layout.addWidget(self.author_label)
        text_layout.addWidget(self.disclaimer_label)

        self.footer_layout.addWidget(text_container)
        self.footer_layout.addStretch(1)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.footer_container)

    def apply_theme(self):
        """应用主题样式"""
        pass
