import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any


class MapMatcher:
    """小地图与大地图的自动特征匹配和坐标转换"""

    def __init__(self, big_map_path: Path, vision_instance=None):
        """
        初始化地图匹配器

        参数:
            big_map_path: 大地图图片路径
            vision_instance: Vision 实例（用于截图）
        """
        self.big_map_path = big_map_path
        self.vision = vision_instance

        self.big_map = None
        self.big_map_gray = None
        self.big_map_keypoints = None
        self.big_map_descriptors = None

        self.orb = cv2.ORB_create(nfeatures=2000, scoreType=cv2.ORB_FAST_SCORE)
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        self.scale_ratio = 1.0
        self.translation = np.array([0.0, 0.0])
        self.rotation = 0.0
        self.is_calibrated = False

        self.last_match_time = 0
        self.last_match_quality = 0.0

        self._load_big_map()

    def _load_big_map(self):
        """加载大地图并提取特征"""
        if not self.big_map_path.exists():
            print(f"[MapMatcher] 大地图不存在: {self.big_map_path}")
            return

        img = cv2.imread(str(self.big_map_path))
        if img is None:
            print(f"[MapMatcher] 无法加载大地图: {self.big_map_path}")
            return

        self.big_map = img
        self.big_map_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        keypoints, descriptors = self.orb.detectAndCompute(self.big_map_gray, None)
        self.big_map_keypoints = keypoints
        self.big_map_descriptors = descriptors

        print(f"[MapMatcher] 大地图加载成功，特征点数量: {len(keypoints)}")

    def extract_minimap(self, screenshot: np.ndarray, center: Tuple[int, int], radius: int) -> np.ndarray:
        """
        从截图中提取圆形小地图

        参数:
            screenshot: 游戏截图
            center: 小地图中心坐标 (x, y)
            radius: 小地图半径

        返回:
            圆形小地图图像
        """
        h, w = screenshot.shape[:2]
        cx, cy = center

        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)

        crop = screenshot[y1:y2, x1:x2].copy()

        if crop.size == 0:
            return None

        mask = np.zeros(crop.shape[:2], dtype=np.uint8)
        crop_cx = cx - x1
        crop_cy = cy - y1
        mask_radius = min(radius, crop.shape[0] // 2, crop.shape[1] // 2)
        cv2.circle(mask, (crop_cx, crop_cy), mask_radius, 255, -1)

        result = cv2.bitwise_and(crop, crop, mask=mask)
        return result

    def match_maps(self, minimap: np.ndarray, min_match_count: int = 10) -> bool:
        """
        执行小地图与大地图的特征匹配

        参数:
            minimap: 小地图图像
            min_match_count: 最小匹配点数量

        返回:
            是否匹配成功
        """
        if self.big_map_descriptors is None:
            print("[MapMatcher] 大地图未加载，无法匹配")
            return False

        if minimap is None or minimap.size == 0:
            print("[MapMatcher] 小地图无效，无法匹配")
            return False

        minimap_gray = cv2.cvtColor(minimap, cv2.COLOR_BGR2GRAY)

        keypoints, descriptors = self.orb.detectAndCompute(minimap_gray, None)

        if descriptors is None or len(keypoints) < min_match_count:
            print(f"[MapMatcher] 小地图特征点不足: {len(keypoints) if keypoints else 0}")
            return False

        matches = self.bf_matcher.match(descriptors, self.big_map_descriptors)

        if len(matches) < min_match_count:
            print(f"[MapMatcher] 匹配点不足: {len(matches)}")
            return False

        matches = sorted(matches, key=lambda x: x.distance)
        good_matches = matches[:min(len(matches), 100)]

        src_pts = np.float32([keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([self.big_map_keypoints[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if M is None:
            print("[MapMatcher] 无法计算变换矩阵")
            return False

        inliers = np.sum(mask)
        quality = inliers / len(good_matches)

        if quality < 0.1:
            print(f"[MapMatcher] 匹配质量过低: {quality:.2f}")
            return False

        self._extract_transform_params(M, inliers, len(good_matches))
        self.is_calibrated = True
        self.last_match_quality = quality

        print(f"[MapMatcher] 匹配成功! 质量={quality:.2f}, 内点={inliers}/{len(good_matches)}")
        print(f"[MapMatcher] 变换矩阵:\n{M}")
        print(f"[MapMatcher] 缩放={self.scale_ratio:.4f}, 平移=({self.translation[0]:.2f}, {self.translation[1]:.2f})")

        return True

    def _extract_transform_params(self, M: np.ndarray, inliers: int = 0, total_matches: int = 0):
        """
        从仿射变换矩阵中提取变换参数

        参数:
            M: 3x3 仿射变换矩阵
            inliers: 内点数量
            total_matches: 总匹配点数量
        """
        sx = np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2)
        sy = np.sqrt(M[0, 1] ** 2 + M[1, 1] ** 2)
        self.scale_ratio = (sx + sy) / 2

        self.translation = np.array([M[0, 2], M[1, 2]])

        self.rotation = np.arctan2(M[1, 0], M[0, 0]) * 180 / np.pi

        if total_matches > 0:
            print(f"[MapMatcher] 内点比例: {inliers/total_matches:.2%}")

    def minimap_to_bigmap(self, x: float, y: float) -> Tuple[float, float]:
        """
        将小地图坐标转换为大地图坐标

        参数:
            x, y: 小地图坐标

        返回:
            大地图坐标 (x, y)
        """
        if not self.is_calibrated:
            return x, y

        big_x = x * self.scale_ratio + self.translation[0]
        big_y = y * self.scale_ratio + self.translation[1]

        return big_x, big_y

    def bigmap_to_minimap(self, x: float, y: float) -> Tuple[float, float]:
        """
        将大地图坐标转换为小地图坐标

        参数:
            x, y: 大地图坐标

        返回:
            小地图坐标 (x, y)
        """
        if not self.is_calibrated or self.scale_ratio == 0:
            return x, y

        mini_x = (x - self.translation[0]) / self.scale_ratio
        mini_y = (y - self.translation[1]) / self.scale_ratio

        return mini_x, mini_y

    def get_transform_params(self) -> Dict[str, Any]:
        """
        获取当前变换参数

        返回:
            包含变换参数的字典
        """
        return {
            "scale_ratio": self.scale_ratio,
            "translation": self.translation.tolist(),
            "rotation": self.rotation,
            "is_calibrated": self.is_calibrated,
            "match_quality": self.last_match_quality
        }

    def reset_calibration(self):
        """重置校准状态"""
        self.is_calibrated = False
        self.scale_ratio = 1.0
        self.translation = np.array([0.0, 0.0])
        self.rotation = 0.0
        self.last_match_quality = 0.0
        print("[MapMatcher] 校准已重置")

    def calibrate_from_screenshot(self, minimap_center: Tuple[int, int], minimap_radius: int) -> bool:
        """
        从游戏截图进行校准

        参数:
            minimap_center: 小地图中心坐标 (x, y)
            minimap_radius: 小地图半径

        返回:
            是否校准成功
        """
        if self.vision is None:
            print("[MapMatcher] Vision 实例未设置，无法截图")
            return False

        screenshot = self.vision.screenshot()

        if screenshot is None:
            print("[MapMatcher] 截图失败")
            return False

        minimap = self.extract_minimap(screenshot, minimap_center, minimap_radius)

        if minimap is None:
            print("[MapMatcher] 提取小地图失败")
            return False

        return self.match_maps(minimap)

    def get_player_position_on_bigmap(self, minimap_center: Tuple[int, int], minimap_radius: int = 136) -> Optional[Tuple[float, float]]:
        """
        获取玩家在大地图上的位置

        参数:
            minimap_center: 小地图在屏幕上的中心坐标 (x, y)
            minimap_radius: 小地图半径

        返回:
            大地图坐标 (x, y)，如果未校准则返回 None
        """
        if not self.is_calibrated:
            return None

        player_x = self.translation[0] + minimap_radius * self.scale_ratio
        player_y = self.translation[1] + minimap_radius * self.scale_ratio

        return (player_x, player_y)
