import sys
from PySide6.QtCore import Qt, QSize, Signal, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    setTheme,
    Theme,
)

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
from src.managers.signal_manager import SignalManager
from src.managers.cycle_reset_manager import CycleResetManager
from src.managers.audio_manager import AudioManager
from src.managers.sales_limit_manager import SalesLimitManager


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
            return True, 0  # Indicate that the event has been handled

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

        # Initialize managers
        self.audio_manager = AudioManager(self)
        self.signal_manager = SignalManager(self)
        self.cycle_reset_manager = CycleResetManager(self)
        self.sales_limit_manager = SalesLimitManager(self)

        print("Setting up navigation...")
        # Reduce navigation panel width since labels are short (2 chars)
        self.navigationInterface.setExpandWidth(150)

        # 添加导航
        self.addSubInterface(self.home_interface, FluentIcon.HOME, "主页")
        self.addSubInterface(self.records_interface, FluentIcon.HISTORY, "记录")
        self.addSubInterface(self.profit_interface, FluentIcon.SHOPPING_CART, "收益")
        self.addSubInterface(self.pokedex_interface, FluentIcon.LIBRARY, "图鉴")
        self.addSubInterface(
            self.settings_interface,
            FluentIcon.SETTING,
            "设置",
            NavigationItemPosition.BOTTOM,
        )

        print("Connecting signals...")
        self.signal_manager.connect_all()

        # Start the worker thread, but it will be initially paused
        self.worker.start()
        self.popup_worker.start()

        # Start listening for hotkeys
        self.input_controller.start_listening()

        # Initialize overlay limit
        self._update_overlay_limit()

        # 恢复悬浮窗状态和位置
        self._restore_overlay_state()

        # 启动周期重置管理器
        self.cycle_reset_manager.start()

    def _update_overlay_limit(self, _=None):
        """更新悬浮窗和首页的销售额度显示"""
        self.sales_limit_manager.update_overlay_limit(_)

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
        self.overlay.update_fish_preview()

    def _on_theme_changed(self, theme: str):
        if theme == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

        # 主题切换后刷新记录和主页，以更新颜色
        if hasattr(self.records_interface, "refresh_table_colors"):
            self.records_interface.refresh_table_colors()

        if hasattr(self.home_interface, "refresh_table_colors"):
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
            self.audio_manager.play_control_sound("start")
        else:
            self.worker.pause()
            self.audio_manager.play_control_sound("pause")

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
