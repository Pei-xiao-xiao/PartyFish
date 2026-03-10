"""
视觉工具服务
负责 OCR、颜色检测和调试绘图功能
"""

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from src.config import cfg


class VisionUtilsService:
    """视觉工具服务类"""

    def __init__(self, screenshot_service):
        """
        初始化视觉工具服务

        Args:
            screenshot_service: ScreenshotService 实例
        """
        self.screenshot_service = screenshot_service
        self.ocr = RapidOCR()

    def find_text_position(self, text, region=None):
        """
        使用 OCR 检测文字位置

        Returns:
            (x, y): 中心坐标，或 None
        """
        screenshot = self.screenshot_service.screenshot(region=region)

        result, _ = self.ocr(screenshot)
        if result is None:
            return None

        for item in result:
            detected_text = item[1]
            if text in detected_text:
                box = item[0]
                center_x = int((box[0][0] + box[2][0]) / 2)
                center_y = int((box[0][1] + box[2][1]) / 2)

                if region:
                    center_x += region[0]
                    center_y += region[1]

                print(f"[OCR] 找到文字 '{text}' 在位置: ({center_x}, {center_y})")
                return (center_x, center_y)

        return None

    def ocr_text_detection(self, image):
        """使用 OCR 识别图像中的文字"""
        if image is None or image.size == 0:
            return None
        return self.ocr(image)

    def detect_star_color(self, image):
        """识别星星外围背景色（品质颜色）"""
        if image is None or image.size == 0:
            return None

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        color_ranges = {
            "gray": ([0, 0, 50], [180, 50, 210]),
            "green": ([35, 100, 150], [55, 200, 255]),
            "blue": ([95, 100, 200], [115, 200, 255]),
            "purple": ([130, 100, 200], [150, 200, 255]),
            "yellow": ([15, 150, 200], [30, 255, 255]),
        }

        priority_order = ["yellow", "purple", "blue", "green", "gray"]

        pixel_counts = {}
        for color in priority_order:
            lower, upper = color_ranges[color]
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            pixel_count = cv2.countNonZero(mask)
            pixel_counts[color] = pixel_count

        print(f"[颜色检测] 像素统计: {pixel_counts}")

        sorted_counts = sorted(pixel_counts.items(), key=lambda x: x[1], reverse=True)
        max_color, max_pixels = sorted_counts[0]
        second_max_pixels = sorted_counts[1][1] if len(sorted_counts) > 1 else 0

        if max_pixels < 10:
            print(f"[颜色检测] 像素数太少({max_pixels})，判定为无星星")
            return None

        if max_color == "gray":
            purple_pixels = pixel_counts.get("purple", 0)
            yellow_pixels = pixel_counts.get("yellow", 0)

            if purple_pixels > max_pixels * 0.2 and purple_pixels > 15:
                print(
                    f"[颜色检测] 灰色误判修正: 检测到紫色像素{purple_pixels}，修正为purple"
                )
                max_color = "purple"
                max_pixels = purple_pixels
            elif yellow_pixels > max_pixels * 0.2 and yellow_pixels > 15:
                print(
                    f"[颜色检测] 灰色误判修正: 检测到黄色像素{yellow_pixels}，修正为yellow"
                )
                max_color = "yellow"
                max_pixels = yellow_pixels

        if max_color in ["purple", "yellow"]:
            required_ratio = 3.0
            if (
                second_max_pixels > 0
                and max_pixels < second_max_pixels * required_ratio
            ):
                print(
                    f"[颜色检测] 高品质({max_color})置信度不足: {max_pixels} < {second_max_pixels} * {required_ratio}"
                )
                return None
            if max_pixels < 30:
                print(f"[颜色检测] 高品质({max_color})像素数不足: {max_pixels} < 30")
                return None
        else:
            if second_max_pixels > 0 and max_pixels < second_max_pixels * 2:
                print(f"[颜色检测] 置信度不足: {max_pixels} < {second_max_pixels} * 2")
                return None

        print(f"[颜色检测] 识别为: {max_color} (像素数: {max_pixels})")
        return max_color

    def draw_debug_rects(self, image, config, recognition_results=None):
        """绘制调试矩形和中文标签"""
        print("[DEBUG] Entering draw_debug_rects.")
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
            "bucket_close_button": "鱼桶关闭按钮",
        }

        font_cjk = None
        pil_available = False
        font_load_error = ""

        try:
            from PIL import Image, ImageDraw, ImageFont

            pil_available = True

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

        img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil, "RGBA")

        legend_x, legend_y = 10, 10
        legend_line_height = 20
        legend_width = 350
        legend_content = ["调试图例:"]
        if font_load_error:
            legend_content.append(font_load_error)

        if recognition_results:
            legend_content.append("--- 识别结果 ---")
            legend_content.extend(recognition_results)
            legend_content.append("--- 区域坐标 ---")

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

        draw.rectangle(
            [legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
            fill=(0, 0, 0, 128),
        )
        for i, text in enumerate(legend_content):
            draw.text(
                (legend_x + 5, legend_y + 5 + i * legend_line_height),
                text,
                font=font_cjk,
                fill=(255, 255, 255),
            )

        for name, rect_data in config.items():
            if name == "scale" or not isinstance(rect_data, list):
                continue

            print(f"[DEBUG] Drawing rect: {name} with data {rect_data}")

            x, y, w, h = rect_data

            draw.rectangle([x, y, x + w, y + h], outline=(0, 255, 0), width=2)

            if name == "bait_count":
                slice_width = int(cfg.BAIT_CROP_WIDTH1_BASE * cfg.scale)
                slice_width = max(slice_width, 1)

                draw.rectangle(
                    [x, y, x + slice_width, y + h], outline=(255, 0, 0), width=1
                )

                draw.rectangle(
                    [x + w - slice_width, y, x + w, y + h], outline=(0, 0, 255), width=1
                )

                center_start = x + (w - slice_width) // 2
                draw.rectangle(
                    [center_start, y, center_start + slice_width, y + h],
                    outline=(255, 255, 0),
                    width=1,
                )

            label_text = label_map.get(name, name)

            try:
                bbox = draw.textbbox((0, 0), label_text, font=font_cjk)
                text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except AttributeError:
                text_w, text_h = draw.textsize(label_text, font=font_cjk)

            text_x = x
            text_y = y - text_h - 5
            if text_y < 0:
                text_y = y + h + 5

            draw.rectangle(
                [text_x, text_y, text_x + text_w, text_y + text_h], fill=(0, 0, 0, 128)
            )
            draw.text((text_x, text_y), label_text, font=font_cjk, fill=(0, 255, 0))

        image[:] = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

        print("[DEBUG] Exiting draw_debug_rects.")
        return image
