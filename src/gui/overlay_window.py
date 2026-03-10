from PySide6.QtCore import Qt, Signal, QPoint, QRect, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QApplication,
)
from PySide6.QtGui import (
    QMouseEvent,
    QPixmap,
    QPainter,
    QPainterPath,
    QColor,
    QPen,
    QFont,
    QFontDatabase,
    QScreen,
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
        font_path = os.path.join(
            str(cfg._get_base_path()), "resources", "fonts", "ZCOOLKuaiLe.ttf"
        )
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
        avatar_path = os.path.join(str(cfg._get_base_path()), "resources", "avatar.png")
        if not os.path.exists(avatar_path):
            # 如果没有avatar.png,尝试使用favicon.ico
            avatar_path = os.path.join(
                str(cfg._get_base_path()), "resources", "favicon.ico"
            )

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
        icon_path = os.path.join(
            str(cfg._get_base_path()), "resources", "fish_icon_nobg.png"
        )
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

        # UNO状态显示（第三行）
        self.uno_container = QWidget()
        uno_h_layout = QHBoxLayout(self.uno_container)
        uno_h_layout.setContentsMargins(0, 0, 0, 0)
        uno_h_layout.setSpacing(4)

        # UNO图标/标签
        self.uno_icon = QLabel("🎴")
        self.uno_icon.setObjectName("unoIcon")
        self.uno_icon.setFixedSize(18, 18)

        # UNO牌数标签
        self.uno_label = QLabel(
            f"UNO: 7/{cfg.global_settings.get('uno_max_cards', 35)}"
        )
        self.uno_label.setObjectName("unoLabel")
        uno_font = QFont(self._cute_font_family)
        uno_font.setPointSize(11)
        uno_font.setBold(True)
        self.uno_label.setFont(uno_font)

        # UNO倒计时标签
        self.uno_countdown_label = QLabel("")
        self.uno_countdown_label.setObjectName("unoCountdownLabel")
        countdown_font = QFont("Comic Sans MS")
        countdown_font.setPointSize(12)
        countdown_font.setBold(True)
        self.uno_countdown_label.setFont(countdown_font)
        self.uno_countdown_label.setVisible(False)

        uno_h_layout.addWidget(self.uno_icon)
        uno_h_layout.addWidget(self.uno_label)
        uno_h_layout.addWidget(self.uno_countdown_label)
        uno_h_layout.addStretch()

        # 默认隐藏UNO显示
        self.uno_container.setVisible(False)

        # 文字布局 (垂直)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 5, 0, 5)
        text_layout.addWidget(self.status_label)
        text_layout.addWidget(self.limit_container)
        text_layout.addWidget(self.uno_container)
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
        self.main_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        self.main_layout.addWidget(main_frame)

        # 初始状态:如果没有预览内容,收起下方区域
        self.preview_container.setVisible(False)

        # 缓存上次检测到的条件，避免每秒重建UI
        self._last_time = None
        self._last_weather = None

        # 智能定时检测条件变化
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self._check_conditions)

        # 初始更新
        self._check_conditions()

        # 监听图鉴数据变化
        pokedex.data_changed.connect(self.update_fish_preview)

        # 应用QSS样式
        self.apply_stylesheet()

        # 用于窗口拖动
        self._drag_start_position = None

        # 设置默认位置：当前屏幕左上角
        self._set_default_position()

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
            #unoIcon {
                background-color: transparent;
                font-size: 14px;
            }
            #unoLabel {
                color: #FF6B35;
                letter-spacing: 0.5px;
            }
            #unoCountdownLabel {
                color: #f57f17;
                letter-spacing: 0.5px;
                margin-left: 4px;
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
            display_text = "准备好了"
        elif "等待咬钩" in display_text:
            display_text = "等鱼上钩中..."
        elif "上鱼了" in display_text:
            display_text = "好鱼来了！"
        elif "鱼跑了" in display_text:
            display_text = "鱼跑掉了"
        elif "未检测到游戏" in display_text or "环境检查失败" in display_text:
            display_text = "找不到游戏了"
        elif "没有鱼饵" in display_text:
            display_text = "鱼饵用完了"
        elif "切换鱼饵" in display_text:
            display_text = "切鱼饵中..."
        elif "寻找可用鱼饵" in display_text:
            display_text = "检查鱼饵中..."
        elif "鱼桶" in display_text and "满" in display_text:
            display_text = "鱼桶满了"
        elif "抛竿" in display_text:
            display_text = "正在抛竿..."
        elif "放生" in display_text:
            display_text = "正在放生..."
        elif "记录" in display_text:
            display_text = "记录中"
        elif "暂停" in display_text:
            display_text = "休息一下"

        self.status_label.setText(display_text)

    def update_fish_count(self, count: int):
        """更新钓鱼计数 (保留接口兼容性,不再显示)"""
        pass  # 已移除钓鱼计数显示

    def update_uno_cards(self, current: int, maximum: int, is_running: bool = True):
        """更新UNO牌数显示

        Args:
            current: 当前牌数
            maximum: 最大牌数
            is_running: 是否正在运行
        """
        if is_running:
            self.uno_container.setVisible(True)
            self.uno_label.setText(f"UNO: {current}/{maximum}")

            # 根据进度改变颜色
            progress = current / maximum if maximum > 0 else 0
            if progress >= 0.9:
                self.uno_label.setStyleSheet(
                    "color: #4CAF50; letter-spacing: 0.5px;"  # 绿色 - 即将完成
                )
            elif progress >= 0.5:
                self.uno_label.setStyleSheet(
                    "color: #FF9800; letter-spacing: 0.5px;"  # 橙色 - 过半
                )
            else:
                self.uno_label.setStyleSheet(
                    "color: #FF6B35; letter-spacing: 0.5px;"  # 默认橙红色
                )
        else:
            self.uno_container.setVisible(False)

        # 调整窗口大小
        self.adjustSize()

    def update_uno_countdown(self, seconds: int):
        """更新UNO倒计时显示

        Args:
            seconds: 剩余秒数，0或负数表示隐藏
        """
        if seconds > 0:
            self.uno_countdown_label.setVisible(True)
            self.uno_countdown_label.setText(f"⏱️ {seconds}s")
            # 倒计时颜色：最后3秒变红
            if seconds <= 3:
                self.uno_countdown_label.setStyleSheet(
                    "color: #f44336; letter-spacing: 0.5px; margin-left: 4px;"  # 红色
                )
            else:
                self.uno_countdown_label.setStyleSheet(
                    "color: #f57f17; letter-spacing: 0.5px; margin-left: 4px;"  # 橙色
                )
        else:
            self.uno_countdown_label.setVisible(False)
            self.uno_countdown_label.setText("")

        self.adjustSize()

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

    def _check_conditions(self):
        """每秒检测天气和时段，变化时才刷新UI"""
        try:
            current_time = pokedex.get_current_game_time()
            current_weather = pokedex.detect_current_weather()

            # 游戏窗口不存在或最小化时，暂停刷新并保留上次状态
            if cfg.game_hwnd is None or cfg.screen_width <= 0 or cfg.screen_height <= 0:
                return

            if current_time != self._last_time or current_weather != self._last_weather:
                self._last_time = current_time
                self._last_weather = current_weather
                self.update_fish_preview()
        except Exception as e:
            print(f"[Overlay] 检测条件失败: {e}")
        finally:
            self.preview_timer.start(1000)

    def update_fish_preview(self):
        """更新当前可钓鱼种预览（仅在条件变化时调用）"""
        try:
            # 1. 清空旧图标
            while self.preview_layout.count():
                item = self.preview_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            current_time = self._last_time
            current_weather = self._last_weather

            # 构建筛选条件：时间 + 天气 + 季节（排除冬季）
            criteria = {"time": [current_time]}
            if current_weather:
                criteria["weather"] = [current_weather]
            if cfg.global_settings.get("enable_season_filter", True):
                criteria["season"] = ["春季"]
            else:
                criteria["season"] = ["春季", "夏季", "秋季"]

            all_fish = pokedex.get_all_fish()
            catchable_fish = pokedex.filter_fish_multi(all_fish, criteria)

            # 过滤掉已完全收集的 (所有品质都已有)
            visible_fish = []
            for fish in catchable_fish:
                status = pokedex.get_collection_status(fish["name"])
                # 如果有任意品质未收集(即为None)，则保留
                if not all(status.get(q) is not None for q in QUALITIES):
                    visible_fish.append(fish)
            catchable_fish = visible_fish

            # 过滤掉冰钓鱼种
            catchable_fish = [
                f for f in catchable_fish if "冰钓" not in f.get("type", "")
            ]

            # 应用类型过滤 (同步 Home 界面设置)
            filter_mode = getattr(cfg, "fish_filter_mode", "all")
            if filter_mode == "lure":
                catchable_fish = [
                    f for f in catchable_fish if "路亚" in f.get("type", "")
                ]
            elif filter_mode == "ice":
                catchable_fish = [
                    f for f in catchable_fish if "池塘" in f.get("type", "")
                ]

            rod_filter_mode = getattr(cfg, "rod_filter_mode", "all")
            if rod_filter_mode == "heavy":
                catchable_fish = [
                    f for f in catchable_fish if "重竿" in f.get("type", "")
                ]
            elif rod_filter_mode == "light":
                catchable_fish = [
                    f for f in catchable_fish if "轻竿" in f.get("type", "")
                ]

            if not catchable_fish:
                self.preview_container.setVisible(False)
                self.adjustSize()
                return

            self.preview_container.setVisible(True)

            # 3. 排序:复用 Pokedex 的加权排序 (未收集高品质者优先)
            sorted_fish = pokedex.sort_fish(
                catchable_fish, sort_key="progress", reverse=False
            )

            # 4. 按地点分组显示：[地点图标][鱼1][鱼2]... | [地点图标][鱼3]...
            displayed_fish = sorted_fish[:5]
            loc_base = str(cfg._get_base_path() / "resources" / "location")

            # 为每条鱼找到匹配当前条件的地点
            fish_by_location = {}
            for fish in displayed_fish:
                fish_locs = set()
                for loc in fish.get("locations", []):
                    raw_loc = loc.get("location", "")
                    loc_list = (
                        raw_loc
                        if isinstance(raw_loc, list)
                        else [raw_loc] if raw_loc else []
                    )
                    for cond in loc.get("conditions", []):
                        time_ok = not current_time or current_time in cond.get(
                            "time_of_day", []
                        )
                        weather_ok = not current_weather or current_weather in cond.get(
                            "weather", []
                        )
                        season_ok = not cfg.global_settings.get(
                            "enable_season_filter", True
                        ) or "春季" in cond.get("season", [])
                        if time_ok and weather_ok and season_ok:
                            fish_locs.update(loc_list)
                # 取第一个匹配地点作为分组键
                loc_key = sorted(fish_locs)[0] if fish_locs else ""
                fish_by_location.setdefault(loc_key, []).append(fish)

            first_group = True
            for loc_name in sorted(fish_by_location.keys()):
                if not first_group:
                    sep = QLabel()
                    sep.setFixedSize(1, 24)
                    sep.setStyleSheet("background-color: rgba(255,255,255,80);")
                    self.preview_layout.addWidget(sep)
                first_group = False

                # 该地点的鱼
                for fish in fish_by_location[loc_name]:
                    fish_name = fish.get("name", "Unknown")
                    image_path = pokedex.get_fish_image_path(fish_name)
                    loc_icon_path = (
                        os.path.join(loc_base, f"{loc_name}.png") if loc_name else None
                    )
                    preview_item = FishPreviewItem(
                        fish_name,
                        str(image_path) if image_path else None,
                        loc_icon_path,
                    )
                    preview_item.setToolTip(f"{fish_name} ({loc_name})")
                    self.preview_layout.addWidget(preview_item)

            # 强制窗口根据内容调整大小
            self.adjustSize()

        except Exception as e:
            print(f"[Overlay] 更新预览失败: {e}")

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

    def _set_default_position(self):
        """设置悬浮窗默认位置为当前屏幕中心"""
        # 获取鼠标所在的屏幕（即当前活动屏幕）
        cursor_pos = QApplication.primaryScreen().geometry().center()
        screen = QApplication.screenAt(QPoint(cursor_pos.x(), cursor_pos.y()))
        if not screen:
            screen = QApplication.primaryScreen()

        # 获取屏幕几何信息
        screen_geometry = screen.availableGeometry()

        # 设置窗口位置为屏幕中心
        x = screen_geometry.center().x() - self.width() // 2
        y = screen_geometry.center().y() - self.height() // 2

        self.move(x, y)
