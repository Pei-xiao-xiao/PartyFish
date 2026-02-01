"""
坐标服务
负责处理屏幕坐标的缩放和锚点计算
"""


class CoordinateService:
    """坐标服务类"""

    def __init__(self, config):
        """
        初始化坐标服务

        Args:
            config: Config 实例引用
        """
        self.config = config

    def recalculate_scale(self):
        """重新计算缩放因子，基于当前 screen_width 和 screen_height"""
        self.config.scale_x = self.config.screen_width / self.config.BASE_SCREEN_WIDTH
        self.config.scale_y = self.config.screen_height / self.config.BASE_SCREEN_HEIGHT
        self.config.scale = self.config.scale_y

    def get_top_center_rect(self, coords):
        """
        Calculates coordinates for a top-center anchored region.
        Scales based on height (self.scale) to maintain aspect ratio.
        """
        base_x, base_y, base_w, base_h = coords

        base_center_x = base_x + (base_w / 2)
        offset_from_center_x = base_center_x - (self.config.BASE_SCREEN_WIDTH / 2)

        new_w = int(base_w * self.config.scale)
        new_h = int(base_h * self.config.scale)

        new_center_x = (self.config.screen_width / 2) + (
            offset_from_center_x * self.config.scale
        )

        new_x = int(new_center_x - (new_w / 2))
        new_y = int(base_y * self.config.scale)

        return (new_x, new_y, new_w, new_h)

    def get_bottom_center_rect(self, coords):
        """Calculates coordinates for a bottom-center anchored region."""
        base_x, base_y, base_w, base_h = coords

        base_center_x = base_x + (base_w / 2)
        offset_from_center_x = base_center_x - (self.config.BASE_SCREEN_WIDTH / 2)

        offset_from_bottom = self.config.BASE_SCREEN_HEIGHT - base_y

        new_w = int(base_w * self.config.scale)
        new_h = int(base_h * self.config.scale)

        new_center_x = (self.config.screen_width / 2) + (
            offset_from_center_x * self.config.scale
        )

        new_y = int(
            self.config.screen_height - (offset_from_bottom * self.config.scale)
        )

        new_x = int(new_center_x - (new_w / 2))

        return (new_x, new_y, new_w, new_h)

    def get_bottom_right_rect(self, coords):
        """Calculates coordinates for a bottom-right anchored region."""
        base_x, base_y, base_w, base_h = coords

        offset_from_right = self.config.BASE_SCREEN_WIDTH - base_x
        offset_from_bottom = self.config.BASE_SCREEN_HEIGHT - base_y

        new_w = int(base_w * self.config.scale)
        new_h = int(base_h * self.config.scale)

        new_x = int(self.config.screen_width - (offset_from_right * self.config.scale))
        new_y = int(
            self.config.screen_height - (offset_from_bottom * self.config.scale)
        )

        return (new_x, new_y, new_w, new_h)

    def get_bottom_right_pos(self, coords):
        """
        Calculates coordinates for a bottom-right anchored point (x, y).
        Uses separate scale_x and scale_y for proper scaling.
        """
        base_x, base_y = coords

        offset_from_right = self.config.BASE_SCREEN_WIDTH - base_x
        offset_from_bottom = self.config.BASE_SCREEN_HEIGHT - base_y

        new_x = int(
            self.config.screen_width - (offset_from_right * self.config.scale_x)
        )
        new_y = int(
            self.config.screen_height - (offset_from_bottom * self.config.scale_y)
        )

        return (new_x, new_y)

    def get_center_anchored_rect(self, coords):
        """
        Calculates coordinates for a center-center anchored region.
        弹窗 UI 保持宽高比，所以偏移缩放使用 min(scale_x, scale_y)。
        """
        base_x, base_y, base_w, base_h = coords

        base_center_x = base_x + (base_w / 2)
        base_center_y = base_y + (base_h / 2)

        offset_from_center_x = base_center_x - (self.config.BASE_SCREEN_WIDTH / 2)
        offset_from_center_y = base_center_y - (self.config.BASE_SCREEN_HEIGHT / 2)

        popup_scale = min(self.config.scale_x, self.config.scale_y)

        new_w = int(base_w * popup_scale)
        new_h = int(base_h * popup_scale)

        new_center_x = (self.config.screen_width / 2) + (
            offset_from_center_x * popup_scale
        )
        new_center_y = (self.config.screen_height / 2) + (
            offset_from_center_y * popup_scale
        )

        new_x = int(new_center_x - (new_w / 2))
        new_y = int(new_center_y - (new_h / 2))

        return (new_x, new_y, new_w, new_h)

    def get_center_anchored_pos(self, coords):
        """
        Calculates coordinates for a center-center anchored point (x, y).
        弹窗 UI 保持宽高比，所以偏移缩放使用 min(scale_x, scale_y)。
        """
        base_x, base_y = coords

        offset_from_center_x = base_x - (self.config.BASE_SCREEN_WIDTH / 2)
        offset_from_center_y = base_y - (self.config.BASE_SCREEN_HEIGHT / 2)

        popup_scale = min(self.config.scale_x, self.config.scale_y)

        new_x = int(
            (self.config.screen_width / 2) + (offset_from_center_x * popup_scale)
        )
        new_y = int(
            (self.config.screen_height / 2) + (offset_from_center_y * popup_scale)
        )

        return (new_x, new_y)

    def get_rect(self, name):
        """
        Calculates the scaled rectangle for a predefined region using an anchor-based dispatcher.
        """
        if name not in self.config.REGIONS:
            raise KeyError(f"Region '{name}' not defined in Config.")

        region_info = self.config.REGIONS[name]
        coords = region_info["coords"]
        anchor_type = region_info.get("anchor", "default")

        dispatcher = {
            "top_center": self.get_top_center_rect,
            "bottom_center": self.get_bottom_center_rect,
            "bottom_right": self.get_bottom_right_rect,
            "center": self.get_center_anchored_rect,
        }

        calculation_method = dispatcher.get(anchor_type)

        if calculation_method:
            return calculation_method(coords)
        else:
            x, y, w, h = coords
            scaled_x = int(x * self.config.scale_x)
            scaled_y = int(y * self.config.scale_y)
            scaled_w = int(w * self.config.scale_x)
            scaled_h = int(h * self.config.scale_y)
            return (scaled_x, scaled_y, scaled_w, scaled_h)
