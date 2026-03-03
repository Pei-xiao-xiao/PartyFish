from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import (
    Qt,
    QPropertyAnimation,
    QPoint,
    QEasingCurve,
    Signal,
    QRect,
    QEvent,
)
from PySide6.QtGui import QColor, QPainter

from src.gui.components.filter_panel import FilterPanel


class FilterDrawer(QWidget):
    """
    侧边抽屉式筛选栏
    - 全屏透明遮罩
    - 右侧滑出面板
    """

    filterChanged = Signal(dict)

    def __init__(self, parent=None, initial_criteria=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # 确保覆盖在最上层
        self.raise_()

        # 记录父窗口以便调整大小
        self.parent_widget = parent
        if parent:
            parent.installEventFilter(self)
        if parent:
            self._adjust_geometry()

        self.panel_width = 340

        # 筛选面板
        self.panel = FilterPanel(self)
        self.panel.setFixedSize(self.panel_width, self.height())
        self.panel.set_criteria(initial_criteria)
        self.panel.refresh_theme()
        self.panel.filterChanged.connect(self.filterChanged)

        # 初始位置：屏幕右侧之外
        self.panel.move(self.width(), 0)

        # 动画
        self.animation = QPropertyAnimation(self.panel, b"pos")
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        # 显示并开始动画
        self.show()
        self.slide_in()

    def _title_bar_height(self):
        """获取标题栏高度"""
        # FluentWindow 的 titleBar 属性
        if self.parent_widget and hasattr(self.parent_widget, "titleBar"):
            return self.parent_widget.titleBar.height()
        return 0

    def _adjust_geometry(self):
        """调整自身大小和位置"""
        if not self.parent_widget:
            return

        h_offset = self._title_bar_height()
        # 自身覆盖在标题栏下方区域
        self.setGeometry(
            0,
            h_offset,
            self.parent_widget.width(),
            self.parent_widget.height() - h_offset,
        )

    def slide_in(self):
        """滑入动画"""
        self.animation.stop()
        self.animation.setStartValue(QPoint(self.width(), 0))
        self.animation.setEndValue(QPoint(self.width() - self.panel_width, 0))
        self.animation.start()

    def slide_out(self):
        """滑出动画"""
        self.animation.stop()
        self.animation.setStartValue(self.panel.pos())
        self.animation.setEndValue(QPoint(self.width(), 0))
        self.animation.finished.connect(self.close)
        self.animation.start()

    def resizeEvent(self, event):
        """跟随父窗口大小"""
        # 注意: 这里的 self 已经是被 setGeometry 设置过的大小（不包含标题栏）
        # 所以 panel 的高度就是 self.height()
        self.panel.setFixedHeight(self.height())

        # 重新调整自身 geometry 以匹配父窗口变化 (如果父窗口大小变了，我们需要刷新 geometry)
        # 但 resizeEvent 是自身大小变化触发的...
        # 逻辑：当父窗口 resize 时，会触发 layout update or we need an event filter.
        # 不过通常 Overlay 这种做全屏覆盖的，需要 connect parent 的 resize 信号
        # 或者仅仅依靠 resizeEvent 可能不够，因为如果父窗口变大，我们还没变大。
        # 简单处理：在 __init__ 不需要绑定 resize，因为我们是其 child，如果不设 layout，大小不自动跟随后果自负。
        # 最好的方式是 installEventFilter 到 parent。
        pass

    def parentResizeEvent(self):
        """手动调用，当父窗口大小改变时"""
        self._adjust_geometry()
        self.panel.setFixedHeight(self.height())
        if self.animation.state() == QPropertyAnimation.Stopped:
            self.panel.move(self.width() - self.panel_width, 0)

    def refresh_theme(self):
        if hasattr(self.panel, "refresh_theme"):
            self.panel.refresh_theme()

    # 更加稳健的方式：重写 eventFilter
    def eventFilter(self, obj, event):
        if obj == self.parent_widget and event.type() == QEvent.Resize:
            self._adjust_geometry()
            # 同时也需要更新 panel 位置
            if self.animation.state() == QPropertyAnimation.Stopped:
                self.panel.move(self.width() - self.panel_width, 0)
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        """绘制透明背景"""
        # 虽然 user 要求全透明，但这里保留 paintEvent 结构以便未来扩展（如半透明）
        # 目前不做任何绘制，保持完全透明
        pass

    def mousePressEvent(self, event):
        """点击遮罩关闭"""
        # 检查点击位置是否在面板外
        if not self.panel.geometry().contains(event.pos()):
            self.slide_out()
        else:
            super().mousePressEvent(event)
