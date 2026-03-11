"""
钓鱼服务
负责处理钓鱼的核心流程：抛竿、等待咬钩、收竿、记录渔获
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor
from src.config import cfg
from src.services.ocr_service import OCRService
from src.services.record_schema import infer_time_period_from_timestamp
from src.services.record_service import RecordService
from src.services.screenshot_service import ScreenshotService


class FishingService:
    """钓鱼服务类"""

    def __init__(self, worker):
        self.worker = worker
        # 保持异步捕获任务串行执行，避免并发记录写入。
        self._async_executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="catch-recorder"
        )
        self._async_futures = []
        self._async_futures_lock = threading.Lock()
        # 使用默认 OCR 线程以提高后台识别吞吐量。
        self._async_ocr_service = OCRService()

    def _build_signal_record(
        self,
        name: str,
        quality: str,
        weight,
        is_new_record: bool,
        saved_record: dict | None = None,
    ) -> dict:
        """构建一条已保存或回退记录的 UI 数据。"""
        timestamp = (
            saved_record.get("Timestamp")
            if saved_record and saved_record.get("Timestamp")
            else time.strftime("%Y-%m-%d %H:%M:%S")
        )
        return {
            "timestamp": timestamp,
            "time_period": (
                saved_record.get("TimePeriod")
                if saved_record and saved_record.get("TimePeriod") is not None
                else infer_time_period_from_timestamp(timestamp)
            ),
            "weather": (
                saved_record.get("Weather")
                if saved_record and saved_record.get("Weather") is not None
                else ""
            ),
            "name": name,
            "weight": weight,
            "quality": quality,
            "is_new_record": is_new_record,
        }

    def _try_switch_bait(self):
        """
        尝试切换到下一个鱼饵

        Returns:
            bool: 是否成功切换
        """
        if not hasattr(self.worker, "bait_manager") or not self.worker.bait_manager:
            return False

        # 检测当前鱼饵
        current_bait = self.worker.vision.detect_current_bait() or cfg.current_bait
        if current_bait:
            self.worker.bait_manager.set_current_bait(current_bait)

        if not self.worker.bait_manager.has_more_baits():
            self.worker.log_updated.emit("所有选择的鱼饵都用完了。")
            return False

        next_bait = self.worker.bait_manager.get_next_bait()

        if not next_bait:
            return False

        self.worker.log_updated.emit(f"正在切换鱼饵：{current_bait} -> {next_bait}")
        success = self.worker._switch_to_target_bait(current_bait, next_bait)
        if not success:
            self.worker.log_updated.emit("弹窗已处理，重新切换鱼饵...")
            time.sleep(0.5)
            success = self.worker._switch_to_target_bait(current_bait, next_bait)

        if success and cfg.current_bait:
            self.worker.bait_manager.set_current_bait(cfg.current_bait)

        return success

    def _get_initial_bait_amount(self):
        """
        获取抛竿前的鱼饵数量

        Returns:
            int or None: 鱼饵数量，如果无法获取则返回 None
        """
        for _ in range(10):
            if not self.worker.running:
                return None
            while self.worker.paused:
                self.worker.msleep(100)

            bait_amount = self.worker.vision.get_bait_amount()
            if bait_amount is not None:
                self.worker.log_updated.emit(f"[调试] 抛竿前鱼饵数量: {bait_amount}")
                return bait_amount
            self.worker.msleep(200)

        self.worker.log_updated.emit("错误: 抛竿前无法获取鱼饵数量。")
        if cfg.global_settings.get("enable_sound_alert", False):
            self.worker.sound_alert_requested.emit("no_bait")
        self.worker.pause(reason="无法识别鱼饵数量")
        return None

    def _set_waiting_bait_baseline(self, bait_amount):
        """存储等待咬钩阶段的鱼饵数量基线。"""
        self.worker._initial_bait_for_bite = bait_amount

    def refresh_waiting_bait_baseline(self):
        """
        从当前屏幕刷新等待咬钩阶段的鱼饵数量基线。

        当脚本检测到已经处于等待状态且未经过正常抛竿验证路径时使用此方法。
        """
        for _ in range(5):
            if not self.worker.running:
                break
            while self.worker.paused:
                self.worker.msleep(100)

            bait_amount = self.worker.vision.get_bait_amount()
            if bait_amount is not None:
                self._set_waiting_bait_baseline(bait_amount)
                return bait_amount

            self.worker.msleep(100)

        self.worker._initial_bait_for_bite = None
        return None

    def _handle_cast_verification_timeout(self, initial_bait, cast_icon_ever_gone):
        """
        处理抛竿验证超时的情况

        Args:
            initial_bait: 抛竿前的鱼饵数量
            cast_icon_ever_gone: 抛竿图标是否消失过

        Returns:
            bool: False 表示需要重试
        """
        if initial_bait is not None and not self.worker.paused:
            final_bait = self.worker.vision.get_bait_amount()
            if final_bait is not None and final_bait < initial_bait:
                self.worker.log_updated.emit(
                    f"鱼饵减少 ({initial_bait} -> {final_bait}) 但未成功收竿，判定为鱼跑了。"
                )
                self._record_event("鱼跑了")
                return False

        if not self.worker.running or self.worker.paused:
            self.worker.log_updated.emit("抛竿验证期间被手动暂停或停止，重置状态。")
            return False

        if not cast_icon_ever_gone:
            bait_amount = self.worker.vision.get_bait_amount()
            if bait_amount == 0:
                self.worker.log_updated.emit("鱼饵用完了。")
                # 尝试切换到下一个鱼饵
                if self._try_switch_bait():
                    return False
                # 没有更多鱼饵，暂停
                if cfg.global_settings.get("enable_sound_alert", False):
                    self.worker.sound_alert_requested.emit("no_bait")
                self.worker.pause(reason="没有鱼饵了")
            else:
                self.worker.log_updated.emit("检测到鱼桶已满（抛竿图标未消失）。")
                if cfg.global_settings.get("auto_release_enabled", False):
                    released_count = (
                        self.worker.release_service.check_and_auto_release()
                    )
                    if released_count == -1:
                        # 弹窗中止，重新尝试放生
                        self.worker.log_updated.emit("弹窗已处理，重新尝试放生...")
                        released_count = (
                            self.worker.release_service.check_and_auto_release()
                        )
                        if released_count == -1 or released_count == 0:
                            self.worker.log_updated.emit(
                                "自动放生未放生任何鱼，鱼桶可能仍然满载或没有符合放生条件的鱼。"
                            )
                            if cfg.global_settings.get("enable_sound_alert", False):
                                self.worker.sound_alert_requested.emit("inventory_full")
                            self.worker.pause(reason="鱼桶已满且无法自动放生")
                    elif released_count == 0:
                        self.worker.log_updated.emit(
                            "自动放生未放生任何鱼，鱼桶可能仍然满载或没有符合放生条件的鱼。"
                        )
                        if cfg.global_settings.get("enable_sound_alert", False):
                            self.worker.sound_alert_requested.emit("inventory_full")
                        self.worker.pause(reason="鱼桶已满且无法自动放生")
                else:
                    if cfg.global_settings.get("enable_sound_alert", False):
                        self.worker.sound_alert_requested.emit("inventory_full")
                    self.worker.pause(reason="鱼桶已满")
            return False

        self.worker.log_updated.emit("抛竿验证超时，将重新尝试。")
        return False

    def _verify_cast_success(self, key, found_region, initial_bait):
        """
        验证抛竿是否成功

        Args:
            key: 检测的按键图标
            found_region: 抛竿图标所在区域
            initial_bait: 抛竿前的鱼饵数量

        Returns:
            tuple: (success, cast_icon_ever_gone) - success 表示是否成功，cast_icon_ever_gone 表示抛竿图标是否消失过
        """
        verification_start_time = time.time()
        verification_timeout = 5  # 增加超时时间从3秒到5秒
        wait_bite_region = cfg.get_rect("wait_bite")

        verification_check_count = 0
        cast_icon_ever_gone = False
        max_match_score = 0.0  # 记录最大匹配分数

        self.worker.log_updated.emit(
            f"[诊断] 开始抛竿验证，超时时间: {verification_timeout}秒"
        )

        while time.time() - verification_start_time < verification_timeout:
            # 检测抛竿图标是否消失
            cast_icon_gone = not self.worker.vision.find_template(
                key, region=found_region, threshold=0.8
            )

            # 检测等待图标是否出现
            wait_icon_appeared = self.worker.vision.find_template(
                key, region=wait_bite_region, threshold=0.8
            )

            verification_check_count += 1

            if cast_icon_gone:
                cast_icon_ever_gone = True

            if cast_icon_gone and wait_icon_appeared:
                self._set_waiting_bait_baseline(initial_bait)
                self.worker.log_updated.emit("已抛竿, 进入等待咬钩状态。")
                self.worker.status_updated.emit("等待咬钩")
                return True, cast_icon_ever_gone

            self.worker.msleep(200)

        # 记录更详细的诊断信息
        elapsed_time = time.time() - verification_start_time
        self.worker.log_updated.emit(
            f"[诊断] 抛竿验证超时。检测次数: {verification_check_count}, 耗时: {elapsed_time:.2f}秒"
        )

        return False, cast_icon_ever_gone

    def cast_rod(self):
        """抛竿阶段"""
        if not self.worker.running:
            return False
        self.worker.status_updated.emit("抛竿阶段")
        self.worker.log_updated.emit("正在寻找抛竿提示...")

        start_time = time.time()
        timeout = 10
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")

        while time.time() - start_time < timeout:
            if not self.worker.running:
                return False
            while self.worker.paused:
                self.worker.msleep(100)

            for key in ["F1_grayscale", "F2_grayscale"]:
                found_region = None
                if self.worker.vision.find_template(
                    key, region=cast_rod_region, threshold=0.8
                ):
                    found_region = cast_rod_region
                elif self.worker.vision.find_template(
                    key, region=cast_rod_ice_region, threshold=0.8
                ):
                    found_region = cast_rod_ice_region

                if found_region:
                    self.worker.log_updated.emit(f"检测到抛竿提示, 准备抛竿。")

                    initial_bait_before_cast = self._get_initial_bait_amount()
                    if initial_bait_before_cast is None:
                        return False

                    self.worker.inputs.hold_mouse(cfg.cast_time)

                    self.worker.smart_sleep(1.0)

                    success, cast_icon_ever_gone = self._verify_cast_success(
                        key, found_region, initial_bait_before_cast
                    )
                    if success:
                        return True

                    return self._handle_cast_verification_timeout(
                        initial_bait_before_cast, cast_icon_ever_gone
                    )

            self.worker.msleep(200)

        self.worker.log_updated.emit("抛竿超时, 未找到抛竿提示。")
        return False

    def _check_for_unhook(self, initial_bait, cast_rod_region, cast_rod_ice_region):
        """
        检查是否错过咬钩导致鱼跑了

        Args:
            initial_bait: 初始鱼饵数量
            cast_rod_region: 抛竿区域
            cast_rod_ice_region: 冰钓抛竿区域

        Returns:
            bool: True 表示检测到脱钩（鱼跑了），False 表示没有脱钩
        """
        check_bait = self.worker.vision.get_bait_amount()
        if check_bait is not None and check_bait < initial_bait:
            for key in ["F1_grayscale", "F2_grayscale"]:
                if self.worker.vision.find_template(
                    key, region=cast_rod_region, threshold=0.8
                ) or self.worker.vision.find_template(
                    key, region=cast_rod_ice_region, threshold=0.8
                ):
                    self.worker.log_updated.emit(
                        f"鱼饵减少 ({initial_bait} -> {check_bait}) 且抛竿图标出现，错过咬钩，鱼跑了！"
                    )
                    self._record_event("鱼跑了")
                    return True
        return False

    def _get_initial_bait_for_bite(self):
        """
        获取等待咬钩阶段的初始鱼饵数量

        Returns:
            int or None: 初始鱼饵数量，如果无法获取则返回 -1 表示将监控任意变化
        """
        initial_bait = getattr(self.worker, "_initial_bait_for_bite", None)

        if initial_bait is not None:
            self.worker._initial_bait_for_bite = None
            self.worker.log_updated.emit(f"初始鱼饵数量: {initial_bait}")
            return initial_bait

        self.worker.log_updated.emit("抛竿阶段未获取到鱼饵数量，尝试重新获取...")
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")

        for attempt in range(10):
            if not self.worker.running:
                return None
            while self.worker.paused:
                self.worker.msleep(100)

            initial_bait = self.worker.vision.get_bait_amount()
            if initial_bait is not None:
                self.worker.log_updated.emit(f"初始鱼饵数量: {initial_bait}")
                return initial_bait

            if attempt > 0 and attempt % 3 == 0:
                for key in ["F1_grayscale", "F2_grayscale"]:
                    if self.worker.vision.find_template(
                        key, region=cast_rod_region, threshold=0.8
                    ) or self.worker.vision.find_template(
                        key, region=cast_rod_ice_region, threshold=0.8
                    ):
                        self.worker.log_updated.emit(
                            "检测到抛竿图标，可能未抛竿成功或已超时。重置循环。"
                        )
                        return None

            self.worker.smart_sleep(0.3)

        self.worker.log_updated.emit("警告: 无法获取初始鱼饵数量，将监控任意鱼饵变化。")
        return -1

    def wait_for_bite(self):
        """等待鱼儿咬钩"""
        if not self.worker.running:
            return False
        self.worker.status_updated.emit("等待咬钩")
        self.worker.log_updated.emit("等待鱼饵数量减少...")

        initial_bait = self._get_initial_bait_for_bite()
        if initial_bait is None:
            return False

        timeout = 120
        start_time = time.time()

        last_known_bait = initial_bait
        consecutive_none_count = 0
        none_warning_threshold = 20
        total_none_count = 0
        total_checks = 0

        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
        unhook_check_interval = 20

        while time.time() - start_time < timeout:
            if not self.worker.running or self.worker.paused:
                return False

            current_bait = self.worker.vision.get_bait_amount()
            total_checks += 1

            if current_bait is None:
                consecutive_none_count += 1
                total_none_count += 1

                if consecutive_none_count == none_warning_threshold:
                    pass
            else:
                consecutive_none_count = 0

                if initial_bait == -1:
                    initial_bait = current_bait
                    last_known_bait = current_bait
                    self.worker.log_updated.emit(f"已获取基准鱼饵数量: {initial_bait}")
                    continue

                last_known_bait = current_bait

                if current_bait != initial_bait:
                    self.worker.msleep(30)

                    confirm_bait = self.worker.vision.get_bait_amount()
                    if confirm_bait is not None and confirm_bait != initial_bait:
                        self.worker.log_updated.emit(
                            f"检测到鱼饵数量变化 ({initial_bait} -> {confirm_bait}), 判定为咬钩。"
                        )
                        return True
                    else:
                        self.worker.log_updated.emit(
                            f"[调试] 疑似过渡帧，忽略 ({initial_bait} -> {current_bait} -> {confirm_bait})"
                        )

            if total_checks % unhook_check_interval == 0:
                if self._check_for_unhook(
                    initial_bait, cast_rod_region, cast_rod_ice_region
                ):
                    return False

            self.worker.msleep(50)

        self.worker.log_updated.emit(
            f"等待咬钩超时。最后已知鱼饵: {last_known_bait}, 初始: {initial_bait}"
        )
        return False

    def reel_in(self):
        """收竿阶段"""
        if not self.worker.running:
            return False
        self.worker.status_updated.emit("上鱼了! 开始收竿!")
        self.worker.log_updated.emit("进入收放线循环...")

        star_region = cfg.get_rect("reel_in_star")

        for i in range(cfg.max_pulls):
            if not self.worker.running or self.worker.paused:
                return False

            self.worker.log_updated.emit(f"第 {i+1}/{cfg.max_pulls} 次尝试: 收线...")

            self.worker.inputs.press_mouse_button()
            pull_start_time = time.time()
            pull_duration = cfg.reel_in_time

            try:
                while time.time() - pull_start_time < pull_duration:
                    if not self.worker.running or self.worker.paused:
                        return False

                    time.sleep(0.05)
            finally:
                self.worker.inputs.release_mouse_button()

            self.worker.log_updated.emit("放线...")
            sleep_duration = self.worker.inputs.add_jitter(cfg.release_time)
            self.worker.smart_sleep(sleep_duration)

            if self.worker.vision.find_template(
                "star_grayscale", region=star_region, threshold=0.7
            ):
                self.worker.log_updated.emit("检测到星星，成功！")
                return True

            cast_rod_region = cfg.get_rect("cast_rod")
            cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
            for key in ["F1_grayscale", "F2_grayscale"]:
                if self.worker.vision.find_template(
                    key, region=cast_rod_region, threshold=0.8
                ) or self.worker.vision.find_template(
                    key, region=cast_rod_ice_region, threshold=0.8
                ):
                    self.worker.log_updated.emit(
                        "未检测到星星，抛竿提示出现，判定为鱼跑了！"
                    )
                    self.worker.status_updated.emit("鱼跑了!")
                    self._record_event("鱼跑了")
                    return False

        self.worker.log_updated.emit("达到最大拉竿次数，仍未检测到星星。")
        return False

    def record_catch(self):
        """截图识别渔获信息"""
        if not self.worker.running:
            return False

        if not cfg.global_settings.get("enable_fish_recognition", True):
            self.worker.log_updated.emit("鱼类识别已关闭，等待并关闭渔获弹窗")
            self.worker.status_updated.emit("关闭渔获弹窗")

            self.worker.smart_sleep(0.5)

            max_attempts = 10
            shangyu_region = cfg.get_rect("shangyu")
            shangyu_found = False

            for attempt in range(max_attempts):
                if not self.worker.running:
                    return False

                for key in ["shangyu_grayscale", "shoubing_shangyu_grayscale"]:
                    if self.worker.vision.find_template(
                        key, region=shangyu_region, threshold=0.8
                    ):
                        self.worker.log_updated.emit("检测到'收起'按钮，准备关闭弹窗")
                        shangyu_found = True
                        break
                if shangyu_found:
                    break

                self.worker.msleep(500)

            if not shangyu_found:
                self.worker.log_updated.emit(
                    "警告: 未检测到'收起'按钮，尝试直接点击关闭"
                )

            return False

        release_mode = cfg.global_settings.get("release_mode", "off")
        if release_mode == "single":
            # 单条放生模式在识别后立即执行，此处保留放生状态。
            self.worker.status_updated.emit("自动放生中")
        else:
            self.worker.status_updated.emit("记录渔获")
        self.worker.log_updated.emit("正在识别渔获信息...")

        self.worker.smart_sleep(0.5)

        shangyu_region = cfg.get_rect("shangyu")
        for key in ["shangyu_grayscale", "shoubing_shangyu_grayscale"]:
            if self.worker.vision.find_template(
                key, region=shangyu_region, threshold=0.8
            ):
                self.worker.log_updated.emit("检测到'收起'按钮，确认上鱼成功。")
                break

        success, catch_data = self.worker.ocr_service.recognize_catch_info(
            self.worker.vision, self.worker.log_updated.emit
        )

        if not success:
            return False

        fish_name = catch_data["name"]
        quality = catch_data["quality"]
        weight = catch_data["weight"]
        is_new_record = catch_data["is_new_record"]

        self.worker.log_updated.emit(
            f"钓到鱼: {fish_name}, 重量: {weight}kg, 品质: {quality}"
        )

        saved_record = RecordService.save_catch_record(
            fish_name, quality, weight, is_new_record
        )
        if not saved_record:
            self.worker.log_updated.emit("写入记录文件失败")

        catch_data = self._build_signal_record(
            fish_name, quality, weight, is_new_record, saved_record
        )
        self.worker.record_added.emit(catch_data)

        # 使用统一的放生品质配置
        if fish_name:
            # 有鱼类名称时，使用基于稀有度的判断
            should_release = self.worker.release_service._should_release_by_rarity(fish_name, quality)
        else:
            # 没有鱼类名称信息时，使用旧逻辑
            release_map = {
                "标准": "release_standard",
                "非凡": "release_uncommon",
                "稀有": "release_rare",
                "史诗": "release_epic",
                "传奇": "release_legendary",
            }
            should_release = cfg.global_settings.get(release_map.get(quality), False)

        if is_new_record and cfg.global_settings.get(
            "enable_first_catch_screenshot", True
        ):
            self.worker.log_updated.emit("首次捕获! 正在截图保存...")
            success, result = ScreenshotService.capture_first_catch(fish_name, quality)
            if success:
                self.worker.log_updated.emit(f"截图已保存至 {result}")
            else:
                self.worker.log_updated.emit(f"截图失败: {result}")

        if quality == "传奇" and cfg.global_settings.get(
            "enable_legendary_screenshot", True
        ):
            self.worker.log_updated.emit("哇! 钓到了传奇品质的鱼, 正在截图保存...")
            success, result = ScreenshotService.capture_legendary(
                fish_name, quality, is_new_record
            )
            if success:
                self.worker.log_updated.emit(f"截图已保存至 {result}")
            else:
                self.worker.log_updated.emit(f"截图失败: {result}")

        return should_release

    def _should_run_async_catch_processing(self) -> bool:
        """当渔获识别可以异步运行时返回 True。"""
        release_mode = cfg.global_settings.get("release_mode", "off")
        if release_mode == "single":
            # 单条放生模式依赖当前渔获结果。
            self.worker.log_updated.emit("单条放生模式已开启，渔获识别保持同步执行。")
            return False

        return True

    def _capture_catch_snapshots(self):
        """在弹窗关闭前快速捕获 OCR 帧。"""
        ocr_area = cfg.get_rect("ocr_area")
        if not ocr_area:
            return []

        self.worker.smart_sleep(0.15)

        snapshots = []
        for index in range(2):
            frame = self.worker.vision.screenshot(ocr_area)
            if frame is not None:
                snapshots.append(frame)
            if index == 0:
                self.worker.msleep(80)

        return snapshots

    def _maybe_trigger_steam_screenshot_early(self, ocr_snapshots):
        """
        Steam 模式截图必须立即触发。
        使用缓存的 OCR 帧来决定是否在弹窗关闭前按 F12。
        """
        screenshot_mode = cfg.global_settings.get("screenshot_mode", "wegame")
        if screenshot_mode != "steam":
            return

        first_enabled = cfg.global_settings.get("enable_first_catch_screenshot", True)
        legend_enabled = cfg.global_settings.get("enable_legendary_screenshot", True)
        if not first_enabled and not legend_enabled:
            return

        success, catch_data = self.worker.ocr_service.recognize_catch_info_from_images(
            ocr_snapshots, log_callback=None
        )
        if not success:
            self.worker.log_updated.emit("Steam 截图预判失败，跳过即时 F12。")
            return

        fish_name = catch_data["name"]
        quality = catch_data["quality"]
        is_new_record = catch_data["is_new_record"]

        need_first = is_new_record and first_enabled
        need_legend = quality == "传奇" and legend_enabled

        if need_first:
            shot_ok, result = ScreenshotService.capture_first_catch(fish_name, quality)
            self.worker.log_updated.emit(
                f"Steam 首捕截图: {result}"
                if shot_ok
                else f"Steam 首捕截图失败: {result}"
            )

        if need_legend:
            shot_ok, result = ScreenshotService.capture_legendary(
                fish_name, quality, is_new_record
            )
            self.worker.log_updated.emit(
                f"Steam 传奇截图: {result}"
                if shot_ok
                else f"Steam 传奇截图失败: {result}"
            )

    def _process_catch_in_background(self, ocr_snapshots):
        """在后台线程中运行 OCR + 记录持久化。"""
        logs = []
        success, catch_data = self._async_ocr_service.recognize_catch_info_from_images(
            ocr_snapshots, log_callback=None
        )

        if not success:
            logs.append("后台渔获识别失败，本轮未写入记录。")
            return {"logs": logs, "catch_data": None}

        fish_name = catch_data["name"]
        quality = catch_data["quality"]
        weight = catch_data["weight"]
        is_new_record = catch_data["is_new_record"]

        logs.append(f"钓到鱼: {fish_name}, 重量: {weight}kg, 品质: {quality}")

        saved_record = RecordService.save_catch_record(
            fish_name, quality, weight, is_new_record
        )
        if not saved_record:
            logs.append("写入记录文件失败")

        screenshot_mode = cfg.global_settings.get("screenshot_mode", "wegame")
        if screenshot_mode == "steam":
            # Steam F12 必须在前台提前触发，跳过延迟的后台触发。
            return {
                "logs": logs,
                "catch_data": self._build_signal_record(
                    fish_name, quality, weight, is_new_record, saved_record
                ),
            }

        if is_new_record and cfg.global_settings.get(
            "enable_first_catch_screenshot", True
        ):
            success, result = ScreenshotService.capture_first_catch(fish_name, quality)
            logs.append(f"截图已保存至 {result}" if success else f"截图失败: {result}")

        if quality == "传奇" and cfg.global_settings.get(
            "enable_legendary_screenshot", True
        ):
            success, result = ScreenshotService.capture_legendary(
                fish_name, quality, is_new_record
            )
            logs.append(f"截图已保存至 {result}" if success else f"截图失败: {result}")

        return {
            "logs": logs,
            "catch_data": self._build_signal_record(
                fish_name, quality, weight, is_new_record, saved_record
            ),
        }

    def _dispatch_async_result(self, result):
        """立即从完成回调中发出异步捕获结果信号。"""
        for message in result.get("logs", []):
            self.worker.log_updated.emit(message)

        catch_data = result.get("catch_data")
        if catch_data:
            self.worker.record_added.emit(catch_data)

    def _on_async_catch_done(self, future):
        """处理一个已完成的异步捕获任务。"""
        try:
            result = future.result()
        except Exception as e:
            self.worker.log_updated.emit(f"后台渔获处理异常: {type(e).__name__}: {e}")
        else:
            self._dispatch_async_result(result)
        finally:
            with self._async_futures_lock:
                if future in self._async_futures:
                    self._async_futures.remove(future)

    def _submit_async_catch_processing(self, ocr_snapshots) -> bool:
        try:
            future = self._async_executor.submit(
                self._process_catch_in_background, ocr_snapshots
            )
            with self._async_futures_lock:
                self._async_futures.append(future)
            future.add_done_callback(self._on_async_catch_done)
            return True
        except Exception as e:
            self.worker.log_updated.emit(f"后台任务提交失败: {type(e).__name__}: {e}")
            return False

    def drain_async_results(self):
        """轻量级清理；实际结果分发由回调驱动。"""
        with self._async_futures_lock:
            self._async_futures = [f for f in self._async_futures if not f.done()]

    def shutdown_async_processing(self, wait: bool = False):
        """关闭异步执行器以避免应用退出时残留线程。"""
        try:
            with self._async_futures_lock:
                futures = list(self._async_futures)
                self._async_futures.clear()

            for future in futures:
                if not future.done():
                    future.cancel()
            self._async_executor.shutdown(wait=wait, cancel_futures=True)
        except Exception:
            pass

    def record_catch_non_blocking(self):
        """
        非阻塞捕获入口：
        - 异步路径：快速捕获 OCR 帧并立即返回。
        - 回退路径：运行现有的同步 record_catch()。
        """
        if not self.worker.running:
            return False

        if not cfg.global_settings.get("enable_fish_recognition", True):
            return self.record_catch()

        if not self._should_run_async_catch_processing():
            return self.record_catch()

        self.worker.status_updated.emit("记录渔获(后台)")

        snapshots = self._capture_catch_snapshots()
        if not snapshots:
            self.worker.log_updated.emit("未采集到有效渔获快照，回退到同步识别。")
            return self.record_catch()

        self._maybe_trigger_steam_screenshot_early(snapshots)

        if snapshots and self._submit_async_catch_processing(snapshots):
            self.worker.log_updated.emit("渔获识别已转入后台...")
            return False

        self.worker.log_updated.emit("后台处理启动失败，回退到同步识别。")
        return self.record_catch()

    def _record_event(self, event_type: str):
        """记录事件到CSV"""
        saved_record = RecordService.save_event_record(event_type)
        if not saved_record:
            self.worker.log_updated.emit("写入记录文件失败")

        event_data = self._build_signal_record(
            event_type,
            "",
            "",
            False,
            saved_record if saved_record and "Timestamp" in saved_record else None,
        )
        self.worker.record_added.emit(event_data)
