import sys
import os
import time
import math
import cv2
from datetime import datetime
from pathlib import Path

from src.vision import vision
from src.config import cfg
from src.services.fishing_service import FishingService
from src.services.smart_pointer_debug_service import SmartPointerDebugService


def _angle_to_point(center_x, center_y, radius, angle_deg):
    radians = math.radians(angle_deg)
    point_x = int(center_x + (radius * math.cos(radians)))
    point_y = int(center_y - (radius * math.sin(radians)))
    return point_x, point_y


def _format_point(point):
    if point is None:
        return "None"
    return f"({int(round(point[0]))}, {int(round(point[1]))})"


def _draw_pointer_candidate(
    image,
    candidate,
    center_point,
    origin=(0, 0),
    line_color=(255, 255, 0),
    box_color=(255, 200, 0),
    label_prefix="DBG",
):
    return


def _capture_gauge_frames(gauge_region, initial_frame, frame_count=6, interval_s=0.03):
    frames = [initial_frame.copy()]
    for _ in range(max(0, frame_count - 1)):
        time.sleep(interval_s)
        frame = vision.screenshot(gauge_region)
        if frame is None or getattr(frame, "size", 0) == 0:
            continue
        frames.append(frame.copy())
    return frames


def _blend_motion_heatmap(image, heatmap):
    return image


def _draw_angle_marker(
    image,
    center_point,
    angle,
    radius,
    color,
    label,
):
    return


def _draw_smart_tension_overlay(image, recognition_results):
    gauge_region = cfg.get_rect("smart_tension_gauge")
    x, y, w, h = gauge_region
    gauge_image = image[y : y + h, x : x + w].copy()
    gauge_frames = _capture_gauge_frames(gauge_region, gauge_image)
    geometry = FishingService.detect_smart_gauge_geometry(gauge_image, gauge_region)
    legacy_pointer = FishingService.detect_smart_pointer(
        vision, gauge_image, gauge_region, geometry
    )
    gauge_debug_image = gauge_image.copy()

    if geometry is not None:
        center_x, center_y = map(int, geometry["center"])
        line_radius = max(1, int(geometry["radius"]))
    else:
        center_x = x + (w // 2)
        center_y = y + h
        line_radius = int(max(w, h) * 0.45)

    local_center = (center_x - x, center_y - y)
    local_center_int = (int(local_center[0]), int(local_center[1]))

    if legacy_pointer is not None:
        pointer_x, pointer_y = map(int, legacy_pointer["center"])
    else:
        pointer_x = None
        pointer_y = None

    danger_angle = FishingService.SMART_DANGER_ANGLE
    configured_release_angle = danger_angle + max(
        0.0, float(getattr(cfg, "smart_release_angle", 18.0))
    )
    configured_release_angle = min(configured_release_angle, 170.0)
    legacy_pointer_angle = None

    if legacy_pointer is not None:
        legacy_pointer_angle = math.degrees(
            math.atan2(center_y - pointer_y, pointer_x - center_x)
        )
        if legacy_pointer_angle < 0:
            legacy_pointer_angle += 360.0
        pointer_end = _angle_to_point(
            center_x, center_y, line_radius, legacy_pointer_angle
        )
    else:
        pointer_end = None

    debug_result = None
    debug_best = None
    motion_result = None
    motion_best = None
    fused_result = None
    try:
        if geometry is not None:
            vision._ensure_loaded()
            pointer_template = vision.raw_templates.get("pointer")
            if pointer_template is not None:
                debug_result = SmartPointerDebugService.analyze_pointer(
                    gauge_image,
                    pointer_template,
                    local_center,
                    float(line_radius),
                )
                debug_best = debug_result["best_candidate"]
    except Exception as e:
        recognition_results.append(f"张力盘新调试识别失败: {e}")

    try:
        motion_result = SmartPointerDebugService.analyze_motion_pointer(
            gauge_frames,
            local_center,
            float(line_radius),
        )
        motion_best = motion_result["best_candidate"]
    except Exception as e:
        recognition_results.append(f"张力盘运动识别失败: {e}")

    try:
        legacy_candidate = None
        if legacy_pointer_angle is not None:
            legacy_source = (
                "legacy_color"
                if legacy_pointer.get("method") == "color"
                else "legacy_template"
            )
            legacy_candidate = {
                "source": legacy_source,
                "angle": legacy_pointer_angle,
                "score": legacy_pointer.get("score", 0.0),
                "point": (
                    float(pointer_x - x),
                    float(pointer_y - y),
                ),
            }

        template_candidates = []
        if debug_result is not None:
            for candidate in debug_result.get("candidates", []):
                template_candidates.append(
                    {
                        "source": "template",
                        "angle": candidate["angle"],
                        "score": candidate["score"],
                        "point": candidate["tip_point"],
                    }
                )
        motion_candidate = None
        if motion_best is not None:
            motion_candidate = {
                "source": "motion",
                "angle": motion_best["angle"],
                "score": motion_best["score"],
                "point": motion_best["tip_point"],
            }

        fused_result = SmartPointerDebugService.fuse_pointer_candidates(
            legacy_candidate=legacy_candidate,
            template_candidates=template_candidates,
            motion_candidate=motion_candidate,
        )
    except Exception as e:
        recognition_results.append(f"融合识别失败: {e}")

    display_pointer_angle = None
    display_pointer_source = None
    if fused_result is not None and fused_result.get("angle") is not None:
        display_pointer_angle = fused_result["angle"]
        display_pointer_source = "fused"
    elif motion_best is not None:
        display_pointer_angle = motion_best["angle"]
        display_pointer_source = "motion"
    elif debug_best is not None:
        display_pointer_angle = debug_best["angle"]
        display_pointer_source = "template"
    elif legacy_pointer_angle is not None:
        display_pointer_angle = legacy_pointer_angle
        display_pointer_source = "legacy"

    danger_end = _angle_to_point(center_x, center_y, line_radius, danger_angle)
    configured_release_end = _angle_to_point(
        center_x, center_y, line_radius + 14, configured_release_angle
    )
    local_danger_end = _angle_to_point(
        local_center[0], local_center[1], line_radius, danger_angle
    )
    local_release_end = _angle_to_point(
        local_center[0], local_center[1], line_radius + 10, configured_release_angle
    )

    cv2.line(image, (center_x, center_y), configured_release_end, (0, 165, 255), 2)
    cv2.line(image, (center_x, center_y), danger_end, (0, 0, 255), 2)
    cv2.line(gauge_debug_image, local_center_int, local_release_end, (0, 165, 255), 2)
    cv2.line(gauge_debug_image, local_center_int, local_danger_end, (0, 0, 255), 2)

    if display_pointer_angle is not None:
        display_pointer_end = _angle_to_point(
            center_x, center_y, line_radius, display_pointer_angle
        )
        local_pointer_end = _angle_to_point(
            local_center[0], local_center[1], line_radius, display_pointer_angle
        )
        cv2.line(image, (center_x, center_y), display_pointer_end, (255, 255, 0), 2)
        cv2.line(
            gauge_debug_image,
            local_center_int,
            local_pointer_end,
            (255, 255, 0),
            2,
        )

    if geometry is not None:
        recognition_results.append(
            f"张力盘几何: center={_format_point((center_x, center_y))} radius={line_radius}"
        )
    else:
        recognition_results.append("张力盘几何: 未识别到圆弧，以下为兜底绘制")

    if legacy_pointer is not None:
        recognition_results.append(
            "旧识别: "
            f"method={legacy_pointer.get('method', 'unknown')} "
            f"angle={legacy_pointer_angle:.1f} "
            f"score={legacy_pointer.get('score', 0.0):.2f} "
            f"point={_format_point((pointer_x, pointer_y))}"
        )
    else:
        recognition_results.append("旧识别: 未识别到指针")

    if debug_best is not None:
        debug_tip_abs = (x + debug_best["tip_point"][0], y + debug_best["tip_point"][1])
        debug_root_abs = (
            x + debug_best["root_point"][0],
            y + debug_best["root_point"][1],
        )
        recognition_results.append(
            "新识别: "
            f"angle={debug_best['angle']:.1f} "
            f"score={debug_best['score']:.2f} "
            f"rot={debug_best['rotation']} "
            f"tip={_format_point(debug_tip_abs)} "
            f"root={_format_point(debug_root_abs)}"
        )
        if legacy_pointer_angle is not None:
            recognition_results.append(
                f"新旧角差: {SmartPointerDebugService.angle_delta(legacy_pointer_angle, debug_best['angle']):.1f}"
            )
    else:
        recognition_results.append("新识别: 未识别到指针")

    if debug_result:
        for index, candidate in enumerate(debug_result["candidates"][1:4], start=2):
            _draw_pointer_candidate(
                gauge_debug_image,
                candidate,
                local_center_int,
                origin=(0, 0),
                line_color=(180, 180, 0),
                box_color=(120, 200, 120),
                label_prefix=f"DBG{index}",
            )
            recognition_results.append(
                f"候选{index}: angle={candidate['angle']:.1f} score={candidate['score']:.2f} rot={candidate['rotation']}"
            )

    if motion_best is not None:
        recognition_results.append(
            "运动识别: "
            f"angle={motion_best['angle']:.1f} "
            f"score={motion_best['score']:.1f} "
            f"tip={_format_point((x + motion_best['tip_point'][0], y + motion_best['tip_point'][1]))}"
        )
        if debug_best is not None:
            recognition_results.append(
                f"运动-模板角差: {SmartPointerDebugService.angle_delta(motion_best['angle'], debug_best['angle']):.1f}"
            )
        if legacy_pointer_angle is not None:
            recognition_results.append(
                f"运动-旧识别角差: {SmartPointerDebugService.angle_delta(motion_best['angle'], legacy_pointer_angle):.1f}"
            )
    else:
        recognition_results.append("运动识别: 未识别到有效移动目标")

    if fused_result is not None:
        _draw_angle_marker(
            image,
            (center_x, center_y),
            fused_result["angle"],
            max(1, line_radius - 10),
            (255, 128, 0),
            "FUSED",
        )
        _draw_angle_marker(
            gauge_debug_image,
            local_center_int,
            fused_result["angle"],
            max(1, line_radius - 10),
            (255, 128, 0),
            "FUSED",
        )
        recognition_results.append(
            f"fusion: angle={fused_result['angle']:.1f} sources={'+'.join(fused_result['sources'])}"
        )
    else:
        recognition_results.append("fusion: none")

    return {
        "gauge_crop": gauge_debug_image,
        "best_candidate": debug_best,
        "motion_candidate": motion_best,
        "fused_candidate": fused_result,
    }


def generate_debug_screenshot(show_image=False):
    """
    Captures screen, draws debug overlays, and saves/shows the image.
    增强版：显示识别结果和置信度
    """
    print("Capturing screenshot...")
    screenshot = vision.screenshot()

    # 关键修复：使用 cfg.get_rect() 构建包含缩放坐标的配置字典
    debug_config = {}
    for name in cfg.REGIONS.keys():
        try:
            # 获取当前屏幕分辨率的正确缩放矩形
            debug_config[name] = list(cfg.get_rect(name))
        except Exception as e:
            print(f"Error calculating rect for {name}: {e}")

    # ========== 收集识别结果和置信度 ==========
    recognition_results = []

    # 1. 鱼饵数量识别
    try:
        bait_amount = vision.get_bait_amount()
        recognition_results.append(
            f"鱼饵数量: {bait_amount if bait_amount is not None else '无法识别'}"
        )
    except Exception as e:
        recognition_results.append(f"鱼饵数量: 错误 ({e})")

    # 2. 抛竿检测 (F1/F2)
    for template_name in ["F1_grayscale", "F2_grayscale"]:
        for region_name in ["cast_rod", "cast_rod_ice", "wait_bite"]:
            try:
                region = cfg.get_rect(region_name)
                result = vision.find_template_with_score(template_name, region=region)
                if result:
                    score, pos = result
                    if score >= 0.5:  # 只显示有一定置信度的结果
                        recognition_results.append(
                            f"{region_name}/{template_name}: {score:.2f}"
                        )
            except:
                pass

    # 3. 星星检测
    try:
        star_region = cfg.get_rect("reel_in_star")
        result = vision.find_template_with_score("star_grayscale", region=star_region)
        if result:
            score, pos = result
            recognition_results.append(f"收竿星星: {score:.2f}")
    except:
        pass

    # 4. 收鱼检测
    try:
        shangyu_region = cfg.get_rect("shangyu")
        result = vision.find_template_with_score(
            "shangyu_grayscale", region=shangyu_region
        )
        if result:
            score, pos = result
            recognition_results.append(f"收鱼按钮: {score:.2f}")
    except:
        pass

    # 5. 统一弹窗检测（感叹号）
    try:
        popup_region = cfg.get_rect("popup_exclamation")
        result = vision.find_template_with_score(
            "exclamation_grayscale", region=popup_region
        )
        if result:
            score, pos = result
            recognition_results.append(f"弹窗感叹号: {score:.2f}")
    except:
        pass

    # 6. 鱼桶图标检测
    try:
        result = vision.find_template_with_score("tong_gray", threshold=0.8)
        if result:
            score, pos = result
            recognition_results.append(f"鱼桶图标: {score:.2f} at {pos}")
    except:
        pass

    # 7. 鱼名提示区域检测（用于自动放生）
    try:
        fish_name_region = cfg.get_rect("fish_name_tooltip")
        recognition_results.append(f"鱼名提示区域: {fish_name_region}")
    except:
        pass

    # 8. 鱼桶关闭按钮区域检测
    try:
        bucket_close_region = cfg.get_rect("bucket_close_button")
        recognition_results.append(f"鱼桶关闭按钮区域: {bucket_close_region}")
        result = vision.find_template_with_score(
            "esc__grayscale", region=bucket_close_region
        )
        if result:
            score, pos = result
            recognition_results.append(f"鱼桶关闭按钮: {score:.2f} at {pos}")
    except:
        pass

    # 9. 智能收线张力盘三条线
    try:
        _draw_smart_tension_overlay(screenshot, recognition_results)
    except Exception as e:
        recognition_results.append(f"张力盘调试绘制失败: {e}")

    print("Drawing debug overlay...")
    # 使用新的 vision 方法就地修改截图
    # 传递识别结果给绘图函数
    vision.draw_debug_rects(screenshot, debug_config, recognition_results)

    # 绘制鱼桶 Zone1 的网格单元格、星星和锁定区域
    fish_inv = cfg.REGIONS.get("fish_inventory", {})
    zones = fish_inv.get("zones", [])
    if zones:
        zone = zones[0]  # 仅 Zone1
        x, y, w, h = zone["coords"]
        sx, sy = int(x * cfg.scale_x), int(y * cfg.scale_y)
        sw, sh = int(w * cfg.scale_x), int(h * cfg.scale_y)
        cv2.rectangle(screenshot, (sx, sy), (sx + sw, sy + sh), (255, 165, 0), 2)
        cv2.putText(
            screenshot,
            f"Zone{zone['id']}",
            (sx, sy - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 165, 0),
            2,
        )

        grid = zone.get("grid", {})
        rows, cols = grid.get("rows", 4), grid.get("cols", 4)
        cell_w, cell_h = grid.get("cell_width", 152), grid.get("cell_height", 151)
        star_ox, star_oy = grid.get("star_offset", (58, 112))
        star_w, star_h = grid.get("star_size", (47, 33))

        scaled_cell_w = int(cell_w * cfg.scale_x)
        scaled_cell_h = int(cell_h * cfg.scale_y)

        # 只绘制第一格 (row=0, col=0)
        # 星星区域 (青色)
        star_x = sx + int(star_ox * cfg.scale_x)
        star_y = sy + int(star_oy * cfg.scale_y)
        star_sw = int(star_w * cfg.scale_x)
        star_sh = int(star_h * cfg.scale_y)
        cv2.rectangle(
            screenshot,
            (star_x, star_y),
            (star_x + star_sw, star_y + star_sh),
            (255, 255, 0),
            1,
        )

        # 锁定区域 (红色)
        lock_x, lock_y, lock_w, lock_h = cfg.get_rect("fish_inventory_lock_slot_1")
        cv2.rectangle(
            screenshot,
            (lock_x, lock_y),
            (lock_x + lock_w, lock_y + lock_h),
            (0, 0, 255),
            1,
        )

    # 绘制加时按钮圆圈
    jiashi_yes_pos = cfg.get_center_anchored_pos(cfg.BTN_JIASHI_YES)
    jiashi_no_pos = cfg.get_center_anchored_pos(cfg.BTN_JIASHI_NO)

    cv2.circle(screenshot, jiashi_yes_pos, 10, (0, 255, 0), 2)
    cv2.putText(
        screenshot,
        "YES",
        (jiashi_yes_pos[0] + 15, jiashi_yes_pos[1] + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        2,
    )

    cv2.circle(screenshot, jiashi_no_pos, 10, (0, 0, 255), 2)
    cv2.putText(
        screenshot,
        "NO",
        (jiashi_no_pos[0] + 15, jiashi_no_pos[1] + 5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        2,
    )

    # 绘制鱼名提示区域（用于自动放生）
    try:
        fish_name_region = cfg.get_rect("fish_name_tooltip")
        x, y, w, h = fish_name_region
        cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.putText(
            screenshot,
            "Fish Name",
            (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            2,
        )
    except:
        pass

    # 绘制鱼桶关闭按钮区域
    try:
        x, y, w, h = cfg.get_rect("bucket_close_button")
        cv2.rectangle(screenshot, (x, y), (x + w, y + h), (255, 0, 255), 2)
        cv2.putText(
            screenshot,
            "Bucket Close",
            (x - 5, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 255),
            2,
        )
    except:
        pass

    # 绘制 UNO卡牌检测区域
    try:
        uno_region = cfg.get_rect("UNO卡牌")
        x, y, w, h = uno_region
        cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 0), 2)
    except:
        pass

    # 保存调试图像
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 使用集中配置获取正确的基础路径
    save_dir = cfg._get_application_path() / "debug_screenshots"

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    filename = f"visual_debug_{timestamp}.png"
    filepath = os.path.join(save_dir, filename)

    # 使用 cv2.imencode 优雅地处理潜在的非 ASCII 路径
    is_success, buffer = cv2.imencode(".png", screenshot)
    if is_success:
        with open(filepath, "wb") as f:
            f.write(buffer)
        print(f"Debug screenshot saved to: {filepath}")
    else:
        print("Failed to save debug screenshot.")
        return None

    if show_image:
        try:
            # Windows 使用 os.startfile，使用默认查看器
            os.startfile(filepath)
        except AttributeError:
            # 非 Windows 系统的回退方案
            import subprocess

            try:
                subprocess.call(["xdg-open", filepath])  # Linux
            except:
                try:
                    subprocess.call(["open", filepath])  # MacOS
                except:
                    # 如果系统查看器失败，回退到 OpenCV 窗口
                    print("Could not open default image viewer. Using OpenCV.")
                    cv2.imshow("Debug Overlay", screenshot)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()

    return filepath


def main():
    print("Starting Debug Overlay...")
    print(f"Screen Resolution: {cfg.screen_width}x{cfg.screen_height}")
    generate_debug_screenshot(show_image=False)


if __name__ == "__main__":
    main()
