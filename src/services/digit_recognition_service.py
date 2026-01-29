"""
数字识别服务
负责数字识别和鱼饵数量检测
"""

import cv2
import numpy as np
import time
from src.config import cfg


class DigitRecognitionService:
    """数字识别服务类"""

    def __init__(self, screenshot_service, template_service):
        """
        初始化数字识别服务

        Args:
            screenshot_service: ScreenshotService 实例
            template_service: TemplateService 实例
        """
        self.screenshot_service = screenshot_service
        self.template_service = template_service

    def get_bait_amount(self, region=None, threshold=0.75, expect_double_digit=False):
        """
        精准识别鱼饵数量

        Args:
            region: 检测区域
            threshold: 匹配阈值
            expect_double_digit: 是否期望两位数

        Returns:
            int: 鱼饵数量，或 None
        """
        if region is None:
            region = cfg.get_rect("bait_count")

        screenshot = self.screenshot_service.screenshot(region)
        result = self._detect_digits_raw(screenshot, threshold, return_details=False)

        if result is not None and expect_double_digit:
            if result < 10:
                return None

        return result

    def _detect_single_digit(self, img, threshold):
        """
        检测单个数字

        Returns:
            int: 数字，或 None
        """
        self.template_service._ensure_loaded()
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        best_match = -1
        max_score = -1

        for i in range(10):
            template_name = f"{i}_grayscale"
            template = self.template_service.templates.get(template_name)
            if template is None:
                continue

            t_h, t_w = template.shape[:2]
            i_h, i_w = gray_img.shape[:2]

            if t_h > i_h or t_w > i_w:
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
        基础数字检测

        Returns:
            int 或 (int, list)
        """
        self.template_service._ensure_loaded()
        gray_screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        found_digits = []

        for i in range(10):
            template_name = f"{i}_grayscale"
            template = self.template_service.templates.get(template_name)
            if template is None:
                continue

            t_h, t_w = template.shape[:2]
            i_h, i_w = gray_screenshot.shape[:2]

            if t_h > i_h or t_w > i_w:
                continue

            res = cv2.matchTemplate(gray_screenshot, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            for pt in zip(*loc[::-1]):
                found_digits.append({"digit": i, "x": pt[0]})

        if not found_digits:
            return (None, []) if return_details else None

        found_digits.sort(key=lambda d: d["x"])

        unique_digits = []
        if found_digits:
            unique_digits.append(found_digits[0])
            for i in range(1, len(found_digits)):
                if found_digits[i]["x"] > unique_digits[-1]["x"] + 5:
                    unique_digits.append(found_digits[i])

        try:
            number_str = "".join([str(d["digit"]) for d in unique_digits])
            result = int(number_str)
            return (result, unique_digits) if return_details else result
        except (ValueError, TypeError):
            return (None, []) if return_details else None

    def _detect_digits_raw(self, img, threshold, return_details=False):
        """
        多尺度数字检测

        Returns:
            int 或 (int, list)
        """
        self.template_service._ensure_loaded()
        gray_screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        candidates = []

        search_scales = {1.0, cfg.scale}
        search_scales.update(np.arange(0.5, 3.1, 0.25))
        sorted_scales = sorted(list(search_scales))

        for i in range(10):
            template_name = f"{i}_grayscale"
            raw_t = self.template_service.raw_templates.get(template_name)
            if raw_t is None:
                continue

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

        best_cand = max(candidates, key=lambda d: d["score"])
        ref_scale = best_cand["scale"]

        candidates = [c for c in candidates if abs(c["scale"] - ref_scale) <= 0.25]
        candidates.sort(key=lambda d: d["score"], reverse=True)

        final_digits = []

        for cand in candidates:
            is_duplicate = False
            for kept in final_digits:
                center1 = cand["x"] + cand["width"] / 2
                center2 = kept["x"] + kept["width"] / 2
                dist = abs(center1 - center2)

                min_dist = (cand["width"] + kept["width"]) / 2 * 0.85

                if dist < min_dist:
                    is_duplicate = True
                    break

            if not is_duplicate:
                final_digits.append(cand)

        final_digits.sort(key=lambda d: d["x"])

        try:
            number_str = "".join([str(d["digit"]) for d in final_digits])
            result = int(number_str)
            return (result, final_digits) if return_details else result
        except (ValueError, TypeError):
            return (None, []) if return_details else None

    def wait_for_bait_change(self, timeout=30):
        """
        等待鱼饵数量变化

        Returns:
            bool: 是否检测到变化
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
            time.sleep(0.5)

        print("Timeout waiting for bait change.")
        return False
