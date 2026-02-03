)
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
    QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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
        self.should_continue = False  # 用户是否选择继续

        self._init_ui()

    def _init_ui(self):
        """初始化UI"""
        self.setWindowTitle("卖鱼确认")
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 内容容器
        content_frame = QFrame(self)
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
        """)

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        # 标题
        title_label = QLabel("⚠️ 卖鱼确认", content_frame)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #e74c3c;
            }
        """)
        content_layout.addWidget(title_label)

        # 信息标签
        total = self.price + self.current_progress
        info_text = f"当前卖鱼价格: {self.price}
今日已卖进度: {self.current_progress}
合计: {total} (超过899)"
        info_label = QLabel(info_text, content_frame)
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #333333;
                line-height: 1.5;
            }
        """)
        content_layout.addWidget(info_label)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # 取消按钮
        cancel_button = QPushButton("取消", content_frame)
        cancel_button.setFixedSize(120, 36)
        cancel_button.setStyleSheet("""
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
        """)
        cancel_button.clicked.connect(self._on_cancel)

        # 继续按钮
        continue_button = QPushButton("继续", content_frame)
        continue_button.setFixedSize(120, 36)
        continue_button.setStyleSheet("""
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
        """)
        continue_button.clicked.connect(self._on_continue)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(continue_button)
        button_layout.addStretch()

        content_layout.addLayout(button_layout)
        content_layout.addStretch()

        main_layout.addWidget(content_frame)

    def _on_cancel(self):
        """取消按钮点击事件"""
        self.should_continue = False
        self.accept()

    def _on_continue(self):
        """继续按钮点击事件"""
        self.should_continue = True
        self.accept()

    def get_user_choice(self) -> bool:
        """
        获取用户选择

        Returns:
            bool: True表示继续，False表示取消
        """
        return self.should_continue
