"""
信号管理器
负责管理 MainWindow 中的所有信号连接
"""


class SignalManager:
    """信号管理器类"""

    def __init__(self, main_window):
        """
        初始化信号管理器

        Args:
            main_window: MainWindow 实例
        """
        self.window = main_window

    def connect_all(self):
        """连接所有信号"""
        self._connect_worker_signals()
        self._connect_popup_worker_signals()
        self._connect_input_controller_signals()
        self._connect_settings_signals()
        self._connect_home_signals()
        self._connect_overlay_signals()
        self._connect_account_signals()
        self._connect_hotkey_signals()

    def _connect_worker_signals(self):
        """连接 worker 相关信号"""
        self.window.worker.log_updated.connect(self.window.append_log)
        self.window.worker.status_updated.connect(self.window.update_status)
        self.window.worker.record_added.connect(
            self.window.records_interface.add_record
        )
        self.window.worker.record_added.connect(
            self.window.home_interface.update_catch_info
        )
        self.window.worker.record_added.connect(
            self.window.home_interface.add_record_to_session_table
        )
        self.window.worker.record_added.connect(
            lambda x: self.window.profit_interface.request_reload()
        )
        self.window.worker.sale_recorded.connect(
            self.window.profit_interface.add_sale_record
        )
        self.window.worker.sale_recorded.connect(self.window._update_overlay_limit)
        self.window.worker.sound_alert_requested.connect(
            self.window.audio_manager.play_sound_alert
        )

    def _connect_popup_worker_signals(self):
        """连接 popup worker 相关信号"""
        self.window.popup_worker.log_updated.connect(self.window.append_log)

    def _connect_input_controller_signals(self):
        """连接输入控制器相关信号"""
        self.window.input_controller.toggle_script_signal.connect(
            self.window.toggle_script
        )
        self.window.input_controller.debug_screenshot_signal.connect(
            self.window.take_debug_screenshot
        )
        self.window.input_controller.sell_hotkey_signal.connect(
            self.window.worker.trigger_sell
        )
        self.window.input_controller.uno_hotkey_signal.connect(self.window.toggle_uno)

    def _connect_settings_signals(self):
        """连接设置界面相关信号"""
        self.window.settings_interface.hotkey_changed_signal.connect(
            self.window.home_interface.update_hotkey_display
        )
        self.window.settings_interface.debug_hotkey_changed_signal.connect(
            self.window.home_interface.update_debug_hotkey_display
        )
        self.window.settings_interface.hotkey_changed_signal.connect(
            self.window.input_controller._update_hotkey_handler
        )
        self.window.settings_interface.debug_hotkey_changed_signal.connect(
            self.window.input_controller._update_debug_hotkey_handler
        )
        self.window.settings_interface.sell_hotkey_changed_signal.connect(
            self.window.input_controller._update_sell_hotkey_handler
        )
        self.window.settings_interface.sell_hotkey_changed_signal.connect(
            self.window.home_interface.update_sell_hotkey_display
        )
        self.window.settings_interface.uno_hotkey_changed_signal.connect(
            self.window.input_controller._update_uno_hotkey_handler
        )
        self.window.settings_interface.theme_changed_signal.connect(
            self.window._on_theme_changed
        )
        self.window.settings_interface.account_list_changed_signal.connect(
            self.window.home_interface.refresh_account_list
        )
        self.window.settings_interface.account_list_changed_signal.connect(
            self.window.settings_interface.refresh_account_ui
        )
        self.window.settings_interface.records_updated_signal.connect(
            self.window.records_interface._load_data
        )
        self.window.settings_interface.records_updated_signal.connect(
            self.window.profit_interface.reload_data
        )
        self.window.settings_interface.records_updated_signal.connect(
            self.window.pokedex_interface.reload_data
        )
        self.window.settings_interface.reset_overlay_position_signal.connect(
            self.window.overlay._set_default_position
        )

    def _connect_home_signals(self):
        """连接首页相关信号"""
        self.window.home_interface.preset_changed_signal.connect(
            self.window.on_preset_changed
        )
        self.window.home_interface.toggle_overlay_signal.connect(
            self.window.toggle_overlay
        )
        self.window.home_interface.fishFilterChanged.connect(
            self.window.overlay.update_fish_preview
        )
        self.window.home_interface.account_changed_signal.connect(
            self.window._on_account_changed
        )

    def _connect_overlay_signals(self):
        """连接悬浮窗相关信号"""
        self.window.worker.status_updated.connect(self.window.overlay.update_status)
        self.window.worker.record_added.connect(
            lambda: self.window.overlay.update_fish_count(
                self.window.home_interface.total_catch
            )
        )
        self.window.worker.sale_recorded.connect(self.window._update_overlay_limit)

    def _connect_account_signals(self):
        """连接账号相关信号"""
        self.window.profit_interface.data_changed_signal.connect(
            self.window._update_overlay_limit
        )
        self.window.profit_interface.server_changed_signal.connect(
            self.window.cycle_reset_manager.on_server_region_changed
        )

    def _connect_hotkey_signals(self):
        """连接快捷键相关信号"""
        self.window.preset_should_change.connect(self.window.worker.update_preset)
        self.window.settings_interface.gamepad_mapping_changed_signal.connect(
            self.window.input_controller._reinit_gamepad
        )
