from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpacerItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

# 导入硬件信息模块
from src.services.hardware_info import (
    get_account_name,
    get_cpu_info,
    get_memory_info,
    get_gpu_info,
    get_all_hardware_info,
)


class WelcomeDialog(QDialog):
    """欢迎提示窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 PartyFish")
        self.setFixedSize(400, 200)  # 恢复原窗口大小
        self.setWindowModality(Qt.ApplicationModal)

        # 设置窗口居中
        self.move(
            self.screen().availableGeometry().center() - self.frameGeometry().center()
        )

        # 初始化UI
        self.init_ui()

    def init_ui(self):
        """初始化UI布局"""
        from src.config import cfg

        # 获取UI字体
        ui_font = cfg.get_ui_font()

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # 标题
        title_label = QLabel("🎉 欢迎使用 PartyFish")
        title_font = QFont(ui_font)
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # 提示信息
        message_label = QLabel(
            "免费软件\n从任何渠道购买请申请退款并举报\n\n点击确认开始使用"
        )
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        # 设置提示信息的字体
        message_font = QFont(ui_font)
        message_font.setPointSize(10)
        message_label.setFont(message_font)
        main_layout.addWidget(message_label)

        # 底部按钮布局
        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        # 确定按钮
        ok_button = QPushButton("确定")
        ok_button.setFixedSize(100, 32)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        button_layout.addSpacerItem(
            QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum)
        )

        main_layout.addLayout(button_layout)


def show_welcome_dialog():
    """显示欢迎提示窗口"""
    # 获取硬件信息（绑定但不显示）
    hardware_info = get_all_hardware_info()

    # 可以在这里添加硬件信息绑定逻辑（如果需要）
    # 例如：保存到配置文件或发送到服务器

    dialog = WelcomeDialog()
    dialog.exec()

    # 返回硬件信息
    return hardware_info
