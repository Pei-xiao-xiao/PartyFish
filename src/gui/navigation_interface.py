from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtGui import (
    QPixmap,
    QPainter,
    QColor,
    QPen,
    QFont,
)
from PySide6.QtCore import Qt, QPoint, QTimer
from qfluentwidgets import (
    CardWidget,
    BodyLabel,
    TitleLabel,
    StrongBodyLabel,
    CaptionLabel,
    IconWidget,
    FluentIcon as FIF,
    InfoBadge,
    InfoLevel,
)
from src.config import cfg
from src.map_matcher import MapMatcher
from pathlib import Path


class MapWidget(QWidget):
    """地图显示组件，支持在地图上绘制标记点"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("MapWidget")
        
        self.map_pixmap = None
        self.player_point = None
        self.center_point = None
        self.markers = []
        
        self.setMinimumSize(600, 400)
        self.setStyleSheet("background-color: #f5f5f5; border-radius: 8px;")

    def load_map(self, map_path: Path):
        """加载地图图片"""
        if map_path.exists():
            self.map_pixmap = QPixmap(str(map_path))
            self.update()

    def set_center_point(self, x: float, y: float):
        """设置地图中心点坐标（相对坐标 0-1）"""
        self.center_point = (x, y)
        self.update()

    def set_player_position(self, x: float, y: float):
        """设置玩家位置（相对坐标 0-1）"""
        self.player_point = (x, y)
        self.update()

    def add_marker(self, x: float, y: float, color: QColor = QColor(52, 211, 153)):
        """添加标记点（相对坐标 0-1）"""
        self.markers.append({"x": x, "y": y, "color": color})
        self.update()

    def clear_markers(self):
        """清除所有标记点"""
        self.markers = []
        self.update()

    def paintEvent(self, event):
        """绘制地图和标记点"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self.map_pixmap:
            scaled_pixmap = self.map_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
            
            map_width = scaled_pixmap.width()
            map_height = scaled_pixmap.height()
            
            if self.player_point:
                px, py = self.player_point
                player_x = x + int(px * map_width)
                player_y = y + int(py * map_height)
                
                painter.setPen(QPen(QColor(52, 211, 153), 3))
                painter.setBrush(QColor(52, 211, 153))
                painter.drawEllipse(QPoint(player_x, player_y), 10, 10)
                
                painter.setPen(QPen(QColor(52, 211, 153, 150), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPoint(player_x, player_y), 18, 18)
            
            for marker in self.markers:
                mx, my = marker["x"], marker["y"]
                marker_x = x + int(mx * map_width)
                marker_y = y + int(my * map_height)
                
                painter.setPen(QPen(marker["color"], 2))
                painter.setBrush(marker["color"])
                painter.drawEllipse(QPoint(marker_x, marker_y), 6, 6)
        else:
            painter.fillRect(self.rect(), QColor(240, 240, 240))
            painter.setPen(QPen(QColor(200, 200, 200), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))


class NavigationInterface(QWidget):
    """导航界面 - 显示地图和坐标信息"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("NavigationInterface")

        self.current_x = 1280.0
        self.current_y = 720.0
        self.is_calibrated = False
        self.calibration_count = 0
        self.navigation_path = []
        self.auto_navigate_enabled = False
        
        # 定义两个目标点
        self.target_points = {
            "wote": (440, 407),
            "jiafu": (505, 487)
        }

        self.v_box_layout = QVBoxLayout(self)
        self.v_box_layout.setContentsMargins(40, 40, 40, 20)
        self.v_box_layout.setSpacing(24)

        self._init_map_matcher()
        self._init_header()
        self._init_main_content()
        self._init_footer()
        self._start_update_timer()
        
        # 初始化Vision对象
        from src.vision import Vision
        self.vision = Vision()
        self.vision._ensure_loaded()

    def _init_map_matcher(self):
        """初始化地图匹配器"""
        map_path = cfg._get_base_path() / "resources" / "maps" / "ditu.png"
        self.map_matcher = MapMatcher(map_path)

    def _init_header(self):
        """初始化标题区域"""
        self.header_container = QWidget(self)
        header_layout = QHBoxLayout(self.header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        header_icon = IconWidget(FIF.VIEW, self.header_container)
        header_icon.setFixedSize(24, 24)

        header_title = TitleLabel("地图导航", self.header_container)

        header_layout.addWidget(header_icon)
        header_layout.addWidget(header_title)
        header_layout.addStretch(1)

        self.v_box_layout.addWidget(self.header_container)

    def _init_main_content(self):
        """初始化主要内容区域"""
        content_layout = QHBoxLayout()
        content_layout.setSpacing(24)

        self._init_map_area()
        self._init_coordinate_panel()

        content_layout.addWidget(self.map_container, 3)
        content_layout.addWidget(self.coordinate_container, 1)

        self.v_box_layout.addLayout(content_layout)

    def _init_map_area(self):
        """初始化地图区域"""
        self.map_container = CardWidget(self)
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(20, 20, 20, 20)
        map_layout.setSpacing(16)

        map_header = QHBoxLayout()
        map_icon = IconWidget(FIF.VIEW, self.map_container)
        map_icon.setFixedSize(16, 16)
        map_title = StrongBodyLabel("当前地图", self.map_container)
        
        self.map_status_badge = InfoBadge.info("", self.map_container)
        self.map_status_badge.setFixedHeight(20)
        
        map_header.addWidget(map_icon)
        map_header.addWidget(map_title)
        map_header.addWidget(self.map_status_badge)
        map_header.addStretch(1)
        map_layout.addLayout(map_header)

        self.map_widget = MapWidget(self.map_container)
        map_layout.addWidget(self.map_widget, 1)

        map_path = cfg._get_base_path() / "resources" / "maps" / "ditu.png"
        self.map_widget.load_map(map_path)
        self.map_widget.set_center_point(0.5, 0.5)

    def _init_coordinate_panel(self):
        """初始化坐标信息面板"""
        self.coordinate_container = CardWidget(self)
        coord_layout = QVBoxLayout(self.coordinate_container)
        coord_layout.setContentsMargins(20, 20, 20, 20)
        coord_layout.setSpacing(16)

        coord_header = QHBoxLayout()
        coord_icon = IconWidget(FIF.TAG, self.coordinate_container)
        coord_icon.setFixedSize(16, 16)
        coord_title = StrongBodyLabel("坐标信息", self.coordinate_container)
        
        coord_header.addWidget(coord_icon)
        coord_header.addWidget(coord_title)
        coord_header.addStretch(1)
        coord_layout.addLayout(coord_header)

        self._create_coordinate_display(coord_layout)
        self._create_status_display(coord_layout)
        self._create_params_display(coord_layout)

        coord_layout.addStretch(1)

    def _create_coordinate_display(self, parent_layout):
        """创建坐标显示区域"""
        coord_display = QWidget()
        coord_display_layout = QVBoxLayout(coord_display)
        coord_display_layout.setContentsMargins(0, 0, 0, 0)
        coord_display_layout.setSpacing(12)

        x_container = QWidget()
        x_layout = QHBoxLayout(x_container)
        x_layout.setContentsMargins(0, 0, 0, 0)
        x_layout.setSpacing(8)
        
        x_label = CaptionLabel("X 坐标:", x_container)
        x_label.setStyleSheet("color: #6b7280; font-size: 13px;")
        self.x_value = BodyLabel(f"{self.current_x:.1f}", x_container)
        self.x_value.setStyleSheet(
            "color: #0ea5e9; font-size: 18px; font-weight: bold;"
        )
        
        x_layout.addWidget(x_label)
        x_layout.addWidget(self.x_value)
        x_layout.addStretch(1)
        coord_display_layout.addWidget(x_container)

        y_container = QWidget()
        y_layout = QHBoxLayout(y_container)
        y_layout.setContentsMargins(0, 0, 0, 0)
        y_layout.setSpacing(8)
        
        y_label = CaptionLabel("Y 坐标:", y_container)
        y_label.setStyleSheet("color: #6b7280; font-size: 13px;")
        self.y_value = BodyLabel(f"{self.current_y:.1f}", y_container)
        self.y_value.setStyleSheet(
            "color: #0ea5e9; font-size: 18px; font-weight: bold;"
        )
        
        y_layout.addWidget(y_label)
        y_layout.addWidget(self.y_value)
        y_layout.addStretch(1)
        coord_display_layout.addWidget(y_container)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #e5e7eb; border: none;")
        coord_display_layout.addWidget(separator)

        parent_layout.addWidget(coord_display)

    def _create_status_display(self, parent_layout):
        """创建状态显示区域"""
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        
        self.status_icon = IconWidget(FIF.INFO, status_container)
        self.status_icon.setFixedSize(14, 14)
        self.status_label = CaptionLabel("等待校准...", status_container)
        self.status_label.setStyleSheet("color: #94a3b8;")
        
        status_layout.addWidget(self.status_icon)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch(1)
        parent_layout.addWidget(status_container)

    def _create_params_display(self, parent_layout):
        """创建参数显示区域"""
        params_container = QWidget()
        params_layout = QVBoxLayout(params_container)
        params_layout.setContentsMargins(0, 0, 0, 0)
        params_layout.setSpacing(8)

        scale_container = QWidget()
        scale_layout = QHBoxLayout(scale_container)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.setSpacing(8)

        scale_label = CaptionLabel("缩放比:", scale_container)
        scale_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.scale_value = CaptionLabel("--", scale_container)
        self.scale_value.setStyleSheet("color: #0ea5e9; font-size: 12px;")

        scale_layout.addWidget(scale_label)
        scale_layout.addWidget(self.scale_value)
        scale_layout.addStretch(1)
        params_layout.addWidget(scale_container)

        translation_container = QWidget()
        trans_layout = QHBoxLayout(translation_container)
        trans_layout.setContentsMargins(0, 0, 0, 0)
        trans_layout.setSpacing(8)

        trans_label = CaptionLabel("平移:", translation_container)
        trans_label.setStyleSheet("color: #6b7280; font-size: 12px;")
        self.trans_value = CaptionLabel("--", translation_container)
        self.trans_value.setStyleSheet("color: #0ea5e9; font-size: 12px;")

        trans_layout.addWidget(trans_label)
        trans_layout.addWidget(self.trans_value)
        trans_layout.addStretch(1)
        params_layout.addWidget(translation_container)

        params_layout.addStretch(1)
        parent_layout.addWidget(params_container)

    def _init_footer(self):
        """初始化底部校准按钮"""
        footer_container = QWidget()
        footer_layout = QHBoxLayout(footer_container)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(12)

        from qfluentwidgets import PrimaryPushButton, SwitchButton

        self.calibrate_btn = PrimaryPushButton("开始校准", footer_container)
        self.calibrate_btn.setFixedWidth(100)
        self.calibrate_btn.clicked.connect(self._on_calibrate)

        self.wote_btn = PrimaryPushButton("前往卖鱼", footer_container)
        self.wote_btn.setFixedWidth(100)
        self.wote_btn.clicked.connect(lambda: self._on_navigate_to_target("wote"))

        self.jiafu_btn = PrimaryPushButton("前往鱼饵", footer_container)
        self.jiafu_btn.setFixedWidth(100)
        self.jiafu_btn.clicked.connect(lambda: self._on_navigate_to_target("jiafu"))

        # 自动寻路开关
        self.auto_navigate_switch = SwitchButton(footer_container)
        self.auto_navigate_switch.setFixedWidth(50)
        self.auto_navigate_switch.checkedChanged.connect(self._on_auto_navigate_toggled)
        
        auto_nav_label = BodyLabel("自动寻路", footer_container)
        auto_nav_label.setStyleSheet("font-size: 13px;")

        footer_layout.addWidget(self.calibrate_btn)
        footer_layout.addWidget(self.wote_btn)
        footer_layout.addWidget(self.jiafu_btn)
        footer_layout.addStretch(1)
        footer_layout.addWidget(auto_nav_label)
        footer_layout.addWidget(self.auto_navigate_switch)

        self.v_box_layout.addWidget(footer_container, 0, Qt.AlignBottom)

    def _start_update_timer(self):
        """启动更新定时器"""
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_position)
        self.update_timer.start(1000)

    def _on_auto_navigate_toggled(self, checked: bool):
        """自动寻路开关状态改变"""
        self.auto_navigate_enabled = checked
        if checked:
            self.status_label.setText("自动寻路已开启")
            self.status_icon.setStyleSheet("color: #10b981;")
        else:
            self.status_label.setText("自动寻路已关闭")
            self.status_icon.setStyleSheet("color: #6b7280;")

    def _on_calibrate(self):
        """执行校准"""
        self.calibrate_btn.setEnabled(False)
        self.calibrate_btn.setText("校准中...")

        minimap_config = cfg.REGIONS.get("minimap", {})
        center = minimap_config.get("center", (2363, 188))
        radius = minimap_config.get("radius", 136)

        from src.vision import Vision
        vision = Vision()
        vision._ensure_loaded()

        self.map_matcher.vision = vision
        success = self.map_matcher.calibrate_from_screenshot(center, radius)

        if success:
            self.is_calibrated = True
            self._update_status(True)
            self._update_params_display()
            self.map_status_badge.setText("已校准")
            self.map_status_badge.setLevel(InfoLevel.SUCCESS)
            self.status_label.setText("匹配成功")
            self.status_icon.setStyleSheet("color: #10b981;")
        else:
            self.is_calibrated = False
            self._update_status(False)
            self.map_status_badge.setText("未校准")
            self.map_status_badge.setLevel(InfoLevel.WARNING)
            self.status_label.setText("匹配失败")
            self.status_icon.setStyleSheet("color: #ef4444;")

        self.calibrate_btn.setEnabled(True)
        self.calibrate_btn.setText("开始校准")

    def _update_status(self, calibrated: bool):
        """更新校准状态显示"""
        if calibrated:
            params = self.map_matcher.get_transform_params()
            self.scale_value.setText(f"{params['scale_ratio']:.2f}")
            trans = params['translation']
            self.trans_value.setText(f"({trans[0]:.0f}, {trans[1]:.0f})")
        else:
            self.scale_value.setText("--")
            self.trans_value.setText("--")

    def _update_params_display(self):
        """更新参数显示"""
        if self.is_calibrated:
            params = self.map_matcher.get_transform_params()
            self.scale_value.setText(f"{params['scale_ratio']:.2f}")
            trans = params['translation']
            self.trans_value.setText(f"({trans[0]:.0f}, {trans[1]:.0f})")

    def _update_position(self):
        """更新玩家位置（包含自动校准）"""
        if not self.auto_navigate_enabled:
            return
            
        minimap_config = cfg.REGIONS.get("minimap", {})
        center = minimap_config.get("center", (2363, 188))
        radius = minimap_config.get("radius", 136)

        try:
            # 每10次更新执行一次校准（约5秒一次）
            self.calibration_count += 1
            if self.calibration_count >= 10:
                self.calibration_count = 0
                self.map_matcher.vision = self.vision
                success = self.map_matcher.calibrate_from_screenshot(center, radius)

                if success:
                    self.is_calibrated = True
                    self._update_params_display()
                    self.map_status_badge.setText("已校准")
                    self.map_status_badge.setLevel(InfoLevel.SUCCESS)
                    self.status_label.setText("匹配成功")
                    self.status_icon.setStyleSheet("color: #10b981;")
                else:
                    self.is_calibrated = False
                    self.map_status_badge.setText("未校准")
                    self.map_status_badge.setLevel(InfoLevel.WARNING)
                    self.status_label.setText("匹配失败")
                    self.status_icon.setStyleSheet("color: #f59e0b;")

            player_pos = self.map_matcher.get_player_position_on_bigmap(center, radius)
            if player_pos:
                self.update_coordinates(player_pos[0], player_pos[1])
                self.set_player_on_map(player_pos[0], player_pos[1])
        except Exception as e:
            print(f"[Navigation] 更新位置失败: {e}")

    def update_coordinates(self, x: float, y: float):
        """更新坐标显示"""
        self.current_x = x
        self.current_y = y
        self.x_value.setText(f"{x:.1f}")
        self.y_value.setText(f"{y:.1f}")

    def update_map_center(self, x: float, y: float):
        """更新地图中心点（相对坐标 0-1）"""
        self.map_widget.set_center_point(x, y)

    def set_player_on_map(self, x: float, y: float):
        """设置玩家在大地图上的位置"""
        if self.map_matcher.is_calibrated and self.map_matcher.big_map is not None:
            big_width = self.map_matcher.big_map.shape[1]
            big_height = self.map_matcher.big_map.shape[0]
            if big_width > 0 and big_height > 0:
                rel_x = x / big_width
                rel_y = y / big_height
                self.map_widget.set_player_position(rel_x, rel_y)

    def _on_navigate_to_target(self, target_name: str):
        """开始自动寻路到指定目标点"""
        if target_name not in self.target_points:
            return
            
        # 禁用所有寻路按钮
        self.wote_btn.setEnabled(False)
        self.jiafu_btn.setEnabled(False)
        
        # 设置按钮文本
        if target_name == "wote":
            self.wote_btn.setText("寻路中...")
        else:
            self.jiafu_btn.setText("寻路中...")
        
        # 获取目标点坐标
        target_x, target_y = self.target_points[target_name]
        
        # 生成导航路径
        self.navigation_path = self._generate_navigation_path(self.current_x, self.current_y, target_x, target_y)
        
        # 在地图上绘制路径
        self._draw_navigation_path()
        
        # 执行实际操作控制
        self._execute_navigation(target_name)
        
        # 恢复按钮状态
        self.wote_btn.setEnabled(True)
        self.jiafu_btn.setEnabled(True)
        self.wote_btn.setText("前往wote")
        self.jiafu_btn.setText("前往jiafu")
        
    def _generate_navigation_path(self, start_x: float, start_y: float, end_x: float, end_y: float) -> list:
        """生成导航路径"""
        path = []
        
        # 示例：生成直线路径
        steps = 10
        dx = (end_x - start_x) / steps
        dy = (end_y - start_y) / steps
        
        for i in range(steps + 1):
            x = start_x + dx * i
            y = start_y + dy * i
            path.append((x, y))
        
        return path
        
    def _draw_navigation_path(self):
        """在地图上绘制导航路径"""
        pass
                    
    def _execute_navigation(self, target_name: str):
        """执行实际操作控制"""
        if not self.navigation_path:
            return
            
        print(f"开始自动寻路到{target_name}...")
        
        # 导入键盘控制模块
        import pyautogui
        pyautogui.PAUSE = 0.1
        
        # 计算移动方向和距离
        start_x, start_y = self.current_x, self.current_y
        target_x, target_y = self.target_points[target_name]
        
        dx = target_x - start_x
        dy = target_y - start_y
        
        # 计算移动方向
        active_key = None
        if abs(dx) > abs(dy):
            # 水平移动为主
            if dx > 0:
                print("向右移动...")
                pyautogui.keyDown('d')
                active_key = 'd'
            else:
                print("向左移动...")
                pyautogui.keyDown('a')
                active_key = 'a'
        else:
            # 垂直移动为主
            if dy > 0:
                print("向上移动...")
                pyautogui.keyDown('w')
                active_key = 'w'
            else:
                print("向下移动...")
                pyautogui.keyDown('s')
                active_key = 's'
        
        # 模拟移动过程
        import time
        for i in range(10):
            progress = (i + 1) / 10
            current_x = start_x + dx * progress
            current_y = start_y + dy * progress
            print(f"移动进度: {progress*100:.0f}% - 当前位置: ({current_x:.1f}, {current_y:.1f})")
            time.sleep(0.5)
        
        # 释放按键
        pyautogui.keyUp('w')
        pyautogui.keyUp('s')
        pyautogui.keyUp('a')
        pyautogui.keyUp('d')
        
        print(f"已到达{target_name}目标点")
