"""
OCR 服务
负责处理文本识别和解析
"""

import re
import time
from rapidfuzz import process, fuzz
import cv2
from rapidocr_onnxruntime import RapidOCR
from src.config import cfg


class OCRService:
    """OCR 服务类"""

    def __init__(self, intra_op_num_threads: int = 4, inter_op_num_threads: int = 4):
        """初始化 OCR 引擎"""
        self.ocr = RapidOCR(
            intra_op_num_threads=intra_op_num_threads,
            inter_op_num_threads=inter_op_num_threads,
        )

    def recognize_catch_info(self, vision, log_callback=None) -> tuple[bool, dict]:
        """
        识别渔获信息（带重试机制）

        Args:
            vision: 视觉模块实例
            log_callback: 日志回调函数

        Returns:
            (成功标志, 渔获数据字典)
            渔获数据包含: name, quality, weight, is_new_record
        """
        rect = cfg.get_rect("ocr_area")
        if not rect:
            if log_callback:
                log_callback("错误: 未在配置中找到 'ocr_area' 区域。")
            return False, {}

        max_ocr_retries = 3
        result = None
        image = None

        for ocr_attempt in range(max_ocr_retries):
            image = vision.screenshot(rect)
            if image is None:
                if log_callback:
                    log_callback("截图失败。")
                return False, {}

            result, _ = self.ocr(image)

            if result:
                break
            else:
                if ocr_attempt < max_ocr_retries - 1:
                    if log_callback:
                        log_callback(
                            f"OCR 未识别到内容，等待 0.5 秒后重试 ({ocr_attempt + 1}/{max_ocr_retries})..."
                        )
                    time.sleep(0.5)
                else:
                    if log_callback:
                        log_callback("OCR未能识别到有效的渔获信息。")
                    try:
                        debug_dir = cfg._get_application_path() / "debug_screenshots"
                        if not debug_dir.exists():
                            debug_dir.mkdir(parents=True)
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        debug_filename = debug_dir / f"ocr_failed_{timestamp}.png"
                        cv2.imwrite(str(debug_filename), image)
                        if log_callback:
                            log_callback(f"OCR失败，已保存调试截图: {debug_filename}")
                    except Exception as e:
                        if log_callback:
                            log_callback(f"保存调试截图失败: {e}")
                    return False, {}

        full_text = "".join([res[1] for res in result])
        if log_callback:
            log_callback(f"识别到原始文本: {full_text}")

        # 解析文本
        return self._parse_catch_text(full_text, log_callback)

    def recognize_catch_info_from_images(
        self, images, log_callback=None
    ) -> tuple[bool, dict]:
        """Recognize catch info from pre-captured image frames."""
        if images is None:
            if log_callback:
                log_callback("OCR input is empty.")
            return False, {}

        if not isinstance(images, (list, tuple)):
            images = [images]

        valid_images = [img for img in images if img is not None]
        if not valid_images:
            if log_callback:
                log_callback("OCR did not receive any valid frame.")
            return False, {}

        total = len(valid_images)
        for idx, image in enumerate(valid_images, start=1):
            result, _ = self.ocr(image)
            if not result:
                if log_callback:
                    log_callback(f"OCR frame {idx}/{total}: no text detected.")
                continue

            full_text = "".join([res[1] for res in result])
            if log_callback:
                log_callback(f"OCR raw text (frame {idx}): {full_text}")

            success, catch_data = self._parse_catch_text(full_text, log_callback)
            if success:
                return True, catch_data

        if log_callback:
            log_callback("OCR failed on all cached frames.")

        try:
            debug_dir = cfg._get_application_path() / "debug_screenshots"
            if not debug_dir.exists():
                debug_dir.mkdir(parents=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            debug_filename = debug_dir / f"ocr_failed_snapshot_{timestamp}.png"
            cv2.imwrite(str(debug_filename), valid_images[-1])
            if log_callback:
                log_callback(f"Saved OCR debug snapshot: {debug_filename}")
        except Exception as e:
            if log_callback:
                log_callback(f"Failed to save OCR debug snapshot: {e}")

        return False, {}

    def _parse_catch_text(self, full_text: str, log_callback=None) -> tuple[bool, dict]:
        """
        解析渔获文本

        Args:
            full_text: OCR 识别的完整文本
            log_callback: 日志回调函数

        Returns:
            (成功标志, 渔获数据字典)
        """
        # 检测新纪录
        new_record_patterns = ["新纪录", "新记录", "新紀錄"]
        is_new_record = any(p in full_text for p in new_record_patterns)
        if is_new_record and log_callback:
            log_callback("检测到新纪录！")
        for p in new_record_patterns:
            full_text = full_text.replace(p, "")

        # 检查关键字
        catch_prefix_found = "你钓到了" in full_text or "你釣到了" in full_text
        if not catch_prefix_found:
            if "千克" in full_text or "公斤" in full_text:
                if log_callback:
                    log_callback(
                        "未检测到'你钓到了'前缀，但发现重量单位，尝试继续解析。"
                    )
            else:
                if log_callback:
                    log_callback("OCR结果不包含关键字，判定为钓鱼失败。")
                return False, {}

        cleaned_text = full_text.replace(" ", "").replace("(", "").replace(")", "")

        # 清理新纪录关键词
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
                is_new_record = True
                cleaned_text = cleaned_text.replace(kw, "")

        cleaned_text = cleaned_text.replace(":", "").replace("：", "")

        try:
            # 移除前缀
            if "你钓到了" in cleaned_text:
                text_after_prefix = cleaned_text.split("你钓到了", 1)[-1]
            elif "你釣到了" in cleaned_text:
                text_after_prefix = cleaned_text.split("你釣到了", 1)[-1]
            else:
                text_after_prefix = cleaned_text

            # 品质列表
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
                text_after_prefix = text_after_prefix.replace(
                    weight_match.group(0), ""
                ).strip()

            # 提取品质
            quality = "普通"
            for q in qualities:
                if q in text_after_prefix:
                    quality = q
                    text_after_prefix = text_after_prefix.replace(q, "").strip()
                    break

            # 品质归一化
            quality_mapping = {
                "传说": "传奇",
                "傳說": "传奇",
                "傳奇": "传奇",
                "標準": "标准",
                "史詩": "史诗",
                "稀少": "稀有",
            }
            if quality in quality_mapping:
                quality = quality_mapping[quality]

            # 剩下的是鱼名
            fish_name = text_after_prefix.strip()

            # 鱼名清理与模糊匹配
            if hasattr(cfg, "fish_names_list") and cfg.fish_names_list:
                search_name = fish_name
                if re.search(r"[\u4e00-\u9fa5]", fish_name):
                    search_name = "".join(re.findall(r"[\u4e00-\u9fa5]+", fish_name))

                matches = process.extract(
                    search_name,
                    cfg.fish_names_list,
                    scorer=fuzz.ratio,
                    limit=1,
                    score_cutoff=60,
                )

                if not matches and search_name != fish_name:
                    matches = process.extract(
                        fish_name,
                        cfg.fish_names_list,
                        scorer=fuzz.ratio,
                        limit=1,
                        score_cutoff=60,
                    )

                if matches:
                    matched_name = matches[0][0]
                    if fish_name != matched_name and log_callback:
                        log_callback(f"鱼名校正: '{fish_name}' -> '{matched_name}'")
                    fish_name = matched_name
                else:
                    if re.search(r"[\u4e00-\u9fa5]", fish_name):
                        fish_name = re.sub(r"[^\u4e00-\u9fa50-9]+$", "", fish_name)
                    else:
                        fish_name = ""
            else:
                if re.search(r"[\u4e00-\u9fa5]", fish_name):
                    fish_name = re.sub(r"[^\u4e00-\u9fa50-9]+$", "", fish_name)
                else:
                    cleaned_non_chinese = re.sub(r"[^a-zA-Z0-9]+", "", fish_name)
                    fish_name = cleaned_non_chinese if len(cleaned_non_chinese) >= 2 else ""

            fish_name = fish_name.strip()

            if not fish_name:
                if log_callback:
                    log_callback(f"无法从 '{full_text}' 中解析出鱼名。")
                return False, {}

            if log_callback:
                log_callback(
                    f"解析结果 -> 鱼名: '{fish_name}', 品质: '{quality}', 重量: {weight}"
                )

            return True, {
                "name": fish_name,
                "weight": weight,
                "quality": quality,
                "is_new_record": is_new_record,
            }

        except Exception as e:
            if log_callback:
                log_callback(f"数据解析过程中发生错误: {e}")
            return False, {}

    def recognize_text(self, image) -> str:
        """
        识别图像中的文本（简单版本，用于鱼名和菜单识别）

        Args:
            image: 图像数据

        Returns:
            识别到的文本，如果失败返回空字符串
        """
        if image is None:
            return ""

        result, _ = self.ocr(image)
        if result:
            for item in result:
                text = item[1].strip()
                if text and len(text) > 1:
                    return text
        return ""

    def recognize_text_with_boxes(self, image) -> list:
        """
        识别图像中的文本并返回位置信息

        Args:
            image: 图像数据

        Returns:
            OCR 结果列表，每项包含 [box, text]
        """
        if image is None:
            return []

        result, _ = self.ocr(image)
        return result if result else []
