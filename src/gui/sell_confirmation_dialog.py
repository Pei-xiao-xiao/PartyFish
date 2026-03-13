"""
卖鱼确认对话框
当一键卖鱼的价格+当前今日进度大于899时，弹出确认对话框
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QColor
from qfluentwidgets import setTheme, Theme, isDarkTheme


class SellConfirmationDialog(QDialog):
    """卖鱼确认对话框"""

    def __init__(self, price: int, current_progress: int, parent=None):
        """
        初始化对话框

        Args:
            price: 当前卖鱼价格
            current_progress: 当前今日进度
            parent: 父窗口
        """
        super().__init__(parent)
        self.price = price
        self.current_progress = current_progress
        self.should_continue = False

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("卖鱼确认")
        self.setFixedSize(400, 200)
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        content_frame = QFrame(self)
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet(
            """
            QFrame#contentFrame {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """
        )

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        title_label = QLabel("⚠️ 卖鱼确认", content_frame)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #e74c3c;
                letter-spacing: -1px;
            }
        """
        )
        content_layout.addWidget(title_label)

        total = self.price + self.current_progress
        info_text = f"当前卖鱼价格: {self.price}\n今日已卖进度: {self.current_progress}\n合计: {total} (超过899)"
        info_label = QLabel(info_text, content_frame)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #333333;
                line-height: 1.5;
            }
        """
        )
        content_layout.addWidget(info_label)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        cancel_button = QPushButton("取消", content_frame)
        cancel_button.setFixedSize(120, 36)
        cancel_button.setStyleSheet(
            """
            QPushButton {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                color: #333333;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """
        )
        cancel_button.clicked.connect(self._on_cancel)

        continue_button = QPushButton("继续", content_frame)
        continue_button.setFixedSize(120, 36)
        continue_button.setStyleSheet(
            """
            QPushButton {
                background-color: #e74c3c;
                border: none;
                border-radius: 6px;
                color: white;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """
        )
        continue_button.clicked.connect(self._on_continue)

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(continue_button)
        button_layout.addStretch()

        content_layout.addLayout(button_layout)
        content_layout.addStretch()

        main_layout.addWidget(content_frame)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        is_dark = isDarkTheme()
        if is_dark:
            painter.fillRect(self.rect(), Qt.transparent)
        else:
            color = QColor(0, 0, 0, 80)
            painter.fillRect(self.rect(), color)

    def refresh_theme(self):
        self.update()

    def _on_cancel(self):
        self.should_continue = False
        self.accept()

    def _on_continue(self):
        self.should_continue = True
        self.accept()

    def get_user_choice(self) -> bool:
        return self.should_continue
