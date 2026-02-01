"""
图鉴进度图生成服务
使用 Pillow 生成图鉴进度图片
"""
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont
from src.pokedex import pokedex, QUALITIES
from src.config import cfg


class PokedexImageGenerator:
    """图鉴图片生成器"""

    CARD_WIDTH = 200
    CARD_HEIGHT = 220
    CARD_MARGIN = 10
    CARD_PADDING = 10

    FISH_IMAGE_SIZE = 120

    DOT_SIZE = 14
    DOT_MARGIN = 5

    BG_COLOR = (245, 245, 245)
    CARD_BG_COLOR = (255, 255, 255)
    CARD_BORDER_COLOR = (220, 220, 220)

    TEXT_COLOR = (80, 80, 80)

    QUALITY_COLORS = {
        "标准": (96, 96, 96),
        "非凡": (30, 158, 0),
        "稀有": (0, 122, 204),
        "史诗": (138, 43, 226),
        "传奇": (255, 140, 0)
    }

    def __init__(self):
        """初始化图片生成器"""
        self.screenshots_dir = cfg._get_application_path() / "screenshots" / "pokedex"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def generate_pokedex_image(self, image_type: str = 'all') -> Path:
        """
        生成图鉴进度图

        Args:
            image_type: 'all' - 全部图鉴, 'uncollected' - 未收集图鉴

        Returns:
            生成的图片路径
        """
        # 获取鱼类列表
        all_fish = pokedex.get_all_fish()

        if image_type == 'uncollected':
            # 显示没有收集齐全部5个品质的鱼
            fish_list = [f for f in all_fish if pokedex.get_fish_collected_count(f.get('name', '')) < len(QUALITIES)]
            prefix = "未收集"
        else:
            # 显示所有鱼
            fish_list = all_fish
            prefix = "全部"

        if not fish_list:
            return None

        # 计算网格布局
        cols = 6
        rows = (len(fish_list) + cols - 1) // cols

        # 计算画布大小
        canvas_width = cols * (self.CARD_WIDTH + self.CARD_MARGIN) + self.CARD_MARGIN
        canvas_height = rows * (self.CARD_HEIGHT + self.CARD_MARGIN) + self.CARD_MARGIN + 40

        # 创建画布
        img = Image.new('RGB', (canvas_width, canvas_height), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            font = ImageFont.truetype(str(cfg._get_base_path() / "resources" / "fonts" / "ZCOOLKuaiLe-Regular.ttf"), 16)
            title_font = ImageFont.truetype(str(cfg._get_base_path() / "resources" / "fonts" / "ZCOOLKuaiLe-Regular.ttf"), 28)
        except:
            font = ImageFont.load_default()
            title_font = ImageFont.load_default()

        # 绘制标题
        title = f"{prefix}图鉴 ({len(fish_list)})"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (canvas_width - title_width) // 2
        draw.text((title_x, 10), title, fill=self.TEXT_COLOR, font=title_font)

        # 绘制卡片
        for idx, fish in enumerate(fish_list):
            row = idx // cols
            col = idx % cols

            x = self.CARD_MARGIN + col * (self.CARD_WIDTH + self.CARD_MARGIN)
            y = 40 + self.CARD_MARGIN + row * (self.CARD_HEIGHT + self.CARD_MARGIN)

            self._draw_card(img, draw, fish, x, y)

        # 保存图片
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_图鉴_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        img.save(filepath)

        return filepath

    def _draw_card(self, img: Image.Image, draw: ImageDraw.Draw, fish: Dict, x: int, y: int):
        """绘制单张卡片"""
        # 绘制卡片背景
        draw.rectangle(
            [x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT],
            fill=self.CARD_BG_COLOR,
            outline=self.CARD_BORDER_COLOR,
            width=1
        )

        # 获取鱼名
        fish_name = fish.get('name', '未知')

        # 加载并绘制鱼图
        img_path = pokedex.get_fish_image_path(fish_name)
        if img_path and img_path.exists():
            try:
                fish_img = Image.open(img_path)
                # 保持宽高比缩放
                fish_img.thumbnail((self.FISH_IMAGE_SIZE, self.FISH_IMAGE_SIZE), Image.Resampling.LANCZOS)
                fish_img = fish_img.convert('RGBA')

                # 居中绘制
                img_x = x + (self.CARD_WIDTH - fish_img.width) // 2
                img_y = y + self.CARD_PADDING

                # 将鱼图粘贴到主画布上
                img.paste(fish_img, (img_x, img_y), fish_img)
            except Exception as e:
                print(f"[PokedexImageGenerator] 加载鱼图失败 {fish_name}: {e}")
                # 绘制占位符
                self._draw_placeholder(draw, x, y)
        else:
            # 绘制占位符
            self._draw_placeholder(draw, x, y)

        # 加载字体 - 尝试多个字体
        font = None
        font_paths = [
            cfg._get_base_path() / "resources" / "fonts" / "ZCOOLKuaiLe-Regular.ttf",
            cfg._get_base_path() / "resources" / "fonts" / "msyh.ttc",
            cfg._get_base_path() / "resources" / "fonts" / "msyh.ttf",
        ]

        for font_path in font_paths:
            try:
                if font_path.exists():
                    font = ImageFont.truetype(str(font_path), 14)
                    break
            except:
                continue

        if font is None:
            try:
                font = ImageFont.truetype("C:\\Windows\\Fonts\\msyh.ttc", 14)
            except:
                try:
                    font = ImageFont.truetype("C:\\Windows\\Fonts\\msyh.ttf", 14)
                except:
                    font = ImageFont.load_default()

        # 绘制鱼名
        name_bbox = draw.textbbox((0, 0), fish_name, font=font)
        name_width = name_bbox[2] - name_bbox[0]
        name_x = x + (self.CARD_WIDTH - name_width) // 2
        name_y = y + self.CARD_PADDING + self.FISH_IMAGE_SIZE + 4
        draw.text((name_x, name_y), fish_name, fill=self.TEXT_COLOR, font=font)

        # 绘制品质圆点
        status = pokedex.get_collection_status(fish_name)
        dots_width = len(QUALITIES) * (self.DOT_SIZE + self.DOT_MARGIN) - self.DOT_MARGIN
        dots_x = x + (self.CARD_WIDTH - dots_width) // 2
        dots_y = name_y + 18

        for i, quality in enumerate(QUALITIES):
            dot_x = dots_x + i * (self.DOT_SIZE + self.DOT_MARGIN)
            is_collected = status.get(quality) is not None
            color = self.QUALITY_COLORS.get(quality, (128, 128, 128))

            if is_collected:
                # 实心圆
                draw.ellipse(
                    [dot_x, dots_y, dot_x + self.DOT_SIZE, dots_y + self.DOT_SIZE],
                    fill=color,
                    outline=color
                )
            else:
                # 空心圆
                draw.ellipse(
                    [dot_x, dots_y, dot_x + self.DOT_SIZE, dots_y + self.DOT_SIZE],
                    fill=None,
                    outline=color,
                    width=2
                )

    def _draw_placeholder(self, draw: ImageDraw.Draw, x: int, y: int):
        """绘制占位符"""
        placeholder_width = self.FISH_IMAGE_SIZE
        placeholder_height = self.FISH_IMAGE_SIZE
        placeholder_x = x + (self.CARD_WIDTH - placeholder_width) // 2
        placeholder_y = y + self.CARD_PADDING
        draw.rectangle(
            [placeholder_x, placeholder_y, placeholder_x + placeholder_width, placeholder_y + placeholder_height],
            fill=(240, 240, 240),
            outline=(200, 200, 200)
        )


# 全局单例
pokedex_image_generator = PokedexImageGenerator()
