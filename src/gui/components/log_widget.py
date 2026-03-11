"""
Log 组件 - 负责主页日志区域的 UI 构建和日志输出
"""
from pathlib import Path

from PySide6.QtCore import Qt, QDateTime
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    CardWidget,
    TextEdit,
    StrongBodyLabel,
    IconWidget,
    ToolButton,
    FluentIcon,
    qconfig,
)

from src.config import cfg


class LogWidget(QWidget):
    """日志组件 - 显示运行日志"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        """初始化日志 UI"""
        self.log_container = CardWidget(self)
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setContentsMargins(20, 16, 20, 20)
        self.log_layout.setSpacing(12)
        
        log_header_layout = QHBoxLayout()
        log_icon = IconWidget(FluentIcon.COMMAND_PROMPT, self.log_container)
        log_icon.setFixedSize(16, 16)
        self.log_header_label = StrongBodyLabel("运行日志", self.log_container)
        
        self.download_log_button = ToolButton(self.log_container)
        self.download_log_button.setIcon(FluentIcon.DOWNLOAD)
        self.download_log_button.setToolTip("下载日志到 debug_screenshots 文件夹")
        self.download_log_button.setFixedSize(24, 24)
        self.download_log_button.clicked.connect(self._download_log)
        
        log_header_layout.addWidget(log_icon)
        log_header_layout.addWidget(self.log_header_label)
        log_header_layout.addStretch(1)
        log_header_layout.addWidget(self.download_log_button)
        self.log_layout.addLayout(log_header_layout)
        
        self.log_output = TextEdit(self.log_container)
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("LogOutput")
        
        self._apply_theme_styles()
        
        self.log_layout.addWidget(self.log_output)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.log_container)
    
    def _download_log(self):
        """下载日志到 debug_screenshots 文件夹"""
        try:
            log_content = self.log_output.toPlainText()
            if not log_content.strip():
                self.append_log("[系统] 日志为空，无需保存")
                return
            
            debug_dir = cfg._get_application_path() / "debug_screenshots"
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_hhmmss")
            log_file = debug_dir / f"app_{timestamp}.log"
            
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(log_content)
            
            self.append_log(f"[系统] 日志已保存到: {log_file}")
        except Exception as e:
            self.append_log(f"[系统] 保存日志失败: {e}")
    
    def _apply_theme_styles(self):
        """应用主题样式"""
        is_dark = qconfig.theme.value == "Dark"
        bg = "#1f2937" if is_dark else "#f9fafb"
        hover_bg = "#273244" if is_dark else "#f3f4f6"
        border = "#374151" if is_dark else "#e5e7eb"
        hover_border = "#4b5563" if is_dark else "#d1d5db"
        text_color = "#e5e7eb" if is_dark else "#111827"
        self.log_output.setStyleSheet(f"""
            TextEdit {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                color: {text_color};
                padding: 8px;
            }}
            TextEdit:hover {{
                background-color: {hover_bg};
                border: 1px solid {hover_border};
            }}
        """)
    
    def append_log(self, text: str):
        """追加日志"""
        self.log_output.append(text)
    
    def get_log_content(self) -> str:
        """获取日志内容"""
        return self.log_output.toPlainText()
    
    def apply_theme(self):
        """应用主题样式"""
        self._apply_theme_styles()
