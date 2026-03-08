"""
图鉴进度图生成服务
使用 Pillow 生成图鉴进度图片（优化版）
"""
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from src.pokedex import pokedex, QUALITIES
from src.config import cfg


class PokedexImageGenerator:
    """图鉴图片生成器"""

    # 卡片尺寸
    CARD_WIDTH = 200
    CARD_HEIGHT = 220
    CARD_MARGIN = 12
    CARD_PADDING = 12
    CARD_RADIUS = 10  # 圆角半径

    # 图片尺寸
    FISH_IMAGE_SIZE = 120

    # 品质圆点
    DOT_SIZE = 16
    DOT_MARGIN = 6

    # 颜色配置（优化版）
    BG_COLOR = (240, 242, 245)
    CARD_BG_START = (255, 255, 255)
    CARD_BG_END = (248, 250, 252)
    CARD_BORDER_COLOR = (100, 181, 246)  # 醒目的蓝色边框
    CARD_BORDER_WIDTH = 2
    CARD_SHADOW_COLOR = (0, 0, 0, 30)

    # 鱼图片背景色（淡蓝色圆形）
    FISH_BG_COLOR = (230, 240, 250)
    FISH_BG_SIZE = 140  # 圆形背景直径

    TEXT_COLOR = (60, 70, 80)
    TITLE_COLOR = (50, 60, 70)
    SUBTITLE_COLOR = (100, 115, 130)

    # 品质颜色（优化版）
    QUALITY_COLORS = {
        "标准": (100, 100, 100),
        "非凡": (34, 178, 0),
        "稀有": (0, 142, 230),
        "史诗": (153, 51, 255),
        "传奇": (255, 153, 0)
    }

    def __init__(self):
        """初始化图片生成器"""
        self.screenshots_dir = cfg._get_application_path() / "截图" / "图鉴"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    def generate_pokedex_image(self, image_type: str = 'all') -> Path:
        """
        生成图鉴进度图

        Args:
            image_type: 'all' - 全部图鉴，'uncollected' - 未收集图鉴

        Returns:
            生成的图片路径
        """
        # 获取鱼类列表
        all_fish = pokedex.get_all_fish()

        if image_type == 'uncollected':
            # 显示没有收集齐全部 5 个品质的鱼
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

        # 计算画布大小（增加顶部图例区域和页眉页脚）
        legend_height = 60  # 鱼种和品质图例区域
        header_height = 80
        footer_height = 50
        canvas_width = cols * (self.CARD_WIDTH + self.CARD_MARGIN) + self.CARD_MARGIN
        canvas_height = legend_height + header_height + rows * (self.CARD_HEIGHT + self.CARD_MARGIN) + self.CARD_MARGIN + footer_height

        # 创建画布
        img = Image.new('RGB', (canvas_width, canvas_height), self.BG_COLOR)
        draw = ImageDraw.Draw(img)

        # 加载字体
        try:
            font_path = str(cfg._get_base_path() / "resources" / "fonts" / "ZCOOLKuaiLe-Regular.ttf")
            title_font = ImageFont.truetype(font_path, 32)
            subtitle_font = ImageFont.truetype(font_path, 18)
            card_font = ImageFont.truetype(font_path, 16)
            footer_font = ImageFont.truetype(font_path, 14)
            legend_font = ImageFont.truetype(font_path, 14)
        except:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            card_font = ImageFont.load_default()
            footer_font = ImageFont.load_default()
            legend_font = ImageFont.load_default()

        # 绘制顶部图例（鱼种和品质）
        self._draw_legend(img, draw, legend_height, legend_font)

        # 绘制页眉
        self._draw_header(img, draw, prefix, len(fish_list), title_font, subtitle_font, header_height, legend_height)

        # 绘制卡片
        for idx, fish in enumerate(fish_list):
            row = idx // cols
            col = idx % cols

            x = self.CARD_MARGIN + col * (self.CARD_WIDTH + self.CARD_MARGIN)
            y = legend_height + header_height + self.CARD_MARGIN + row * (self.CARD_HEIGHT + self.CARD_MARGIN)

            self._draw_card(img, draw, fish, x, y, card_font)

        # 绘制页脚（账号和时间）
        self._draw_footer(img, draw, canvas_height, footer_font)

        # 保存图片
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_图鉴_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        img.save(filepath)

        return filepath

    def _draw_legend(self, img: Image.Image, draw: ImageDraw.Draw, legend_height: int, font):
        """绘制顶部图例（鱼种和品质收集进度）"""
        canvas_width = img.width
        
        # 绘制图例背景
        draw.rectangle([(0, 0), (canvas_width, legend_height)], fill=(235, 238, 242))
        
        # 绘制分隔线
        draw.line([(0, legend_height - 1), (canvas_width, legend_height - 1)], 
                  fill=(210, 215, 220), width=2)
        
        # 计算收集进度
        all_fish = pokedex.get_all_fish()
        total_fish_types = len(all_fish)  # 鱼种总数
        total_qualities = len(all_fish) * len(QUALITIES)
        
        collected_fish_types = 0
        collected_qualities = 0
        
        for fish in all_fish:
            fish_name = fish.get('name', '')
            status = pokedex.get_collection_status(fish_name)
            
            # 统计已收集的鱼种（至少有一个品质已收集）
            if any(v is not None for v in status.values()):
                collected_fish_types += 1
            
            # 统计已收集的品质
            collected_qualities += sum(1 for v in status.values() if v is not None)
        
        # 居中绘制：鱼种 0/68 · 品质 0/340
        type_y = (legend_height - 20) // 2
        progress_text = f"鱼种 {collected_fish_types}/{total_fish_types}  ·  品质 {collected_qualities}/{total_qualities}"
        
        # 计算文字宽度并居中
        text_bbox = draw.textbbox((0, 0), progress_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (canvas_width - text_width) // 2
        
        draw.text((text_x, type_y), progress_text, fill=self.TITLE_COLOR, font=font)

    def _get_fish_type_color(self, fish_type: str):
        """根据鱼竿类型返回颜色"""
        colors = {
            "路亚轻杆": (86, 152, 195),
            "路亚重杆": (194, 72, 72),
            "池塘轻杆": (76, 175, 80),
            "池塘重杆": (255, 152, 0),
            "冰钓轻杆": (0, 188, 212),
            "冰钓重杆": (156, 39, 176)
        }
        return colors.get(fish_type, (128, 128, 128))

    def _draw_header(self, img: Image.Image, draw: ImageDraw.Draw, prefix: str, count: int, 
                     title_font, subtitle_font, header_height: int, legend_height: int):
        """绘制页眉"""
        canvas_width = img.width
        
        # 绘制页眉背景（渐变效果）
        for y in range(legend_height, legend_height + header_height):
            ratio = (y - legend_height) / header_height
            color = tuple(int(self.BG_COLOR[i] * (1 - ratio * 0.3) + 255 * ratio * 0.3) for i in range(3))
            draw.line([(0, y), (canvas_width, y)], fill=color)
        
        # 绘制分隔线
        draw.line([(0, legend_height + header_height - 1), (canvas_width, legend_height + header_height - 1)], 
                  fill=(210, 215, 220), width=2)

        # 绘制主标题
        title = f"{prefix}图鉴"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (canvas_width - title_width) // 2
        draw.text((title_x, legend_height + 15), title, fill=self.TITLE_COLOR, font=title_font)

        # 绘制副标题（数量）
        subtitle = f"共计 {count} 种鱼类"
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=subtitle_font)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (canvas_width - subtitle_width) // 2
        draw.text((subtitle_x, legend_height + 52), subtitle, fill=self.SUBTITLE_COLOR, font=subtitle_font)

    def _draw_card(self, img: Image.Image, draw: ImageDraw.Draw, fish: Dict, x: int, y: int, font):
        """绘制单张卡片（优化版：圆角 + 渐变 + 阴影）"""
        # 绘制卡片阴影
        shadow_offset = 3
        shadow_blur = 8
        shadow_img = Image.new('RGBA', (self.CARD_WIDTH + shadow_blur * 2, 
                                        self.CARD_HEIGHT + shadow_blur * 2), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)
        
        # 绘制阴影形状
        shadow_rect = [(shadow_blur - shadow_offset, shadow_blur - shadow_offset),
                      (shadow_blur - shadow_offset + self.CARD_WIDTH, 
                       shadow_blur - shadow_offset + self.CARD_HEIGHT)]
        shadow_draw.rounded_rectangle(shadow_rect, radius=self.CARD_RADIUS, 
                                     fill=self.CARD_SHADOW_COLOR)
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(shadow_blur))
        
        # 将阴影粘贴到主图
        img.paste(shadow_img, (x - shadow_blur + shadow_offset, y - shadow_blur + shadow_offset), shadow_img)

        # 绘制卡片背景（渐变效果）
        self._draw_rounded_gradient_rect(draw, 
                                        [x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT],
                                        self.CARD_BG_START, 
                                        self.CARD_BG_END,
                                        self.CARD_RADIUS)

        # 绘制卡片边框
        draw.rounded_rectangle([x, y, x + self.CARD_WIDTH, y + self.CARD_HEIGHT],
                              radius=self.CARD_RADIUS, 
                              outline=self.CARD_BORDER_COLOR, 
                              width=self.CARD_BORDER_WIDTH)

        # 获取鱼名
        fish_name = fish.get('name', '未知')

        # 绘制鱼图片背景（正方形色块，带圆角）
        bg_size = self.FISH_BG_SIZE
        bg_x = x + (self.CARD_WIDTH - bg_size) // 2
        bg_y = y + self.CARD_PADDING
        draw.rounded_rectangle(
            [bg_x, bg_y, bg_x + bg_size, bg_y + bg_size],
            radius=15,
            fill=self.FISH_BG_COLOR
        )

        # 加载并绘制鱼图
        img_path = pokedex.get_fish_image_path(fish_name)
        if img_path and img_path.exists():
            try:
                fish_img = Image.open(img_path)
                # 保持宽高比缩放，确保不超出背景区域
                fish_img.thumbnail((self.FISH_IMAGE_SIZE - 10, self.FISH_IMAGE_SIZE - 10), Image.Resampling.LANCZOS)
                fish_img = fish_img.convert('RGBA')

                # 精确居中绘制
                img_x = x + (self.CARD_WIDTH - fish_img.width) // 2
                img_y = y + self.CARD_PADDING + (bg_size - fish_img.height) // 2

                # 将鱼图粘贴到主画布上（在正方形背景上方）
                img.paste(fish_img, (img_x, img_y), fish_img)
            except Exception as e:
                print(f"[PokedexImageGenerator] 加载鱼图失败 {fish_name}: {e}")
                self._draw_placeholder(draw, x, y)
        else:
            self._draw_placeholder(draw, x, y)

        # 绘制鱼名
        name_bbox = draw.textbbox((0, 0), fish_name, font=font)
        name_width = name_bbox[2] - name_bbox[0]
        name_x = x + (self.CARD_WIDTH - name_width) // 2
        name_y = y + self.CARD_PADDING + self.FISH_BG_SIZE + 12  # 在正方形背景下方
        draw.text((name_x, name_y), fish_name, fill=self.TEXT_COLOR, font=font)

        # 绘制品质圆点
        status = pokedex.get_collection_status(fish_name)
        dots_width = len(QUALITIES) * (self.DOT_SIZE + self.DOT_MARGIN) - self.DOT_MARGIN
        dots_x = x + (self.CARD_WIDTH - dots_width) // 2
        dots_y = name_y + 20  # 在鱼名下方

        for i, quality in enumerate(QUALITIES):
            dot_x = dots_x + i * (self.DOT_SIZE + self.DOT_MARGIN)
            is_collected = status.get(quality) is not None
            color = self.QUALITY_COLORS.get(quality, (128, 128, 128))

            if is_collected:
                # 实心圆（带白色外圈和高光）
                # 外圈
                draw.ellipse(
                    [dot_x - 2, dots_y - 2, dot_x + self.DOT_SIZE + 2, dots_y + self.DOT_SIZE + 2],
                    fill=(255, 255, 255)
                )
                # 主圆
                draw.ellipse(
                    [dot_x, dots_y, dot_x + self.DOT_SIZE, dots_y + self.DOT_SIZE],
                    fill=color
                )
                # 高光点
                highlight_x = dot_x + self.DOT_SIZE // 3
                highlight_y = dots_y + self.DOT_SIZE // 3
                draw.ellipse(
                    [highlight_x, highlight_y, highlight_x + 4, highlight_y + 4],
                    fill=(255, 255, 255, 180)
                )
            else:
                # 空心圆（带颜色边框）
                draw.ellipse(
                    [dot_x, dots_y, dot_x + self.DOT_SIZE, dots_y + self.DOT_SIZE],
                    outline=color,
                    width=2
                )

    def _draw_rounded_gradient_rect(self, draw: ImageDraw.Draw, rect: List[int], 
                                    color_start: tuple, color_end: tuple, radius: int):
        """绘制圆角渐变矩形"""
        x0, y0, x1, y1 = rect
        height = y1 - y0
        
        # 垂直渐变
        for y in range(y0, y1):
            ratio = (y - y0) / height
            color = tuple(int(color_start[i] * (1 - ratio) + color_end[i] * ratio) for i in range(3))
            
            # 计算当前行的左右圆角边界
            if y - y0 < radius:
                # 顶部圆角区域
                circle_ratio = ((y - y0) / radius)
                x_offset = int(radius - (radius ** 2 - (y - y0 - radius) ** 2) ** 0.5)
            elif y1 - y <= radius:
                # 底部圆角区域
                circle_ratio = ((y1 - y) / radius)
                x_offset = int(radius - (radius ** 2 - (y1 - y - radius) ** 2) ** 0.5)
            else:
                x_offset = 0
            
            draw.line([(x0 + x_offset, y), (x1 - x_offset, y)], fill=color)

    def _draw_placeholder(self, draw: ImageDraw.Draw, x: int, y: int):
        """绘制占位符"""
        placeholder_size = self.FISH_BG_SIZE
        placeholder_x = x + (self.CARD_WIDTH - placeholder_size) // 2
        placeholder_y = y + self.CARD_PADDING
        draw.rounded_rectangle(
            [placeholder_x, placeholder_y, placeholder_x + placeholder_size, placeholder_y + placeholder_size],
            radius=15,
            fill=(240, 240, 240),
            outline=(200, 200, 200)
        )

    def _draw_footer(self, img: Image.Image, draw: ImageDraw.Draw, canvas_height: int, font):
        """绘制页脚（账号和时间）"""
        account_name = cfg.current_account
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        footer_text = f"{account_name}  |  {timestamp}"
        
        canvas_width = img.width
        
        # 绘制页脚背景
        footer_y = canvas_height - 50
        draw.rectangle([(0, footer_y), (canvas_width, canvas_height)], 
                      fill=(230, 233, 237))
        
        # 绘制分隔线
        draw.line([(0, footer_y), (canvas_width, footer_y)], 
                  fill=(210, 215, 220), width=2)

        # 绘制文字
        text_bbox = draw.textbbox((0, 0), footer_text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_x = (canvas_width - text_width) // 2
        text_y = footer_y + (50 - (text_bbox[3] - text_bbox[1])) // 2
        draw.text((text_x, text_y), footer_text, fill=self.SUBTITLE_COLOR, font=font)


# 全局单例
pokedex_image_generator = PokedexImageGenerator()
