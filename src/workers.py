import time
from PySide6.QtCore import QThread, Signal, Slot
from src.vision import vision
from src.inputs import InputActions
from src.config import cfg
from src.services.record_service import RecordService
from src.services.ocr_service import OCRService
from src.services.state_machine import FishingStateMachine
from src.services.release_service import ReleaseService
from src.services.fishing_service import FishingService


class FishingWorker(QThread):
    """
    自动化钓鱼逻辑的核心线程
    """

    log_updated = Signal(str)
    status_updated = Signal(str)
    record_added = Signal(dict)
    sale_recorded = Signal(int)  # 发出已售出金额的信号
    sound_alert_requested = Signal(str)
    bait_detected = Signal(str)  # 发出检测到的鱼饵名称的信号

    def __init__(self):
        super().__init__()
        self.ocr_service = OCRService()
        self.state_machine = FishingStateMachine()
        self.release_service = ReleaseService(self)
        self.fishing_service = FishingService(self)
        self.running = False
        self.paused = True  # 以暂停状态启动
        self.inputs = InputActions()
        self.vision = vision
        # 初始化鱼饵管理器
        self.bait_manager = None
        self._pending_bait_sync = False
        self._initial_bait_for_bite = None
        self._init_bait_manager()
        # 确保截图目录存在
        screenshots_dir = cfg._get_application_path() / "screenshots"
        if not screenshots_dir.exists():
            screenshots_dir.mkdir(parents=True)

    def _init_bait_manager(self):
        """初始化鱼饵管理器"""
        from src.managers.bait_manager import BaitManager

        selected_baits = cfg.get_global_setting("selected_baits", [])
        if selected_baits:
            self.bait_manager = BaitManager(selected_baits)
        else:
            self.bait_manager = None

    def _sync_current_bait_state(self):
        """
        检测并同步当前鱼饵。
        无论是否启用自动切换，脚本开始运行时都先校准一次当前鱼饵，
        保证收益统计使用的是实际鱼饵。
        """
        self._init_bait_manager()
        self.log_updated.emit("正在检测当前鱼饵...")

        try:
            detected_bait = self.vision.detect_current_bait()
        except Exception as e:
            self.log_updated.emit(f"检测当前鱼饵失败: {type(e).__name__}: {e}")
            return None

        if not detected_bait:
            self.log_updated.emit(f"未能识别当前鱼饵，沿用当前设置: {cfg.current_bait}")
            return None

        cfg.current_bait = detected_bait
        self.log_updated.emit(f"检测到当前鱼饵: {detected_bait}")
        self.bait_detected.emit(detected_bait)

        if self.bait_manager and self.bait_manager.sorted_baits:
            self.bait_manager.configure_runtime_sequence(detected_bait)

        return cfg.current_bait

    def run(self):
        """
        QThread 的入口点, 包含主循环
        """
        self.running = True

        # 检测游戏窗口，更新分辨率和偏移量
        self.log_updated.emit("正在检测游戏窗口...")
        if cfg.update_game_window():
            self.log_updated.emit(f"游戏窗口: {cfg.screen_width}x{cfg.screen_height}")
        else:
            self.log_updated.emit("⚠️ 未找到游戏窗口，使用全屏模式")

        # 启动预检
        self.log_updated.emit("正在执行启动环境预检...")
        env_checked = False

        # 1. 检查抛竿提示
        for key in ["F1_grayscale", "F2_grayscale"]:
            if self.vision.find_template(key, threshold=0.8):
                env_checked = True
                break

        # 3. 检查鱼饵数量
        if not env_checked:
            if self.vision.get_bait_amount() is not None:
                env_checked = True

        if env_checked:
            self.log_updated.emit("环境检查通过。等待启动... 按快捷键开始钓鱼")
        else:
            self.log_updated.emit("⚠️ 未检测到游戏界面，等待启动... 按快捷键开始钓鱼")

        # 等待用户按 F2 解除暂停
        while self.paused and self.running:
            self.fishing_service.drain_async_results()
            self.msleep(100)

        if not self.running:
            return

        # 按 F2 后才激活游戏窗口，确保按键能发送到游戏（解决副屏鼠标焦点问题）
        self.log_updated.emit("开始自动化钓鱼...")
        if cfg.activate_game_window():
            self.log_updated.emit("已激活游戏窗口")

        self._sync_current_bait_state()
        self._pending_bait_sync = False  # 首次启动已检测，清除标志

        while self.running:
            while self.paused:
                if not self.running:
                    break

                self.fishing_service.drain_async_results()
                self.msleep(100)  # 暂停时避免CPU空转

            if not self.running:
                break

            if self._pending_bait_sync:
                self._pending_bait_sync = False
                self._sync_current_bait_state()

            self.fishing_service.drain_async_results()

            try:
                if self.state_machine.is_finding_prompt():
                    if self.fishing_service.cast_rod():
                        self.state_machine.transition_to_waiting()

                elif self.state_machine.is_waiting_for_bite():
                    if not self.fishing_service.wait_for_bite():
                        # 如果等待超时或失败，重置状态
                        self._reset_fishing_cycle()
                    else:
                        self.state_machine.transition_to_reeling()

                elif self.state_machine.is_reeling_in():
                    reel_in_finished = self.fishing_service.reel_in()
                    if not reel_in_finished:
                        # 收线失败（鱼跑了），重置状态机重新开始
                        self._reset_fishing_cycle()
                    else:
                        single_release_decision = (
                            self.fishing_service.record_catch_non_blocking()
                        )
                        self.log_updated.emit("收起渔获, 准备下一轮。")

                        popup_closed = self._close_catch_popup()

                        # 在关闭弹窗后、重新抛竿前执行单条放生
                        release_mode = cfg.get_global_setting("release_mode", "off")
                        if (
                            release_mode == "single"
                            and popup_closed
                            and single_release_decision
                            and single_release_decision.get("should_release")
                        ):
                            self.release_service.execute_single_release(
                                single_release_decision
                            )

                        # 确保弹窗完全关闭后再同步钓鱼状态
                        if popup_closed:
                            self._sync_state_after_catch_popup()

            except KeyboardInterrupt:
                # 用户中断，优雅退出
                self.log_updated.emit("收到用户中断信号")
                self.pause("用户中断")
            except Exception as e:
                error_msg = f"发生错误：{type(e).__name__}: {e}"
                self.log_updated.emit(error_msg)
                print(f"[FishingWorker] {error_msg}")  # 同时输出到控制台
                self.pause()
                self.status_updated.emit(f"错误：{e}, 已暂停")

            self.fishing_service.drain_async_results()

            # 循环间隔，等待指定时间后再进行下一轮
            self.smart_sleep(cfg.get_preset_value("cycle_interval"))

        self.log_updated.emit("自动化钓鱼已停止。")

    def _find_any_template(self, keys, region, threshold=0.8):
        """Return True if any template in the region matches."""
        for key in keys:
            if self.vision.find_template(key, region=region, threshold=threshold):
                return True
        return False

    def _reset_fishing_cycle(self):
        """Reset cycle state and clear any stale bait baseline."""
        self._initial_bait_for_bite = None
        self.state_machine.reset()

    def _close_catch_popup(self):
        """
        关闭上鱼弹窗。

        点击后先等待界面结算，避免弹窗刚关闭时又补点一轮左键，
        导致主界面收到多余点击并误触发再次抛竿。
        """
        max_close_attempts = 10
        shangyu_region = cfg.get_rect("shangyu")
        wait_bite_region = cfg.get_rect("wait_bite")
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
        prompt_keys = ["F1_grayscale", "F2_grayscale"]
        popup_keys = ["shangyu_grayscale", "shoubing_shangyu_grayscale"]

        for close_attempt in range(max_close_attempts):
            if not self.running or self.paused:
                return False

            if not self._find_any_template(popup_keys, shangyu_region):
                if close_attempt > 0:
                    self.log_updated.emit("渔获弹窗已关闭")
                return True

            self.msleep(100)
            self.inputs.left_click()

            settle_deadline = time.time() + 0.8
            while time.time() < settle_deadline:
                if not self.running or self.paused:
                    return False

                if not self._find_any_template(popup_keys, shangyu_region):
                    self.log_updated.emit("渔获弹窗已关闭")
                    return True

                if self._find_any_template(prompt_keys, wait_bite_region):
                    self.log_updated.emit("检测到已进入等待咬钩界面，停止额外点击")
                    return True

                if self._find_any_template(
                    prompt_keys, cast_rod_region
                ) or self._find_any_template(prompt_keys, cast_rod_ice_region):
                    self.log_updated.emit("检测到抛竿提示已恢复，停止额外点击")
                    return True

                self.msleep(100)

        if self.running and not self.paused:
            self.log_updated.emit("警告: 渔获弹窗可能未完全关闭，继续下一轮")
        return False

    def _sync_state_after_catch_popup(self):
        """
        关窗后等待钓鱼 UI 稳定，再决定是回到抛竿还是继续等待咬钩。
        """
        wait_bite_region = cfg.get_rect("wait_bite")
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
        prompt_keys = ["F1_grayscale", "F2_grayscale"]
        sync_deadline = time.time() + max(1.2, cfg.get_preset_value("cast_time") + 0.8)
        stable_prompt_checks = 0

        while time.time() < sync_deadline:
            if not self.running or self.paused:
                return

            if self._find_any_template(prompt_keys, wait_bite_region):
                self.fishing_service.refresh_waiting_bait_baseline()
                self.log_updated.emit("检测到已抛竿，直接进入等待咬钩状态")
                self.state_machine.transition_to_waiting()
                return

            if self._find_any_template(
                prompt_keys, cast_rod_region
            ) or self._find_any_template(prompt_keys, cast_rod_ice_region):
                stable_prompt_checks += 1
                if stable_prompt_checks >= 3:
                    self._reset_fishing_cycle()
                    return
            else:
                stable_prompt_checks = 0

            self.msleep(100)

        self._reset_fishing_cycle()

    def pause(self, reason: str = None):
        """
        暂停线程并重置状态
        :param reason: 暂停的具体原因，如果不为None，将显示此状态，否则显示默认的"已暂停"
        """
        self.paused = True
        self._reset_fishing_cycle()
        self.inputs.ensure_mouse_up()

        status_text = f"已暂停: {reason}" if reason else "已暂停"
        self.status_updated.emit(status_text)
        self.log_updated.emit(
            f"脚本暂停，原因: {status_text}，状态已重置，已强制松开鼠标。"
        )

    def resume(self):
        """
        恢复线程
        """
        self.paused = False
        self._pending_bait_sync = True
        self.status_updated.emit("运行中")
        self.log_updated.emit("自动化已恢复。")

        # 恢复时重新激活游戏窗口（解决副屏暂停后恢复时焦点问题）
        if cfg.activate_game_window():
            self.log_updated.emit("已激活游戏窗口")

    def stop(self, reason: str = None, wait_for_async: bool = False):
        """
        安全地停止线程
        :param reason: 停止的具体原因，将作为最终状态显示在GUI上
        """
        self.running = False
        self.inputs.ensure_mouse_up()
        self.fishing_service.shutdown_async_processing(wait=wait_for_async)
        final_status = reason if reason else "已停止"
        self.status_updated.emit(f"{final_status}")
        self.log_updated.emit(f"收到停止信号, 原因: {final_status}")

    def smart_sleep(self, duration):
        """
        可中断的睡眠函数，能够及时响应停止/暂停信号
        """
        end_time = time.time() + duration
        while self.running and time.time() < end_time:
            if self.paused:
                return False
            sleep_time = min(0.1, end_time - time.time())
            if sleep_time > 0:
                time.sleep(sleep_time)
        return self.running and not self.paused

    @Slot(str)
    def update_preset(self, preset_name):
        """
        线程安全的槽函数，用于更新配置预设
        """
        try:
            self.log_updated.emit(f"接收到预设更改请求: {preset_name}")
            # 在工作线程中安全地加载新配置
            cfg.load_preset(preset_name)
            self.log_updated.emit(f"配置预设 '{preset_name}' 已成功加载。")
        except Exception as e:
            self.log_updated.emit(f"错误：加载预设 '{preset_name}' 失败: {e}")

    def _write_sale_record(self, amount):
        """
        将销售记录写入 CSV。
        成功返回 True，否则返回 False。
        """
        if not RecordService.save_sale_record(amount):
            self.log_updated.emit("写入销售记录失败")
            return False
        return True

    @Slot()
    def trigger_sell(self):
        """
        触发卖鱼逻辑: 截图识别 -> 检查进度 -> 记录 -> 点击
        """
        if self.running and not self.paused:
            self.log_updated.emit("脚本运行中，请先暂停再执行卖鱼操作。")
            return

        self.log_updated.emit("正在执行卖鱼操作...")

        try:
            rect = cfg.get_rect("sell_price_area")
            image = self.vision.screenshot(rect)

            # 使用鱼干图标作为锚点定位数字区域
            fish_icon_result = self.vision.find_template_in_image(
                "fish_icon_grayscale", image, threshold=0.5
            )

            if fish_icon_result:
                # 返回值: (center_x, center_y, width, height)
                center_x, center_y, icon_width, icon_height = fish_icon_result
                # 使用实际模板宽度的一半计算图标右边界
                icon_right_x = center_x + icon_width // 2
                # 从图标右边开始，裁剪到图片右边界
                digits_image = image[:, icon_right_x:]
                self.log_updated.emit(
                    f"[调试] 鱼干图标: 中心({center_x},{center_y}), 尺寸({icon_width}x{icon_height}), 数字起始: {icon_right_x}"
                )
            else:
                # 未找到鱼干图标，使用整个区域（兜底方案）
                self.log_updated.emit("[警告] 未找到鱼干图标，使用整个区域识别")
                digits_image = image

            # 使用模板匹配识别数字
            amount = self.vision._detect_digits_raw(digits_image, threshold=0.7)

            if amount is None:
                self.log_updated.emit("卖鱼失败: 未能识别到价格数字。")
                return

            self.log_updated.emit(f"识别到卖鱼金额: {amount}")

            # 获取当前今日进度
            from src.services.profit_analysis_service import ProfitAnalysisService

            profit_service = ProfitAnalysisService()
            start_time = profit_service.get_current_cycle_start_time()
            today_stats = profit_service.load_today_stats(start_time)
            current_progress = today_stats.total_sales

            self.log_updated.emit(f"当前今日进度: {current_progress}")

            # 检查是否需要弹出确认对话框
            if amount + current_progress > 899:
                self.log_updated.emit(
                    f"警告: 卖鱼金额({amount}) + 今日进度({current_progress}) = {amount + current_progress} > 899"
                )

                # 导入确认对话框
                from src.gui.sell_confirmation_dialog import SellConfirmationDialog
                from PySide6.QtWidgets import QApplication

                # 在主线程中显示对话框
                dialog = SellConfirmationDialog(amount, current_progress)
                dialog.exec()

                if not dialog.get_user_choice():
                    self.log_updated.emit("用户取消卖鱼操作")
                    return
                else:
                    self.log_updated.emit("用户确认继续卖鱼")

            # 在尝试点击之前写入记录
            if self._write_sale_record(amount):
                self.log_updated.emit("销售记录保存成功。")

                # 发出信号更新 UI
                self.sale_recorded.emit(amount)

                if cfg.get_global_setting("auto_click_sell", True):
                    # 点击区域中心（加上窗口偏移转换为屏幕绝对坐标）
                    cx = rect[0] + rect[2] // 2 + cfg.window_offset_x
                    cy = rect[1] + rect[3] // 2 + cfg.window_offset_y

                    # 执行点击
                    self.inputs.click(cx, cy)
                    self.log_updated.emit("已自动点击卖出。")
                else:
                    self.log_updated.emit("自动点击已禁用，仅记录数据。")
            else:
                self.log_updated.emit(
                    "严重错误：销售记录保存失败！为防止数据丢失，已终止出售操作。"
                )
                self.status_updated.emit("记录失败，未出售")
                if cfg.get_global_setting("enable_sound_alert", False):
                    # 如果有错误音效可以在这里播放，或者仅记录日志
                    pass

        except Exception as e:
            self.log_updated.emit(f"卖鱼操作发生错误: {e}")

    def _wait_for_popup_clear(self, timeout=5):
        """等待弹窗清除"""
        popup_region = cfg.get_rect("popup_exclamation")
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not self.vision.find_template_popup(
                "exclamation_grayscale", region=popup_region, threshold=0.7
            ):
                return True
            self.msleep(200)
        return False

    def _check_popup_during_bait_switch(self):
        """检测切换鱼饵过程中的弹窗"""
        popup_region = cfg.get_rect("popup_exclamation")
        if self.vision.find_template_popup(
            "exclamation_grayscale", region=popup_region, threshold=0.7
        ):
            self.log_updated.emit("切换鱼饵过程中检测到加时弹窗，等待处理...")
            if not self._wait_for_popup_clear(timeout=10):
                self.log_updated.emit("等待弹窗清除超时")
            self.smart_sleep(5.0)
            return True
        return False

    def _pause_for_no_bait(self, reason):
        """统一处理切换鱼饵时的无鱼饵暂停逻辑。"""
        if cfg.get_global_setting("enable_sound_alert", False):
            self.sound_alert_requested.emit("no_bait")
        self.pause(reason=reason)

    def _switch_to_target_bait(self, detected_bait, target_bait):
        """
        切换到目标鱼饵

        Args:
            detected_bait: 当前检测到的鱼饵
            target_bait: 目标鱼饵

        Returns:
            bool: True 表示成功，False 表示遇到弹窗需要重试
        """
        self.status_updated.emit("切换鱼饵中")

        # 第一次尝试：按索引计算滚动
        scroll_count = self.bait_manager.calculate_scroll_count(
            detected_bait, target_bait
        )
        if not self.inputs.switch_bait(scroll_count, sleep_fn=self.smart_sleep):
            return False
        self.smart_sleep(0.8)
        if not self.running or self.paused:
            return False

        if self._check_popup_during_bait_switch():
            return False

        new_bait = self.vision.detect_current_bait()
        if new_bait == target_bait:
            cfg.current_bait = target_bait
            if self.bait_manager:
                self.bait_manager.set_current_bait(target_bait)
            self.bait_detected.emit(target_bait)
            self.log_updated.emit(f"已切换到 {target_bait}")
            return True

        if detected_bait and new_bait == detected_bait:
            self._pause_for_no_bait("没有鱼饵了")
            return True

        # 如果没滚动到正确鱼饵，改用逐个滚动检测
        self.log_updated.emit(f"未找到目标，当前: {new_bait}，开始逐个检查")
        self.status_updated.emit("寻找可用鱼饵")
        max_scrolls = 4
        found_bait = False

        for scroll_attempt in range(max_scrolls):
            if not self.inputs.switch_bait(-1, sleep_fn=self.smart_sleep):
                return False
            self.smart_sleep(0.8)
            if not self.running or self.paused:
                return False

            if self._check_popup_during_bait_switch():
                return False

            current_bait = self.vision.detect_current_bait()
            if current_bait:
                self.log_updated.emit(f"检测到: {current_bait}")
                if current_bait == target_bait:
                    cfg.current_bait = target_bait
                    if self.bait_manager:
                        self.bait_manager.set_current_bait(target_bait)
                    self.bait_detected.emit(target_bait)
                    self.log_updated.emit(f"已切换到 {target_bait}")
                    found_bait = True
                    break

        # 如果找不到优先级最高的鱼饵，检查其他勾选的鱼饵
        if not found_bait:
            self.log_updated.emit(f"找不到 {target_bait}，检查其他勾选的鱼饵")
            final_bait = self.vision.detect_current_bait()

            if final_bait and final_bait in self.bait_manager.sorted_baits:
                cfg.current_bait = final_bait
                self.bait_manager.set_current_bait(final_bait)
                self.bait_detected.emit(final_bait)
                self.log_updated.emit(f"使用当前鱼饵: {final_bait}")
            else:
                self.log_updated.emit(f"所有勾选的鱼饵都找不到，暂停脚本")
                self._pause_for_no_bait("找不到勾选的鱼饵")

        return True

    def _check_popup_and_abort_release(self, released_count):
        """检测弹窗，如果存在则等待处理完成后返回"""
        popup_region = cfg.get_rect("popup_exclamation")
        if self.vision.find_template_popup(
            "exclamation_grayscale", region=popup_region, threshold=0.7
        ):
            self.log_updated.emit("放生过程中检测到加时弹窗，等待处理完成...")
            if not self._wait_for_popup_clear(timeout=10):
                self.log_updated.emit("等待弹窗清除超时")

            self.smart_sleep(5.0)
            self.log_updated.emit(
                f"检测到弹窗已处理，已回到正常钓鱼界面，本次放生了{released_count}条鱼"
            )

            self.status_updated.emit("运行中")
            return True
        return False


class PopupWorker(QThread):
    """
    一个专门用于在后台检测和处理游戏弹窗的独立工作线程.
    """

    log_updated = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.vision = vision
        self.inputs = InputActions()

    def run(self):
        """
        QThread 的入口点, 包含主循环, 持续检测弹窗.
        """
        self.running = True
        self.log_updated.emit("弹窗处理服务已启动。")

        minimized_log_printed = False

        while self.running:
            try:
                # 检查窗口状态：如果窗口最小化 (0x0)，则暂停检测并等待
                # 注意：cfg.update_game_window() 会更新 cfg.screen_width/height
                cfg.update_game_window()
                if cfg.screen_width <= 0 or cfg.screen_height <= 0:
                    if not minimized_log_printed:
                        self.log_updated.emit(
                            "检测到游戏窗口最小化，已暂停检测，等待窗口恢复..."
                        )
                        minimized_log_printed = True
                    self.msleep(1000)
                    continue

                if minimized_log_printed:
                    self.log_updated.emit("游戏窗口已恢复，继续检测弹窗。")
                    minimized_log_printed = False

                # --- 统一弹窗检测（加时弹窗 + AFK弹窗） ---
                # 两种弹窗都有相同的感叹号图标，使用统一模板检测
                popup_region = cfg.get_rect("popup_exclamation")
                if self.vision.find_template_popup(
                    "exclamation_grayscale", region=popup_region, threshold=0.7
                ):
                    self.log_updated.emit("检测到弹窗（加时/AFK），正在处理...")

                    # 根据用户设置决定点击位置
                    # 对于加时弹窗：enable_jiashi=True 点击"是"，False 点击"否"
                    # 对于 AFK 弹窗：无论点哪个位置都能关闭
                    if cfg.get_global_setting("enable_jiashi", True):
                        target_x, target_y = cfg.get_center_anchored_pos(
                            cfg.BTN_JIASHI_YES
                        )
                        self.log_updated.emit("已自动点击'是'。")
                    else:
                        target_x, target_y = cfg.get_center_anchored_pos(
                            cfg.BTN_JIASHI_NO
                        )
                        self.log_updated.emit("已自动点击'否'。")

                    # 加上窗口偏移转换为屏幕绝对坐标
                    self.inputs.click(
                        target_x + cfg.window_offset_x, target_y + cfg.window_offset_y
                    )
                    self.msleep(1000)  # 点击后等待，防止重复检测

            except Exception as e:
                error_msg = str(e)
                # 忽略 mss 截图相关的已知错误，避免刷屏
                if "ScreenShotError" in error_msg or "_thread._local" in error_msg:
                    pass
                elif "KeyboardInterrupt" in error_msg:
                    pass
                else:
                    self.log_updated.emit(
                        f"[弹窗处理服务] 发生错误：{type(e).__name__}: {e}"
                    )

            # 控制循环频率
            self.msleep(500)  # 每 0.5 秒检测一次

        self.log_updated.emit("弹窗处理服务已停止。")

    def stop(self):
        """
        安全地停止线程.
        """
        self.running = False
        self.log_updated.emit("收到停止弹窗处理服务的信号。")
