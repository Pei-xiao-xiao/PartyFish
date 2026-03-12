import math

import cv2
import numpy as np


class SmartPointerDebugService:
    """Debug-only pointer matcher used to validate smart tension gauge detection."""

    POINTER_EDGE_LOW = 40
    POINTER_EDGE_HIGH = 120
    POINTER_MIN_RADIUS_RATIO = 1.15
    POINTER_MAX_RADIUS_RATIO = 1.95
    MOTION_MIN_RADIUS_RATIO = 1.0
    MOTION_MAX_RADIUS_RATIO = 2.1
    MOTION_DIFF_THRESHOLD = 18
    MOTION_HEAT_THRESHOLD_RATIO = 0.55
    MOTION_MIN_CONTOUR_AREA = 20

    @staticmethod
    def compute_angle(center_point, target_point):
        angle = math.degrees(
            math.atan2(
                center_point[1] - target_point[1], target_point[0] - center_point[0]
            )
        )
        if angle < 0:
            angle += 360.0
        return angle

    @staticmethod
    def angle_delta(angle_a, angle_b):
        diff = abs(angle_a - angle_b) % 360.0
        return min(diff, 360.0 - diff)

    @classmethod
    def _weighted_angle_average(cls, weighted_angles):
        if not weighted_angles:
            return None

        sum_x = 0.0
        sum_y = 0.0
        for angle, weight in weighted_angles:
            radians = math.radians(angle)
            sum_x += math.cos(radians) * weight
            sum_y += math.sin(radians) * weight

        if abs(sum_x) < 1e-6 and abs(sum_y) < 1e-6:
            total_weight = sum(weight for _, weight in weighted_angles)
            if total_weight <= 0.0:
                return None
            return (
                sum(angle * weight for angle, weight in weighted_angles) / total_weight
            )

        angle = math.degrees(math.atan2(sum_y, sum_x))
        if angle < 0:
            angle += 360.0
        return angle

    @staticmethod
    def _normalize_candidate(candidate):
        if candidate is None:
            return None

        angle = candidate.get("angle")
        if angle is None:
            return None

        normalized = dict(candidate)
        normalized["angle"] = float(angle)
        normalized["score"] = float(candidate.get("score", 0.0) or 0.0)
        normalized["source"] = str(candidate.get("source", "unknown"))
        return normalized

    @classmethod
    def _fusion_weight(cls, candidate):
        source = candidate.get("source", "unknown")
        raw_score = candidate.get("score", 0.0)
        raw_score = float(raw_score) if np.isfinite(raw_score) else 1.0
        raw_score = max(raw_score, 0.0)

        if source == "legacy_color":
            return 2.8 + min(raw_score, 1.0) * 1.6
        if source == "legacy_template":
            return 0.6 + min(raw_score, 1.0) * 0.3
        if source == "motion":
            return 2.2 + min(raw_score / 200.0, 1.8)
        if source == "template":
            return max(0.1, min(raw_score, 1.0) * 2.0)
        return 0.5 + min(raw_score, 1.0)

    @classmethod
    def fuse_pointer_candidates(
        cls,
        legacy_candidate=None,
        template_candidates=None,
        motion_candidate=None,
        angle_threshold=12.0,
    ):
        normalized_candidates = []
        for candidate in [legacy_candidate, motion_candidate]:
            normalized = cls._normalize_candidate(candidate)
            if normalized is not None:
                normalized["fusion_weight"] = cls._fusion_weight(normalized)
                normalized_candidates.append(normalized)

        for candidate in template_candidates or []:
            normalized = cls._normalize_candidate(candidate)
            if normalized is not None:
                normalized["fusion_weight"] = cls._fusion_weight(normalized)
                normalized_candidates.append(normalized)

        if not normalized_candidates:
            return None

        clusters = []
        for candidate in sorted(
            normalized_candidates,
            key=lambda item: item["fusion_weight"],
            reverse=True,
        ):
            best_cluster = None
            best_delta = None
            for cluster in clusters:
                delta = cls.angle_delta(candidate["angle"], cluster["center_angle"])
                if delta > angle_threshold:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_cluster = cluster

            if best_cluster is None:
                best_cluster = {
                    "candidates": [],
                    "center_angle": candidate["angle"],
                }
                clusters.append(best_cluster)

            best_cluster["candidates"].append(candidate)
            weighted_angles = [
                (item["angle"], item["fusion_weight"])
                for item in best_cluster["candidates"]
            ]
            best_cluster["center_angle"] = cls._weighted_angle_average(weighted_angles)

        best_cluster = None
        best_score = None
        for cluster in clusters:
            cluster_candidates = cluster["candidates"]
            sources = {item["source"] for item in cluster_candidates}
            cluster_weight = sum(item["fusion_weight"] for item in cluster_candidates)
            cluster_weight += max(0, len(sources) - 1) * 0.35
            if "motion" in sources:
                cluster_weight += 0.8
            if "legacy_color" in sources:
                cluster_weight += 0.6

            strongest = max(cluster_candidates, key=lambda item: item["fusion_weight"])[
                "fusion_weight"
            ]
            ordering = (cluster_weight, strongest, len(cluster_candidates))
            if best_score is None or ordering > best_score:
                best_score = ordering
                best_cluster = cluster

        if best_cluster is None:
            return None

        weighted_angles = [
            (item["angle"], item["fusion_weight"])
            for item in best_cluster["candidates"]
        ]
        fused_angle = cls._weighted_angle_average(weighted_angles)
        weighted_points = [
            (item.get("point"), item["fusion_weight"])
            for item in best_cluster["candidates"]
            if item.get("point") is not None
        ]
        fused_point = None
        if weighted_points:
            total_weight = sum(weight for _, weight in weighted_points)
            if total_weight > 0.0:
                fused_point = (
                    sum(point[0] * weight for point, weight in weighted_points)
                    / total_weight,
                    sum(point[1] * weight for point, weight in weighted_points)
                    / total_weight,
                )

        return {
            "angle": fused_angle,
            "score": best_score[0] if best_score is not None else 0.0,
            "point": fused_point,
            "sources": sorted({item["source"] for item in best_cluster["candidates"]}),
            "candidates": best_cluster["candidates"],
        }

    @classmethod
    def _extract_edges(cls, image):
        gray_image = (
            cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        )
        return cv2.Canny(gray_image, cls.POINTER_EDGE_LOW, cls.POINTER_EDGE_HIGH)

    @staticmethod
    def _rotate_template_with_alpha(template, angle):
        height, width = template.shape[:2]
        center = (width / 2.0, height / 2.0)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos_value = abs(matrix[0, 0])
        sin_value = abs(matrix[0, 1])
        bound_w = max(1, int((height * sin_value) + (width * cos_value)))
        bound_h = max(1, int((height * cos_value) + (width * sin_value)))

        matrix[0, 2] += (bound_w / 2.0) - center[0]
        matrix[1, 2] += (bound_h / 2.0) - center[1]

        border_value = (0, 0, 0, 0) if template.shape[2] == 4 else (0, 0, 0)
        rotated = cv2.warpAffine(
            template,
            matrix,
            (bound_w, bound_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_value,
        )

        if rotated.ndim == 3 and rotated.shape[2] == 4:
            alpha = rotated[:, :, 3]
            non_zero = cv2.findNonZero(alpha)
            if non_zero is None:
                return None
            crop_x, crop_y, crop_w, crop_h = cv2.boundingRect(non_zero)
            return rotated[crop_y : crop_y + crop_h, crop_x : crop_x + crop_w]

        return rotated

    @classmethod
    def _build_position_mask(
        cls, result_shape, template_width, template_height, gauge_center, gauge_radius
    ):
        x_coords = np.arange(result_shape[1], dtype=np.float32) + (template_width / 2.0)
        y_coords = np.arange(result_shape[0], dtype=np.float32) + (
            template_height / 2.0
        )
        grid_x, grid_y = np.meshgrid(x_coords, y_coords)

        delta_x = grid_x - gauge_center[0]
        delta_y = grid_y - gauge_center[1]
        distances = np.sqrt((delta_x * delta_x) + (delta_y * delta_y))

        angles = np.degrees(np.arctan2(gauge_center[1] - grid_y, delta_x))
        angles[angles < 0] += 360.0

        min_radius = gauge_radius * cls.POINTER_MIN_RADIUS_RATIO
        max_radius = gauge_radius * cls.POINTER_MAX_RADIUS_RATIO
        return (
            (distances >= min_radius)
            & (distances <= max_radius)
            & (angles >= 0.0)
            & (angles <= 180.0)
        )

    @classmethod
    def _build_candidate(
        cls,
        score,
        rotation,
        max_loc,
        mask_points,
        gauge_center,
        template_width,
        template_height,
    ):
        translated_points = mask_points + np.array(max_loc, dtype=np.float32)
        center_distances = np.linalg.norm(translated_points - gauge_center, axis=1)

        if translated_points.size == 0:
            return None

        tip_cutoff = np.quantile(center_distances, 0.98)
        root_cutoff = np.quantile(center_distances, 0.02)
        tip_point = translated_points[center_distances >= tip_cutoff].mean(axis=0)
        root_point = translated_points[center_distances <= root_cutoff].mean(axis=0)
        centroid_point = translated_points.mean(axis=0)
        bbox_center = np.array(
            [
                max_loc[0] + (template_width / 2.0),
                max_loc[1] + (template_height / 2.0),
            ],
            dtype=np.float32,
        )

        return {
            "score": float(score),
            "rotation": int(rotation),
            "bbox": (
                int(max_loc[0]),
                int(max_loc[1]),
                int(template_width),
                int(template_height),
            ),
            "bbox_center": (float(bbox_center[0]), float(bbox_center[1])),
            "tip_point": (float(tip_point[0]), float(tip_point[1])),
            "root_point": (float(root_point[0]), float(root_point[1])),
            "centroid_point": (float(centroid_point[0]), float(centroid_point[1])),
            "angle": cls.compute_angle(gauge_center, tip_point),
            "tip_distance": float(np.linalg.norm(tip_point - gauge_center)),
            "root_distance": float(np.linalg.norm(root_point - gauge_center)),
        }

    @classmethod
    def _evaluate_rotation(
        cls,
        gauge_edges,
        rotated_template,
        rotation,
        gauge_center,
        gauge_radius,
    ):
        if rotated_template is None:
            return None

        if rotated_template.ndim == 3 and rotated_template.shape[2] == 4:
            template_image = rotated_template[:, :, :3]
            template_mask = rotated_template[:, :, 3]
        else:
            template_image = rotated_template
            template_mask = None

        edge_template = cls._extract_edges(template_image)
        template_height, template_width = edge_template.shape[:2]
        gauge_height, gauge_width = gauge_edges.shape[:2]
        if template_height > gauge_height or template_width > gauge_width:
            return None

        result = cv2.matchTemplate(gauge_edges, edge_template, cv2.TM_CCOEFF_NORMED)
        if result.size == 0:
            return None

        valid_mask = cls._build_position_mask(
            result.shape,
            template_width,
            template_height,
            gauge_center,
            gauge_radius,
        )
        if not np.any(valid_mask):
            return None

        scored_result = result.copy()
        scored_result[~valid_mask] = -1.0
        _, max_val, _, max_loc = cv2.minMaxLoc(scored_result)
        if not np.isfinite(max_val) or max_val <= -1.0:
            return None

        if template_mask is not None:
            mask_binary = template_mask > 0
        else:
            mask_binary = edge_template > 0

        ys, xs = np.where(mask_binary)
        if xs.size == 0:
            return None

        mask_points = np.stack([xs.astype(np.float32), ys.astype(np.float32)], axis=1)
        return cls._build_candidate(
            max_val,
            rotation,
            max_loc,
            mask_points,
            gauge_center,
            template_width,
            template_height,
        )

    @staticmethod
    def _merge_candidates(candidates, top_k):
        merged = {}
        for candidate in candidates:
            if candidate is None:
                continue
            key = (
                candidate["rotation"],
                candidate["bbox"][0],
                candidate["bbox"][1],
            )
            previous = merged.get(key)
            if previous is None or candidate["score"] > previous["score"]:
                merged[key] = candidate

        ordered = sorted(
            merged.values(),
            key=lambda item: (item["score"], -item["root_distance"]),
            reverse=True,
        )
        return ordered[:top_k]

    @classmethod
    def _build_annulus_mask(
        cls,
        image_shape,
        gauge_center,
        gauge_radius,
        min_ratio=None,
        max_ratio=None,
    ):
        min_ratio = (
            cls.MOTION_MIN_RADIUS_RATIO if min_ratio is None else float(min_ratio)
        )
        max_ratio = (
            cls.MOTION_MAX_RADIUS_RATIO if max_ratio is None else float(max_ratio)
        )

        mask = np.zeros(image_shape[:2], dtype=np.uint8)
        grid_y, grid_x = np.indices(mask.shape, dtype=np.float32)
        delta_x = grid_x - gauge_center[0]
        delta_y = grid_y - gauge_center[1]
        distances = np.sqrt((delta_x * delta_x) + (delta_y * delta_y))
        angles = np.degrees(np.arctan2(gauge_center[1] - grid_y, delta_x))
        angles[angles < 0] += 360.0

        mask[
            (distances >= gauge_radius * min_ratio)
            & (distances <= gauge_radius * max_ratio)
            & (angles >= 0.0)
            & (angles <= 180.0)
        ] = 255
        return mask

    @classmethod
    def _extract_motion_mask(cls, previous_frame, current_frame, annulus_mask):
        kernel = np.ones((3, 3), dtype=np.uint8)
        previous_gray = cv2.GaussianBlur(
            cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY), (5, 5), 0
        )
        current_gray = cv2.GaussianBlur(
            cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY), (5, 5), 0
        )

        diff_image = cv2.absdiff(current_gray, previous_gray)
        _, diff_mask = cv2.threshold(
            diff_image, cls.MOTION_DIFF_THRESHOLD, 255, cv2.THRESH_BINARY
        )

        previous_edges = cls._extract_edges(previous_gray)
        current_edges = cls._extract_edges(current_gray)
        previous_edges = cv2.dilate(previous_edges, kernel, iterations=1)
        added_edges = cv2.bitwise_and(current_edges, cv2.bitwise_not(previous_edges))

        motion_mask = cv2.bitwise_or(diff_mask, added_edges)
        motion_mask = cv2.bitwise_and(motion_mask, annulus_mask)
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel)
        motion_mask = cv2.dilate(motion_mask, kernel, iterations=1)
        return motion_mask

    @classmethod
    def _build_motion_candidate(
        cls, contour, heatmap, latest_motion_mask, gauge_center, image_width
    ):
        area = cv2.contourArea(contour)
        if area < cls.MOTION_MIN_CONTOUR_AREA:
            return None

        contour_mask = np.zeros(heatmap.shape, dtype=np.uint8)
        cv2.drawContours(contour_mask, [contour], -1, 255, thickness=-1)
        ys, xs = np.where(contour_mask > 0)
        if xs.size == 0:
            return None

        points = np.stack([xs.astype(np.float32), ys.astype(np.float32)], axis=1)
        point_weights = heatmap[ys, xs].astype(np.float32)
        if float(point_weights.sum()) <= 0.0:
            return None

        latest_selector = latest_motion_mask > 0
        latest_ys, latest_xs = np.where(latest_selector)
        if latest_xs.size >= 8:
            motion_points = np.stack(
                [latest_xs.astype(np.float32), latest_ys.astype(np.float32)], axis=1
            )
            motion_weights = np.ones(latest_xs.shape[0], dtype=np.float32)
        else:
            motion_points = points
            motion_weights = point_weights

        center_distances = np.linalg.norm(motion_points - gauge_center, axis=1)
        tip_cutoff = np.quantile(center_distances, 0.97)
        root_cutoff = np.quantile(center_distances, 0.03)
        tip_weights = motion_weights[center_distances >= tip_cutoff]
        tip_points = motion_points[center_distances >= tip_cutoff]
        root_weights = motion_weights[center_distances <= root_cutoff]
        root_points = motion_points[center_distances <= root_cutoff]
        tip_point = np.average(tip_points, axis=0, weights=tip_weights)
        root_point = np.average(root_points, axis=0, weights=root_weights)
        centroid_point = np.average(points, axis=0, weights=point_weights)

        bbox_x, bbox_y, bbox_w, bbox_h = cv2.boundingRect(contour)
        mean_weight = float(point_weights.mean())
        weight_sum = float(point_weights.sum())
        right_bias = (
            1.0 + (float(centroid_point[0]) / max(float(image_width), 1.0)) * 0.15
        )
        score = weight_sum * right_bias

        return {
            "score": score,
            "area": float(area),
            "bbox": (int(bbox_x), int(bbox_y), int(bbox_w), int(bbox_h)),
            "bbox_center": (
                float(bbox_x + (bbox_w / 2.0)),
                float(bbox_y + (bbox_h / 2.0)),
            ),
            "tip_point": (float(tip_point[0]), float(tip_point[1])),
            "root_point": (float(root_point[0]), float(root_point[1])),
            "centroid_point": (float(centroid_point[0]), float(centroid_point[1])),
            "angle": cls.compute_angle(gauge_center, tip_point),
            "tip_distance": float(np.linalg.norm(tip_point - gauge_center)),
            "root_distance": float(np.linalg.norm(root_point - gauge_center)),
            "mean_weight": mean_weight,
        }

    @classmethod
    def analyze_pointer(
        cls,
        gauge_image,
        template_rgba,
        gauge_center,
        gauge_radius,
        coarse_step=3,
        refine_step=1,
        refine_window=3,
        top_k=5,
    ):
        if gauge_image is None or getattr(gauge_image, "size", 0) == 0:
            return {"best_candidate": None, "candidates": []}
        if template_rgba is None:
            return {"best_candidate": None, "candidates": []}

        gauge_edges = cls._extract_edges(gauge_image)
        candidates = []

        coarse_best = None
        for rotation in range(0, 181, coarse_step):
            rotated_template = cls._rotate_template_with_alpha(template_rgba, rotation)
            candidate = cls._evaluate_rotation(
                gauge_edges,
                rotated_template,
                rotation,
                gauge_center,
                gauge_radius,
            )
            if candidate is not None:
                candidates.append(candidate)
                if coarse_best is None or candidate["score"] > coarse_best["score"]:
                    coarse_best = candidate

        if coarse_best is None:
            return {"best_candidate": None, "candidates": []}

        refine_start = max(0, coarse_best["rotation"] - refine_window)
        refine_end = min(180, coarse_best["rotation"] + refine_window)
        for rotation in range(refine_start, refine_end + 1, refine_step):
            rotated_template = cls._rotate_template_with_alpha(template_rgba, rotation)
            candidate = cls._evaluate_rotation(
                gauge_edges,
                rotated_template,
                rotation,
                gauge_center,
                gauge_radius,
            )
            if candidate is not None:
                candidates.append(candidate)

        top_candidates = cls._merge_candidates(candidates, top_k)
        best_candidate = top_candidates[0] if top_candidates else None
        return {
            "best_candidate": best_candidate,
            "candidates": top_candidates,
        }

    @classmethod
    def analyze_motion_pointer(
        cls,
        gauge_frames,
        gauge_center,
        gauge_radius,
        top_k=5,
    ):
        if gauge_frames is None or len(gauge_frames) < 2:
            return {
                "best_candidate": None,
                "candidates": [],
                "heatmap": None,
                "candidate_mask": None,
                "latest_motion_mask": None,
            }

        annulus_mask = cls._build_annulus_mask(
            gauge_frames[0].shape,
            gauge_center,
            gauge_radius,
        )
        heatmap = np.zeros(annulus_mask.shape, dtype=np.float32)
        latest_motion_mask = np.zeros_like(annulus_mask)

        for index in range(1, len(gauge_frames)):
            motion_mask = cls._extract_motion_mask(
                gauge_frames[index - 1],
                gauge_frames[index],
                annulus_mask,
            )
            latest_motion_mask = motion_mask
            heatmap += (index + 1) * (motion_mask > 0).astype(np.float32)

        max_value = float(heatmap.max())
        if max_value <= 0.0:
            return {
                "best_candidate": None,
                "candidates": [],
                "heatmap": heatmap,
                "candidate_mask": None,
                "latest_motion_mask": latest_motion_mask,
            }

        candidate_mask = (
            heatmap >= max(1.0, max_value * cls.MOTION_HEAT_THRESHOLD_RATIO)
        ).astype(np.uint8) * 255
        contours, _ = cv2.findContours(
            candidate_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        candidates = []
        for contour in contours:
            candidate = cls._build_motion_candidate(
                contour,
                heatmap,
                latest_motion_mask,
                gauge_center,
                gauge_frames[0].shape[1],
            )
            if candidate is not None:
                candidates.append(candidate)

        ordered_candidates = sorted(
            candidates,
            key=lambda item: (item["score"], item["tip_point"][0]),
            reverse=True,
        )[:top_k]

        return {
            "best_candidate": ordered_candidates[0] if ordered_candidates else None,
            "candidates": ordered_candidates,
            "heatmap": heatmap,
            "candidate_mask": candidate_mask,
            "latest_motion_mask": latest_motion_mask,
        }
