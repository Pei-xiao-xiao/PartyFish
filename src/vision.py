import cv2
import numpy as np
import mss
import os
import time
import sys
import threading
from src.config import cfg
from rapidocr_onnxruntime import RapidOCR


class Vision:
    def __init__(self):
        print("Initializing Vision (Lazy)...")
        self.templates = {}  # 缩放后的模板
        self.raw_templates = {}  # 原始未缩放的模板
        self._loaded = False
        self._last_scale = None  # 记录上次使用的缩放比例
        # 线程锁，用于保护截图操作的线程安全
        self._screenshot_lock = threading.Lock()

        # 使用 threading.local() 来存储每个线程独立的 mss 实例
        # 解决 AttributeError: '_thread._local' object has no attribute 'data'
        self._thread_local = threading.local()

        # UNO 模板
        self.uno_template = None

        # OCR引擎
        self.ocr = RapidOCR()

    def _ensure_loaded(self):
        # 如果未加载，则加载
        if not self._loaded:
            self.load_templates()
            self._loaded = True
            print(f"Vision templates loaded. Count: {len(self.templates)}")
            # load_templates 内部会调用 _rescale_templates，所以这里设置 _last_scale
            self._last_scale = cfg.scale
            return

        # 如果已加载，检查缩放是否变化
        if self._last_scale != cfg.scale:
            print(
                f"[Vision] Scale changed from {self._last_scale} to {cfg.scale}. Rescaling templates..."
            )
            self._rescale_templates()
            self._last_scale = cfg.scale

    def load_templates(self):
        print("Loading templates from disk...")
        resources_path = cfg._get_base_path() / "resources"

        for filename in os.listdir(resources_path):
            if filename.endswith(".png"):
                # Load image with alpha channel, supporting Chinese characters in path
                file_path = os.path.join(resources_path, filename)
                img = cv2.imdecode(
                    np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED
                )
                if img is None:
                    continue

                # Extract template name from filename
                template_name = os.path.splitext(filename)[0]

                # 保存原始模板
                self.raw_templates[template_name] = img

        # 初始缩放
        self._rescale_templates()

    def _rescale_templates(self):
        """Re-generate scaled templates from raw_templates based on current cfg.scale"""
        self.templates.clear()

        for name, raw_img in self.raw_templates.items():
            if cfg.scale != 1.0:
                width = int(raw_img.shape[1] * cfg.scale)
                height = int(raw_img.shape[0] * cfg.scale)
                # Ensure at least 1x1
                width = max(width, 1)
                height = max(height, 1)

                # 优化插值：放大用 LINEAR，缩小用 AREA
                interpolation = cv2.INTER_LINEAR if cfg.scale > 1.0 else cv2.INTER_AREA
                img = cv2.resize(raw_img, (width, height), interpolation=interpolation)
            else:
                img = raw_img.copy()

            self.templates[name] = img

    def screenshot(self, region=None):
        # 使用线程锁保护截图操作，避免多线程同时访问 mss 和 cfg
        with self._screenshot_lock:
            # 每次截图前刷新窗口状态，以应对窗口移动或模式切换
            cfg.update_game_window()

            # 重试机制：应对 mss 在某些情况下 (Windows/多线程) 可能出现的 _thread._local 错误
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # 确保当前线程的 sct 实例存在
                    if (
                        not hasattr(self._thread_local, "sct")
                        or self._thread_local.sct is None
                    ):
                        self._thread_local.sct = mss.mss()

                    if region is None:
                        # 截取整个游戏窗口（考虑偏移）
                        monitor = {
                            "left": cfg.window_offset_x,
                            "top": cfg.window_offset_y,
                            "width": cfg.screen_width,
                            "height": cfg.screen_height,
                        }
                    else:
                        # 区域坐标是相对游戏窗口的，需要加上窗口偏移
                        monitor = {
                            "left": region[0] + cfg.window_offset_x,
                            "top": region[1] + cfg.window_offset_y,
                            "width": region[2],
                            "height": region[3],
                        }

                    # Grab the data using the persistent instance
                    sct_img = self._thread_local.sct.grab(monitor)

                    # Convert to a numpy array
                    img = np.array(sct_img)

                    # Convert BGRA to BGR
                    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

                except Exception as e:
                    # 如果发生错误，尝试关闭并重建 sct 实例
                    try:
                        if (
                            hasattr(self._thread_local, "sct")
                            and self._thread_local.sct
                        ):
                            self._thread_local.sct.close()
                    except:
                        pass
                    self._thread_local.sct = None

                    if attempt < max_retries - 1:
                        time.sleep(0.1)
                        continue
                    # 其他错误直接抛出
                    raise e

    def get_bait_amount(self, region=None, threshold=0.75, expect_double_digit=False):
        """
        精准识别鱼饵数量。

        参数：
        - threshold: 匹配阈值（默认 0.75）
        - expect_double_digit: 是否期望两位数。
          如果为 True，则只尝试两位数识别，失败则返回 None，不回退到一位数策略。
          这可以防止 31 被误识别为 3 的情况。
        """
        if region is None:
            region = cfg.get_rect("bait_count")

        if region is None:
            region = cfg.get_rect("bait_count")

        screenshot = self.screenshot(region)

        # Use the robust, multi-scale, multi-instance digit detection.
        # This handles:
        # 1. Scale variations (fixing the "7 recognized as 1" issue due to template size mismatch)
        # 2. Overlapping/duplicate digits (cleaning up noise)
        # 3. Variable positioning (no rigid slicing)
        result = self._detect_digits_raw(screenshot, threshold, return_details=False)

        # expect_double_digit logic:
        # If we expect a double digit (e.g., >= 10) but get a single digit, return None?
        # The original docstring says: "If True, only try double digit recognition... used to prevent 31 being read as 3".
        # Since _detect_digits_raw detects *all* digits, if it sees "31", it returns 31.
        # It won't return 3 unless it missed the 1.
        # With the new robust algorithm, missing a digit is less likely.
        # However, to maintain the contract: if return value < 10 and expect_double_digit is True, return None.

        if result is not None and expect_double_digit:
            if result < 10:
                return None

        return result

    def _detect_single_digit(self, img, threshold):
        """
        Detects the single best matching digit in a small image crop.
        Returns the digit (int) or None.
        """
        self._ensure_loaded()
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        best_match = -1
        max_score = -1

        for i in range(10):
            template_name = f"{i}_grayscale"
            template = self.templates.get(template_name)
            if template is None:
                continue

            # Resize template if it's larger than the image crop
            t_h, t_w = template.shape[:2]
            i_h, i_w = gray_img.shape[:2]

            if t_h > i_h or t_w > i_w:
                # Skip if template is bigger than crop (shouldn't happen if config is right)
                continue

            res = cv2.matchTemplate(gray_img, template, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            if max_val > max_score:
                max_score = max_val
                best_match = i

        if max_score >= threshold:
            return best_match

        return None

    def _detect_digits(self, img, threshold, return_details=False):
        """
        Helper method to detect digits in a given image (BGR).
        """
        self._ensure_loaded()
        gray_screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found_digits = []
        for i in range(10):
            template_name = f"{i}_grayscale"
            template = self.templates.get(template_name)
            if template is None:
                continue

            # Resize template if it's larger than the image crop - SAFETY CHECK
            t_h, t_w = template.shape[:2]
            i_h, i_w = gray_screenshot.shape[:2]

            if t_h > i_h or t_w > i_w:
                # Skip if template is bigger than crop
                continue

            res = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            for pt in zip(*loc[::-1]):
                found_digits.append({"digit": i, "x": pt[0]})

        if not found_digits:
            return (None, []) if return_details else None

        found_digits.sort(key=lambda d: d["x"])

        # Filter out overlapping detections
        unique_digits = []
        if found_digits:
            unique_digits.append(found_digits[0])
            for i in range(1, len(found_digits)):
                # If the x-coordinate is far enough from the last one, it's a new digit
                if (
                    found_digits[i]["x"] > unique_digits[-1]["x"] + 5
                ):  # 5px horizontal threshold
                    unique_digits.append(found_digits[i])

        try:
            number_str = "".join([str(d["digit"]) for d in unique_digits])
            result = int(number_str)
            return (result, unique_digits) if return_details else result
        except (ValueError, TypeError):
            return (None, []) if return_details else None

            # 如果该数字的最佳匹配超过阈值，加入候选
            if best_digit_score >= threshold:
                candidates.append(
                    {
                        "digit": i,
                        "x": best_digit_x,
                        "score": best_digit_score,
                        "width": sorted_scales[0]
                        * raw_t.shape[1],  # 估算最小宽度用于排序，实际去重用动态宽度
                    }
                )
                # 记录该候选对应的实际宽度（基于最佳 scale）
                # 为了简化，我们上面的循环没有保存最佳 scale，这里需要优化一下逻辑
                # 但实际上，我们可以直接存储 best_digit_width

    def _detect_digits_raw(self, img, threshold, return_details=False):
        """
        多尺度数字检测：
        扫描多个缩放比例的模板，以适应游戏 UI 缩放不跟随分辨率的情况（如高 DPI 屏幕）。
        虽然计算量稍大，但对于卖鱼结算（低频操作）是可接受的。
        """
        self._ensure_loaded()
        gray_screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 收集所有匹配候选结果：(score, x, digit, width)
        candidates = []

        # 定义要扫描的缩放比例列表
        search_scales = {1.0, cfg.scale}
        search_scales.update(np.arange(0.5, 3.1, 0.25))

        sorted_scales = sorted(list(search_scales))

        for i in range(10):
            template_name = f"{i}_grayscale"
            raw_t = self.raw_templates.get(template_name)
            if raw_t is None:
                continue

            # 为每个数字找到最佳匹配的 scale 和位置
            for scale in sorted_scales:
                w = int(raw_t.shape[1] * scale)
                h = int(raw_t.shape[0] * scale)
                w = max(w, 1)
                h = max(h, 1)

                if w > gray_screenshot.shape[1] or h > gray_screenshot.shape[0]:
                    continue

                resized_t = cv2.resize(raw_t, (w, h), interpolation=cv2.INTER_LINEAR)
                res = cv2.matchTemplate(
                    gray_screenshot, resized_t, cv2.TM_CCOEFF_NORMED
                )

                # Find all matches above threshold
                loc = np.where(res >= threshold)
                for pt in zip(*loc[::-1]):
                    score = res[pt[1], pt[0]]
                    candidates.append(
                        {
                            "digit": i,
                            "x": pt[0],
                            "score": float(score),
                            "width": w,
                            "scale": scale,
                        }
                    )

        if not candidates:
            return (None, []) if return_details else None

        # Scale Consistency Filtering:
        # Numbers in the same price/text should have roughly the same scale.
        # We find the candidate with the highest confidence and use its scale as the reference.
        # This effectively filters out false positives looking like "1" at very small scales.
        best_cand = max(candidates, key=lambda d: d["score"])
        ref_scale = best_cand["scale"]

        # Filter candidates that deviate too much from the reference scale (e.g., more than 20%)
        # Note: We use a loose threshold because slight scale variations might exist?
        # Actually standard template matching uses discrete scales, so we can be relatively strict.
        # Let's say +/- 0.25 difference is allowed.
        candidates = [c for c in candidates if abs(c["scale"] - ref_scale) <= 0.25]

        # 按置信度排序（高的在前）
        candidates.sort(key=lambda d: d["score"], reverse=True)

        # 去重：如果两个候选结果重叠超过一定程度，则丢弃分数低的那个
        final_digits = []

        for cand in candidates:
            is_duplicate = False
            for kept in final_digits:
                # 计算中心点距离
                center1 = cand["x"] + cand["width"] / 2
                center2 = kept["x"] + kept["width"] / 2
                dist = abs(center1 - center2)

                # 动态阈值：取两个宽度平均值的一半
                # 0.85系数是为了更激进地去重，特别是针对同一位置的重复检测
                min_dist = (cand["width"] + kept["width"]) / 2 * 0.85

                if dist < min_dist:
                    is_duplicate = True
                    break

            if not is_duplicate:
                final_digits.append(cand)

        # 最后按 x 坐标排序，组成数字
        final_digits.sort(key=lambda d: d["x"])

        try:
            number_str = "".join([str(d["digit"]) for d in final_digits])
            result = int(number_str)
            return (result, final_digits) if return_details else result
        except (ValueError, TypeError):
            return (None, []) if return_details else None

    def wait_for_bait_change(self, timeout=30):
        """
        Waits for the bait count to decrease.
        """
        initial_amount = self.get_bait_amount()
        if initial_amount is None:
            print("Could not determine initial bait amount.")
            return False

        start_time = time.time()
        while time.time() - start_time < timeout:
            current_amount = self.get_bait_amount()
            if current_amount is not None and current_amount < initial_amount:
                print(f"Bait amount changed from {initial_amount} to {current_amount}.")
                return True
            time.sleep(0.5)  # Polling interval

        print("Timeout waiting for bait change.")
        return False

    def find_template(self, template_name, region=None, threshold=0.8):
        self._ensure_loaded()
        screenshot = self.screenshot(region)
        template = self.templates.get(template_name)

        if template is None:
            raise ValueError(f"Template '{template_name}' not found.")

        # 安全检查：确保模板不比截图大
        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            # 模板比截图大，无法匹配，返回 None 而不是崩溃
            return None

        # Handle alpha channel and dimensionality
        if len(template.shape) == 3:
            if template.shape[2] == 4:
                # Separate the alpha channel as a mask
                mask = template[:, :, 3]
                template = template[:, :, :3]
                # Use the mask in template matching
                result = cv2.matchTemplate(
                    screenshot, template, cv2.TM_CCORR_NORMED, mask=mask
                )
            else:
                # BGR Template
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        else:
            # Grayscale Template - convert screenshot to grayscale for matching
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            # Get the center of the found template
            template_w = template.shape[1]
            template_h = template.shape[0]
            center_x = max_loc[0] + template_w // 2
            center_y = max_loc[1] + template_h // 2
            return (center_x, center_y)

        return None

    def find_template_in_image(self, template_name, image, threshold=0.8):
        """
        在给定的图片中查找模板（不进行截图）。
        使用多尺度匹配以适应不同分辨率。
        返回 (center_x, center_y, width, height) 或 None。
        """
        self._ensure_loaded()

        # 使用原始模板进行多尺度匹配
        raw_template = self.raw_templates.get(template_name)
        if raw_template is None:
            return None

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # 多尺度匹配
        best_score = -1
        best_loc = None
        best_size = None

        for scale in [0.5, 0.75, 1.0, 1.25, 1.5, cfg.scale]:
            w = int(raw_template.shape[1] * scale)
            h = int(raw_template.shape[0] * scale)
            w = max(w, 1)
            h = max(h, 1)

            if w > gray_image.shape[1] or h > gray_image.shape[0]:
                continue

            resized_t = cv2.resize(raw_template, (w, h), interpolation=cv2.INTER_LINEAR)

            # 转灰度
            if len(resized_t.shape) == 3:
                resized_t_gray = cv2.cvtColor(resized_t, cv2.COLOR_BGR2GRAY)
            else:
                resized_t_gray = resized_t

            result = cv2.matchTemplate(gray_image, resized_t_gray, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_size = (w, h)

        if best_score >= threshold and best_loc and best_size:
            center_x = best_loc[0] + best_size[0] // 2
            center_y = best_loc[1] + best_size[1] // 2
            # 返回 (中心x, 中心y, 宽度, 高度)
            return (center_x, center_y, best_size[0], best_size[1])

        return None

    def find_template_popup(self, template_name, region=None, threshold=0.8):
        """
        专门用于中心锚定区域（弹窗）的模板匹配。
        使用 popup_scale = min(scale_x, scale_y) 动态缩放模板，解决比例不匹配问题。
        """
        self._ensure_loaded()
        screenshot = self.screenshot(region)

        # 获取原始模板
        raw_template = self.raw_templates.get(template_name)
        if raw_template is None:
            raise ValueError(f"Template '{template_name}' not found.")

        # 使用 popup_scale 缩放模板
        popup_scale = min(cfg.scale_x, cfg.scale_y)
        if popup_scale != 1.0:
            width = int(raw_template.shape[1] * popup_scale)
            height = int(raw_template.shape[0] * popup_scale)
            # 确保缩放后尺寸至少为 1x1
            width = max(width, 1)
            height = max(height, 1)
            template = cv2.resize(
                raw_template, (width, height), interpolation=cv2.INTER_AREA
            )
        else:
            template = raw_template

        # 安全检查：确保模板不比截图大
        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            # 模板比截图大，无法匹配，返回 None 而不是崩溃
            return None

        # Handle alpha channel and dimensionality
        if len(template.shape) == 3:
            if template.shape[2] == 4:
                mask = template[:, :, 3]
                template = template[:, :, :3]
                result = cv2.matchTemplate(
                    screenshot, template, cv2.TM_CCORR_NORMED, mask=mask
                )
            else:
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        else:
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            template_w = template.shape[1]
            template_h = template.shape[0]
            center_x = max_loc[0] + template_w // 2
            center_y = max_loc[1] + template_h // 2
            return (center_x, center_y)

        return None

    def find_template_with_score(self, template_name, region=None):
        """
        返回模板匹配的分数和位置，用于调试。
        返回 (score, (x, y)) 或 None。
        """
        self._ensure_loaded()
        screenshot = self.screenshot(region)
        template = self.templates.get(template_name)

        if template is None:
            return None

        # 安全检查：确保模板不比截图大
        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            # 模板比截图大，无法匹配，返回 None 而不是崩溃
            return None

        # Handle alpha channel and dimensionality
        if len(template.shape) == 3:
            if template.shape[2] == 4:
                mask = template[:, :, 3]
                template = template[:, :, :3]
                result = cv2.matchTemplate(
                    screenshot, template, cv2.TM_CCORR_NORMED, mask=mask
                )
            else:
                result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        else:
            gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
            result = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        template_w = template.shape[1]
        template_h = template.shape[0]
        center_x = max_loc[0] + template_w // 2
        center_y = max_loc[1] + template_h // 2

        return (max_val, (center_x, center_y))

    def draw_debug_rects(self, image, config, recognition_results=None):
        """
        Draw debug rectangles with Chinese labels and a legend on the image.
        recognition_results: 可选的识别结果列表，将显示在图例中
        """
        # --- DEBUGGING: Remove the big red square ---
        print("[DEBUG] Entering draw_debug_rects.")
        # cv2.rectangle(image, (0, 0), (100, 100), (0, 0, 255), -1) # Big Red Square REMOVED
        print(f"[DEBUG] Received config with {len(config)} items.")

        label_map = {
            "cast_rod": "抛竿检测",
            "cast_rod_ice": "冰钓抛竿",
            "wait_bite": "咬钩等待",
            "reel_in": "收杆检测",
            "bait_count": "鱼饵计数",
            "f3_menu": "F3菜单",
            "repair": "修理检测",
            "shangyu": "收鱼检测",
            "reel_in_star": "收杆判定",
            "jiashi_popup": "加时弹窗",
            "afk_popup": "AFK弹窗",
            "ocr_area": "OCR区域",
            "sell_price_area": "鱼干价格",
        }

        font_cjk = None
        pil_available = False
        font_load_error = ""

        try:
            from PIL import Image, ImageDraw, ImageFont

            pil_available = True

            # Try to load a font that supports Chinese
            try:
                font_cjk = ImageFont.truetype("msyh.ttc", 15)
            except IOError:
                try:
                    font_cjk = ImageFont.truetype("simhei.ttf", 15)
                except IOError:
                    font_load_error = "未找到中文字体(msyh.ttc, simhei.ttf)"
                    font_cjk = ImageFont.load_default()
        except ImportError:
            font_load_error = "PIL(Pillow)库未安装"
            print("PIL not found, falling back to English labels for debug overlay.")

        # If PIL is not available, draw basic boxes with OpenCV and return
        if not pil_available:
            cv2.putText(
                image,
                font_load_error,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 0, 255),
                2,
            )
            for name, rect_data in config.items():
                if name == "scale" or not isinstance(rect_data, list):
                    continue
                x, y, w, h = rect_data
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(
                    image,
                    name,
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    1,
                )
            return image

        # --- PIL Drawing Logic ---
        # 1. Convert OpenCV image to PIL image
        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil, "RGBA")  # Draw with transparency support

        # 2. Draw everything directly on the PIL image
        # --- Draw Legend Box ---
        legend_x, legend_y = 10, 10
        legend_line_height = 20
        legend_width = 350
        legend_content = ["调试图例:"]
        if font_load_error:
            legend_content.append(font_load_error)

        # 添加识别结果到图例（如果有）
        if recognition_results:
            legend_content.append("--- 识别结果 ---")
            legend_content.extend(recognition_results)
            legend_content.append("--- 区域坐标 ---")

        # Create a dictionary of rects that are valid and should be in the legend
        rects_for_legend = {
            k: config[k]
            for k in label_map
            if k in config and isinstance(config.get(k), list)
        }
        legend_content.extend(
            [
                f"- {label_map[name]}: ({rect[0]},{rect[1]},{rect[2]},{rect[3]})"
                for name, rect in rects_for_legend.items()
            ]
        )

        legend_height = len(legend_content) * legend_line_height + 10

        # Draw legend background (semi-transparent)
        draw.rectangle(
            [legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
            fill=(0, 0, 0, 128),
        )
        # Draw legend text
        for i, text in enumerate(legend_content):
            draw.text(
                (legend_x + 5, legend_y + 5 + i * legend_line_height),
                text,
                font=font_cjk,
                fill=(255, 255, 255),
            )

        # --- Draw Rectangles and Labels ---
        for name, rect_data in config.items():
            if name == "scale" or not isinstance(rect_data, list):
                continue

            # --- FINAL DEBUG STEP ---
            print(f"[DEBUG] Drawing rect: {name} with data {rect_data}")

            x, y, w, h = rect_data

            # Draw rectangle outline
            draw.rectangle([x, y, x + w, y + h], outline=(0, 255, 0), width=2)

            # 为 bait_count 区域额外显示切片区域
            if name == "bait_count":
                slice_width = int(cfg.BAIT_CROP_WIDTH1_BASE * cfg.scale)
                slice_width = max(slice_width, 1)

                # 左切片（红色）：用于识别十位
                draw.rectangle(
                    [x, y, x + slice_width, y + h], outline=(255, 0, 0), width=1
                )

                # 右切片（蓝色）：用于识别个位
                draw.rectangle(
                    [x + w - slice_width, y, x + w, y + h], outline=(0, 0, 255), width=1
                )

                # 中切片（黄色）：用于识别一位数
                center_start = x + (w - slice_width) // 2
                draw.rectangle(
                    [center_start, y, center_start + slice_width, y + h],
                    outline=(255, 255, 0),
                    width=1,
                )

            # Prepare label text
            label_text = label_map.get(name, name)

            # Use textbbox for modern Pillow, fallback to textsize
            try:
                bbox = draw.textbbox((0, 0), label_text, font=font_cjk)
                text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                text_w, text_h = draw.textsize(label_text, font=font_cjk)

            text_x = x
            text_y = y - text_h - 5
            if text_y < 0:
                text_y = y + h + 5

            # Draw semi-transparent background for the label
            draw.rectangle(
                [text_x, text_y, text_x + text_w, text_y + text_h], fill=(0, 0, 0, 128)
            )
            draw.text((text_x, text_y), label_text, font=font_cjk, fill=(0, 255, 0))

        # 3. Convert back to OpenCV image and update the original
        image[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        print("[DEBUG] Exiting draw_debug_rects.")
        return image

    def find_uno_card(self, region=None, threshold=0.8):
        """
        识别 UNO 卡片（tiao_gray 模板）
        使用本项目的缩放逻辑进行多尺度匹配

        Args:
            region: 检测区域 (x, y, w, h)，None 表示使用默认区域
            threshold: 匹配阈值

        Returns:
            bool: 是否识别到 UNO 卡片
        """
        self._ensure_loaded()

        # 加载 UNO 模板
        if self.uno_template is None:
            resources_path = cfg._get_base_path() / "resources"
            uno_path = resources_path / "tiao_gray.png"
            if uno_path.exists():
                img = cv2.imdecode(
                    np.fromfile(str(uno_path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE
                )
                if img is not None:
                    self.uno_template = img

        if self.uno_template is None:
            return False

        # 默认检测区域（右下角，基于 2560x1440）
        if region is None:
            base_x, base_y, base_w, base_h = 2242, 1314, 80, 40
            region = cfg.get_bottom_right_rect((base_x, base_y, base_w, base_h))

        screenshot = self.screenshot(region)
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        # 多尺度匹配
        best_score = 0
        for scale in [0.5, 0.75, 1.0, cfg.scale, 1.5, 2.0]:
            w = int(self.uno_template.shape[1] * scale)
            h = int(self.uno_template.shape[0] * scale)

            if w > gray_screenshot.shape[1] or h > gray_screenshot.shape[0]:
                continue

            resized_template = cv2.resize(
                self.uno_template, (w, h), interpolation=cv2.INTER_LINEAR
            )
            result = cv2.matchTemplate(
                gray_screenshot, resized_template, cv2.TM_CCOEFF_NORMED
            )
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val

        return best_score >= threshold

    def detect_star_color(self, image):
        """识别星星外围背景色（品质颜色），如果检测不到返回None"""
        if image is None or image.size == 0:
            return None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 优化后的颜色范围（更精确，减少重叠）
        color_ranges = {
            "gray": ([0, 0, 50], [180, 50, 210]),
            "green": ([35, 100, 150], [55, 200, 255]),  # #8FC659
            "blue": ([95, 100, 200], [115, 200, 255]),  # #6EACF1
            "purple": (
                [130, 100, 200],
                [150, 200, 255],
            ),  # #AA68F9 (调整范围避免与蓝色重叠)
            "yellow": ([15, 150, 200], [30, 255, 255]),  # #FAC439
        }

        # 按优先级检测（高品质优先，避免误判）
        priority_order = ["yellow", "purple", "blue", "green", "gray"]

        pixel_counts = {}
        for color in priority_order:
            lower, upper = color_ranges[color]
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            pixel_count = cv2.countNonZero(mask)
            pixel_counts[color] = pixel_count

        # 调试输出
        print(f"[颜色检测] 像素统计: {pixel_counts}")

        # 找出最大值和次大值
        sorted_counts = sorted(pixel_counts.items(), key=lambda x: x[1], reverse=True)
        max_color, max_pixels = sorted_counts[0]
        second_max_pixels = sorted_counts[1][1] if len(sorted_counts) > 1 else 0

        # 如果检测到的像素太少，说明没有星星
        if max_pixels < 10:
            print(f"[颜色检测] 像素数太少({max_pixels})，判定为无星星")
            return None

        # 【关键改进】如果检测为灰色，但紫色或黄色像素数也很多，则优先判定为高品质
        if max_color == "gray":
            purple_pixels = pixel_counts.get("purple", 0)
            yellow_pixels = pixel_counts.get("yellow", 0)

            # 如果紫色像素数超过灰色的20%且大于15个，判定为紫色（史诗）
            if purple_pixels > max_pixels * 0.2 and purple_pixels > 15:
                print(
                    f"[颜色检测] 灰色误判修正: 检测到紫色像素{purple_pixels}，修正为purple"
                )
                max_color = "purple"
                max_pixels = purple_pixels
            # 如果黄色像素数超过灰色的20%且大于15个，判定为黄色（传奇）
            elif yellow_pixels > max_pixels * 0.2 and yellow_pixels > 15:
                print(
                    f"[颜色检测] 灰色误判修正: 检测到黄色像素{yellow_pixels}，修正为yellow"
                )
                max_color = "yellow"
                max_pixels = yellow_pixels

        # 针对高品质（史诗、传奇）使用更严格的置信度要求
        if max_color in ["purple", "yellow"]:
            # 高品质要求：最大值必须是次大值的3倍以上
            required_ratio = 3.0
            if (
                second_max_pixels > 0
                and max_pixels < second_max_pixels * required_ratio
            ):
                print(
                    f"[颜色检测] 高品质({max_color})置信度不足: {max_pixels} < {second_max_pixels} * {required_ratio}"
                )
                return None
            # 额外要求：高品质必须有足够的像素数（至少30个）
            if max_pixels < 30:
                print(f"[颜色检测] 高品质({max_color})像素数不足: {max_pixels} < 30")
                return None
        else:
            # 普通品质：最大值必须是次大值的2倍以上
            if second_max_pixels > 0 and max_pixels < second_max_pixels * 2:
                print(f"[颜色检测] 置信度不足: {max_pixels} < {second_max_pixels} * 2")
                return None

        print(f"[颜色检测] 识别为: {max_color} (像素数: {max_pixels})")
        return max_color

    def find_text_position(self, text, region=None):
        """使用OCR检测文字位置，返回中心坐标(x, y)，未找到返回None"""
        screenshot = self.screenshot(region=region)

        result, _ = self.ocr(screenshot)
        if result is None:
            return None

        for item in result:
            detected_text = item[1]
            if text in detected_text:
                box = item[0]
                center_x = int((box[0][0] + box[2][0]) / 2)
                center_y = int((box[0][1] + box[2][1]) / 2)

                # 如果指定了region，需要加上region的偏移量
                if region:
                    center_x += region[0]
                    center_y += region[1]

                print(f"[OCR] 找到文字 '{text}' 在位置: ({center_x}, {center_y})")
                return (center_x, center_y)

        return None


# Instantiate the vision class to be used by other modules
vision = Vision()
