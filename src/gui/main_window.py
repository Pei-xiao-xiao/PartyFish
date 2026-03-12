import sys
import subprocess
import re
import time
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import Qt, QSize, Signal, QUrl, QTimer
from PySide6.QtGui import QIcon, QPainter, QColor, QFont, QPixmap
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    qconfig,
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
            return super().nativeEvent(event_type, message)
        except KeyboardInterrupt:
            print("DEBUG: Caught and ignored KeyboardInterrupt in nativeEvent.")
            return True, 0

    def __init__(self):
        super().__init__()
        print("Initializing MainWindow UI...")
        self.setObjectName("MainWindow")
        self.setWindowTitle("PartyFish")

        # 设置窗口图标
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

        # 初始化管理器
        self.audio_manager = AudioManager(self)
        self.signal_manager = SignalManager(self)
        self.cycle_reset_manager = CycleResetManager(self)
        self.sales_limit_manager = SalesLimitManager(self)

        print("Setting up navigation...")
        # 缩小导航面板宽度
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

        # 连接设置页面的放生模式变化信号到主页
        self.settings_interface.release_mode_changed_signal.connect(
            self.home_interface.update_release_mode_segment
        )

        # 连接季节筛选变化信号
        self.settings_interface.season_filter_changed_signal.connect(
            lambda: self.overlay.update_fish_preview()
        )
        self.settings_interface.season_filter_changed_signal.connect(
            lambda: self.home_interface.fish_preview_widget.refresh()
        )

        # 启动工作线程（初始为暂停状态）
        self.worker.start()
        self.popup_worker.start()

        # 开始监听热键
        self.input_controller.start_listening()

        # 初始化悬浮窗额度
        self._update_overlay_limit()

        # 恢复悬浮窗状态和位置
        self._restore_overlay_state()

        # 连接UNO管理器信号
        self._connect_uno_signals()

        # 启动周期重置管理器
        self.cycle_reset_manager.start()

        # 水印缓存
        self._watermark_cache = None
        self._watermark_cache_size = QSize(0, 0)

        # 隐蔽信息水印相关
        self._external_ip = self._load_cached_ip()
        self._hidden_info_executor = ThreadPoolExecutor(max_workers=1)
        self._async_fetch_external_ip()

    def _fetch_external_ip(self):
        ip = self._try_requests_library()
        if ip:
            return ip
        ip = self._try_urllib_library()
        if ip:
            return ip
        ip = self._try_powershell_ip()
        if ip:
            return ip
        ip = self._try_nslookup_opendns()
        if ip:
            return ip
        return "未知IP"

    def _try_nslookup_opendns(self):
        try:
            result = subprocess.run(
                ["nslookup", "myip.opendns.com", "resolver1.opendns.com"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            ips = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', result.stdout)
            for ip in ips:
                if ip != "208.67.222.222":
                    parts = ip.split('.')
                    if len(parts) == 4:
                        first_octet = int(parts[0])
                        second_octet = int(parts[1])
                        if first_octet == 10:
                            continue
                        if first_octet == 172 and 16 <= second_octet <= 31:
                            continue
                        if first_octet == 192 and second_octet == 168:
                            continue
                        if first_octet == 127:
                            continue
                        return ip
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError, ValueError, IndexError):
            pass
        except Exception:
            pass
        return None

    def _try_powershell_ip(self):
        try:
            result = subprocess.run(
                ["powershell", "-Command", "(Invoke-RestMethod -Uri 'https://api.ipify.org' -TimeoutSec 5)"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            ip = result.stdout.strip()
            if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                parts = ip.split('.')
                if len(parts) == 4:
                    first_octet = int(parts[0])
                    second_octet = int(parts[1])
                    if first_octet == 10:
                        return None
                    if first_octet == 172 and 16 <= second_octet <= 31:
                        return None
                    if first_octet == 192 and second_octet == 168:
                        return None
                    if first_octet == 127:
                        return None
                    return ip
        except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError, ValueError, IndexError):
            pass
        except Exception:
            pass
        return None

    def _try_requests_library(self):
        try:
            import requests
        except ImportError:
            return None

        apis = [
            "http://checkip.amazonaws.com",
            "https://ipinfo.io/ip",
            "https://icanhazip.com"
        ]

        for api in apis:
            for attempt in range(3):
                try:
                    response = requests.get(api, timeout=3)
                    ip = response.text.strip()
                    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                        return ip
                except (requests.RequestException, requests.Timeout, requests.ConnectionError):
                    if attempt < 2:
                        time.sleep(1)
                except Exception:
                    if attempt < 2:
                        time.sleep(1)
        return None

    def _try_urllib_library(self):
        import urllib.request
        import urllib.error

        apis = [
            "http://checkip.amazonaws.com",
            "https://ipinfo.io/ip",
            "https://icanhazip.com"
        ]

        for api in apis:
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(api, timeout=5) as response:
                        ip = response.read().decode('utf-8').strip()
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            return ip
                except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError):
                    if attempt < 2:
                        time.sleep(1)
                except Exception:
                    if attempt < 2:
                        time.sleep(1)
        return None

    def _load_cached_ip(self):
        from src.config import cfg
        import time as time_module

        cached_ip = cfg.global_settings.get("external_ip")
        cached_time = cfg.global_settings.get("external_ip_updated_at", 0)
        current_time = time_module.time()

        if cached_ip and (current_time - cached_time) < 86400:
            return cached_ip
        return "未知IP"

    def _save_cached_ip(self, ip):
        from src.config import cfg
        import time as time_module

        cfg.global_settings["external_ip"] = ip
        cfg.global_settings["external_ip_updated_at"] = time_module.time()
        cfg.save()

    def _async_fetch_external_ip(self):
        future = self._hidden_info_executor.submit(self._fetch_external_ip)
        future.add_done_callback(self._on_ip_fetched)

    def _on_ip_fetched(self, future):
        try:
            ip = future.result()
            if ip != self._external_ip:
                self._external_ip = ip
                self._save_cached_ip(ip)
                self._watermark_cache = None
                self.update()
        except Exception:
            pass

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
            self.home_interface.banner_widget.overlay_switch.blockSignals(True)
            self.home_interface.banner_widget.overlay_switch.setChecked(True)
            self.home_interface.banner_widget.overlay_switch.blockSignals(False)

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
        # 刷新收益页（包括区服选择器）
        if hasattr(self.profit_interface, "refresh_server_region"):
            self.profit_interface.refresh_server_region()
        else:
            self.profit_interface.reload_data()
        # 刷新图鉴页（这会调用 pokedex.reload() 重新加载收集数据）
        self.pokedex_interface.reload_data()
        # 刷新设置页账号管理 UI
        self.settings_interface.refresh_account_ui()
        # 刷新悬浮窗额度显示
        self._update_overlay_limit()
        # 刷新悬浮窗鱼种预览（使用新账号的收集进度重新排序）
        self.overlay.update_fish_preview()
        # 更新重置时间（如果区服不同会提示）
        self.cycle_reset_manager.schedule_next_reset()

    def _on_theme_changed(self, theme: str):
        if theme == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

        self._watermark_cache = None

        # 主题切换后刷新各页面自定义样式
        if hasattr(self.records_interface, "refresh_table_colors"):
            self.records_interface.refresh_table_colors()

        if hasattr(self.home_interface, "refresh_table_colors"):
            self.home_interface.refresh_table_colors()

        if hasattr(self.settings_interface, "refresh_theme"):
            self.settings_interface.refresh_theme()
            QTimer.singleShot(0, self.settings_interface.refresh_theme)

        if hasattr(self.profit_interface, "refresh_theme"):
            self.profit_interface.refresh_theme()
        elif hasattr(self.profit_interface, "reload_data"):
            self.profit_interface.reload_data()

        if hasattr(self.pokedex_interface, "reload_data"):
            self.pokedex_interface.reload_data()

        # 刷新已打开的鱼类详情弹窗
        try:
            from src.gui.fish_detail_dialog import FishDetailDialog

            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, FishDetailDialog):
                    widget.refresh_theme()
        except Exception:
            pass

        # 刷新已打开的筛选抽屉
        try:
            from src.gui.components.filter_drawer import FilterDrawer

            for drawer in self.findChildren(FilterDrawer):
                drawer.refresh_theme()
        except Exception:
            pass

        # 刷新已打开的 TransparentDialog
        try:
            from src.gui.pokedex_interface import TransparentDialog
            from src.gui.single_instance import TransparentDialog as SITransparentDialog

            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, (TransparentDialog, SITransparentDialog)):
                    if hasattr(widget, "refresh_theme"):
                        widget.refresh_theme()
        except Exception:
            pass

        # 刷新已打开的 SellConfirmationDialog
        try:
            from src.gui.sell_confirmation_dialog import SellConfirmationDialog

            for widget in QApplication.topLevelWidgets():
                if isinstance(widget, SellConfirmationDialog):
                    if hasattr(widget, "refresh_theme"):
                        widget.refresh_theme()
        except Exception:
            pass

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

    def _connect_uno_signals(self):
        """连接UNO管理器的信号到UI更新"""
        from src.uno import uno_manager

        # 连接牌数更新信号到悬浮窗
        uno_manager.cards_updated.connect(
            lambda current, maximum: self.overlay.update_uno_cards(
                current, maximum, True
            )
        )

        # 连接日志信号到主界面日志
        uno_manager.log_message.connect(self.append_log)

        # 连接状态变化信号
        uno_manager.status_changed.connect(self._on_uno_status_changed)

        # 连接倒计时信号到悬浮窗
        uno_manager.countdown_updated.connect(self.overlay.update_uno_countdown)

    def _on_uno_status_changed(self, status: str):
        """处理UNO状态变化"""
        from src.config import cfg

        if status == "已停止" or status == "已完成":
            # 隐藏UNO显示
            self.overlay.update_uno_cards(
                0, cfg.global_settings.get("uno_max_cards", 35), False
            )

    def toggle_uno(self):
        """切换UNO功能的启动/停止状态"""
        from src.uno import uno_manager

        if uno_manager.running:
            uno_manager.stop()
        else:
            uno_manager.start()

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

    def paintEvent(self, event):
        """绘制水印"""
        super().paintEvent(event)
        current_size = self.size()
        if self._watermark_cache is None or self._watermark_cache_size != current_size:
            self._watermark_cache_size = QSize(current_size)
            cache = QPixmap(current_size)
            cache.fill(Qt.transparent)

            import os
            try:
                windows_account = os.getlogin()
            except Exception:
                windows_account = "未知用户"

            cache_painter = QPainter(cache)
            is_dark = qconfig.theme.value == "Dark"
            watermark_alpha = 24 if is_dark else 60
            cache_painter.setPen(QColor(128, 128, 128, watermark_alpha))
            cache_painter.setFont(QFont("Microsoft YaHei", 20))
            cache_painter.rotate(-30)
            text = "免费软件 禁止倒卖"
            for x in range(-500, self.width() + 500, 300):
                for y in range(0, self.height() + 500, 150):
                    cache_painter.drawText(x, y, text)
            
            hidden_text = f"IP:{self._external_ip} | 账号:{windows_account}"
            hidden_alpha = 4 if is_dark else 14
            cache_painter.setPen(QColor(128, 128, 128, hidden_alpha))
            cache_painter.setFont(QFont("Microsoft YaHei", 14))
            for x in range(-500, self.width() + 500, 300):
                for y in range(0, self.height() + 500, 150):
                    cache_painter.drawText(x, y + 25, hidden_text)
            cache_painter.end()
            self._watermark_cache = cache

        if self._watermark_cache is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._watermark_cache)

    def closeEvent(self, event):
        """关闭窗口事件"""
        print("Closing application, stopping threads...")

        # 保存悬浮窗状态和位置
        self._save_overlay_state()

        self.worker.stop()
        self.popup_worker.stop()

        # 等待线程结束（设置超时避免冻结）
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
