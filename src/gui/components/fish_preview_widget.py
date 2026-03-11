"""
FishPreview 组件 - 负责主页鱼种预览区域的 UI 构建和过滤逻辑
"""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout
from qfluentwidgets import (
    CardWidget,
    StrongBodyLabel,
    CaptionLabel,
    SegmentedWidget,
    IconWidget,
    FluentIcon,
)

from src.config import cfg
from src.gui.components.draggable_scroll_area import DraggableScrollArea
from src.gui.components.home_fish_card import HomeFishCard


class FishPreviewWidget(QWidget):
    """鱼种预览组件 - 显示当前可钓鱼种"""
    
    filter_changed = Signal()
    log_message = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_time = None
        self._last_weather = None
        self._init_ui()
        self._start_condition_check()
    
    def _init_ui(self):
        """初始化鱼种预览 UI"""
        self.session_records_container = CardWidget(self)
        layout = QVBoxLayout(self.session_records_container)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(0)
        
        header_layout = QHBoxLayout()
        header_icon = IconWidget(FluentIcon.CALORIES, self.session_records_container)
        header_icon.setFixedSize(16, 16)
        self.fish_preview_title = StrongBodyLabel("当前可钓", self.session_records_container)
        self.fish_preview_time_label = CaptionLabel("", self.session_records_container)
        self.fish_preview_time_label.setStyleSheet("color: #9ca3af;")
        
        header_layout.setSpacing(12)
        header_layout.addWidget(header_icon)
        header_layout.addWidget(self.fish_preview_title)
        header_layout.addWidget(self.fish_preview_time_label)
        
        self.fish_filter_segment = SegmentedWidget(self.session_records_container)
        self.fish_filter_segment.addItem("all", "全部")
        self.fish_filter_segment.addItem("lure", "路亚")
        self.fish_filter_segment.addItem("ice", "池塘")
        
        current_mode = getattr(cfg, "fish_filter_mode", "all")
        self.fish_filter_segment.setCurrentItem(current_mode)
        self.fish_filter_segment.currentItemChanged.connect(self._on_fish_filter_changed)
        header_layout.addWidget(self.fish_filter_segment)
        
        self.rod_filter_segment = SegmentedWidget(self.session_records_container)
        self.rod_filter_segment.addItem("all", "全部")
        self.rod_filter_segment.addItem("heavy", "重竿")
        self.rod_filter_segment.addItem("light", "轻竿")
        
        current_rod_mode = getattr(cfg, "rod_filter_mode", "all")
        self.rod_filter_segment.setCurrentItem(current_rod_mode)
        self.rod_filter_segment.currentItemChanged.connect(self._on_rod_filter_changed)
        header_layout.addWidget(self.rod_filter_segment)
        header_layout.addStretch(1)
        
        layout.addLayout(header_layout)
        
        self.fish_scroll_area = DraggableScrollArea(self.session_records_container)
        self.fish_scroll_area.setWidgetResizable(True)
        self.fish_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)
        self.fish_scroll_area.setFixedHeight(165)
        
        self.fish_cards_container = QWidget()
        self.fish_cards_layout = QHBoxLayout(self.fish_cards_container)
        self.fish_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.fish_cards_layout.setSpacing(4)
        self.fish_cards_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        
        self.fish_scroll_area.setWidget(self.fish_cards_container)
        layout.addWidget(self.fish_scroll_area)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.session_records_container)
    
    def _start_condition_check(self):
        """启动条件检测定时器"""
        self.fish_preview_timer = QTimer(self)
        self.fish_preview_timer.timeout.connect(self._check_conditions)
        QTimer.singleShot(500, self._check_conditions)
    
    def _on_fish_filter_changed(self, routeKey: str):
        """处理鱼种过滤改变"""
        cfg.fish_filter_mode = routeKey
        cfg.save()
        self._refresh_fish_preview()
        self.filter_changed.emit()
    
    def _on_rod_filter_changed(self, routeKey: str):
        """处理竿类型过滤改变"""
        cfg.rod_filter_mode = routeKey
        cfg.save()
        self._refresh_fish_preview()
        self.filter_changed.emit()
    
    def _check_conditions(self):
        """每秒检测天气和时段，变化时才刷新UI"""
        from src.pokedex import pokedex
        
        try:
            current_time = pokedex.get_current_game_time()
            current_weather = pokedex.detect_current_weather()
            
            if cfg.game_hwnd is None or cfg.screen_width <= 0 or cfg.screen_height <= 0:
                return
            
            if current_time != self._last_time or current_weather != self._last_weather:
                self._last_time = current_time
                self._last_weather = current_weather
                self.log_message.emit(f"[天气] 当前: {current_weather or '未识别'} · {current_time}")
                self._refresh_fish_preview()
        except Exception as e:
            print(f"[Home] 检测条件失败: {e}")
        finally:
            self.fish_preview_timer.start(1000)
    
    def _refresh_fish_preview(self):
        """刷新当前可钓鱼种预览"""
        from src.pokedex import pokedex, QUALITIES
        
        try:
            while self.fish_cards_layout.count():
                item = self.fish_cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            current_time = self._last_time
            current_weather = self._last_weather
            
            weather_text = current_weather or "未知"
            season_text = (
                "春季"
                if cfg.global_settings.get("enable_season_filter", True)
                else "春夏秋"
            )
            self.fish_preview_time_label.setText(
                f"({current_time} · {weather_text} · {season_text})"
            )
            
            criteria = {"time": [current_time]}
            if current_weather:
                criteria["weather"] = [current_weather]
            if cfg.global_settings.get("enable_season_filter", True):
                criteria["season"] = ["春季"]
            else:
                criteria["season"] = ["春季", "夏季", "秋季"]
            
            all_fish = pokedex.get_all_fish()
            catchable_fish = pokedex.filter_fish_multi(all_fish, criteria)
            
            catchable_fish = [
                f for f in catchable_fish if "冰钓" not in f.get("type", "")
            ]
            
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
                empty_label = CaptionLabel(
                    "当前时段暂无可钓鱼种", self.fish_cards_container
                )
                empty_label.setStyleSheet("color: #9ca3af; padding: 20px;")
                self.fish_cards_layout.addWidget(empty_label)
            else:
                visible_fish = []
                for fish in catchable_fish:
                    status = pokedex.get_collection_status(fish["name"])
                    is_fully_collected = all(
                        status.get(q) is not None for q in QUALITIES
                    )
                    
                    if not is_fully_collected:
                        visible_fish.append(fish)
                
                if not visible_fish:
                    empty_label = CaptionLabel(
                        "当前时段所有鱼种已毕业！", self.fish_cards_container
                    )
                    empty_label.setStyleSheet(
                        "color: #10b981; font-weight: bold; padding: 20px;"
                    )
                    self.fish_cards_layout.addWidget(empty_label)
                else:
                    sorted_fish = pokedex.sort_fish(
                        visible_fish, sort_key="progress", reverse=False
                    )
                    
                    for fish in sorted_fish:
                        card = HomeFishCard(fish, self.fish_cards_container)
                        self.fish_cards_layout.addWidget(card)
            
            self.fish_cards_layout.addStretch(1)
            
        except Exception as e:
            print(f"[Home] 刷新鱼种预览失败: {e}")
    
    def refresh(self):
        """刷新鱼种预览"""
        self._refresh_fish_preview()
    
    def apply_theme(self):
        """应用主题样式"""
        pass
