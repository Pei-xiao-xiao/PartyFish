"""
钓鱼服务
负责处理钓鱼的核心流程：抛竿、等待咬钩、收竿、记录渔获
"""

import time
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from src.config import cfg
from src.services.ocr_service import OCRService
from src.services.record_schema import infer_time_period_from_timestamp
from src.services.record_service import RecordService
from src.services.screenshot_service import ScreenshotService
from src.services.smart_pointer_debug_service import SmartPointerDebugService


class FishingService:
    """钓鱼服务类"""

<<<<<<< HEAD
=======
    SMART_PRESET_NAME = "智能钓鱼"
    SMART_DANGER_ANGLE = 34.0
    SMART_DANGER_GUARD_ANGLE = 6.0
    SMART_POINTER_MATCH_THRESHOLD = 0.35
    SMART_POINTER_LOST_LIMIT = 20
    SMART_REEL_TIMEOUT = 45.0
    SMART_POLL_INTERVAL_MS = 20
    SMART_POINTER_ROTATION_STEP = 3
    SMART_GAUGE_WHITE_MAX_SAT = 80
    SMART_GAUGE_WHITE_MIN_VALUE = 140
    SMART_POINTER_EDGE_LOW = 40
    SMART_POINTER_EDGE_HIGH = 120
    SMART_POINTER_MIN_RADIUS_RATIO = 1.15
    SMART_POINTER_MAX_RADIUS_RATIO = 1.95
    SMART_POINTER_HUE_LOW = 10
    SMART_POINTER_HUE_HIGH = 35
    SMART_POINTER_SAT_MIN = 100
    SMART_POINTER_VAL_MIN = 120
    SMART_POINTER_AREA_MIN_RATIO = 0.18
    SMART_POINTER_AREA_MAX_RATIO = 2.6
    SMART_POINTER_SHAPE_MAX_SCORE = 0.65
    SMART_POINTER_TEMPLATE_CACHE = {"scale": None, "templates": []}
    SMART_POINTER_FRAME_COUNT = 4
    SMART_RELEASE_TRIGGER_TOLERANCE = 1.5
    SMART_RUNTIME_LOG_INTERVAL = 0.25
    SMART_RUNTIME_LOG_ANGLE_DELTA = 1.5
    SMART_HOLD_REVERSE_JUMP_LIMIT = 4.0
    SMART_HOLD_FORWARD_DROP_LIMIT = 60.0
    SMART_NEAR_THRESHOLD_RELEASE_MARGIN = 3.0
    SMART_THRESHOLD_GUARD_RELEASE_TIME = 0.12
    SMART_DANGER_FAST_DROP_THRESHOLD = 4.0
    SMART_THRESHOLD_GUARD_ANGLE = 8.0
    SMART_THRESHOLD_FAST_DROP_THRESHOLD = 6.0
    SMART_INITIAL_RELEASE_ARM_MARGIN = 3.0
    SMART_INITIAL_RELEASE_SUPPRESS_TIME = 0.45
    SMART_INITIAL_THRESHOLD_LOG_SUPPRESS_TIME = 1.20
    SMART_POINTER_LOSS_RELEASE_COUNT = 2
    SMART_POINTER_LOSS_RELEASE_MARGIN = 3.0

>>>>>>> origin/fix/smart-fishing-popup-ocr
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
<<<<<<< HEAD
=======
        self._smart_gauge_geometry = None
        self._smart_gauge_frame_history = deque(maxlen=self.SMART_POINTER_FRAME_COUNT)
        self._last_reel_success_signal = None
>>>>>>> origin/fix/smart-fishing-popup-ocr

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

    def _build_single_release_decision(self, fish_name: str, quality: str) -> dict:
        """Build the single-release decision from catch recognition results."""
        if (
            cfg.global_settings.get("enable_fish_name_protection", False)
            and fish_name
            and cfg.is_fish_protected(fish_name, quality)
        ):
            self.worker.log_updated.emit(
                f"检测到保护鱼: {fish_name}({quality})，继续钓鱼"
            )
            return {
                "fish_name": fish_name,
                "quality": quality,
                "should_release": False,
                "is_protected": True,
            }

        if not fish_name:
            self.worker.log_updated.emit("未识别到鱼名，跳过单条放生")
            return {
                "fish_name": fish_name,
                "quality": quality,
                "should_release": False,
                "is_protected": False,
            }

        should_release = self.worker.release_service._should_release_by_rarity(
            fish_name, quality
        )

        return {
            "fish_name": fish_name,
            "quality": quality,
            "should_release": should_release,
            "is_protected": False,
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

<<<<<<< HEAD
=======
    def _is_smart_preset(self):
        return cfg.current_preset_name == self.SMART_PRESET_NAME

    @staticmethod
    def _average_extreme_point(points, axis_index, pick_min=True, tolerance=3):
        axis_values = points[:, axis_index]
        extreme_value = axis_values.min() if pick_min else axis_values.max()
        if pick_min:
            selected_points = points[axis_values <= (extreme_value + tolerance)]
        else:
            selected_points = points[axis_values >= (extreme_value - tolerance)]

        if len(selected_points) == 0:
            selected_points = points

        return (
            float(selected_points[:, 0].mean()),
            float(selected_points[:, 1].mean()),
        )

    @staticmethod
    def _compute_circle_center_from_points(point1, point2, point3):
        x1, y1 = point1
        x2, y2 = point2
        x3, y3 = point3

        denominator = 2.0 * ((x1 * (y2 - y3)) + (x2 * (y3 - y1)) + (x3 * (y1 - y2)))
        if abs(denominator) < 1e-6:
            return None

        x1_sq = (x1 * x1) + (y1 * y1)
        x2_sq = (x2 * x2) + (y2 * y2)
        x3_sq = (x3 * x3) + (y3 * y3)

        center_x = (
            (x1_sq * (y2 - y3)) + (x2_sq * (y3 - y1)) + (x3_sq * (y1 - y2))
        ) / denominator
        center_y = (
            (x1_sq * (x3 - x2)) + (x2_sq * (x1 - x3)) + (x3_sq * (x2 - x1))
        ) / denominator

        return (float(center_x), float(center_y))

    @classmethod
    def _extract_smart_gauge_arc_contour(cls, gauge_image):
        hsv_image = cv2.cvtColor(gauge_image, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(
            hsv_image,
            (0, 0, cls.SMART_GAUGE_WHITE_MIN_VALUE),
            (180, cls.SMART_GAUGE_WHITE_MAX_SAT, 255),
        )

        height, width = white_mask.shape[:2]
        white_mask[: max(1, int(height * 0.08)), :] = 0
        white_mask[max(1, int(height * 0.92)) :, :] = 0

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )

        best_contour = None
        best_score = -1
        min_area = max(60, int((width * height) * 0.01))
        min_width = max(20, int(width * 0.18))

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area:
                continue

            bound_x, bound_y, bound_w, bound_h = cv2.boundingRect(contour)
            if bound_w < min_width:
                continue
            if (bound_y + bound_h) < int(height * 0.35):
                continue

            contour_score = area + (bound_w * 2)
            if contour_score > best_score:
                best_score = contour_score
                best_contour = contour

        return best_contour

    @classmethod
    def detect_smart_gauge_geometry(cls, gauge_image, gauge_region):
        contour = cls._extract_smart_gauge_arc_contour(gauge_image)
        if contour is None:
            return None

        contour_points = contour.reshape(-1, 2)
        left_point = cls._average_extreme_point(contour_points, 0, pick_min=True)
        right_point = cls._average_extreme_point(contour_points, 0, pick_min=False)
        top_point = cls._average_extreme_point(contour_points, 1, pick_min=True)

        center = cls._compute_circle_center_from_points(
            left_point, right_point, top_point
        )
        if center is None:
            fallback_center, _ = cv2.minEnclosingCircle(contour)
            center = (float(fallback_center[0]), float(fallback_center[1]))

        radius = (math.dist(center, left_point) + math.dist(center, right_point)) / 2.0
        if radius <= 1:
            return None

        region_x, region_y, _, _ = gauge_region

        def _to_absolute(point):
            return (point[0] + region_x, point[1] + region_y)

        return {
            "center": _to_absolute(center),
            "left_point": _to_absolute(left_point),
            "right_point": _to_absolute(right_point),
            "top_point": _to_absolute(top_point),
            "radius": radius,
        }

    @staticmethod
    def _rotate_template_with_alpha(template, angle):
        height, width = template.shape[:2]
        center = (width / 2, height / 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        cos_value = abs(matrix[0, 0])
        sin_value = abs(matrix[0, 1])
        bound_w = max(1, int((height * sin_value) + (width * cos_value)))
        bound_h = max(1, int((height * cos_value) + (width * sin_value)))

        matrix[0, 2] += (bound_w / 2) - center[0]
        matrix[1, 2] += (bound_h / 2) - center[1]

        border_value = (0, 0, 0, 0) if template.shape[2] == 4 else (0, 0, 0)
        rotated = cv2.warpAffine(
            template,
            matrix,
            (bound_w, bound_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_value,
        )

        if rotated.ndim == 3 and rotated.shape[2] == 4:
            alpha = rotated[:, :, 3]
            non_zero = cv2.findNonZero(alpha)
            if non_zero is None:
                return None
            crop_x, crop_y, crop_w, crop_h = cv2.boundingRect(non_zero)
            return rotated[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]

        return rotated

    @classmethod
    def _extract_pointer_edges(cls, image):
        gray_image = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
        )
        return cv2.Canny(
            gray_image, cls.SMART_POINTER_EDGE_LOW, cls.SMART_POINTER_EDGE_HIGH
        )

    @classmethod
    def _build_pointer_position_mask(
        cls, result_shape, template_width, template_height, gauge_geometry, gauge_region
    ):
        center_x = gauge_geometry["center"][0] - gauge_region[0]
        center_y = gauge_geometry["center"][1] - gauge_region[1]

        x_coords = np.arange(result_shape[1], dtype=np.float32) + (template_width / 2.0)
        y_coords = np.arange(result_shape[0], dtype=np.float32) + (
            template_height / 2.0
        )
        grid_x, grid_y = np.meshgrid(x_coords, y_coords)

        delta_x = grid_x - center_x
        delta_y = grid_y - center_y
        distances = np.sqrt((delta_x * delta_x) + (delta_y * delta_y))

        angles = np.degrees(np.arctan2(center_y - grid_y, delta_x))
        angles[angles < 0] += 360.0

        min_radius = gauge_geometry["radius"] * cls.SMART_POINTER_MIN_RADIUS_RATIO
        max_radius = gauge_geometry["radius"] * cls.SMART_POINTER_MAX_RADIUS_RATIO

        return (
            (distances >= min_radius)
            & (distances <= max_radius)
            & (angles >= 0.0)
            & (angles <= 180.0)
        )

    @classmethod
    def _get_smart_pointer_templates(cls, vision_obj):
        vision_obj._ensure_loaded()

        cached_scale = cls.SMART_POINTER_TEMPLATE_CACHE.get("scale")
        cached_templates = cls.SMART_POINTER_TEMPLATE_CACHE.get("templates", [])
        if cached_scale == cfg.scale and cached_templates:
            return cached_templates

        raw_template = vision_obj.raw_templates.get("pointer")
        if raw_template is None:
            raise ValueError("Template 'pointer' not found.")

        if cfg.scale != 1.0:
            scaled_width = max(1, int(raw_template.shape[1] * cfg.scale))
            scaled_height = max(1, int(raw_template.shape[0] * cfg.scale))
            interpolation = cv2.INTER_LINEAR if cfg.scale > 1.0 else cv2.INTER_AREA
            base_template = cv2.resize(
                raw_template, (scaled_width, scaled_height), interpolation=interpolation
            )
        else:
            base_template = raw_template.copy()

        rotated_templates = []
        for angle in range(0, 181, cls.SMART_POINTER_ROTATION_STEP):
            rotated_template = cls._rotate_template_with_alpha(base_template, angle)
            if rotated_template is None:
                continue
            template_mask = None
            template_image = rotated_template
            if rotated_template.ndim == 3 and rotated_template.shape[2] == 4:
                template_mask = rotated_template[:, :, 3]
                template_image = rotated_template[:, :, :3]

            template_image = cls._extract_pointer_edges(template_image)
            if template_mask is not None:
                template_mask = cv2.threshold(template_mask, 1, 255, cv2.THRESH_BINARY)[
                    1
                ]

            rotated_templates.append((template_image, template_mask))

        cls.SMART_POINTER_TEMPLATE_CACHE = {
            "scale": cfg.scale,
            "templates": rotated_templates,
        }
        return rotated_templates

    @classmethod
    def _get_pointer_shape_reference(cls, vision_obj):
        vision_obj._ensure_loaded()
        raw_template = vision_obj.raw_templates.get("pointer")
        if raw_template is None:
            return None

        if cfg.scale != 1.0:
            scaled_width = max(1, int(raw_template.shape[1] * cfg.scale))
            scaled_height = max(1, int(raw_template.shape[0] * cfg.scale))
            interpolation = cv2.INTER_LINEAR if cfg.scale > 1.0 else cv2.INTER_AREA
            template_image = cv2.resize(
                raw_template, (scaled_width, scaled_height), interpolation=interpolation
            )
        else:
            template_image = raw_template.copy()

        if template_image.ndim != 3 or template_image.shape[2] != 4:
            return None

        template_mask = cv2.threshold(
            template_image[:, :, 3], 1, 255, cv2.THRESH_BINARY
        )[1]
        contours, _ = cv2.findContours(
            template_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None

        reference_contour = max(contours, key=cv2.contourArea)
        return {
            "contour": reference_contour,
            "area": cv2.contourArea(reference_contour),
        }

    @classmethod
    def _detect_smart_pointer_by_color(
        cls, vision_obj, gauge_image, gauge_region, gauge_geometry
    ):
        hsv_image = cv2.cvtColor(gauge_image, cv2.COLOR_BGR2HSV)
        pointer_mask = cv2.inRange(
            hsv_image,
            (
                cls.SMART_POINTER_HUE_LOW,
                cls.SMART_POINTER_SAT_MIN,
                cls.SMART_POINTER_VAL_MIN,
            ),
            (cls.SMART_POINTER_HUE_HIGH, 255, 255),
        )

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        pointer_mask = cv2.morphologyEx(pointer_mask, cv2.MORPH_OPEN, kernel)
        pointer_mask = cv2.morphologyEx(pointer_mask, cv2.MORPH_CLOSE, kernel)

        reference = cls._get_pointer_shape_reference(vision_obj)
        if reference is None:
            return None

        expected_area = max(reference["area"], 1.0)
        contours, _ = cv2.findContours(
            pointer_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        best_candidate = None
        best_score = -1.0
        center_x = gauge_geometry["center"][0] - gauge_region[0]
        center_y = gauge_geometry["center"][1] - gauge_region[1]
        min_radius = gauge_geometry["radius"] * cls.SMART_POINTER_MIN_RADIUS_RATIO
        max_radius = gauge_geometry["radius"] * cls.SMART_POINTER_MAX_RADIUS_RATIO

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < expected_area * cls.SMART_POINTER_AREA_MIN_RATIO:
                continue
            if area > expected_area * cls.SMART_POINTER_AREA_MAX_RATIO:
                continue

            moments = cv2.moments(contour)
            if abs(moments["m00"]) < 1e-6:
                continue

            local_x = moments["m10"] / moments["m00"]
            local_y = moments["m01"] / moments["m00"]
            distance = math.dist((center_x, center_y), (local_x, local_y))
            if not (min_radius <= distance <= max_radius):
                continue

            angle = math.degrees(math.atan2(center_y - local_y, local_x - center_x))
            if angle < 0:
                angle += 360.0
            if not (0.0 <= angle <= 180.0):
                continue

            shape_score = cv2.matchShapes(
                contour, reference["contour"], cv2.CONTOURS_MATCH_I1, 0.0
            )
            if shape_score > cls.SMART_POINTER_SHAPE_MAX_SCORE:
                continue

            area_similarity = 1.0 - min(abs(area - expected_area) / expected_area, 1.0)
            candidate_score = (1.0 / (1.0 + shape_score)) + area_similarity
            if candidate_score <= best_score:
                continue

            best_score = candidate_score
            best_candidate = {
                "score": candidate_score / 2.0,
                "shape_score": shape_score,
                "center": (
                    gauge_region[0] + local_x,
                    gauge_region[1] + local_y,
                ),
                "method": "color",
            }

        return best_candidate

    @classmethod
    def _match_smart_pointer(
        cls, vision_obj, gauge_image, gauge_region, gauge_geometry
    ):
        best_score = -1.0
        best_center = None
        edge_gauge_image = cls._extract_pointer_edges(gauge_image)

        for template_image, template_mask in cls._get_smart_pointer_templates(
            vision_obj
        ):
            template_height, template_width = template_image.shape[:2]
            image_height, image_width = edge_gauge_image.shape[:2]
            if template_height > image_height or template_width > image_width:
                continue

            if template_mask is not None:
                result = cv2.matchTemplate(
                    edge_gauge_image,
                    template_image,
                    cv2.TM_CCORR_NORMED,
                    mask=template_mask,
                )
            else:
                result = cv2.matchTemplate(
                    edge_gauge_image, template_image, cv2.TM_CCOEFF_NORMED
                )

            valid_mask = cls._build_pointer_position_mask(
                result.shape,
                template_width,
                template_height,
                gauge_geometry,
                gauge_region,
            )
            if not np.any(valid_mask):
                continue

            result = result.copy()
            result[~valid_mask] = -1.0

            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val <= best_score:
                continue

            best_score = max_val
            best_center = (
                max_loc[0] + (template_width / 2),
                max_loc[1] + (template_height / 2),
            )

        if best_score < cls.SMART_POINTER_MATCH_THRESHOLD or best_center is None:
            return None

        return {"score": best_score, "center": best_center}

    @classmethod
    def detect_smart_pointer(
        cls, vision_obj, gauge_image, gauge_region, gauge_geometry=None
    ):
        if gauge_geometry is None:
            gauge_geometry = cls.detect_smart_gauge_geometry(gauge_image, gauge_region)
        if gauge_geometry is None:
            return None

        color_result = cls._detect_smart_pointer_by_color(
            vision_obj, gauge_image, gauge_region, gauge_geometry
        )
        if color_result is not None:
            return color_result

        match_result = cls._match_smart_pointer(
            vision_obj, gauge_image, gauge_region, gauge_geometry
        )
        if match_result is None:
            return None

        return {
            "score": match_result["score"],
            "center": (
                gauge_region[0] + match_result["center"][0],
                gauge_region[1] + match_result["center"][1],
            ),
            "method": "template",
        }

    @classmethod
    def _compute_smart_release_angle(cls, release_angle_offset):
        configured_release_angle = cls.SMART_DANGER_ANGLE + max(
            0.0, float(release_angle_offset)
        )
        return min(configured_release_angle, 170.0)

    @classmethod
    def _compute_smart_release_duration(cls, smart_release_time, release_reason):
        smart_release_time = max(0.0, float(smart_release_time))
        if release_reason in {"threshold_guard", "threshold_loss_guard"}:
            return min(
                smart_release_time,
                float(cls.SMART_THRESHOLD_GUARD_RELEASE_TIME),
            )
        return smart_release_time

    @classmethod
    def _should_arm_initial_threshold_release(
        cls,
        current_angle,
        configured_release_angle,
        hold_started_at,
        now=None,
        arm_margin=None,
        suppress_time=None,
    ):
        if hold_started_at is None:
            return True

        now = time.time() if now is None else float(now)
        arm_margin = (
            cls.SMART_INITIAL_RELEASE_ARM_MARGIN
            if arm_margin is None
            else max(0.0, float(arm_margin))
        )
        suppress_time = (
            cls.SMART_INITIAL_RELEASE_SUPPRESS_TIME
            if suppress_time is None
            else max(0.0, float(suppress_time))
        )
        if now - float(hold_started_at) >= suppress_time:
            return True
        if current_angle is None:
            return False
        return float(current_angle) >= float(configured_release_angle) + arm_margin

    @classmethod
    def _should_log_initial_threshold_release(
        cls,
        reel_started_at,
        now=None,
        suppress_time=None,
    ):
        if reel_started_at is None:
            return True

        now = time.time() if now is None else float(now)
        suppress_time = (
            cls.SMART_INITIAL_THRESHOLD_LOG_SUPPRESS_TIME
            if suppress_time is None
            else max(0.0, float(suppress_time))
        )
        return (now - float(reel_started_at)) >= suppress_time

    @classmethod
    def _should_release_smart_pointer(
        cls,
        current_angle,
        configured_release_angle,
        danger_release_angle=None,
        release_tolerance=None,
        suppressed_reverse_jump=False,
        near_threshold_release_margin=None,
        previous_angle=None,
        danger_guard_angle=None,
        fast_drop_threshold=None,
        threshold_guard_angle=None,
        threshold_fast_drop_threshold=None,
    ):
        if current_angle is None:
            return None

        danger_release_angle = (
            cls.SMART_DANGER_ANGLE
            if danger_release_angle is None
            else float(danger_release_angle)
        )
        release_tolerance = (
            cls.SMART_RELEASE_TRIGGER_TOLERANCE
            if release_tolerance is None
            else max(0.0, float(release_tolerance))
        )
        near_threshold_release_margin = (
            cls.SMART_NEAR_THRESHOLD_RELEASE_MARGIN
            if near_threshold_release_margin is None
            else max(0.0, float(near_threshold_release_margin))
        )
        danger_guard_angle = (
            cls.SMART_DANGER_GUARD_ANGLE
            if danger_guard_angle is None
            else max(0.0, float(danger_guard_angle))
        )
        fast_drop_threshold = (
            cls.SMART_DANGER_FAST_DROP_THRESHOLD
            if fast_drop_threshold is None
            else max(0.0, float(fast_drop_threshold))
        )
        threshold_guard_angle = (
            cls.SMART_THRESHOLD_GUARD_ANGLE
            if threshold_guard_angle is None
            else max(0.0, float(threshold_guard_angle))
        )
        threshold_fast_drop_threshold = (
            cls.SMART_THRESHOLD_FAST_DROP_THRESHOLD
            if threshold_fast_drop_threshold is None
            else max(0.0, float(threshold_fast_drop_threshold))
        )
        current_angle = float(current_angle)
        configured_release_angle = float(configured_release_angle)
        previous_angle = None if previous_angle is None else float(previous_angle)

        if current_angle <= danger_release_angle:
            return "danger"
        if (
            previous_angle is not None
            and (previous_angle - current_angle) >= fast_drop_threshold
            and current_angle <= danger_release_angle + danger_guard_angle
        ):
            return "danger_guard"
        if (
            previous_angle is not None
            and configured_release_angle > danger_release_angle
            and (previous_angle - current_angle) >= threshold_fast_drop_threshold
            and current_angle <= configured_release_angle + threshold_guard_angle
        ):
            return "threshold_fast_guard"
        if current_angle <= configured_release_angle + release_tolerance:
            return "threshold"
        if (
            suppressed_reverse_jump
            and current_angle
            <= configured_release_angle + near_threshold_release_margin
        ):
            return "threshold_guard"
        return None

    @classmethod
    def _should_release_on_pointer_loss(
        cls,
        last_angle,
        configured_release_angle,
        pointer_missing_count,
        missing_release_count=None,
        missing_release_margin=None,
    ):
        if last_angle is None:
            return None

        missing_release_count = (
            cls.SMART_POINTER_LOSS_RELEASE_COUNT
            if missing_release_count is None
            else max(1, int(missing_release_count))
        )
        missing_release_margin = (
            cls.SMART_POINTER_LOSS_RELEASE_MARGIN
            if missing_release_margin is None
            else max(0.0, float(missing_release_margin))
        )
        if int(pointer_missing_count) < missing_release_count:
            return None

        last_angle = float(last_angle)
        configured_release_angle = float(configured_release_angle)
        if last_angle <= configured_release_angle + missing_release_margin:
            return "threshold_loss_guard"
        return None

    @classmethod
    def _build_smart_pointer_runtime_log(
        cls,
        pointer_state,
        configured_release_angle,
        danger_release_angle,
        release_reason=None,
    ):
        if pointer_state is None:
            return (
                "智能收线检测: angle=None "
                f"threshold={configured_release_angle:.1f} "
                f"danger={danger_release_angle:.1f}"
            )

        source = pointer_state.get("source", "unknown")
        score = float(pointer_state.get("score", 0.0) or 0.0)
        raw_angle = pointer_state.get("raw_angle")
        sources = pointer_state.get("sources") or []
        filter_reason = pointer_state.get("filter_reason")
        message = (
            "智能收线检测: "
            f"angle={float(pointer_state['angle']):.1f} "
            f"threshold={float(configured_release_angle):.1f} "
            f"danger={float(danger_release_angle):.1f} "
            f"source={source} "
            f"score={score:.2f}"
        )
        if raw_angle is not None:
            message += f" raw={float(raw_angle):.1f}"
        if sources:
            message += f" sources={'+'.join(sources)}"
        if filter_reason:
            message += f" filtered={filter_reason}"
        if release_reason is not None:
            message += f" release={release_reason}"
        return message

    @classmethod
    def _apply_hold_direction_filter(
        cls,
        current_angle,
        previous_angle,
        reverse_jump_limit=None,
        forward_drop_limit=None,
    ):
        if current_angle is None:
            return None, None
        if previous_angle is None:
            return float(current_angle), None

        reverse_jump_limit = (
            cls.SMART_HOLD_REVERSE_JUMP_LIMIT
            if reverse_jump_limit is None
            else max(0.0, float(reverse_jump_limit))
        )
        forward_drop_limit = (
            cls.SMART_HOLD_FORWARD_DROP_LIMIT
            if forward_drop_limit is None
            else max(0.0, float(forward_drop_limit))
        )
        current_angle = float(current_angle)
        previous_angle = float(previous_angle)

        if current_angle > previous_angle + reverse_jump_limit:
            return previous_angle, "reverse_jump"
        if current_angle < previous_angle - forward_drop_limit:
            return previous_angle, "forward_jump"
        return current_angle, None

    @staticmethod
    def _to_absolute_gauge_point(gauge_region, local_point):
        if local_point is None:
            return None
        return (
            float(gauge_region[0] + local_point[0]),
            float(gauge_region[1] + local_point[1]),
        )

    @classmethod
    def _resolve_smart_pointer_state(
        cls,
        gauge_region,
        legacy_state=None,
        debug_result=None,
        motion_result=None,
    ):
        legacy_candidate = None
        if legacy_state is not None and legacy_state.get("angle") is not None:
            legacy_pointer = legacy_state.get("pointer")
            legacy_candidate = {
                "source": (
                    "legacy_color"
                    if legacy_state.get("method") == "color"
                    else "legacy_template"
                ),
                "angle": legacy_state["angle"],
                "score": legacy_state.get("score", 0.0),
                "point": (
                    (
                        float(legacy_pointer[0] - gauge_region[0]),
                        float(legacy_pointer[1] - gauge_region[1]),
                    )
                    if legacy_pointer is not None
                    else None
                ),
            }

        template_candidates = []
        debug_best = None
        if debug_result is not None:
            debug_best = debug_result.get("best_candidate")
            for candidate in debug_result.get("candidates", []):
                template_candidates.append(
                    {
                        "source": "template",
                        "angle": candidate["angle"],
                        "score": candidate["score"],
                        "point": candidate.get("tip_point"),
                    }
                )

        motion_best = None
        motion_candidate = None
        if motion_result is not None:
            motion_best = motion_result.get("best_candidate")
        if motion_best is not None:
            motion_candidate = {
                "source": "motion",
                "angle": motion_best["angle"],
                "score": motion_best["score"],
                "point": motion_best.get("tip_point"),
            }

        fused_result = SmartPointerDebugService.fuse_pointer_candidates(
            legacy_candidate=legacy_candidate,
            template_candidates=template_candidates,
            motion_candidate=motion_candidate,
        )

        if fused_result is not None and fused_result.get("angle") is not None:
            return {
                "angle": fused_result["angle"],
                "score": fused_result.get("score", 0.0),
                "pointer": cls._to_absolute_gauge_point(
                    gauge_region, fused_result.get("point")
                )
                or (legacy_state or {}).get("pointer"),
                "source": "fused",
                "sources": fused_result.get("sources", []),
            }

        if motion_best is not None:
            return {
                "angle": motion_best["angle"],
                "score": motion_best.get("score", 0.0),
                "pointer": cls._to_absolute_gauge_point(
                    gauge_region, motion_best.get("tip_point")
                ),
                "source": "motion",
                "sources": ["motion"],
            }

        if debug_best is not None:
            return {
                "angle": debug_best["angle"],
                "score": debug_best.get("score", 0.0),
                "pointer": cls._to_absolute_gauge_point(
                    gauge_region, debug_best.get("tip_point")
                ),
                "source": "template",
                "sources": ["template"],
            }

        if legacy_state is not None and legacy_state.get("angle") is not None:
            return {
                "angle": legacy_state["angle"],
                "score": legacy_state.get("score", 0.0),
                "pointer": legacy_state.get("pointer"),
                "source": legacy_state.get("method", "legacy"),
                "sources": [legacy_state.get("method", "legacy")],
            }

        return None

    def _capture_smart_gauge_frames(self, gauge_region, initial_frame):
        self._smart_gauge_frame_history.append(initial_frame.copy())
        return list(self._smart_gauge_frame_history)

    @staticmethod
    def _detect_reel_in_success_signal(vision, star_region, shangyu_region):
        if vision.find_template("star_grayscale", region=star_region, threshold=0.7):
            return "star"

        if shangyu_region:
            for key in ["shangyu_grayscale", "shoubing_shangyu_grayscale"]:
                if vision.find_template(key, region=shangyu_region, threshold=0.8):
                    return "popup"

        return None

    @classmethod
    def _has_reel_in_success_signal(cls, vision, star_region, shangyu_region):
        return (
            cls._detect_reel_in_success_signal(
                vision=vision,
                star_region=star_region,
                shangyu_region=shangyu_region,
            )
            is not None
        )

    def _get_smart_pointer_state(self):
        gauge_region = cfg.get_rect("smart_tension_gauge")
        gauge_image = self.worker.vision.screenshot(gauge_region)
        if gauge_image is None or getattr(gauge_image, "size", 0) == 0:
            return None

        if self._smart_gauge_geometry is None:
            self._smart_gauge_geometry = self.detect_smart_gauge_geometry(
                gauge_image, gauge_region
            )
        if self._smart_gauge_geometry is None:
            return None

        gauge_center_x, gauge_center_y = self._smart_gauge_geometry["center"]
        gauge_radius = float(self._smart_gauge_geometry["radius"])
        local_center = (
            gauge_center_x - gauge_region[0],
            gauge_center_y - gauge_region[1],
        )
        gauge_frames = self._capture_smart_gauge_frames(gauge_region, gauge_image)

        legacy_match_result = self.detect_smart_pointer(
            self.worker.vision,
            gauge_image,
            gauge_region,
            self._smart_gauge_geometry,
        )
        legacy_state = None
        if legacy_match_result is not None:
            pointer_x, pointer_y = legacy_match_result["center"]
            angle = math.degrees(
                math.atan2(gauge_center_y - pointer_y, pointer_x - gauge_center_x)
            )
            if angle < 0:
                angle += 360.0
            legacy_state = {
                "angle": angle,
                "score": legacy_match_result.get("score", 0.0),
                "pointer": (pointer_x, pointer_y),
                "method": legacy_match_result.get("method", "template"),
            }

        debug_result = None
        try:
            self.worker.vision._ensure_loaded()
            pointer_template = self.worker.vision.raw_templates.get("pointer")
            if pointer_template is not None:
                debug_result = SmartPointerDebugService.analyze_pointer(
                    gauge_image,
                    pointer_template,
                    local_center,
                    gauge_radius,
                )
        except Exception:
            debug_result = None

        motion_result = None
        try:
            motion_result = SmartPointerDebugService.analyze_motion_pointer(
                gauge_frames,
                local_center,
                gauge_radius,
            )
        except Exception:
            motion_result = None

        return self._resolve_smart_pointer_state(
            gauge_region=gauge_region,
            legacy_state=legacy_state,
            debug_result=debug_result,
            motion_result=motion_result,
        )

    def _smart_reel_in(self):
        star_region = cfg.get_rect("reel_in_star")
        shangyu_region = cfg.get_rect("shangyu")
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
        danger_release_angle = self.SMART_DANGER_ANGLE
        configured_release_angle = self._compute_smart_release_angle(
            getattr(cfg, "smart_release_angle", 18.0)
        )
        smart_release_time = max(0.0, float(getattr(cfg, "smart_release_time", 0.8)))

        pointer_missing_count = 0
        is_holding = True
        release_until = 0.0
        start_time = time.time()
        hold_started_at = start_time
        hold_release_armed = False
        last_pointer_log_time = 0.0
        last_logged_angle = None
        hold_session_angle = None
        self._smart_gauge_geometry = None
        self._smart_gauge_frame_history.clear()
        self._last_reel_success_signal = None

        self.worker.log_updated.emit("智能收线中...")

        try:
            self.worker.inputs.press_mouse_button()

            while time.time() - start_time < self.SMART_REEL_TIMEOUT:
                if not self.worker.running or self.worker.paused:
                    return False

                success_signal = self._detect_reel_in_success_signal(
                    vision=self.worker.vision,
                    star_region=star_region,
                    shangyu_region=shangyu_region,
                )
                if success_signal is not None:
                    self._last_reel_success_signal = success_signal
                    self.worker.log_updated.emit("检测到收线成功信号，判定为上鱼成功。")
                    return True

                for key in ["F1_grayscale", "F2_grayscale"]:
                    if self.worker.vision.find_template(
                        key, region=cast_rod_region, threshold=0.8
                    ) or self.worker.vision.find_template(
                        key, region=cast_rod_ice_region, threshold=0.8
                    ):
                        self.worker.log_updated.emit(
                            "未检测到星星，抛竿提示出现，判定为鱼跑了！"
                        )
                        self.worker.status_updated.emit("鱼跑了")
                        self._record_event("鱼跑了")
                        return False

                if not is_holding:
                    if time.time() >= release_until:
                        self.worker.inputs.press_mouse_button()
                        is_holding = True
                        hold_started_at = time.time()
                        hold_release_armed = False
                        hold_session_angle = None
                        pointer_missing_count = 0
                    self.worker.msleep(self.SMART_POLL_INTERVAL_MS)
                    continue

                pointer_state = self._get_smart_pointer_state()
                if pointer_state is None:
                    pointer_missing_count += 1
                    release_reason = self._should_release_on_pointer_loss(
                        last_angle=hold_session_angle,
                        configured_release_angle=configured_release_angle,
                        pointer_missing_count=pointer_missing_count,
                    )
                    if is_holding and release_reason is not None:
                        release_duration = self._compute_smart_release_duration(
                            smart_release_time=smart_release_time,
                            release_reason=release_reason,
                        )
                        self.worker.inputs.release_mouse_button()
                        is_holding = False
                        hold_session_angle = None
                        pointer_missing_count = 0
                        release_until = time.time() + release_duration
                        self.worker.msleep(self.SMART_POLL_INTERVAL_MS)
                        continue
                    if pointer_missing_count >= self.SMART_POINTER_LOST_LIMIT:
                        return False
                    self.worker.msleep(self.SMART_POLL_INTERVAL_MS)
                    continue

                pointer_missing_count = 0
                raw_angle = pointer_state["angle"]
                previous_hold_angle = hold_session_angle
                current_angle, filter_reason = self._apply_hold_direction_filter(
                    current_angle=raw_angle,
                    previous_angle=previous_hold_angle,
                )
                pointer_state = dict(pointer_state)
                pointer_state["raw_angle"] = raw_angle
                pointer_state["angle"] = current_angle
                if filter_reason is not None:
                    pointer_state["filter_reason"] = filter_reason
                hold_session_angle = current_angle

                release_reason = self._should_release_smart_pointer(
                    current_angle=current_angle,
                    configured_release_angle=configured_release_angle,
                    danger_release_angle=danger_release_angle,
                    suppressed_reverse_jump=(filter_reason == "reverse_jump"),
                    previous_angle=previous_hold_angle,
                )
                now = time.time()
                if not hold_release_armed:
                    hold_release_armed = self._should_arm_initial_threshold_release(
                        current_angle=current_angle,
                        configured_release_angle=configured_release_angle,
                        hold_started_at=hold_started_at,
                        now=now,
                    )
                    if not hold_release_armed and release_reason is not None:
                        release_reason = None
                last_pointer_log_time = now
                last_logged_angle = current_angle

                release_duration = self._compute_smart_release_duration(
                    smart_release_time=smart_release_time,
                    release_reason=release_reason,
                )
                if is_holding and release_reason == "danger":
                    self.worker.log_updated.emit("智能收线：进入红色危险区，立即松手")
                    self.worker.inputs.release_mouse_button()
                    is_holding = False
                    hold_session_angle = None
                    release_until = time.time() + release_duration
                elif is_holding and release_reason == "danger_guard":
                    self.worker.log_updated.emit("智能收线：快速逼近红区，提前松手")
                    self.worker.inputs.release_mouse_button()
                    is_holding = False
                    hold_session_angle = None
                    release_until = time.time() + release_duration
                elif is_holding and release_reason == "threshold_fast_guard":
                    self.worker.inputs.release_mouse_button()
                    is_holding = False
                    hold_session_angle = None
                    release_until = time.time() + release_duration
                elif is_holding and release_reason == "threshold":
                    if self._should_log_initial_threshold_release(
                        reel_started_at=start_time,
                        now=now,
                    ):
                        self.worker.log_updated.emit("智能收线：到达配置阈值，松手")
                    self.worker.inputs.release_mouse_button()
                    is_holding = False
                    hold_session_angle = None
                    release_until = time.time() + release_duration
                elif is_holding and release_reason == "threshold_guard":
                    self.worker.inputs.release_mouse_button()
                    is_holding = False
                    hold_session_angle = None
                    release_until = time.time() + release_duration

                self.worker.msleep(self.SMART_POLL_INTERVAL_MS)
        finally:
            self.worker.inputs.ensure_mouse_up()

        return False

>>>>>>> origin/fix/smart-fishing-popup-ocr
    def reel_in(self):
        """收竿阶段"""
        if not self.worker.running:
            return False
        self._last_reel_success_signal = None
        self.worker.status_updated.emit("上鱼了! 开始收竿!")
        self.worker.log_updated.emit("进入收放线循环...")

        star_region = cfg.get_rect("reel_in_star")
        shangyu_region = cfg.get_rect("shangyu")

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

            success_signal = self._detect_reel_in_success_signal(
                vision=self.worker.vision,
                star_region=star_region,
                shangyu_region=shangyu_region,
            )
            if success_signal is not None:
                self._last_reel_success_signal = success_signal
                self.worker.log_updated.emit("检测到收线成功信号，判定为上鱼成功。")
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
            return None

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

            return None

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
            return None

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

        single_release_decision = None
        if release_mode == "single":
            single_release_decision = self._build_single_release_decision(
                fish_name, quality
            )

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

        return single_release_decision

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
            self._last_reel_success_signal = None
            return []

        success_signal = self._last_reel_success_signal
        settle_delay = 0.35 if success_signal == "popup" else 0.15
        frame_count = 3 if success_signal == "popup" else 2
        frame_interval_ms = 100 if success_signal == "popup" else 80

        self.worker.smart_sleep(settle_delay)

        snapshots = []
        for index in range(frame_count):
            frame = self.worker.vision.screenshot(ocr_area)
            if frame is not None:
                snapshots.append(frame)
            if index < frame_count - 1:
                self.worker.msleep(frame_interval_ms)

        self._last_reel_success_signal = None
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
            return None

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
            return None

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
