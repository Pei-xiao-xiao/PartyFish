"""
模板管理和匹配服务
负责模板加载、动态缩放和各种模板匹配功能
"""

import cv2
import numpy as np
import os
from src.config import cfg


class TemplateService:
    """模板管理和匹配服务类"""

    def __init__(self, screenshot_service):
        """
        初始化模板服务

        Args:
            screenshot_service: ScreenshotService 实例
        """
        self.screenshot_service = screenshot_service
        self.templates = {}  # 缩放后的模板
        self.raw_templates = {}  # 原始未缩放的模板
        self._loaded = False
        self._last_scale = None  # 记录上次使用的缩放比例
        self.uno_template = None

    def _ensure_loaded(self):
        """确保模板已加载，并在缩放变化时重新缩放"""
        if not self._loaded:
            self.load_templates()
            self._loaded = True
            self._last_scale = cfg.scale
            return

        if self._last_scale != cfg.scale:
            self._rescale_templates()
            self._last_scale = cfg.scale

    def load_templates(self):
        """从磁盘加载 PNG 模板"""
        resources_path = cfg._get_base_path() / "resources"

        for filename in os.listdir(resources_path):
            if filename.endswith(".png"):
                file_path = os.path.join(resources_path, filename)
                img = cv2.imdecode(
                    np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_UNCHANGED
                )
                if img is None:
                    continue

                template_name = os.path.splitext(filename)[0]
                self.raw_templates[template_name] = img

        self._rescale_templates()

    def _rescale_templates(self):
        """基于当前 cfg.scale 重新缩放所有模板"""
        self.templates.clear()

        for name, raw_img in self.raw_templates.items():
            if cfg.scale != 1.0:
                width = int(raw_img.shape[1] * cfg.scale)
                height = int(raw_img.shape[0] * cfg.scale)
                width = max(width, 1)
                height = max(height, 1)

                interpolation = cv2.INTER_LINEAR if cfg.scale > 1.0 else cv2.INTER_AREA
                img = cv2.resize(raw_img, (width, height), interpolation=interpolation)
            else:
                img = raw_img.copy()

            self.templates[name] = img

    def find_template(self, template_name, region=None, threshold=0.8):
        """
        基础模板匹配

        Args:
            template_name: 模板名称
            region: 搜索区域
            threshold: 匹配阈值

        Returns:
            (center_x, center_y) 或 None
        """
        self._ensure_loaded()
        screenshot = self.screenshot_service.screenshot(region)
        template = self.templates.get(template_name)

        if template is None:
            raise ValueError(f"Template '{template_name}' not found.")

        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            return None

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

    def find_template_in_image(self, template_name, image, threshold=0.8):
        """
        在给定图像中查找模板（多尺度匹配）

        Returns:
            (center_x, center_y, width, height) 或 None
        """
        self._ensure_loaded()

        raw_template = self.raw_templates.get(template_name)
        if raw_template is None:
            return None

        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

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
            return (center_x, center_y, best_size[0], best_size[1])

        return None

    def find_template_popup(self, template_name, region=None, threshold=0.8):
        """
        弹窗专用模板匹配（使用 popup_scale）

        Returns:
            (center_x, center_y) 或 None
        """
        self._ensure_loaded()
        screenshot = self.screenshot_service.screenshot(region)

        raw_template = self.raw_templates.get(template_name)
        if raw_template is None:
            raise ValueError(f"Template '{template_name}' not found.")

        popup_scale = min(cfg.scale_x, cfg.scale_y)
        if popup_scale != 1.0:
            width = int(raw_template.shape[1] * popup_scale)
            height = int(raw_template.shape[0] * popup_scale)
            width = max(width, 1)
            height = max(height, 1)
            template = cv2.resize(
                raw_template, (width, height), interpolation=cv2.INTER_AREA
            )
        else:
            template = raw_template

        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            return None

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
        返回模板匹配的分数和位置

        Returns:
            (score, (x, y)) 或 None
        """
        self._ensure_loaded()
        screenshot = self.screenshot_service.screenshot(region)
        template = self.templates.get(template_name)

        if template is None:
            return None

        t_h, t_w = template.shape[:2]
        s_h, s_w = screenshot.shape[:2]
        if t_h > s_h or t_w > s_w:
            return None

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

    def find_uno_card(self, region=None, threshold=0.8):
        """
        识别 UNO 卡片（tiao_gray 模板）

        Returns:
            bool: 是否识别到 UNO 卡片
        """
        self._ensure_loaded()

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

        if region is None:
            region = cfg.get_rect("UNO卡牌")

        screenshot = self.screenshot_service.screenshot(region)
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

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

    def detect_lock_icon(self, region):
        """检测指定区域是否有锁定图标"""
        self._ensure_loaded()

        raw_template = self.raw_templates.get("lock_grayscale")
        if raw_template is None:
            print("[警告] lock_grayscale 模板未加载")
            return False

        screenshot = self.screenshot_service.screenshot(region)
        if screenshot is None or screenshot.size == 0:
            return False

        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        if len(raw_template.shape) == 3:
            gray_template = cv2.cvtColor(raw_template, cv2.COLOR_BGR2GRAY)
        else:
            gray_template = raw_template

        best_score = 0
        for scale in [0.5, 0.75, 1.0, cfg.scale, 1.5]:
            w = int(gray_template.shape[1] * scale)
            h = int(gray_template.shape[0] * scale)
            w = max(w, 1)
            h = max(h, 1)

            if w > gray_screenshot.shape[1] or h > gray_screenshot.shape[0]:
                continue

            resized_template = cv2.resize(
                gray_template, (w, h), interpolation=cv2.INTER_LINEAR
            )

            result = cv2.matchTemplate(
                gray_screenshot, resized_template, cv2.TM_CCOEFF_NORMED
            )
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val

        print(f"[锁定检测] 匹配分数: {best_score:.3f}")
        return best_score >= 0.8
