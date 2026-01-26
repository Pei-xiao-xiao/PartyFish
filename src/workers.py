import cv2
import re
import csv
import time
import os
import difflib
from pathlib import Path
import mss
from PySide6.QtCore import QThread, Signal, Slot
from rapidocr_onnxruntime import RapidOCR
from src.vision import vision
from src.inputs import InputController
from src.config import cfg


class FishingWorker(QThread):
    """
    自动化钓鱼逻辑的核心线程
    """

    log_updated = Signal(str)
    status_updated = Signal(str)
    record_added = Signal(dict)
    sale_recorded = Signal(int)  # Signal emitting the amount sold
    sound_alert_requested = Signal(str)

    def __init__(self):
        super().__init__()
        # 限制 OCR 线程数为 1，显著降低 CPU 占用
        self.ocr = RapidOCR(intra_op_num_threads=1, inter_op_num_threads=1)
        self.running = False
        self.paused = True  # Start in a paused state
        self.inputs = InputController()
        self.vision = vision
        self.state = "finding_prompt"  # 初始状态
        # 确保截图目录存在
        screenshots_dir = cfg._get_base_path() / "screenshots"
        if not screenshots_dir.exists():
            screenshots_dir.mkdir(parents=True)

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
            self.msleep(100)

        if not self.running:
            return

        # 按 F2 后才激活游戏窗口，确保按键能发送到游戏（解决副屏鼠标焦点问题）
        self.log_updated.emit("开始自动化钓鱼...")
        if cfg.activate_game_window():
            self.log_updated.emit("已激活游戏窗口")

        while self.running:
            while self.paused:
                if not self.running:
                    break

                self.msleep(100)  # 暂停时避免CPU空转

            if not self.running:
                break

            try:
                if self.state == "finding_prompt":
                    if self._cast_rod():
                        self.state = "waiting_for_bite"

                elif self.state == "waiting_for_bite":
                    if not self._wait_for_bite():
                        # 如果等待超时或失败，重置状态
                        self.state = "finding_prompt"
                    else:
                        self.state = "reeling_in"

                elif self.state == "reeling_in":
                    reel_in_finished = self._reel_in()
                    if reel_in_finished:
                        should_release = self._record_catch()
                        self.log_updated.emit("收起渔获, 准备下一轮。")

                        # 改进的关闭弹窗逻辑：循环检测直到弹窗消失
                        max_close_attempts = 10
                        shangyu_region = cfg.get_rect("shangyu")
                        popup_closed = False

                        for close_attempt in range(max_close_attempts):
                            if not self.running or self.paused:
                                break

                            # 检查"收起"按钮是否还在（弹窗是否还存在）
                            if not self.vision.find_template(
                                "shangyu_grayscale",
                                region=shangyu_region,
                                threshold=0.8,
                            ):
                                # 弹窗已消失，成功关闭
                                if close_attempt > 0:  # 只有尝试过点击才输出日志
                                    self.log_updated.emit("渔获弹窗已关闭")
                                popup_closed = True
                                break

                            # 弹窗还在，点击关闭
                            self.msleep(100)
                            self.inputs.left_click()
                            self.smart_sleep(0.3)

                        if not popup_closed and (self.running and not self.paused):
                            # 达到最大尝试次数仍未关闭
                            self.log_updated.emit(
                                "警告: 渔获弹窗可能未完全关闭，继续下一轮"
                            )

                        # 在关闭弹窗后、重新抛竿前执行单条放生
                        if should_release and popup_closed:
                            self._execute_single_release()

                    # 无论成功与否，都重置到初始状态
                    self.state = "finding_prompt"

            except Exception as e:
                self.log_updated.emit(f"发生错误: {e}")
                self.pause()
                self.status_updated.emit(f"错误: {e}, 已暂停")

            # 循环间隔，等待指定时间后再进行下一轮
            self.smart_sleep(cfg.cycle_interval)

        self.log_updated.emit("自动化钓鱼已停止。")

    def _cast_rod(self):
        """
        抛竿阶段
        """
        if not self.running:
            return False
        self.status_updated.emit("抛竿阶段")
        self.log_updated.emit("正在寻找抛竿提示...")

        start_time = time.time()
        timeout = 10
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")

        while time.time() - start_time < timeout:
            if not self.running:
                return False
            while self.paused:
                self.msleep(100)

            for key in ["F1_grayscale", "F2_grayscale"]:
                # 同时检测原有的区域和新的冰钓区域
                found_region = None
                if self.vision.find_template(
                    key, region=cast_rod_region, threshold=0.8
                ):
                    found_region = cast_rod_region
                elif self.vision.find_template(
                    key, region=cast_rod_ice_region, threshold=0.8
                ):
                    found_region = cast_rod_ice_region

                if found_region:
                    self.log_updated.emit(f"检测到抛竿提示, 准备抛竿。")

                    # 抛竿前强制获取初始鱼饵数量（用户要求）
                    initial_bait_before_cast = None
                    for _ in range(10):  # 尝试 10 次（约 2 秒）
                        if not self.running:
                            return False
                        while self.paused:
                            self.msleep(100)

                        initial_bait_before_cast = self.vision.get_bait_amount()
                        if initial_bait_before_cast is not None:
                            self.log_updated.emit(
                                f"[调试] 抛竿前鱼饵数量: {initial_bait_before_cast}"
                            )
                            break
                        self.msleep(200)

                    if initial_bait_before_cast is None:
                        self.log_updated.emit("错误: 抛竿前无法获取鱼饵数量。")
                        if cfg.global_settings.get("enable_sound_alert", False):
                            self.sound_alert_requested.emit(
                                "no_bait"
                            )  # 复用 no_bait 音效
                        self.pause(reason="无法识别鱼饵数量")
                        return False

                    self.inputs.hold_mouse(cfg.cast_time)

                    # -- 状态转换验证（同时检测鱼饵变化） --
                    self.smart_sleep(1.0)  # 等待UI响应

                    verification_start_time = time.time()
                    verification_timeout = 3  # 3秒验证超时
                    wait_bite_region = cfg.get_rect("wait_bite")

                    # 诊断变量
                    last_cast_icon_gone = False
                    last_wait_icon_appeared = False
                    verification_check_count = 0
                    cast_icon_ever_gone = False  # 抛竿图标是否曾经消失过

                    while time.time() - verification_start_time < verification_timeout:
                        # 检测图标状态
                        cast_icon_gone = not self.vision.find_template(
                            key, region=found_region, threshold=0.8
                        )
                        wait_icon_appeared = self.vision.find_template(
                            key, region=wait_bite_region, threshold=0.8
                        )

                        # 更新诊断变量
                        last_cast_icon_gone = cast_icon_gone
                        last_wait_icon_appeared = wait_icon_appeared
                        verification_check_count += 1

                        if cast_icon_gone:
                            cast_icon_ever_gone = True

                        # 成功条件1: 抛竿图标消失 AND 等待图标出现（正常状态转换）
                        if cast_icon_gone and wait_icon_appeared:
                            # 保存初始鱼饵数量供 _wait_for_bite 使用
                            self._initial_bait_for_bite = initial_bait_before_cast
                            self.log_updated.emit("已抛竿, 进入等待咬钩状态。")
                            return True

                        self.msleep(200)

                    # 如果超时，输出详细诊断信息
                    self.log_updated.emit(
                        f"[诊断] 抛竿验证超时。检测次数: {verification_check_count}"
                    )
                    self.log_updated.emit(
                        f"[诊断] 最后状态 - 抛竿图标已消失: {last_cast_icon_gone}, 等待图标已出现: {last_wait_icon_appeared}"
                    )

                    # 最终鱼饵检查：如果鱼饵比抛竿前少了，说明有鱼咬钩后跑掉了
                    # 注意: 暂停状态下不检测，因为用户可能手动取消抛竿
                    if initial_bait_before_cast is not None and not self.paused:
                        final_bait = self.vision.get_bait_amount()
                        if (
                            final_bait is not None
                            and final_bait < initial_bait_before_cast
                        ):
                            self.log_updated.emit(
                                f"鱼饵减少 ({initial_bait_before_cast} -> {final_bait}) 但未成功收杆，判定为鱼跑了。"
                            )
                            self._record_event("鱼跑了")
                            return False

                    # 如果当前处于暂停或停止状态，直接返回
                    if not self.running or self.paused:
                        self.log_updated.emit(
                            "抛竿验证期间被手动暂停或停止，重置状态。"
                        )
                        return False

                    # 根据抛竿图标是否消失判断鱼桶状态
                    if not cast_icon_ever_gone:
                        # 抛竿图标从未消失，说明无法抛竿，检查是没鱼饵还是鱼桶满
                        bait_amount = self.vision.get_bait_amount()
                        if bait_amount == 0:
                            self.log_updated.emit("鱼饵用完了。")
                            if cfg.global_settings.get("enable_sound_alert", False):
                                self.sound_alert_requested.emit("no_bait")
                            self.pause(reason="没有鱼饵了")
                        else:
                            self.log_updated.emit("检测到鱼桶已满（抛竿图标未消失）。")
                            # 检查是否启用自动放生：启用则执行放生，否则暂停脚本
                            if cfg.global_settings.get("auto_release_enabled", False):
                                # 开启放生时，先不播放提示音，执行放生后再判断
                                released_count = self.check_and_auto_release()
                                # 如果放生后仍然无法抛竿（没有放生任何鱼或鱼桶还是满的），暂停脚本并播放提示音
                                if released_count == 0:
                                    self.log_updated.emit(
                                        "自动放生未放生任何鱼，鱼桶可能仍然满载或没有符合放生条件的鱼。"
                                    )
                                    # 在这里播放提示音：没有可放生的鱼但桶满了
                                    if cfg.global_settings.get(
                                        "enable_sound_alert", False
                                    ):
                                        self.sound_alert_requested.emit(
                                            "inventory_full"
                                        )
                                    self.pause(reason="鱼桶已满且无法自动放生")
                            else:
                                # 未开启放生时，鱼桶满就正常播放提示音
                                if cfg.global_settings.get("enable_sound_alert", False):
                                    self.sound_alert_requested.emit("inventory_full")
                                self.pause(reason="鱼桶已满")
                        return False

                    # 抛竿图标曾经消失，说明不是鱼桶满，可能是位置冲突或网络延迟
                    self.log_updated.emit("抛竿验证超时，将重新尝试。")
                    return False
                    # -- 验证结束 --

            self.msleep(200)

        self.log_updated.emit("抛竿超时, 未找到抛竿提示。")
        return False

    def _wait_for_bite(self):
        """
        等待鱼儿咬钩，通过精准检测鱼饵数量变化来判断。

        策略：
        1. 检测鱼饵数量减少即判定咬钩
        2. 高频检测：50ms 轮询
        3. 容错日志：记录识别失败情况便于调试
        4. 连续帧验证：检测到变化后等待 100ms 再确认，避免过渡帧误判
        """
        if not self.running:
            return False
        self.status_updated.emit("等待咬钩")
        self.log_updated.emit("等待鱼饵数量减少...")

        # 优先使用抛竿阶段保存的初始鱼饵数量
        initial_bait = getattr(self, "_initial_bait_for_bite", None)

        if initial_bait is not None:
            self.log_updated.emit(f"初始鱼饵数量: {initial_bait}")
        else:
            # 如果抛竿阶段未获取到，尝试重新获取（最多 10 次）
            self.log_updated.emit("抛竿阶段未获取到鱼饵数量，尝试重新获取...")
            cast_rod_region = cfg.get_rect("cast_rod")
            cast_rod_ice_region = cfg.get_rect("cast_rod_ice")

            for attempt in range(10):
                if not self.running:
                    return False
                while self.paused:
                    self.msleep(100)

                initial_bait = self.vision.get_bait_amount()
                if initial_bait is not None:
                    self.log_updated.emit(f"初始鱼饵数量: {initial_bait}")
                    break

                # 检测抛竿图标，如果出现说明鱼跑了或未抛竿成功
                if attempt > 0 and attempt % 3 == 0:
                    for key in ["F1_grayscale", "F2_grayscale"]:
                        if self.vision.find_template(
                            key, region=cast_rod_region, threshold=0.8
                        ) or self.vision.find_template(
                            key, region=cast_rod_ice_region, threshold=0.8
                        ):
                            self.log_updated.emit(
                                "检测到抛竿图标，可能未抛竿成功或已超时。重置循环。"
                            )
                            return False

                self.smart_sleep(0.3)

            if initial_bait is None:
                # 仍然失败，使用特殊策略：监控任意变化
                self.log_updated.emit(
                    "警告: 无法获取初始鱼饵数量，将监控任意鱼饵变化。"
                )
                initial_bait = -1  # 特殊标记，后续逻辑会处理

        # 进入等待咬钩的主循环
        timeout = 120
        start_time = time.time()

        # 容错变量
        last_known_bait = initial_bait  # 最后一次成功识别的鱼饵数量
        consecutive_none_count = 0  # 连续识别失败次数
        none_warning_threshold = 20  # 连续失败多少次后发出警告（约1秒）
        total_none_count = 0  # 总识别失败次数
        total_checks = 0  # 总检测次数

        # 脱钩检测相关
        cast_rod_region = cfg.get_rect("cast_rod")
        cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
        unhook_check_interval = 20  # 每隔 20 次检测（约 1 秒）检查一次是否脱钩

        while time.time() - start_time < timeout:
            if not self.running or self.paused:
                return False

            current_bait = self.vision.get_bait_amount()
            total_checks += 1

            if current_bait is None:
                # 识别失败，计数并继续
                consecutive_none_count += 1
                total_none_count += 1

                # 连续失败达到阈值时警告（仅警告一次）
                if consecutive_none_count == none_warning_threshold:
                    # self.log_updated.emit(f"警告: 鱼饵数量识别连续失败 {consecutive_none_count} 次")
                    pass
            else:
                # 识别成功，重置连续失败计数
                # if consecutive_none_count >= none_warning_threshold:
                #     self.log_updated.emit(f"鱼饵识别恢复，当前数量: {current_bait}")
                consecutive_none_count = 0

                # 特殊处理：如果之前未获取到初始值，以第一个有效值作为基准
                if initial_bait == -1:
                    initial_bait = current_bait
                    last_known_bait = current_bait
                    self.log_updated.emit(f"已获取基准鱼饵数量: {initial_bait}")
                    continue  # 跳过本次循环，等待下次变化

                # 更新最后已知值
                last_known_bait = current_bait

                # 检测到变化，需要进行二次确认（避免过渡帧误判）
                if current_bait != initial_bait:
                    # 等待 30ms 让过渡帧结束
                    self.msleep(30)

                    # 二次确认
                    confirm_bait = self.vision.get_bait_amount()
                    if confirm_bait is not None and confirm_bait != initial_bait:
                        self.log_updated.emit(
                            f"检测到鱼饵数量变化 ({initial_bait} -> {confirm_bait}), 判定为咬钩。"
                        )
                        return True
                    else:
                        # 疑似过渡帧误判，忽略本次检测
                        self.log_updated.emit(
                            f"[调试] 疑似过渡帧，忽略 ({initial_bait} -> {current_bait} -> {confirm_bait})"
                        )

            # 定期检测是否脱钩（抛竿图标重新出现 + 鱼饵减少 = 错过咬钩，鱼跑了）
            if total_checks % unhook_check_interval == 0:
                # 先检查鱼饵是否减少
                check_bait = self.vision.get_bait_amount()
                if check_bait is not None and check_bait < initial_bait:
                    # 鱼饵已减少，检查是否回到抛竿状态
                    for key in ["F1_grayscale", "F2_grayscale"]:
                        if self.vision.find_template(
                            key, region=cast_rod_region, threshold=0.8
                        ) or self.vision.find_template(
                            key, region=cast_rod_ice_region, threshold=0.8
                        ):
                            self.log_updated.emit(
                                f"鱼饵减少 ({initial_bait} -> {check_bait}) 且抛竿图标出现，错过咬钩，鱼跑了！"
                            )
                            self._record_event("鱼跑了")
                            return False

            # 高频检测（50ms）
            self.msleep(50)

        # 超时后输出详细统计
        self.log_updated.emit(
            f"等待咬钩超时。最后已知鱼饵: {last_known_bait}, 初始: {initial_bait}"
        )
        # self.log_updated.emit(f"[调试] 本轮检测统计: 总检测 {total_checks} 次, 识别失败 {total_none_count} 次 ({total_none_count*100//max(total_checks,1)}%)")
        return False

    def _reel_in(self):
        """
        收杆阶段, 实现收放循环。
        仅通过寻找星星图标来判断何时停止收线。
        """
        if not self.running:
            return False
        self.status_updated.emit("上鱼了! 开始收杆!")
        self.log_updated.emit("进入收放线循环...")

        star_region = cfg.get_rect("reel_in_star")

        for i in range(cfg.max_pulls):
            if not self.running or self.paused:
                return False

            self.log_updated.emit(f"第 {i+1}/{cfg.max_pulls} 次尝试: 收线...")

            # --- START: 改进的收线逻辑，可处理中断 ---
            self.inputs.press_mouse_button()
            pull_start_time = time.time()
            pull_duration = cfg.reel_in_time

            try:
                while time.time() - pull_start_time < pull_duration:
                    if not self.running or self.paused:
                        # 如果在收线时暂停或停止，必须释放鼠标
                        return False  # 直接退出_reel_in

                    time.sleep(0.05)  # 短暂轮询间隔，降低CPU占用
            finally:
                # 确保无论循环如何退出（正常结束、break或异常），鼠标都会被释放
                self.inputs.release_mouse_button()
            # --- END: 改进的收线逻辑 ---

            self.log_updated.emit("放线...")
            # Use smart_sleep but consider jitter. smart_sleep handles intervals > 0.1s better.
            # If jittered time is very short, simple sleep is fine, but for consistency we can use smart_sleep
            # provided input jitter doesn't make it negative.
            sleep_duration = self.inputs.add_jitter(cfg.release_time)
            self.smart_sleep(sleep_duration)

            # --- START: “鱼跑了”检测 ---
            # 在放线间隙，检查是否意外回到了抛竿状态
            cast_rod_region = cfg.get_rect("cast_rod")
            cast_rod_ice_region = cfg.get_rect("cast_rod_ice")
            for key in ["F1_grayscale", "F2_grayscale"]:
                if self.vision.find_template(
                    key, region=cast_rod_region, threshold=0.8
                ) or self.vision.find_template(
                    key, region=cast_rod_ice_region, threshold=0.8
                ):
                    self.log_updated.emit("在收线过程中检测到抛竿提示，判定为鱼跑了！")
                    self.status_updated.emit("鱼跑了!")
                    self._record_event("鱼跑了")  # 记录事件
                    return False  # 返回False，主循环会继续下一次尝试
            # --- END: “鱼跑了”检测 ---

            # 检测是否成功钓到鱼
            if self.vision.find_template(
                "star_grayscale", region=star_region, threshold=0.7
            ):
                self.log_updated.emit("检测到星星，成功！")
                return True

        self.log_updated.emit("达到最大拉杆次数，仍未检测到星星。")
        return False

    def _record_catch(self):
        """
        截图识别渔获信息, 并发送信号
        """
        if not self.running:
            return False

        # 检查是否启用鱼类识别
        if not cfg.global_settings.get("enable_fish_recognition", True):
            self.log_updated.emit("鱼类识别已关闭，等待并关闭渔获弹窗")
            self.status_updated.emit("关闭渔获弹窗")

            # 等待弹窗完全显示
            self.smart_sleep(0.5)

            # 检测"收起"按钮，确保弹窗已显示
            max_attempts = 10  # 最多尝试5秒
            shangyu_region = cfg.get_rect("shangyu")
            shangyu_found = False

            for attempt in range(max_attempts):
                if not self.running:
                    return False

                if self.vision.find_template(
                    "shangyu_grayscale", region=shangyu_region, threshold=0.8
                ):
                    self.log_updated.emit("检测到'收起'按钮，准备关闭弹窗")
                    shangyu_found = True
                    break

                self.msleep(500)  # 每次等待500ms

            if not shangyu_found:
                self.log_updated.emit("警告: 未检测到'收起'按钮，尝试直接点击关闭")

            return False

        self.status_updated.emit("记录渔获")
        self.log_updated.emit("正在识别渔获信息...")

        self.smart_sleep(0.5)  # 等待UI稳定 (优化: 减少等待时间)

        # 尝试检测并点击"收起"按钮 (shangyu)
        shangyu_region = cfg.get_rect("shangyu")
        if self.vision.find_template(
            "shangyu_grayscale", region=shangyu_region, threshold=0.8
        ):
            self.log_updated.emit("检测到'收起'按钮，确认上鱼成功。")
            # shangyu仅作为状态指示，不作为点击位置，稍后统一左键点击关闭
            # 注意：这里我们稍后点击，先截图OCR，防止点击后弹窗消失

        rect = cfg.get_rect("ocr_area")
        if not rect:
            self.log_updated.emit("错误: 未在配置中找到 'ocr_area' 区域。")
            return False

        # OCR 识别渔获信息（带重试机制，防止弹窗干扰）
        max_ocr_retries = 3
        result = None
        image = None

        for ocr_attempt in range(max_ocr_retries):
            if not self.running:
                return False

            image = self.vision.screenshot(rect)
            if image is None:
                self.log_updated.emit("截图失败。")
                return False

            result, _ = self.ocr(image)

            if result:
                # OCR 成功，跳出重试循环
                break
            else:
                # OCR 失败
                if ocr_attempt < max_ocr_retries - 1:
                    # 未达到最大重试次数，等待后重试（等待弹窗处理线程处理完弹窗）
                    self.log_updated.emit(
                        f"OCR 未识别到内容，等待 0.5 秒后重试 ({ocr_attempt + 1}/{max_ocr_retries})..."
                    )
                    self.smart_sleep(0.5)  # 优化: 减少重试等待
                else:
                    # 最后一次尝试仍失败
                    self.log_updated.emit("OCR未能识别到有效的渔获信息。")
                    try:
                        # Debug: save the failed image
                        debug_dir = cfg._get_base_path() / "debug_screenshots"
                        if not debug_dir.exists():
                            debug_dir.mkdir(parents=True)
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        debug_filename = debug_dir / f"ocr_failed_{timestamp}.png"
                        cv2.imwrite(str(debug_filename), image)
                        self.log_updated.emit(
                            f"OCR失败，已保存调试截图: {debug_filename}"
                        )
                    except Exception as e:
                        self.log_updated.emit(f"保存调试截图失败: {e}")
                    return False

        full_text = "".join([res[1] for res in result])
        self.log_updated.emit(f"识别到原始文本: {full_text}")

        # 检测是否为新纪录（支持简体和繁体）
        new_record_patterns = ["新纪录", "新记录", "新紀錄"]
        is_new_record = any(p in full_text for p in new_record_patterns)
        if is_new_record:
            self.log_updated.emit("检测到新纪录！")
            # 移除关键词以免干扰后续解析
            for p in new_record_patterns:
                full_text = full_text.replace(p, "")

        # 增强容错：只要文本中包含关键字即可，不需要精确匹配（支持简体和繁体）
        catch_prefix_found = "你钓到了" in full_text or "你釣到了" in full_text
        if not catch_prefix_found:
            # 尝试模糊匹配或查找后续特征，如"千克"或"公斤"
            if "千克" in full_text or "公斤" in full_text:
                self.log_updated.emit(
                    "未检测到'你钓到了'前缀，但发现重量单位，尝试继续解析。"
                )
                # 假设所有文本都是有效信息
            else:
                self.log_updated.emit("OCR结果不包含关键字，判定为钓鱼失败。")
                return False

        cleaned_text = full_text.replace(" ", "").replace("(", "").replace(")", "")

        # 检测并清理新纪录关键词（支持简体和繁体）
        # 已经在前一步做了初步检测，这里进行清理以防止干扰后续解析
        new_record_keywords = [
            "新纪录",
            "新记录",
            "新紀錄",
            "首次捕获",
            "首次捕獲",
            "首次",
        ]
        for kw in new_record_keywords:
            if kw in cleaned_text:
                is_new_record = True  # 再次确认
                cleaned_text = cleaned_text.replace(kw, "")

        # 额外清理冒号，OCR识别“首次捕获”后常伴随冒号
        cleaned_text = cleaned_text.replace(":", "").replace("：", "")

        try:
            # 移除固定的前缀（支持简体和繁体）
            if "你钓到了" in cleaned_text:
                text_after_prefix = cleaned_text.split("你钓到了", 1)[-1]
            elif "你釣到了" in cleaned_text:
                text_after_prefix = cleaned_text.split("你釣到了", 1)[-1]
            else:
                text_after_prefix = cleaned_text

            # 定义所有可能的品质（简体和繁体）
            # 注意：繁体和简体需要都包含，以便正确识别和后续归一化
            qualities = [
                "标准",
                "非凡",
                "稀有",
                "史诗",
                "传说",
                "传奇",
                "標準",
                "傳說",
                "傳奇",
                "史詩",
                "稀少",
            ]

            # 提取重量
            weight = 0.0
            weight_match = re.search(r"(\d+\.?\d*)千克", text_after_prefix)
            if weight_match:
                weight = float(weight_match.group(1))
                # 从字符串中移除重量信息以便于解析鱼名和品质
                text_after_prefix = text_after_prefix.replace(
                    weight_match.group(0), ""
                ).strip()

            # 提取品质
            quality = "普通"  # 默认值
            for q in qualities:
                if q in text_after_prefix:
                    quality = q
                    # 从字符串中移除品质信息
                    text_after_prefix = text_after_prefix.replace(q, "").strip()
                    break

            # 品质名称归一化（繁体统一转换为简体）
            quality_mapping = {
                "传说": "传奇",
                "傳說": "传奇",
                "傳奇": "传奇",
                "標準": "标准",
                "史詩": "史诗",
                "稀少": "稀有",  # 某些游戏版本可能使用不同译名
            }
            if quality in quality_mapping:
                quality = quality_mapping[quality]

            # 剩下的就是鱼名
            fish_name = text_after_prefix.strip()

            # --- 鱼名清理与模糊匹配校正 ---
            if hasattr(cfg, "fish_names_list") and cfg.fish_names_list:
                # 1. 构造搜索关键词：如果包含中文，提取纯中文部分（移除数字、符号、英文噪声）
                # 2. 这样可以处理 "黄鸭叫10★" -> "黄鸭叫", "地包★天鱼" -> "地包天鱼"
                search_name = fish_name
                if re.search(r"[\u4e00-\u9fa5]", fish_name):
                    search_name = "".join(re.findall(r"[\u4e00-\u9fa5]+", fish_name))

                # 优先使用 search_name 进行匹配
                matches = difflib.get_close_matches(
                    search_name, cfg.fish_names_list, n=1, cutoff=0.6
                )

                # 如果 search_name 匹配失败且与 fish_name 不同，再用原始名尝试一次
                if not matches and search_name != fish_name:
                    matches = difflib.get_close_matches(
                        fish_name, cfg.fish_names_list, n=1, cutoff=0.6
                    )

                if matches:
                    if fish_name != matches[0]:
                        self.log_updated.emit(
                            f"鱼名校正: '{fish_name}' -> '{matches[0]}'"
                        )
                    fish_name = matches[0]
                else:
                    # 匹配失败时的最后清理逻辑：移除尾部噪声
                    if re.search(r"[\u4e00-\u9fa5]", fish_name):
                        fish_name = re.sub(r"[^\u4e00-\u9fa5]+$", "", fish_name)
                    else:
                        fish_name = re.sub(r"[a-zA-Z0-9]+$", "", fish_name)
            else:
                # 如果没有标准库，执行基本的尾部清理
                if re.search(r"[\u4e00-\u9fa5]", fish_name):
                    fish_name = re.sub(r"[^\u4e00-\u9fa5]+$", "", fish_name)
                else:
                    fish_name = re.sub(r"[a-zA-Z0-9]+$", "", fish_name)
            # -------------------

            fish_name = fish_name.strip()

            if not fish_name:
                self.log_updated.emit(f"无法从 '{full_text}' 中解析出鱼名。")
                return False

            self.log_updated.emit(
                f"解析结果 -> 鱼名: '{fish_name}', 品质: '{quality}', 重量: {weight}"
            )

        except Exception as e:
            self.log_updated.emit(f"数据解析过程中发生错误: {e}")
            return False

        self.log_updated.emit(f"钓到鱼: {fish_name}, 重量: {weight}kg, 品质: {quality}")

        catch_data = {
            "name": fish_name,
            "weight": weight,
            "quality": quality,
            "is_new_record": is_new_record,
        }
        self.record_added.emit(catch_data)

        # Persistence: Write to CSV
        try:
            csv_file = cfg.records_file
            file_exists = csv_file.is_file()

            # Ensure parent data directory exists
            if not csv_file.parent.exists():
                csv_file.parent.mkdir(parents=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Bait Info
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)

            encoding = "utf-8-sig" if not file_exists else "utf-8"
            with open(csv_file, "a", encoding=encoding) as f:
                if not file_exists:
                    f.write("Timestamp,Name,Quality,Weight,IsNewRecord,Bait,BaitCost\n")

                # 兼容性处理：如果文件已存在但没有新列，我们附加数据。读取时会处理缺失列。
                is_new_record_str = "Yes" if is_new_record else "No"
                f.write(
                    f"{timestamp},{fish_name},{quality},{weight},{is_new_record_str},{bait_name},{bait_cost}\n"
                )

        except Exception as e:
            self.log_updated.emit(f"写入记录文件失败: {e}")

        # 检查是否需要单条放生（返回标志，不在此处执行）
        release_map = {
            "标准": "single_release_standard",
            "非凡": "single_release_uncommon",
            "稀有": "single_release_rare",
            "史诗": "single_release_epic",
            "传奇": "single_release_legendary",
        }

        should_release = cfg.global_settings.get(release_map.get(quality), False)

        if quality == "传奇":
            self.log_updated.emit("哇! 钓到了传奇品质的鱼, 正在截图保存...")
            try:
                with mss.mss() as sct:
                    # 使用游戏窗口区域截图，支持副屏和窗口化模式
                    monitor = {
                        "left": cfg.window_offset_x,
                        "top": cfg.window_offset_y,
                        "width": cfg.screen_width,
                        "height": cfg.screen_height,
                    }
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = (
                        cfg._get_base_path()
                        / "screenshots"
                        / f"legendary_{fish_name.replace(':', '_')}_{timestamp}.png"
                    )
                    sct_img = sct.grab(monitor)
                    mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(filename))
                    self.log_updated.emit(f"截图已保存至 {filename}")
            except Exception as e:
                self.log_updated.emit(f"截图失败: {e}")

        # 无论结果如何，尝试点击"收起"按钮以关闭弹窗，进入下一轮
        # 优化：交由主循环统一处理点击，避免此处重复点击导致异常
        return should_release

    def _record_event(self, event_type: str):
        """
        记录一个通用事件到CSV文件, 例如 "鱼跑了"
        """
        # 检查是否启用鱼类识别
        if not cfg.global_settings.get("enable_fish_recognition", True):
            return

        # Persistence: Write to CSV
        try:
            csv_file = cfg.records_file
            file_exists = csv_file.is_file()

            # Ensure parent directory exists
            if not csv_file.parent.exists():
                csv_file.parent.mkdir(parents=True)

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Bait Info
            bait_name = cfg.current_bait
            bait_cost = cfg.BAIT_PRICES.get(bait_name, 0)

            encoding = "utf-8-sig" if not file_exists else "utf-8"
            with open(csv_file, "a", encoding=encoding) as f:
                if not file_exists:
                    f.write("Timestamp,Name,Quality,Weight,IsNewRecord,Bait,BaitCost\n")
                # 对于事件，我们只记录名称，其他字段留空，IsNewRecord为No
                f.write(f"{timestamp},{event_type},,,No,{bait_name},{bait_cost}\n")
        except Exception as e:
            self.log_updated.emit(f"写入记录文件失败: {e}")

        # Emit signal to update UI immediately
        event_data = {
            "name": event_type,
            "weight": "",
            "quality": "",
            "is_new_record": False,
        }
        self.record_added.emit(event_data)

    def pause(self, reason: str = None):
        """
        暂停线程并重置状态
        :param reason: 暂停的具体原因，如果不为None，将显示此状态，否则显示默认的"已暂停"
        """
        self.paused = True
        self.state = "finding_prompt"  # 重置状态到初始阶段
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
        self.status_updated.emit("运行中")
        self.log_updated.emit("自动化已恢复。")

        # 恢复时重新激活游戏窗口（解决副屏暂停后恢复时焦点问题）
        if cfg.activate_game_window():
            self.log_updated.emit("已激活游戏窗口")

    def stop(self, reason: str = None):
        """
        安全地停止线程
        :param reason: 停止的具体原因，将作为最终状态显示在GUI上
        """
        self.running = False
        # Remove self.wait() to prevent GUI freezing.
        # The main thread should wait for us, not us blocking inside our own stop method called from main thread.
        # But actually, stop() is called from main thread. If we wait() here, we block main thread until run() finishes.
        # This IS the correct way usually, but if run() is blocked, we freeze.
        # We already improved run() loop responsiveness.
        # However, if 'wait' causes issues, we can remove it and let closeEvent handle the wait with timeout.
        final_status = reason if reason else "已停止"
        self.status_updated.emit(f"{final_status}")
        self.log_updated.emit(f"收到停止信号, 原因: {final_status}")

    def smart_sleep(self, duration):
        """
        可中断的睡眠函数，能够及时响应停止信号
        """
        end_time = time.time() + duration
        while self.running and time.time() < end_time:
            sleep_time = min(0.1, end_time - time.time())
            if sleep_time > 0:
                time.sleep(sleep_time)

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
        Write sale record to CSV.
        Returns True if successful, False otherwise.
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            bait_used = cfg.current_bait

            sales_path = cfg.sales_file

            # Ensure directory exists
            if not sales_path.parent.exists():
                sales_path.parent.mkdir(parents=True)

            file_exists = sales_path.exists()

            # Write to file
            with open(sales_path, "a", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Timestamp", "Amount", "BaitUsed"])
                writer.writerow([timestamp, amount, bait_used])

            return True
        except Exception as e:
            self.log_updated.emit(f"写入销售记录失败: {e}")
            return False

    @Slot()
    def trigger_sell(self):
        """
        触发卖鱼逻辑: 截图识别 -> 记录 -> 点击
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

            # Attempt to write record BEFORE clicking
            if self._write_sale_record(amount):
                self.log_updated.emit("销售记录保存成功。")

                # Emit signal to update UI
                self.sale_recorded.emit(amount)

                if cfg.global_settings.get("auto_click_sell", True):
                    # Click center of the area (加上窗口偏移转换为屏幕绝对坐标)
                    cx = rect[0] + rect[2] // 2 + cfg.window_offset_x
                    cy = rect[1] + rect[3] // 2 + cfg.window_offset_y

                    # Perform click
                    self.inputs.click(cx, cy)
                    self.log_updated.emit("已自动点击卖出。")
                else:
                    self.log_updated.emit("自动点击已禁用，仅记录数据。")
            else:
                self.log_updated.emit(
                    "严重错误：销售记录保存失败！为防止数据丢失，已终止出售操作。"
                )
                self.status_updated.emit("记录失败，未出售")
                if cfg.global_settings.get("enable_sound_alert", False):
                    # Optionally play an error sound here if available, or just log
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

    def check_and_auto_release(self):
        """检查鱼桶并执行自动放生（支持F2暂停，暂停后重新开始）"""
        if not cfg.global_settings.get("auto_release_enabled", False):
            return

        # 更新游戏窗口信息，确保窗口偏移量是最新的
        cfg.update_game_window()

        self.log_updated.emit("开始自动放生...")
        self.status_updated.emit("自动放生中")

        # 打开鱼桶
        self.inputs.hold_key("C")
        self.smart_sleep(0.2)
        if self.paused:
            self.inputs.release_key("C")
            self.log_updated.emit("放生被暂停，已中止")
            return

        bucket_pos = self.vision.find_template("tong_gray", threshold=0.8)
        if bucket_pos:
            import ctypes

            ctypes.windll.user32.SetCursorPos(
                bucket_pos[0] + cfg.window_offset_x, bucket_pos[1] + cfg.window_offset_y
            )
            self.smart_sleep(0.5)
            if self.paused:
                self.inputs.release_key("C")
                self.log_updated.emit("放生被暂停，已中止")
                return

        self.inputs.release_key("C")
        self.smart_sleep(1.0)
        if self.paused:
            self.inputs.press_key("ESC")
            self.log_updated.emit("放生被暂停，已中止")
            return

        released_count = 0
        zones = cfg.REGIONS["fish_inventory"]["zones"]
        locked_detected = False

        # 依次检测3个区域
        for zone_idx, zone in enumerate(zones):
            if not self.running or self.paused:
                break

            zone_id = zone["id"]
            self.log_updated.emit(f"检测区域 {zone_id}...")

            grid = zone["grid"]
            scaled_zone_x = int(zone["coords"][0] * cfg.scale_x)
            scaled_zone_y = int(zone["coords"][1] * cfg.scale_y)
            scaled_cell_width = int(grid["cell_width"] * cfg.scale_x)
            scaled_cell_height = int(grid["cell_height"] * cfg.scale_y)

            # 窗口化模式修正：向左偏移一个半格子宽度
            if cfg.window_offset_x > 0 or cfg.window_offset_y > 0:
                scaled_zone_x -= int(228 * cfg.scale_x)
            scaled_star_offset_x = int(grid["star_offset"][0] * cfg.scale_x)
            scaled_star_offset_y = int(grid["star_offset"][1] * cfg.scale_y)
            scaled_star_width = int(grid["star_size"][0] * cfg.scale_x)
            scaled_star_height = int(grid["star_size"][1] * cfg.scale_y)

            zone_released = 0

            # 按行遍历，每行重复检查直到没有需要放生的鱼
            for row in range(4):
                if not self.running or self.paused or locked_detected:
                    break

                while True:
                    if not self.running or self.paused:
                        break
                    action_in_row = False
                    valid_fish_count = 0
                    for col in range(4):
                        if not self.running or self.paused:
                            break

                        # 检测锁定图标（格子中心区域，约60x60像素）
                        lock_size = int(60 * cfg.scale_x)
                        lock_x = (
                            scaled_zone_x
                            + col * scaled_cell_width
                            + (scaled_cell_width - lock_size) // 2
                        )
                        lock_y = (
                            scaled_zone_y
                            + row * scaled_cell_height
                            + (scaled_cell_height - lock_size) // 2
                        )
                        # 窗口化模式微调：向右和向下偏移
                        if cfg.window_offset_x > 0 or cfg.window_offset_y > 0:
                            lock_x += int(25 * cfg.scale_x)
                            lock_y += int(10 * cfg.scale_y)
                        lock_region = (lock_x, lock_y, lock_size, lock_size)

                        lock_detected = self.vision.detect_lock_icon(lock_region)
                        if lock_detected:
                            self.log_updated.emit(
                                f"位置({row},{col})检测到锁定图标，停止检测"
                            )
                            locked_detected = True
                            break

                        star_x = (
                            scaled_zone_x
                            + col * scaled_cell_width
                            + scaled_star_offset_x
                        )
                        star_y = (
                            scaled_zone_y
                            + row * scaled_cell_height
                            + scaled_star_offset_y
                        )
                        star_region = (
                            star_x,
                            star_y,
                            scaled_star_width,
                            scaled_star_height,
                        )
                        star_img = self.vision.screenshot(star_region)
                        color = self.vision.detect_star_color(star_img)

                        if color is None:
                            continue

                        if color in ["purple", "yellow"]:
                            self.msleep(50)
                            star_img_verify = self.vision.screenshot(star_region)
                            color_verify = self.vision.detect_star_color(
                                star_img_verify
                            )
                            if color_verify != color:
                                self.log_updated.emit(
                                    f"位置({row},{col})高品质验证失败: {color} != {color_verify}，跳过"
                                )
                                continue

                        valid_fish_count += 1

                        quality_map = {
                            "gray": "标准",
                            "green": "非凡",
                            "blue": "稀有",
                            "purple": "史诗",
                            "yellow": "传奇",
                        }
                        quality = quality_map.get(color, "标准")

                        release_map = {
                            "标准": "release_standard",
                            "非凡": "release_uncommon",
                            "稀有": "release_rare",
                            "史诗": "release_epic",
                            "传奇": "release_legendary",
                        }
                        should_release = cfg.global_settings.get(
                            release_map.get(quality), False
                        )

                        # 高品质鱼不放生
                        if color in ["purple", "yellow"]:
                            should_release = False

                        if not self.running or self.paused:
                            break

                        # 检测弹窗并等待处理完成
                        popup_region = cfg.get_rect("popup_exclamation")
                        if self.vision.find_template_popup(
                            "exclamation_grayscale",
                            region=popup_region,
                            threshold=0.7,
                        ):
                            self.log_updated.emit("检测到弹窗，等待处理完成...")
                            if not self._wait_for_popup_clear(timeout=10):
                                self.log_updated.emit("等待弹窗清除超时，继续操作")

                        # 点击鱼打开菜单
                        fish_x = (
                            scaled_zone_x
                            + col * scaled_cell_width
                            + scaled_cell_width // 2
                        )
                        fish_y = (
                            scaled_zone_y
                            + row * scaled_cell_height
                            + scaled_cell_height // 2
                        )
                        self.inputs.click(
                            fish_x + cfg.window_offset_x,
                            fish_y + cfg.window_offset_y,
                        )
                        self.smart_sleep(0.3)

                        if not self.running or self.paused:
                            break

                        # OCR识别菜单
                        zone_width = 4 * scaled_cell_width
                        zone_height = 4 * scaled_cell_height
                        menu_region = (
                            scaled_zone_x,
                            scaled_zone_y,
                            zone_width,
                            zone_height,
                        )
                        menu_img = self.vision.screenshot(menu_region)

                        if menu_img is None:
                            self.log_updated.emit("截取菜单失败，跳过")
                            continue

                        ocr_result, _ = self.ocr(menu_img)
                        action_found = False

                        if ocr_result:
                            target_text = "放生" if should_release else "锁定"
                            for item in ocr_result:
                                text = item[1]
                                if target_text in text:
                                    box = item[0]
                                    center_x = int((box[0][0] + box[2][0]) / 2)
                                    center_y = int((box[0][1] + box[2][1]) / 2)
                                    action_x = scaled_zone_x + center_x
                                    action_y = scaled_zone_y + center_y
                                    self.inputs.click(
                                        action_x + cfg.window_offset_x,
                                        action_y + cfg.window_offset_y,
                                    )
                                    action_found = True
                                    self.log_updated.emit(
                                        f"位置({row},{col})品质:{quality}，{'放生' if should_release else '锁定'}"
                                    )
                                    break

                        if not action_found:
                            self.log_updated.emit(
                                f"未识别到{'放生' if should_release else '锁定'}按钮，跳过"
                            )
                            continue

                        time.sleep(0.3)

                        import ctypes

                        screen_right = cfg.window_offset_x + cfg.screen_width - 10
                        screen_top = cfg.window_offset_y + 10
                        ctypes.windll.user32.SetCursorPos(screen_right, screen_top)

                        self.smart_sleep(0.8)

                        if not self.running or self.paused:
                            break

                        if should_release:
                            released_count += 1
                            zone_released += 1
                            action_in_row = True
                        elif row == 0:
                            # 锁定操作只在第一排时重复检测
                            action_in_row = True

                        self.smart_sleep(0.3)
                        break

                    if valid_fish_count == 0 or not action_in_row or locked_detected:
                        break

            if locked_detected:
                self.log_updated.emit("检测到锁定，停止所有检测")
                break

            # 输出当前区域的放生结果
            if zone_released > 0:
                self.log_updated.emit(f"区域 {zone_id} 放生了 {zone_released} 条鱼")
            else:
                self.log_updated.emit(f"区域 {zone_id} 无可放生的鱼")

            # 如果不是最后一个区域，滚动到下一个区域
            if zone_idx < len(zones) - 1:
                self.log_updated.emit("滚动到下一区域...")
                # 将鼠标移到鱼桶中心位置，确保滚轮生效
                import ctypes

                center_x = scaled_zone_x + (4 * scaled_cell_width) // 2
                center_y = scaled_zone_y + (4 * scaled_cell_height) // 2
                ctypes.windll.user32.SetCursorPos(
                    center_x + cfg.window_offset_x, center_y + cfg.window_offset_y
                )
                self.smart_sleep(0.2)
                # 向下滚动3次
                for _ in range(3):
                    if not self.running or self.paused:
                        break
                    self.inputs.scroll_wheel(-1)
                    self.smart_sleep(0.8)
                self.smart_sleep(0.5)

        # 关闭鱼桶
        self.inputs.press_key("ESC")
        self.smart_sleep(0.5)

        if self.paused:
            self.log_updated.emit(f"放生被暂停，已放生{released_count}条鱼")
        else:
            self.log_updated.emit(f"自动放生完成，共放生{released_count}条鱼")
        self.status_updated.emit("运行中")

        return released_count

    def _execute_single_release(self):
        """执行单条放生操作"""
        try:
            # 打开鱼桶
            self.inputs.hold_key("C")
            self.msleep(300)

            bucket_pos = self.vision.find_template("tong_gray", threshold=0.8)
            self.msleep(200)

            if bucket_pos:
                import ctypes

                ctypes.windll.user32.SetCursorPos(
                    bucket_pos[0] + cfg.window_offset_x,
                    bucket_pos[1] + cfg.window_offset_y,
                )
                self.msleep(500)

            self.inputs.release_key("C")
            self.msleep(1200)

            if not bucket_pos:
                self.log_updated.emit("未识别到桶图标，放生操作失败。")
                return

            # 使用固定坐标点击第一条鱼（2K基准：1933, 600）
            fish_x = int(1933 * cfg.scale_x)
            fish_y = int(600 * cfg.scale_y)

            # 窗口化模式修正：向左偏移一个半格子宽度
            if cfg.window_offset_x > 0 or cfg.window_offset_y > 0:
                fish_x -= int(228 * cfg.scale_x)

            self.msleep(200)

            self.inputs.click(
                fish_x + cfg.window_offset_x, fish_y + cfg.window_offset_y
            )
            self.msleep(800)

            # 使用配置的偏移点击放生按钮（相对于鱼的位置，向右下偏移）
            offset = cfg.REGIONS["fish_inventory"]["single_release_button_offset"]
            release_x = fish_x + int(offset[0] * cfg.scale_x)
            release_y = fish_y + int(offset[1] * cfg.scale_y)
            self.msleep(200)

            self.inputs.click(
                release_x + cfg.window_offset_x,
                release_y + cfg.window_offset_y,
            )
            self.log_updated.emit("已点击放生按钮，鱼已放生")
            self.msleep(800)

            # 关闭鱼桶
            self.inputs.press_key("ESC")
            self.msleep(500)

        except Exception as e:
            self.log_updated.emit(f"单条放生操作发生错误: {e}")
            self.inputs.press_key("ESC")


class PopupWorker(QThread):
    """
    一个专门用于在后台检测和处理游戏弹窗的独立工作线程.
    """

    log_updated = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.vision = vision
        self.inputs = InputController()

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
                    if cfg.enable_jiashi:
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
                    # 可以在控制台打印但不发送到 UI
                    # print(f"[弹窗处理服务] 截图失败(已忽略): {e}")
                    pass
                else:
                    self.log_updated.emit(f"[弹窗处理服务] 发生错误: {e}")

            # 控制循环频率
            self.msleep(500)  # 每0.5秒检测一次

        self.log_updated.emit("弹窗处理服务已停止。")

    def stop(self):
        """
        安全地停止线程.
        """
        self.running = False
        # Remove wait() here too
        self.log_updated.emit("收到停止弹窗处理服务的信号。")
