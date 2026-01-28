from PySide6.QtCore import Qt, Signal, QPoint, QRect, QTimer
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from PySide6.QtGui import (
    QMouseEvent,
    QPixmap,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QFont,
    QFontDatabase,
)
import os
from datetime import datetime
from src.config import cfg
from src.pokedex import pokedex, QUALITIES
from src.gui.components.fish_preview import FishPreviewItem


class OverlayWindow(QWidget):
    """
    一个悬浮窗,用于显示实时状态和提供快捷操作。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置窗口无边框、总在最前、工具窗口类型
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        # 设置背景透明
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 主框架,用于设置圆角和背景色
        main_frame = QFrame(self)
        main_frame.setObjectName("mainFrame")

        # 可爱字体配置 - 优先使用系统圆体字体
        # 按优先级尝试：华文圆体 > 幼圆 > 微软雅黑
        self._cute_font_family = "YouYuan"  # 幼圆 - Windows自带的圆润字体

        # 尝试加载自定义字体作为备选
        font_path = os.path.join("resources", "fonts", "ZCOOLKuaiLe-Regular.ttf")
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id >= 0:
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    self._cute_font_family = families[0]

        # --- 头像部分 ---
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(50, 50)
        self.avatar_label.setObjectName("avatarLabel")
        self.avatar_label.setScaledContents(True)  # 允许内容缩放以支持高清图

        # 加载头像
        avatar_path = os.path.join("resources", "avatar.png")
        if not os.path.exists(avatar_path):
            # 如果没有avatar.png,尝试使用favicon.ico
            avatar_path = os.path.join("resources", "favicon.ico")

        if os.path.exists(avatar_path):
            pixmap = QPixmap(avatar_path)
            # 处理头像:居中裁剪 + 圆角方形 + 高清边框
            self.avatar_label.setPixmap(self._process_avatar(pixmap, 50))

        # --- 文字信息部分 ---
        # 第一行:状态
        self.status_label = QLabel("准备好啦")
        self.status_label.setObjectName("statusLabel")
        # 设置可爱的圆润粗体字体
        status_font = QFont(self._cute_font_family)
        status_font.setPointSize(14)
        status_font.setBold(True)  # 加粗更可爱
        self.status_label.setFont(status_font)

        # 第二行:可卖额度 (图标 + 数字)
        self.limit_container = QWidget()
        limit_h_layout = QHBoxLayout(self.limit_container)
        limit_h_layout.setContentsMargins(0, 0, 0, 0)
        limit_h_layout.setSpacing(4)

        # 鱼干图标 (HiDPI 超采样渲染)
        self.limit_icon = QLabel()
        self.limit_icon.setObjectName("limitIcon")
        icon_path = os.path.join("resources", "fish_icon_nobg.png")
        icon_size = 18  # 显示尺寸
        if os.path.exists(icon_path):
            # 使用 2 倍分辨率渲染,确保高清显示
            render_size = icon_size * 2
            icon_pixmap = QPixmap(icon_path).scaled(
                render_size, render_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            icon_pixmap.setDevicePixelRatio(2.0)  # 设置设备像素比,实现 HiDPI 效果
            self.limit_icon.setPixmap(icon_pixmap)
        self.limit_icon.setFixedSize(icon_size, icon_size)

        # 数字标签
        self.limit_label = QLabel("900")
        self.limit_label.setObjectName("limitLabel")
        # 设置数字字体 - 使用 Comic Sans MS，公认的可爱手写风格数字
        limit_font = QFont("Comic Sans MS")
        limit_font.setPointSize(14)
        limit_font.setBold(True)
        self.limit_label.setFont(limit_font)

        limit_h_layout.addWidget(self.limit_icon)
        limit_h_layout.addWidget(self.limit_label)
        limit_h_layout.addStretch()

        # 文字布局 (垂直)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 5, 0, 5)
        text_layout.addWidget(self.status_label)
        text_layout.addWidget(self.limit_container)
        text_layout.setAlignment(Qt.AlignVCenter)

        # 1. 创建主容器和布局
        main_v_layout = QVBoxLayout(main_frame)
        main_v_layout.setContentsMargins(0, 0, 0, 0)
        main_v_layout.setSpacing(0)

        # 2. 上半部分:头像和文字 (水平)
        content_container = QWidget()
        content_layout = QHBoxLayout(content_container)
        content_layout.setContentsMargins(10, 5, 15, 5)
        content_layout.setSpacing(10)
        content_layout.addWidget(self.avatar_label)
        content_layout.addLayout(text_layout)

        # 3. 下半部分:鱼种预览 (水平)
        self.preview_container = QWidget()
        self.preview_layout = QHBoxLayout(self.preview_container)
        self.preview_layout.setSpacing(5)
        self.preview_layout.setContentsMargins(15, 0, 15, 8)
        self.preview_layout.setAlignment(Qt.AlignLeft)

        # 组装到主垂直布局
        main_v_layout.addWidget(content_container)
        main_v_layout.addWidget(self.preview_container)

        # 4. 设置窗口总布局 (包含 main_frame)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(main_frame)

        # 初始状态:如果没有预览内容,收起下方区域
        self.preview_container.setVisible(False)

        # 智能定时刷新 (使用 SingleShot 模式,在 update 中计算下次唤醒时间)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_fish_preview)

        # 初始更新
        # 初始更新
        self.update_fish_preview()

        # 监听图鉴数据变化
        pokedex.data_changed.connect(self.update_fish_preview)

        # 应用QSS样式
        self.apply_stylesheet()

        # 用于窗口拖动
        self._drag_start_position = None

    def _process_avatar(self, pixmap, size):
        """
        处理头像:
        1. 居中裁剪为正方形
        2. 绘制圆角方形 (Squircle)
        3. 绘制边框
        4. 使用2倍分辨率渲染以保证高清
        """
        # 渲染参数
        ratio = 2.0  # 高清倍率
        render_size = int(size * ratio)
        radius = int(12 * ratio)  # 圆角半径 (12px * 2 = 24px)
        border_width = int(2.5 * ratio)  # 边框宽度 (2.5px * 2 = 5px)
        border_color = QColor("#E6D2B4")

        # 1. 居中裁剪正方形
        img_size = pixmap.size()
        min_side = min(img_size.width(), img_size.height())
        x = (img_size.width() - min_side) // 2
        y = (img_size.height() - min_side) // 2

        # 复制并缩放到渲染尺寸
        square_pixmap = pixmap.copy(x, y, min_side, min_side)
        scaled_pixmap = square_pixmap.scaled(
            render_size, render_size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )

        # 2. 准备画布
        result_pixmap = QPixmap(render_size, render_size)
        result_pixmap.fill(Qt.transparent)

        painter = QPainter(result_pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # 定义绘制路径 (考虑边框的一半宽度,防止被切掉)
        # QRectF 参数: x, y, width, height
        # 内缩半个边框宽,确保边框完整画在画布内
        rect_margin = border_width / 2.0
        draw_rect = QRect(0, 0, render_size, render_size).adjusted(
            int(rect_margin), int(rect_margin), -int(rect_margin), -int(rect_margin)
        )

        path = QPainterPath()
        path.addRoundedRect(draw_rect, radius, radius)

        # 3. 绘制图片 (使用 Clip Path)
        painter.save()
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled_pixmap)
        painter.restore()

        # 4. 绘制边框
        pen = QPen(border_color, border_width)
        # 边框应该画在形状的轮廓上
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

        painter.end()

        return result_pixmap

    def apply_stylesheet(self):
        """应用QSS样式"""
        style = """
            #mainFrame {
                background-color: rgba(255, 245, 215, 0.9);
                border-radius: 30px;
                border: 3px solid rgba(230, 210, 180, 0.95);
            }
            #statusLabel {
                color: #5C4033;
                letter-spacing: 1px;
            }
            #limitLabel {
                color: #8C6A51;
                letter-spacing: 0.5px;
            }
            #limitIcon {
                background-color: transparent;
            }
            #avatarLabel {
                background-color: transparent;
            }
        """
        self.setStyleSheet(style)

    def update_status(self, status: str):
        """更新状态标签"""
        # 简化状态显示,去掉"状态: "前缀,让显示更紧凑
        display_text = status
        if "状态: " in status:
            display_text = status.replace("状态: ", "")

        # 特殊状态处理 - 使用更可爱的用词
        if "准备" in display_text:
            display_text = "准备好啦"
        elif "等待咬钩" in display_text:
            display_text = "等果冻鱼上钩中"
        elif "上鱼了" in display_text:
            display_text = "好鱼来了！"
        elif "鱼跑了" in display_text:
            display_text = "呜呜跑掉了"
        elif "未检测到游戏" in display_text or "环境检查失败" in display_text:
            display_text = "找不到游戏啦"
        elif "没有鱼饵" in display_text:
            display_text = "鱼饵用完啦"
        elif "鱼桶" in display_text and "满" in display_text:
            display_text = "鱼桶满满的"
        elif "抛竿" in display_text:
            display_text = "正在抛竿呢"
        elif "记录" in display_text:
            display_text = "记录中"
        elif "暂停" in display_text:
            display_text = "休息一下下"

        self.status_label.setText(display_text)

    def update_fish_count(self, count: int):
        """更新钓鱼计数 (保留接口兼容性,不再显示)"""
        pass  # 已移除钓鱼计数显示

    def update_limit(self, remaining: int, current_sales: int = 0):
        """更新剩余额度标签

        Args:
            remaining: 剩余可卖额度
            current_sales: 当前已卖金额
        """
        # 判断金额状态
        if current_sales == 899:
            # 刚好 899，完美！使用中文字体，字号小一些
            self.limit_label.setText("刚刚好！")
            self.limit_label.setStyleSheet(
                "color: #4CAF50; letter-spacing: 0.5px;"
            )  # 绿色表示完美
            # 中文使用与状态相同的幼圆字体，12pt
            limit_font = QFont(self._cute_font_family)
            limit_font.setPointSize(12)
            limit_font.setBold(True)
            self.limit_label.setFont(limit_font)
        elif remaining <= 0:
            # 超过 899，使用中文字体，字号小一些
            self.limit_label.setText("不能再卖鱼啦")
            self.limit_label.setStyleSheet(
                "color: #f57f17; letter-spacing: 0.5px;"
            )  # 橙色警告
            # 中文使用与状态相同的幼圆字体，12pt
            limit_font = QFont(self._cute_font_family)
            limit_font.setPointSize(12)
            limit_font.setBold(True)
            self.limit_label.setFont(limit_font)
        else:
            # 还有额度，显示剩余数量，使用数字字体，14pt
            self.limit_label.setText(str(remaining))
            if remaining < 100:
                self.limit_label.setStyleSheet(
                    "color: #f57f17; letter-spacing: 0.5px;"
                )  # 橙色提醒
            else:
                self.limit_label.setStyleSheet(
                    "color: #8C6A51; letter-spacing: 0.5px;"
                )  # 正常颜色
            # 数字使用 Comic Sans MS，14pt
            limit_font = QFont("Comic Sans MS")
            limit_font.setPointSize(14)
            limit_font.setBold(True)
            self.limit_label.setFont(limit_font)

    def update_fish_preview(self):
        """更新当前可钓鱼种预览"""
        try:
            # 1. 清空旧图标
            while self.preview_layout.count():
                item = self.preview_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # 2. 获取当前时段和可钓鱼
            current_time = pokedex.get_current_game_time()
            all_fish = pokedex.get_all_fish()

            # 使用 filter_fish_multi 筛选当前时段
            catchable_fish = pokedex.filter_fish_multi(
                all_fish, {"time": [current_time]}
            )

            # 过滤掉已完全收集的 (所有品质都已有)
            visible_fish = []
            for fish in catchable_fish:
                status = pokedex.get_collection_status(fish["name"])
                # 如果有任意品质未收集(即为None)，则保留
                if not all(status.get(q) is not None for q in QUALITIES):
                    visible_fish.append(fish)
            catchable_fish = visible_fish

            # 应用类型过滤 (同步 Home 界面设置)
            filter_mode = getattr(cfg, "fish_filter_mode", "all")
            if filter_mode == "lure":
                catchable_fish = [
                    f for f in catchable_fish if "路亚" in f.get("type", "")
                ]
            elif filter_mode == "ice":
                catchable_fish = [
                    f for f in catchable_fish if "冰钓" in f.get("type", "")
                ]

            if not catchable_fish:
                self.preview_container.setVisible(False)
                self.adjustSize()
                return

            self.preview_container.setVisible(True)

            # 3. 排序:复用 Pokedex 的加权排序 (未收集高品质者优先)
            # sort_key='progress', reverse=False -> 未收集权重高的排在前面
            sorted_fish = pokedex.sort_fish(
                catchable_fish, sort_key="progress", reverse=False
            )

            # 4. 取前5个显示
            for fish in sorted_fish[:5]:
                fish_name = fish.get("name", "Unknown")
                image_path = pokedex.get_fish_image_path(fish_name)

                preview_item = FishPreviewItem(
                    fish_name, str(image_path) if image_path else None
                )
                preview_item.setToolTip(f"{fish_name} ({current_time})")
                self.preview_layout.addWidget(preview_item)

            # 强制窗口根据内容调整大小
            self.adjustSize()

        except Exception as e:
            print(f"[Overlay] 更新预览失败: {e}")

        finally:
            # 计算下一次刷新的时间 (距离下一个整10分钟节点的秒数)
            # 游戏时间每10分钟变化一次 (0-10, 10-20...)
            now = datetime.now()
            # 剩余分钟数 = 10 - 当前分钟个位数
            minutes_left = 10 - (now.minute % 10)
            # 目标秒数 = 剩余分钟 * 60 - 当前秒数
            # 多加 2 秒缓冲,确保肯定跨过了时间边界
            seconds_to_wait = minutes_left * 60 - now.second + 2

            if seconds_to_wait <= 0:
                seconds_to_wait = 1

            # print(f"[Overlay] 下次刷新将在 {seconds_to_wait} 秒后")
            self.preview_timer.start(seconds_to_wait * 1000)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self._drag_start_position = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self._drag_start_position:
            self.move(event.globalPosition().toPoint() - self._drag_start_position)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._drag_start_position = None
        event.accept()
