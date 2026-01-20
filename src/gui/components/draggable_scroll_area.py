from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QMouseEvent, QWheelEvent
from qfluentwidgets import SmoothScrollArea

class DraggableScrollArea(SmoothScrollArea):
    """
    支持鼠标拖拽和滚轮横向滚动的滚动区域
    同时隐藏了水平和垂直滚动条
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 隐藏滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 允许鼠标追踪
        self.setMouseTracking(True)
        
        # 拖拽相关变量
        self._is_dragging = False
        self._last_pos = None
        
        # 设置平滑滚动属性 (继承自 SmoothScrollArea)
        # SmoothScrollArea 默认开启平滑滚动，无需手动设置
        # self.setSmoothMode(True)
        
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._last_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._is_dragging = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_dragging and self._last_pos:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            
            # 水平拖拽
            h_bar = self.horizontalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        # 将垂直滚轮转换为水平滚动
        if event.angleDelta().y() != 0:
            h_bar = self.horizontalScrollBar()
            # 滚轮向下(负值) -> 向右滚动(增加 value)
            # 滚轮向上(正值) -> 向左滚动(减少 value)
            scroll_step = 40  # 滚动步长
            delta = -event.angleDelta().y() / 120 * scroll_step
            h_bar.setValue(h_bar.value() + delta)
            event.accept()
        else:
            super().wheelEvent(event)
