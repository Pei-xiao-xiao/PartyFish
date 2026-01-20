"""
首页专用的鱼种卡片组件
显示大图、名称、品质收集状态
"""
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPixmap, QPainter, QPainterPath, QColor
import os

from src.pokedex import pokedex, QUALITIES
from src.gui.components import QUALITY_COLORS


class HomeFishCard(QWidget):
    """
    首页鱼种卡片 - 显示可钓鱼种信息和收集状态
    """
    def __init__(self, fish_data: dict, parent=None):
        super().__init__(parent)
        self.fish_data = fish_data
        self.fish_name = fish_data.get('name', 'Unknown')
        
        self.setFixedSize(120, 155)
        
        self._init_ui()
        self._update_collection_status()
    
    def _init_ui(self):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignCenter)
        
        # 鱼类图片
        self.image_label = QLabel(self)
        self.image_label.setFixedSize(88, 88)
        self.image_label.setAlignment(Qt.AlignCenter)
        
        image_path = pokedex.get_fish_image_path(self.fish_name)
        if image_path and os.path.exists(str(image_path)):
            pixmap = QPixmap(str(image_path))
            self.image_label.setPixmap(self._process_image(pixmap, 88))
        
        layout.addWidget(self.image_label, 0, Qt.AlignCenter)
        
        # 鱼名
        self.name_label = QLabel(self.fish_name, self)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 500;
                color: #374151;
            }
        """)
        layout.addWidget(self.name_label, 0, Qt.AlignCenter)
        
        # 品质收集状态（5个圆点）
        self.dots_container = QWidget(self)
        self.dots_layout = QHBoxLayout(self.dots_container)
        self.dots_layout.setContentsMargins(0, 0, 0, 0)
        self.dots_layout.setSpacing(3)
        self.dots_layout.setAlignment(Qt.AlignCenter)
        
        self.quality_dots = {}
        for quality in QUALITIES:
            dot = QLabel(self.dots_container)
            dot.setFixedSize(10, 10)
            self.quality_dots[quality] = dot
            self.dots_layout.addWidget(dot)
        
        layout.addWidget(self.dots_container, 0, Qt.AlignCenter)
        
        # 卡片背景样式
        self.setStyleSheet("""
            HomeFishCard {
                background-color: rgba(255, 255, 255, 0.8);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.05);
            }
        """)
    
    def _process_image(self, pixmap: QPixmap, size: int) -> QPixmap:
        """处理鱼类图片：HiDPI + 圆角背景"""
        ratio = 2.0
        render_size = int(size * ratio)
        radius = int(12 * ratio)
        
        result = QPixmap(render_size, render_size)
        result.fill(Qt.transparent)
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        
        # 绘制背景
        bg_color = QColor(245, 240, 230, 180)  # 暖色调背景
        path = QPainterPath()
        path.addRoundedRect(0, 0, render_size, render_size, radius, radius)
        painter.fillPath(path, bg_color)
        
        # 绘制鱼图
        margin = int(6 * ratio)
        fish_rect = QRect(margin, margin, render_size - 2 * margin, render_size - 2 * margin)
        scaled_fish = pixmap.scaled(fish_rect.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        x = fish_rect.x() + (fish_rect.width() - scaled_fish.width()) // 2
        y = fish_rect.y() + (fish_rect.height() - scaled_fish.height()) // 2
        painter.drawPixmap(x, y, scaled_fish)
        
        painter.end()
        result.setDevicePixelRatio(ratio)
        return result
    
    def _update_collection_status(self):
        """更新品质收集状态显示"""
        collection_status = pokedex.get_collection_status(self.fish_name)
        
        for quality, dot in self.quality_dots.items():
            is_collected = collection_status.get(quality) is not None
            
            # 获取品质对应的颜色
            if quality in QUALITY_COLORS:
                color = QUALITY_COLORS[quality][0]  # 使用浅色主题颜色
            else:
                color = QColor("#9ca3af")
            
            if is_collected:
                # 实心圆 - 已收集
                dot.setStyleSheet(f"""
                    QLabel {{
                        background-color: {color.name()};
                        border-radius: 5px;
                    }}
                """)
            else:
                # 空心圆 - 未收集
                dot.setStyleSheet(f"""
                    QLabel {{
                        background-color: transparent;
                        border: 2px solid {color.name()};
                        border-radius: 5px;
                    }}
                """)
