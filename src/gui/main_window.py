import sys
from PySide6.QtCore import Qt, QSize, Signal, QUrl, QTimer, QDate
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition, setTheme, Theme

try:
    from src._version import __version__
except ImportError:
    __version__ = "DEV"

from src.gui.home_interface import HomeInterface
from src.gui.records_interface import RecordsInterface
from src.gui.profit_interface import ProfitInterface
from src.gui.settings_interface import SettingsInterface
from src.gui.pokedex_interface import PokedexInterface
from src.gui.overlay_window import OverlayWindow
from src.workers import FishingWorker, PopupWorker
from src.inputs import InputController


class MainWindow(FluentWindow):

    preset_should_change = Signal(str)

    def nativeEvent(self, event_type, message):
        """
        Override the native event handler to gracefully handle KeyboardInterrupts
        that might be raised by underlying libraries (like pynput) interacting
        with the Qt event loop.
        """
        try:
            # Pass the event to the parent class's handler
            return super().nativeEvent(event_type, message)
        except KeyboardInterrupt:
            # This is a workaround for an issue where pynput's listener can
            # cause a KeyboardInterrupt in the main thread when a hotkey is pressed.
            # We catch it here to prevent it from crashing the application or printing
            # an error to the console, and simply ignore it.
            print("DEBUG: Caught and ignored KeyboardInterrupt in nativeEvent.")
            return True, 0 # Indicate that the event has been handled

    def __init__(self):
        super().__init__()
        print("Initializing MainWindow UI...")
        self.setObjectName("MainWindow")
        self.setWindowTitle("PartyFish")
        
        # Set window icon
        from src.config import cfg
        icon_path = cfg._get_base_path() / "resources" / "favicon.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            self.setWindowIcon(FluentIcon.GAME.icon())
            
        self.resize(1100, 750)

        print("Instantiating interfaces...")
        self.home_interface = HomeInterface(self)
        self.records_interface = RecordsInterface(self)
        self.profit_interface = ProfitInterface(self)
        self.pokedex_interface = PokedexInterface(self)
        self.settings_interface = SettingsInterface(self)
 
        self.overlay = OverlayWindow()

        print("Instantiating worker and input controller...")
        self.worker = FishingWorker()
        self.popup_worker = PopupWorker()
        self.input_controller = InputController()

        # Initialize Audio Player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        print("Setting up navigation...")
        # Reduce navigation panel width since labels are short (2 chars)
        self.navigationInterface.setExpandWidth(150)

        # 添加导航
        self.addSubInterface(self.home_interface, FluentIcon.HOME, "主页")
        self.addSubInterface(self.records_interface, FluentIcon.HISTORY, "记录")
        self.addSubInterface(self.profit_interface, FluentIcon.SHOPPING_CART, "收益")
        self.addSubInterface(self.pokedex_interface, FluentIcon.LIBRARY, "图鉴")
        self.addSubInterface(self.settings_interface, FluentIcon.SETTING, "设置", NavigationItemPosition.BOTTOM)

        print("Connecting signals...")
        self.worker.log_updated.connect(self.append_log)
        self.worker.status_updated.connect(self.update_status)
        self.worker.record_added.connect(self.records_interface.add_record)
        self.worker.record_added.connect(self.home_interface.update_catch_info)
        self.worker.record_added.connect(self.home_interface.add_record_to_session_table)
        # Refresh profit interface when a new record (cost) is added
        self.worker.record_added.connect(lambda x: self.profit_interface.reload_data())
        self.worker.sale_recorded.connect(self.profit_interface.add_sale_record)
        
        # Connect profit updates to overlay
        self.worker.sale_recorded.connect(self._update_overlay_limit)
        self.profit_interface.data_changed_signal.connect(self._update_overlay_limit)
        # 当服务器切换时，重新计算下次重置时间
        self.profit_interface.server_changed_signal.connect(self._on_server_region_changed)

        self.popup_worker.log_updated.connect(self.append_log)
        self.input_controller.toggle_script_signal.connect(self.toggle_script)
        self.input_controller.debug_screenshot_signal.connect(self.take_debug_screenshot)
        self.settings_interface.hotkey_changed_signal.connect(self.home_interface.update_hotkey_display)
        self.settings_interface.debug_hotkey_changed_signal.connect(self.home_interface.update_debug_hotkey_display)
        self.settings_interface.hotkey_changed_signal.connect(self.input_controller._update_hotkey_handler)
        self.settings_interface.debug_hotkey_changed_signal.connect(self.input_controller._update_debug_hotkey_handler)
        self.settings_interface.sell_hotkey_changed_signal.connect(self.input_controller._update_sell_hotkey_handler)
        self.settings_interface.sell_hotkey_changed_signal.connect(self.home_interface.update_sell_hotkey_display)
        self.settings_interface.uno_hotkey_changed_signal.connect(self.input_controller._update_uno_hotkey_handler)
        self.home_interface.preset_changed_signal.connect(self.on_preset_changed)
        self.settings_interface.theme_changed_signal.connect(self._on_theme_changed)
        self.preset_should_change.connect(self.worker.update_preset)
        self.home_interface.toggle_overlay_signal.connect(self.toggle_overlay)
        self.home_interface.fishFilterChanged.connect(self.overlay.update_fish_preview)
        
        # Overlay signals
        self.worker.status_updated.connect(self.overlay.update_status)
        self.worker.record_added.connect(lambda: self.overlay.update_fish_count(self.home_interface.total_catch))
        # Connect profit updates to overlay
        self.worker.sale_recorded.connect(self._update_overlay_limit)
        self.worker.sound_alert_requested.connect(self.play_sound_alert)
        
        # 账号切换信号：刷新各界面数据
        self.home_interface.account_changed_signal.connect(self._on_account_changed)
        # 设置页账号列表变化信号：刷新首页账号下拉框
        self.settings_interface.account_list_changed_signal.connect(self.home_interface.refresh_account_list)
        self.settings_interface.account_list_changed_signal.connect(self.settings_interface.refresh_account_ui)
        # 设置页记录更新信号：刷新相关界面数据
        self.settings_interface.records_updated_signal.connect(self.records_interface._load_data)
        self.settings_interface.records_updated_signal.connect(self.profit_interface.reload_data)
        self.settings_interface.records_updated_signal.connect(self.pokedex_interface.reload_data)

        # Start the worker thread, but it will be initially paused
        self.worker.start()
        self.popup_worker.start()

        # Connect sell hotkey
        self.input_controller.sell_hotkey_signal.connect(self.worker.trigger_sell)

        # Connect uno hotkey
        self.input_controller.uno_hotkey_signal.connect(self.toggle_uno)

        # Start listening for hotkeys
        self.input_controller.start_listening()
        
        # Initialize overlay limit
        self._update_overlay_limit()
        
        # 恢复悬浮窗状态和位置
        self._restore_overlay_state()
        
        # 精确定时重置：使用持久 QTimer，在重置时刻触发
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._on_cycle_reset)
        self._schedule_next_reset()

    def _schedule_next_reset(self):
        """计算并安排下一次重置触发"""
        from datetime import datetime, timedelta
        from src.config import cfg
        
        # 计算下一次重置时间
        region = cfg.global_settings.get("server_region", "CN")
        now = datetime.now()
        
        if region == "CN":
            next_reset = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            noon_today = now.replace(hour=12, minute=0, second=0, microsecond=0)
            next_reset = noon_today if now < noon_today else noon_today + timedelta(days=1)
        
        ms_until_reset = max(1000, int((next_reset - now).total_seconds() * 1000))
        
        # 停止旧定时器，设置新间隔并启动
        self._reset_timer.stop()
        self._reset_timer.setInterval(ms_until_reset)
        self._reset_timer.start()
        
        print(f"下次重置: {next_reset.strftime('%H:%M')} ({ms_until_reset // 3600000}h {(ms_until_reset % 3600000) // 60000}m 后)")

    def _on_cycle_reset(self):
        """周期重置时触发"""
        self.profit_interface.reload_data()
        self._update_overlay_limit()
        self.append_log("新的一天开始了，今日统计数据已重置。")
        self._schedule_next_reset()

    def _on_server_region_changed(self, new_region: str):
        """服务器区域切换时，重新安排重置时间"""
        self._schedule_next_reset()

    def _update_overlay_limit(self, _=None):
        # Calculate remaining limit
        # This is a bit redundant with ProfitInterface logic, but safe.
        # Ideally, ProfitInterface should emit a signal.
        total_sales = 0
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        import csv
        from src.config import cfg
        try:
            path = cfg.sales_file
            if path.exists():
                # 获取准确的时间窗口
                start_time = getattr(self.profit_interface, '_get_current_cycle_start_time', lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))()
                
                with open(path, 'r', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    for row in reader:
                        if row:
                            try:
                                row_dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                                if row_dt >= start_time:
                                    total_sales += int(row[1])
                            except ValueError:
                                pass
        except:
            pass
        
        remaining = 899 - total_sales
        # 传递剩余额度和当前销售金额
        self.overlay.update_limit(remaining, total_sales)
        
        # 同时更新首页的销售进度
        if hasattr(self, 'home_interface'):
            self.home_interface.update_sales_progress(total_sales, 899)
            # 顺便更新一下图鉴进度（因为可能会有新捕获）
            self.home_interface.update_pokedex_progress()

    def play_sound_alert(self, alert_type):
        """播放提示音"""
        try:
            from src.config import cfg
            base_path = cfg._get_base_path()
            if alert_type == "no_bait":
                sound_file = base_path / "resources" / "audio" / "no_bait.mp3"
            elif alert_type == "inventory_full":
                sound_file = base_path / "resources" / "audio" / "inventory_full.mp3"
            else:
                return
            
            # 使用 QUrl.fromLocalFile 处理路径
            self.player.setSource(QUrl.fromLocalFile(str(sound_file)))
            self.player.play()
            self.append_log(f"播放提示音: {sound_file.name}")
        except Exception as e:
            self.append_log(f"播放提示音失败: {e}")

    def toggle_overlay(self):
        from src.config import cfg
        if self.overlay.isVisible():
            self.overlay.hide()
            cfg.global_settings["overlay_visible"] = False
        else:
            self.overlay.show()
            cfg.global_settings["overlay_visible"] = True
        cfg.save()
    
    def _restore_overlay_state(self):
        """恢复悬浮窗的上次状态和位置"""
        from src.config import cfg
        
        # 恢复位置
        pos = cfg.global_settings.get("overlay_position")
        if pos and isinstance(pos, list) and len(pos) == 2:
            self.overlay.move(pos[0], pos[1])
        
        # 恢复可见状态
        if cfg.global_settings.get("overlay_visible", False):
            self.overlay.show()
            # 阻止信号发射，避免触发 toggle_overlay 导致悬浮窗被隐藏
            self.home_interface.overlay_switch.blockSignals(True)
            self.home_interface.overlay_switch.setChecked(True)
            self.home_interface.overlay_switch.blockSignals(False)
    
    def _save_overlay_state(self):
        """保存悬浮窗的当前状态和位置"""
        from src.config import cfg
        
        # 保存可见状态
        cfg.global_settings["overlay_visible"] = self.overlay.isVisible()
        
        # 保存位置
        pos = self.overlay.pos()
        cfg.global_settings["overlay_position"] = [pos.x(), pos.y()]
        
        cfg.save()

    def _on_account_changed(self, account_name: str):
        """账号切换时刷新各界面数据"""
        self.append_log(f"已切换到账号: {account_name}")
        # 刷新记录页
        self.records_interface._load_data()
        # 刷新收益页
        self.profit_interface.reload_data()
        # 刷新图鉴页（这会调用 pokedex.reload() 重新加载收集数据）
        self.pokedex_interface.reload_data()
        # 刷新设置页账号管理 UI
        self.settings_interface.refresh_account_ui()
        # 刷新悬浮窗额度显示
        self._update_overlay_limit()
        # 刷新悬浮窗鱼种预览（使用新账号的收集进度重新排序）
        self.overlay._update_fish_preview()

    def _on_theme_changed(self, theme: str):
        if theme == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)
        
        # 主题切换后刷新记录和主页，以更新颜色
        if hasattr(self.records_interface, 'refresh_table_colors'):
            self.records_interface.refresh_table_colors()
            
        if hasattr(self.home_interface, 'refresh_table_colors'):
            self.home_interface.refresh_table_colors()

    def append_log(self, message):
        """在日志窗口追加日志"""
        self.home_interface.update_log(message)

    def update_status(self, status):
        """更新状态标签"""
        self.home_interface.update_status(status)

    def toggle_script(self):
        """切换脚本的运行/暂停状态"""
        if self.worker.paused:
            self.worker.resume()
        else:
            self.worker.pause()

    def toggle_uno(self):
        """切换UNO功能的启动/停止状态"""
        from src.uno import uno_manager
        if uno_manager.running:
            uno_manager.stop()
            self.append_log("UNO识别已停止")
        else:
            uno_manager.start()
            self.append_log("UNO识别已启动")

    def take_debug_screenshot(self):
        """Taking debug screenshot and opening it"""
        print("Taking debug screenshot via hotkey...")
        try:
            # Import from src.debug_overlay
            from src.debug_overlay import generate_debug_screenshot
            
            filepath = generate_debug_screenshot(show_image=True)
            self.append_log(f"调试截图已保存: {filepath}")
            self.update_status("调试截图已生成")
            
        except Exception as e:
            print(f"Failed to take debug screenshot: {e}")
            self.append_log(f"截图失败: {e}")

    def on_preset_changed(self, preset_name: str):
        """
        当UI中的预设改变时，通过信号安全地通知工作线程。
        """
        self.append_log(f"UI请求更改预设为: {preset_name}")

        # 发射信号，将预设名称传递给工作线程
        self.preset_should_change.emit(preset_name)

        # 切换预设后，为安全起见，强制暂停脚本
        # 这可以防止在新配置加载期间发生意外行为
        if not self.worker.paused:
            self.worker.pause()
            
        self.update_status(f"预设已切换为 '{preset_name}'，脚本已暂停。")
        self.append_log("请检查配置，然后按快捷键继续。")

    def closeEvent(self, event):
        """关闭窗口事件"""
        print("Closing application, stopping threads...")
        
        # 保存悬浮窗状态和位置
        self._save_overlay_state()
        
        self.worker.stop()
        self.popup_worker.stop()
        
        # Wait for threads to finish with a timeout to avoid freezing
        if not self.worker.wait(2000):
            print("Worker thread did not stop in time, terminating...")
            self.worker.terminate()
            
        if not self.popup_worker.wait(2000):
            print("Popup worker thread did not stop in time, terminating...")
            self.popup_worker.terminate()
        
        self.input_controller.stop_listening()
        print("All threads stopped. Goodbye.")
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
