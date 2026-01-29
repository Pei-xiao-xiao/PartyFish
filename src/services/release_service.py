"""
放生服务
负责处理自动放生和单条放生逻辑
"""

import time
import ctypes
from src.config import cfg


class ReleaseService:
    """放生服务类"""

    def __init__(self, worker):
        """
        初始化放生服务

        Args:
            worker: FishingWorker 实例，用于访问输入、视觉、OCR等功能
        """
        self.worker = worker

    def _open_fish_bucket(self):
        """
        打开鱼桶界面

        Returns:
            bool: True 表示成功打开，False 表示需要中止
        """
        self.worker.inputs.hold_key("C")
        self.worker.smart_sleep(0.2)
        if self.worker.paused:
            self.worker.inputs.release_key("C")
            self.worker.log_updated.emit("放生被暂停，已中止")
            self.worker.status_updated.emit("已暂停")
            return False

        bucket_pos = self.worker.vision.find_template("tong_gray", threshold=0.8)
        if bucket_pos:
            ctypes.windll.user32.SetCursorPos(
                bucket_pos[0] + cfg.window_offset_x, bucket_pos[1] + cfg.window_offset_y
            )
            self.worker.smart_sleep(0.5)
            if self.worker.paused:
                self.worker.inputs.release_key("C")
                self.worker.log_updated.emit("放生被暂停，已中止")
                self.worker.status_updated.emit("已暂停")
                return False

            if self.worker._check_popup_and_abort_release(0):
                self.worker.inputs.release_key("C")
                return False

        self.worker.inputs.release_key("C")
        self.worker.smart_sleep(1.0)
        if self.worker.paused:
            self.worker.inputs.press_key("ESC")
            self.worker.log_updated.emit("放生被暂停，已中止")
            self.worker.status_updated.emit("已暂停")
            return False

        if self.worker._check_popup_and_abort_release(0):
            return False

        return True

    def _detect_fish_quality(self, star_region, row, col):
        """
        检测鱼的品质

        Args:
            star_region: 星星区域坐标 (x, y, w, h)
            row: 行号
            col: 列号

        Returns:
            str: 品质名称（"标准"/"非凡"/"稀有"/"史诗"/"传奇"），如果没有鱼则返回 None
        """
        star_img = self.worker.vision.screenshot(star_region)
        color = self.worker.vision.detect_star_color(star_img)

        if color is None:
            return None

        # 高品质鱼需要二次验证
        if color in ["purple", "yellow"]:
            self.worker.msleep(50)
            star_img_verify = self.worker.vision.screenshot(star_region)
            color_verify = self.worker.vision.detect_star_color(star_img_verify)
            if color_verify != color:
                self.worker.log_updated.emit(
                    f"位置({row},{col})高品质验证失败: {color} != {color_verify}，跳过"
                )
                return None

        quality_map = {
            "gray": "标准",
            "green": "非凡",
            "blue": "稀有",
            "purple": "史诗",
            "yellow": "传奇",
        }
        return quality_map.get(color, "标准")

    def _check_fish_protection(self, fish_x, fish_y, quality, row, col, released_count):
        """
        检查鱼是否受保护

        Args:
            fish_x: 鱼的屏幕 x 坐标
            fish_y: 鱼的屏幕 y 坐标
            quality: 鱼的品质
            row: 行号
            col: 列号
            released_count: 当前已放生数量

        Returns:
            bool: True 表示鱼受保护，False 表示不受保护，None 表示需要中止
        """
        if not cfg.global_settings.get("enable_fish_name_protection", False):
            return False  # 未启用保护，鱼不受保护

        self.worker.smart_sleep(0.5)
        self.worker.inputs.double_click(
            fish_x + cfg.window_offset_x, fish_y + cfg.window_offset_y
        )
        self.worker.smart_sleep(0.5)

        if self.worker._check_popup_and_abort_release(released_count):
            return None

        fish_name_region = cfg.get_rect("fish_name_tooltip")
        fish_name_img = self.worker.vision.screenshot(fish_name_region)
        fish_name = None
        if fish_name_img is not None:
            fish_name = self.worker.ocr_service.recognize_text(fish_name_img)

        if fish_name and cfg.is_fish_protected(fish_name, quality):
            self.worker.log_updated.emit(
                f"位置({row},{col})检测到保护鱼:{fish_name}({quality})，锁定"
            )
            return True  # 鱼受保护

        return False  # 鱼不受保护

    def _execute_fish_action(
        self,
        fish_x,
        fish_y,
        should_release,
        quality,
        row,
        col,
        scaled_zone_x,
        scaled_zone_y,
        scaled_cell_width,
        scaled_cell_height,
        released_count,
    ):
        """
        执行放生或锁定操作

        Args:
            fish_x: 鱼的 x 坐标
            fish_y: 鱼的 y 坐标
            should_release: 是否应该放生
            quality: 鱼的品质
            row: 行号
            col: 列号
            scaled_zone_x: 区域 x 坐标
            scaled_zone_y: 区域 y 坐标
            scaled_cell_width: 单元格宽度
            scaled_cell_height: 单元格高度
            released_count: 当前已放生数量

        Returns:
            tuple: (success, should_increment) - success 表示操作是否成功，should_increment 表示是否应该增加计数
                   如果需要中止，返回 (None, None)
        """
        self.worker.inputs.click(
            fish_x + cfg.window_offset_x, fish_y + cfg.window_offset_y
        )
        self.worker.smart_sleep(0.3)

        if self.worker._check_popup_and_abort_release(released_count):
            return None, None

        if not self.worker.running or self.worker.paused:
            return False, False

        zone_width = 4 * scaled_cell_width
        zone_height = 4 * scaled_cell_height
        menu_region = (scaled_zone_x, scaled_zone_y, zone_width, zone_height)
        menu_img = self.worker.vision.screenshot(menu_region)

        if menu_img is None:
            self.worker.log_updated.emit("截取菜单失败，跳过")
            return False, False

        ocr_result = self.worker.ocr_service.recognize_text_with_boxes(menu_img)
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
                    self.worker.inputs.click(
                        action_x + cfg.window_offset_x, action_y + cfg.window_offset_y
                    )
                    action_found = True
                    self.worker.log_updated.emit(
                        f"位置({row},{col})品质:{quality}，{'放生' if should_release else '锁定'}"
                    )
                    break

        if not action_found:
            self.worker.log_updated.emit(
                f"未识别到{'放生' if should_release else '锁定'}按钮，跳过"
            )
            return False, False

        time.sleep(0.3)

        if self.worker._check_popup_and_abort_release(released_count):
            return None, None

        screen_right = cfg.window_offset_x + cfg.screen_width - 10
        screen_top = cfg.window_offset_y + 10
        ctypes.windll.user32.SetCursorPos(screen_right, screen_top)

        self.worker.smart_sleep(0.8)

        if self.worker._check_popup_and_abort_release(released_count):
            return None, None

        if not self.worker.running or self.worker.paused:
            return False, False

        return True, should_release

    def _process_inventory_grid(
        self,
        scaled_zone_x,
        scaled_zone_y,
        scaled_cell_width,
        scaled_cell_height,
        scaled_star_offset_x,
        scaled_star_offset_y,
        scaled_star_width,
        scaled_star_height,
    ):
        """
        处理鱼桶网格，检测并放生/锁定鱼

        Args:
            zone: 区域配置
            scaled_zone_x: 区域 x 坐标
            scaled_zone_y: 区域 y 坐标
            scaled_cell_width: 单元格宽度
            scaled_cell_height: 单元格高度
            scaled_star_offset_x: 星星偏移 x
            scaled_star_offset_y: 星星偏移 y
            scaled_star_width: 星星宽度
            scaled_star_height: 星星高度

        Returns:
            int: 放生的鱼数量
        """
        released_count = 0
        locked_detected = False

        for row in range(4):
            if not self.worker.running or self.worker.paused or locked_detected:
                break

            while True:
                if not self.worker.running or self.worker.paused:
                    break

                if self.worker._check_popup_and_abort_release(released_count):
                    return released_count

                action_in_row = False
                valid_fish_count = 0
                for col in range(4):
                    if not self.worker.running or self.worker.paused:
                        break

                    lock_size = int(60 * cfg.scale)
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
                    lock_region = (lock_x, lock_y, lock_size, lock_size)

                    lock_detected = self.worker.vision.detect_lock_icon(lock_region)
                    if lock_detected:
                        self.worker.log_updated.emit(
                            f"位置({row},{col})检测到锁定图标，停止检测"
                        )
                        locked_detected = True
                        break

                    star_x = (
                        scaled_zone_x + col * scaled_cell_width + scaled_star_offset_x
                    )
                    star_y = (
                        scaled_zone_y + row * scaled_cell_height + scaled_star_offset_y
                    )
                    star_region = (
                        star_x,
                        star_y,
                        scaled_star_width,
                        scaled_star_height,
                    )

                    quality = self._detect_fish_quality(star_region, row, col)
                    if quality is None:
                        continue

                    valid_fish_count += 1

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

                    if not self.worker.running or self.worker.paused:
                        break

                    if self.worker._check_popup_and_abort_release(released_count):
                        return released_count

                    fish_x = (
                        scaled_zone_x + col * scaled_cell_width + scaled_cell_width // 2
                    )
                    fish_y = (
                        scaled_zone_y
                        + row * scaled_cell_height
                        + scaled_cell_height // 2
                    )

                    is_protected = self._check_fish_protection(
                        fish_x, fish_y, quality, row, col, released_count
                    )
                    if is_protected is None:
                        return released_count
                    if is_protected:
                        should_release = False

                    success, should_increment = self._execute_fish_action(
                        fish_x,
                        fish_y,
                        should_release,
                        quality,
                        row,
                        col,
                        scaled_zone_x,
                        scaled_zone_y,
                        scaled_cell_width,
                        scaled_cell_height,
                        released_count,
                    )

                    if success is None:
                        return released_count
                    if not success:
                        continue

                    if should_increment:
                        released_count += 1
                        action_in_row = True
                    elif row == 0:
                        action_in_row = True

                    self.worker.smart_sleep(0.3)
                    break

                if valid_fish_count == 0 or not action_in_row or locked_detected:
                    break

        if locked_detected:
            self.worker.log_updated.emit("检测到锁定，停止所有检测")

        return released_count

    def check_and_auto_release(self):
        """检查鱼桶并执行自动放生"""
        if not cfg.global_settings.get("auto_release_enabled", False):
            return

        cfg.update_game_window()
        self.worker.log_updated.emit("开始自动放生...")
        self.worker.status_updated.emit("自动放生中")

        # 打开鱼桶
        if not self._open_fish_bucket():
            return 0

        zone = cfg.REGIONS["fish_inventory"]["zones"][0]
        zone_id = zone["id"]
        self.worker.log_updated.emit(f"检测区域 {zone_id}...")

        grid = zone["grid"]
        zone_rect = cfg.get_bottom_right_rect(zone["coords"])
        scaled_zone_x, scaled_zone_y = zone_rect[0], zone_rect[1]
        scaled_cell_width = int(grid["cell_width"] * cfg.scale)
        scaled_cell_height = int(grid["cell_height"] * cfg.scale)
        scaled_star_offset_x = int(grid["star_offset"][0] * cfg.scale)
        scaled_star_offset_y = int(grid["star_offset"][1] * cfg.scale)
        scaled_star_width = int(grid["star_size"][0] * cfg.scale)
        scaled_star_height = int(grid["star_size"][1] * cfg.scale)

        released_count = self._process_inventory_grid(
            scaled_zone_x,
            scaled_zone_y,
            scaled_cell_width,
            scaled_cell_height,
            scaled_star_offset_x,
            scaled_star_offset_y,
            scaled_star_width,
            scaled_star_height,
        )

        self.worker.inputs.press_key("ESC")
        self.worker.smart_sleep(0.5)

        if self.worker.paused:
            self.worker.log_updated.emit(f"放生被暂停，已放生{released_count}条鱼")
            self.worker.status_updated.emit("已暂停")
        else:
            self.worker.log_updated.emit(f"自动放生完成，共放生{released_count}条鱼")
            self.worker.status_updated.emit("运行中")

        return released_count

    def execute_single_release(self):
        """执行单条放生操作"""
        try:
            self.worker.inputs.hold_key("C")
            self.worker.msleep(300)

            bucket_pos = self.worker.vision.find_template("tong_gray", threshold=0.8)
            self.worker.msleep(200)

            if bucket_pos:
                ctypes.windll.user32.SetCursorPos(
                    bucket_pos[0] + cfg.window_offset_x,
                    bucket_pos[1] + cfg.window_offset_y,
                )
                self.worker.msleep(500)

            self.worker.inputs.release_key("C")
            self.worker.msleep(1200)

            if not bucket_pos:
                self.worker.log_updated.emit("未识别到桶图标，放生操作失败。")
                return

            fish_pos = cfg.REGIONS["fish_inventory"]["single_release_fish_pos"]
            fish_rect = cfg.get_bottom_right_rect((fish_pos[0], fish_pos[1], 1, 1))
            fish_x = fish_rect[0]
            fish_y = fish_rect[1]

            self.worker.msleep(200)
            self.worker.inputs.click(
                fish_x + cfg.window_offset_x, fish_y + cfg.window_offset_y
            )
            self.worker.msleep(800)

            offset = cfg.REGIONS["fish_inventory"]["single_release_button_offset"]
            release_x = fish_x + int(offset[0] * cfg.scale)
            release_y = fish_y + int(offset[1] * cfg.scale)
            self.worker.msleep(200)

            self.worker.inputs.click(
                release_x + cfg.window_offset_x, release_y + cfg.window_offset_y
            )
            self.worker.log_updated.emit("已点击放生按钮，鱼已放生")
            self.worker.msleep(800)

            self.worker.inputs.press_key("ESC")
            self.worker.msleep(500)

        except Exception as e:
            self.worker.log_updated.emit(f"单条放生操作发生错误: {e}")
            self.worker.inputs.press_key("ESC")
