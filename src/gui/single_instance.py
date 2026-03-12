
"""
单例应用程序管理器
用于防止应用程序多开
"""
import sys
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PySide6.QtCore import QFile, QIODevice, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from qfluentwidgets import isDarkTheme


class TransparentDialog(QDialog):
    """透明背景对话框，用于解决暗黑模式下白屏问题"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)

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


class SingleInstance:
    """单例应用程序管理器类"""

    def __init__(self, app_name):
        """
        初始化单例管理器

        Args:
            app_name: 应用程序名称，用于创建唯一的标识符
        """
        self.app_name = app_name
        self.server_name = f"{app_name}_server"
        self.server = None

    def is_running(self):
        """
        检查是否已有实例在运行

        Returns:
            bool: True表示已有实例在运行，False表示没有
        """
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)

        # 如果连接成功，说明已有实例在运行
        if socket.waitForConnected(500):
            socket.disconnectFromServer()
            return True

        return False

    def start_server(self):
        """
        启动本地服务器，用于接收其他实例的连接请求

        Returns:
            bool: True表示启动成功，False表示启动失败
        """
        # 先尝试移除可能存在的旧服务器
        QLocalServer.removeServer(self.server_name)

        self.server = QLocalServer()
        self.server.newConnection.connect(self._handle_new_connection)

        if self.server.listen(self.server_name):
            return True
        return False

    def _handle_new_connection(self):
        """处理新的连接请求"""
        socket = self.server.nextPendingConnection()
        if socket:
            # 读取数据（如果有的话）
            if socket.waitForReadyRead(100):
                data = socket.readAll()
                # 这里可以处理其他实例传递的数据
                pass
            socket.disconnectFromServer()

            # 将当前窗口提到前台
            app = QApplication.instance()
            if app:
                for widget in app.topLevelWidgets():
                    if widget.isVisible():
                        widget.show()
                        widget.raise_()
                        widget.activateWindow()
                        break

    def show_running_message(self):
        """显示已有实例运行的提示消息"""
        from PySide6.QtGui import QFont, QIcon
        from pathlib import Path

        # 获取或创建QApplication
        app = QApplication.instance()
        if not app:
            # 设置路径，确保能找到src模块
            if getattr(sys, "frozen", False):
                app_path = Path(sys.executable).parent
            else:
                app_path = Path(__file__).parent.parent.parent

            if str(app_path) not in sys.path:
                sys.path.insert(0, str(app_path))

            app = QApplication([])

        # 尝试加载应用图标
        try:
            if getattr(sys, "frozen", False):
                app_path = Path(sys.executable).parent
            else:
                app_path = Path(__file__).parent.parent.parent

            icon_path = app_path / "resources" / "favicon.ico"
            if icon_path.exists():
                app.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print(f"加载应用图标失败：{e}")

        # 创建自定义对话框
        dialog = TransparentDialog()
        dialog.setWindowTitle("提示")
        dialog.setFixedSize(320, 160)
        dialog.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        # 主布局
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 内容容器
        content_frame = QFrame(dialog)
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet("""
            QFrame#contentFrame {
                background-color: #ffffff;
                border-radius: 10px;
                border: 1px solid #e0e0e0;
            }
        """)

        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(20, 20, 20, 15)
        content_layout.setSpacing(15)

        # 水平布局：图标 + 文本
        info_layout = QHBoxLayout()
        info_layout.setSpacing(12)
        info_layout.setAlignment(Qt.AlignVCenter)

        # 图标标签
        icon_label = QLabel("ℹ️", content_frame)
        icon_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                padding: 0px;
                margin: 0px;
            }
        """)
        icon_label.setFixedSize(32, 32)
        icon_label.setAlignment(Qt.AlignCenter)

        # 文本布局（垂直）
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        text_layout.setAlignment(Qt.AlignVCenter)

        # 主标题
        title_label = QLabel(f"{self.app_name} 正在运行中", content_frame)
        title_label.setStyleSheet("""
            QLabel {
                color: #1f1f1f;
                font-size: 14px;
                font-weight: bold;
                padding: 0px;
            }
        """)

        # 副标题
        subtitle_label = QLabel("请检查任务栏或系统托盘中的程序窗口", content_frame)
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 11px;
                padding: 0px;
            }
        """)

        text_layout.addWidget(title_label)
        text_layout.addWidget(subtitle_label)

        info_layout.addWidget(icon_label)
        info_layout.addLayout(text_layout, 1)
        info_layout.addStretch()

        content_layout.addLayout(info_layout)

        # 按钮布局
        button_layout = QHBoxLayout()
        button_layout.setAlignment(Qt.AlignCenter)

        # 确定按钮
        ok_button = QPushButton("确定", content_frame)
        ok_button.setFixedSize(80, 32)
        ok_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0078d4, stop:1 #005a9e);
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #1084e8, stop:1 #0064b8);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #005a9e, stop:1 #00457a);
            }
        """)
        ok_button.clicked.connect(dialog.accept)

        button_layout.addWidget(ok_button)
        content_layout.addLayout(button_layout)

        main_layout.addWidget(content_frame)

        # 设置字体
        font = QFont()
        font.setFamily("Microsoft YaHei UI")
        dialog.setFont(font)

        # 尝试设置窗口图标
        try:
            if getattr(sys, "frozen", False):
                app_path = Path(sys.executable).parent
            else:
                app_path = Path(__file__).parent.parent.parent

            icon_path = app_path / "resources" / "favicon.ico"
            if icon_path.exists():
                dialog.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            print(f"设置窗口图标失败：{e}")

        dialog.exec()
