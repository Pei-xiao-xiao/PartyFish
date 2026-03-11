"""
主页界面 - 协调器模式
负责协调 Banner、Dashboard、FishPreview、Log、Footer 等组件
"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Slot, Signal, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSplitter
from PySide6.QtGui import QDesktopServices

from src.config import cfg
from src.gui.components.banner_widget import BannerWidget
from src.gui.components.dashboard_widget import DashboardWidget
from src.gui.components.fish_preview_widget import FishPreviewWidget
from src.gui.components.log_widget import LogWidget
from src.gui.components.footer_widget import FooterWidget


class HomeInterface(QWidget):
    """主页界面 - 协调器"""
    
    preset_changed_signal = Signal(str)
    toggle_overlay_signal = Signal()
    fishFilterChanged = Signal()
    account_changed_signal = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HomeInterface")
        
        self.run_time = None
        self._init_run_time()
        self.total_catch = 0
        
        self._init_ui()
        self._connect_signals()
        self._init_timer()
        
        if cfg.startup_errors:
            for error in cfg.startup_errors:
                self.log_widget.append_log(error)
    
    def _init_run_time(self):
        """初始化运行时间"""
        from PySide6.QtCore import QTime
        self.run_time = QTime(0, 0, 0)
    
    def _init_ui(self):
        """初始化 UI"""
        self.v_box_layout = QVBoxLayout(self)
        self.v_box_layout.setContentsMargins(40, 40, 40, 20)
        self.v_box_layout.setSpacing(24)
        
        self.banner_widget = BannerWidget(self)
        self.v_box_layout.addWidget(self.banner_widget)
        
        self.main_splitter = QSplitter(Qt.Horizontal, self)
        
        self.left_widget = QWidget(self)
        self.left_layout = QVBoxLayout(self.left_widget)
        self.left_layout.setContentsMargins(0, 0, 20, 0)
        self.left_layout.setSpacing(24)
        
        self.dashboard_widget = DashboardWidget(self)
        self.left_layout.addWidget(self.dashboard_widget)
        
        self.fish_preview_widget = FishPreviewWidget(self)
        self.left_layout.addWidget(self.fish_preview_widget)
        self.left_layout.addStretch(1)
        
        self.log_widget = LogWidget(self)
        
        self.main_splitter.addWidget(self.left_widget)
        self.main_splitter.addWidget(self.log_widget)
        
        self.main_splitter.setStretchFactor(0, 2)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent;
                width: 1px;
            }
        """)
        
        self.v_box_layout.addWidget(self.main_splitter, 1)
        
        self.footer_widget = FooterWidget(self)
        self.v_box_layout.addWidget(self.footer_widget, 0, Qt.AlignBottom)
    
    def _connect_signals(self):
        """连接信号"""
        self.banner_widget.overlay_toggled.connect(self._on_overlay_toggled)
        self.banner_widget.account_changed.connect(self._on_account_changed)
        self.banner_widget.preset_changed.connect(self._on_preset_changed)
        self.banner_widget.sound_toggled.connect(self._on_sound_toggled)
        self.banner_widget.release_mode_changed.connect(self._on_release_mode_changed)
        self.banner_widget.screenshot_mode_changed.connect(self._on_screenshot_mode_changed)
        
        self.dashboard_widget.data_directory_requested.connect(self._open_data_directory)
        self.dashboard_widget.screenshot_directory_requested.connect(self._open_screenshot_directory)
        
        self.fish_preview_widget.filter_changed.connect(self.fishFilterChanged.emit)
        self.fish_preview_widget.log_message.connect(self.log_widget.append_log)
        
        from src.pokedex import pokedex
        pokedex.data_changed.connect(self._on_pokedex_data_changed)
    
    def _init_timer(self):
        """初始化定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_run_time)
    
    def _on_overlay_toggled(self, checked: bool):
        """处理悬浮窗开关"""
        self.toggle_overlay_signal.emit()
    
    def _on_account_changed(self, account_name: str):
        """处理账号切换"""
        if account_name and account_name != cfg.current_account:
            def delayed_update():
                cfg.switch_account(account_name)
                self.banner_widget.refresh_account_controls()
                self.account_changed_signal.emit(account_name)
                self.fish_preview_widget.refresh()
                self.total_catch = 0
                
                from src.pokedex import pokedex
                pokedex.reload()
            
            QTimer.singleShot(50, delayed_update)
    
    def _on_preset_changed(self, preset_name: str):
        """处理预设切换"""
        if preset_name in cfg.presets:
            cfg.load_preset(preset_name)
            cfg.save()
            self.preset_changed_signal.emit(preset_name)
    
    def _on_sound_toggled(self, checked: bool):
        """处理音效开关"""
        cfg.global_settings["control_sound_enabled"] = checked
        cfg.save()
    
    def _on_release_mode_changed(self, mode: str):
        """处理放生模式变化"""
        cfg.global_settings["release_mode"] = mode
        
        if mode == "auto":
            cfg.global_settings["auto_release_enabled"] = True
        else:
            cfg.global_settings["auto_release_enabled"] = False
        
        cfg.save()
        
        self._notify_settings_interface_update(mode)
        
        mode_text_map = {"off": "关", "single": "单条", "auto": "桶满"}
        self.log_widget.append_log(f"[系统] 放生模式已切换为: {mode_text_map.get(mode, mode)}")
    
    def _on_screenshot_mode_changed(self, mode: str):
        """处理截图模式变化"""
        cfg.global_settings["screenshot_mode"] = mode
        cfg.save()
        mode_text_map = {"wegame": "WeGame", "steam": "Steam"}
        self.log_widget.append_log(f"[系统] 截图模式已切换为: {mode_text_map.get(mode, mode)}")
    
    def _notify_settings_interface_update(self, mode: str):
        """通知设置页面更新放生模式"""
        parent = self.parent()
        while parent:
            if hasattr(parent, "settings_interface"):
                parent.settings_interface.update_release_mode_from_main(mode)
                break
            parent = parent.parent()
    
    def _open_directory(self, directory: Path):
        """打开目录"""
        directory.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(str(directory))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
    
    def _open_data_directory(self):
        """打开数据目录"""
        self._open_directory(cfg.user_data_dir)
    
    def _open_screenshot_directory(self):
        """打开截图目录"""
        self._open_directory(cfg._get_application_path() / "截图")
    
    def _on_pokedex_data_changed(self):
        """图鉴数据变化响应"""
        from src.pokedex import pokedex
        collected, total, collected_q, total_q = pokedex.get_progress()
        self.dashboard_widget.update_pokedex_progress(collected, total, collected_q, total_q)
        self.fish_preview_widget.refresh()
    
    def _update_run_time(self):
        """更新运行时间"""
        self.run_time = self.run_time.addSecs(1)
        self.banner_widget.update_run_time(self.run_time.toString("hh:mm:ss"))
    
    @Slot(str)
    def update_log(self, text: str):
        """更新日志"""
        self.log_widget.append_log(text)
    
    @Slot(str)
    def update_status(self, status: str):
        """更新状态"""
        self.banner_widget.update_status(status)
        
        if status == "运行中":
            if not self.timer.isActive():
                self.timer.start(1000)
        elif "停止" in status:
            self.timer.stop()
    
    @Slot(dict)
    def update_catch_info(self, catch_data: dict):
        """更新捕获数据"""
        self.total_catch += 1
        self._on_pokedex_data_changed()
    
    def update_sales_progress(self, sold: int, limit: int = 899):
        """更新销售进度"""
        self.dashboard_widget.update_sales_progress(sold, limit)
    
    def update_hotkey_display(self, new_hotkey: str):
        """更新热键显示"""
        self.banner_widget.update_hotkey_display("启动", new_hotkey)
    
    def update_debug_hotkey_display(self, new_hotkey: str):
        """更新调试热键显示"""
        self.banner_widget.update_hotkey_display("调试", new_hotkey)
    
    def update_sell_hotkey_display(self, new_hotkey: str):
        """更新卖鱼热键显示"""
        self.banner_widget.update_hotkey_display("卖鱼", new_hotkey)
    
    def refresh_account_list(self):
        """刷新账号列表"""
        self.banner_widget.set_account_list(cfg.get_accounts())
    
    def refresh_account_controls(self):
        """刷新账号控件"""
        self.banner_widget.refresh_account_controls()
    
    def update_release_mode_segment(self, mode: str):
        """从设置页面更新放生模式选择器"""
        self.banner_widget.set_release_mode(mode)
        
        cfg.global_settings["release_mode"] = mode
        if mode == "auto":
            cfg.global_settings["auto_release_enabled"] = True
        else:
            cfg.global_settings["auto_release_enabled"] = False
        cfg.save()
    
    def refresh_table_colors(self):
        """刷新主题样式"""
        self.banner_widget.apply_theme()
        self.dashboard_widget.apply_theme()
        self.fish_preview_widget.apply_theme()
        self.log_widget.apply_theme()
    
    def add_record_to_session_table(self, record):
        """兼容旧代码"""
        pass
    
    def clear_session_table(self):
        """兼容旧代码"""
        pass
