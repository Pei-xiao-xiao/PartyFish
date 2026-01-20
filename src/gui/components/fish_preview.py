from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor, QPen
import os

class FishPreviewItem(QWidget):
    """
    悬浮窗鱼类预览小图标
    """
    def __init__(self, fish_name, image_path, parent=None):
        super().__init__(parent)
        self.fish_name = fish_name
        self.image_path = image_path
        self.setFixedSize(32, 32)  # 缩小后的尺寸
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setScaledContents(True)
        
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.icon_label.setPixmap(self._process_icon(pixmap, 32))
        
        self.layout.addWidget(self.icon_label)
        
    def _process_icon(self, pixmap, size):
        """
        处理图标：圆角矩形背景 + 居中缩放鱼类
        """
        ratio = 2.0  # HiDPI
        render_size = int(size * ratio)
        radius = int(8 * ratio)
        
        result_pixmap = QPixmap(render_size, render_size)
        result_pixmap.fill(Qt.transparent)
        
        painter = QPainter(result_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # 绘制背景
        bg_color = QColor(230, 210, 180, 100)  # 暖色系半透明背景
        path = QPainterPath()
        path.addRoundedRect(0, 0, render_size, render_size, radius, radius)
        painter.fillPath(path, bg_color)
        
        # 绘制鱼图标 (预留边距)
        margin = int(4 * ratio)
        fish_rect = QRect(margin, margin, render_size - 2 * margin, render_size - 2 * margin)
        
        # 缩放并居中绘制鱼
        scaled_fish = pixmap.scaled(fish_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = fish_rect.x() + (fish_rect.width() - scaled_fish.width()) // 2
        y = fish_rect.y() + (fish_rect.height() - scaled_fish.height()) // 2
        painter.drawPixmap(x, y, scaled_fish)
        
        painter.end()
        result_pixmap.setDevicePixelRatio(ratio)  # 设置设备像素比，实现真正的 HiDPI 效果
        return result_pixmap
