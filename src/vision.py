"""
视觉系统主类
作为服务协调器，委托给各个专门的服务类
"""

from src.services.screenshot_service import ScreenshotService
from src.services.template_service import TemplateService
from src.services.digit_recognition_service import DigitRecognitionService
from src.services.vision_utils_service import VisionUtilsService


class Vision:
    def __init__(self):
        print("Initializing Vision (Lazy)...")
        # 初始化所有服务
        self.screenshot_service = ScreenshotService()
        self.template_service = TemplateService(self.screenshot_service)
        self.digit_service = DigitRecognitionService(
            self.screenshot_service, self.template_service
        )
        self.utils_service = VisionUtilsService(self.screenshot_service)

    # 保持向后兼容的属性访问
    @property
    def templates(self):
        return self.template_service.templates

    @property
    def raw_templates(self):
        return self.template_service.raw_templates

    @property
    def uno_template(self):
        return self.template_service.uno_template

    @property
    def ocr(self):
        return self.utils_service.ocr

    # 模板管理方法（委托给 TemplateService）
    def _ensure_loaded(self):
        self.template_service._ensure_loaded()

    def load_templates(self):
        self.template_service.load_templates()

    def _rescale_templates(self):
        self.template_service._rescale_templates()

    # 截图方法（委托给 ScreenshotService）
    def screenshot(self, region=None):
        """委托给 ScreenshotService"""
        return self.screenshot_service.screenshot(region)

    # 模板匹配方法（委托给 TemplateService）
    def find_template(self, template_name, region=None, threshold=0.8):
        return self.template_service.find_template(template_name, region, threshold)

    def find_template_in_image(self, template_name, image, threshold=0.8):
        return self.template_service.find_template_in_image(
            template_name, image, threshold
        )

    def find_template_popup(self, template_name, region=None, threshold=0.8):
        return self.template_service.find_template_popup(
            template_name, region, threshold
        )

    def find_template_with_score(self, template_name, region=None):
        return self.template_service.find_template_with_score(template_name, region)

    def find_uno_card(self, region=None, threshold=0.8):
        return self.template_service.find_uno_card(region, threshold)

    def detect_lock_icon(self, region):
        return self.template_service.detect_lock_icon(region)

    # 数字识别方法（委托给 DigitRecognitionService）
    def get_bait_amount(self, region=None, threshold=0.75, expect_double_digit=False):
        return self.digit_service.get_bait_amount(
            region, threshold, expect_double_digit
        )

    def _detect_single_digit(self, img, threshold):
        return self.digit_service._detect_single_digit(img, threshold)

    def _detect_digits(self, img, threshold, return_details=False):
        return self.digit_service._detect_digits(img, threshold, return_details)

    def _detect_digits_raw(self, img, threshold, return_details=False):
        return self.digit_service._detect_digits_raw(img, threshold, return_details)

    def wait_for_bait_change(self, timeout=30):
        return self.digit_service.wait_for_bait_change(timeout)

    # OCR 和工具方法（委托给 VisionUtilsService）
    def find_text_position(self, text, region=None):
        return self.utils_service.find_text_position(text, region)

    def ocr_text_detection(self, image):
        return self.utils_service.ocr_text_detection(image)

    def detect_star_color(self, image):
        return self.utils_service.detect_star_color(image)

    def draw_debug_rects(self, image, config, recognition_results=None):
        return self.utils_service.draw_debug_rects(image, config, recognition_results)


# Instantiate the vision class to be used by other modules
vision = Vision()
