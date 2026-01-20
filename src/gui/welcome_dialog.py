from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import os

# 导入wmi和psutil库
import wmi
import psutil


def get_account_name():
    """获取当前登录账号名"""
    try:
        return os.getlogin()
    except:
        return "未知账号"


def get_cpu_info():
    """获取CPU型号"""
    cpu_list = []
    try:
        # 使用wmi库获取CPU信息
        c = wmi.WMI()
        for processor in c.Win32_Processor():
            if processor.Name:
                cpu_name = processor.Name.strip()
                if cpu_name not in cpu_list:  # 避免重复
                    cpu_list.append(cpu_name)
        if cpu_list:
            return "; ".join(cpu_list)
    except Exception as e:
        print(f"wmi获取CPU信息失败: {e}")
    
    return "未知CPU"


def get_memory_info():
    """获取内存信息"""
    try:
        # 使用psutil库获取内存信息
        total_memory = psutil.virtual_memory().total
        # 转换为GB
        total_memory_gb = total_memory / (1024 ** 3)
        return f"{total_memory_gb:.1f} GB"
    except Exception as e:
        print(f"psutil获取内存信息失败: {e}")
    
    return "未知内存"


def get_gpu_info():
    """获取GPU型号"""
    gpu_list = []
    try:
        # 使用wmi库获取GPU信息
        c = wmi.WMI()
        for gpu in c.Win32_VideoController():
            if gpu.Name:
                gpu_list.append(gpu.Name.strip())
        if gpu_list:
            return "; ".join(gpu_list)
    except Exception as e:
        print(f"wmi获取GPU信息失败: {e}")
    
    return "未知GPU"


class WelcomeDialog(QDialog):
    """欢迎提示窗口"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("欢迎使用 PartyFish")
        self.setFixedSize(400, 200)  # 恢复原窗口大小
        self.setWindowModality(Qt.ApplicationModal)
        
        # 设置窗口居中
        self.move(self.screen().availableGeometry().center() - self.frameGeometry().center())
        
        # 初始化UI
        self.init_ui()
    
    def init_ui(self):
        """初始化UI布局"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # 标题
        title_label = QLabel("🎉 欢迎使用 PartyFish")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 提示信息
        message_label = QLabel("免费软件\n从任何渠道购买请申请退款并举报\n\n点击确认开始使用")
        message_label.setAlignment(Qt.AlignCenter)
        message_label.setWordWrap(True)
        main_layout.addWidget(message_label)
        
        # 底部按钮布局
        button_layout = QHBoxLayout()
        button_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # 确定按钮
        ok_button = QPushButton("确定")
        ok_button.setFixedSize(100, 32)
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        button_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        main_layout.addLayout(button_layout)



def show_welcome_dialog():
    """显示欢迎提示窗口"""
    # 获取硬件信息（绑定但不显示）
    account_name = get_account_name()
    cpu_info = get_cpu_info()
    memory_info = get_memory_info()
    gpu_info = get_gpu_info()
    
    # 可以在这里添加硬件信息绑定逻辑（如果需要）
    # 例如：保存到配置文件或发送到服务器
    
    dialog = WelcomeDialog()
    dialog.exec()
    
    # 返回硬件信息
    return {
        "account_name": account_name,
        "cpu": cpu_info,
        "memory": memory_info,
        "gpu": gpu_info
    }
