import sys
import os
import cv2
from datetime import datetime
from pathlib import Path

from src.vision import vision
from src.config import cfg


def generate_debug_screenshot(show_image=True):
    """
    Captures screen, draws debug overlays, and saves/shows the image.
    增强版：显示识别结果和置信度
    """
    print("Capturing screenshot...")
    screenshot = vision.screenshot()

    # CRITICAL FIX: Build the config dict with SCALED coordinates from cfg.get_rect()
    debug_config = {}
    for name in cfg.REGIONS.keys():
        try:
            # This gets the correctly scaled rectangle for the current screen resolution
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
            recognition_results.append(f"收杆星星: {score:.2f}")
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

    print("Drawing debug overlay...")
    # Modify the screenshot in-place using the new vision method
    # 传递识别结果给绘图函数
    vision.draw_debug_rects(screenshot, debug_config, recognition_results)

    # Draw fish inventory Zone1 with grid cells, stars, and locks
    fish_inv = cfg.REGIONS.get("fish_inventory", {})
    zones = fish_inv.get("zones", [])
    if zones:
        zone = zones[0]  # Only Zone1
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
        # Star region (cyan)
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

        # Lock region (red)
        lock_size = int(60 * cfg.scale_x)
        lock_x = sx + (scaled_cell_w - lock_size) // 2
        lock_y = sy + (scaled_cell_h - lock_size) // 2
        if cfg.window_offset_x > 0 or cfg.window_offset_y > 0:
            lock_x += int(25 * cfg.scale_x)
            lock_y += int(10 * cfg.scale_y)
        cv2.rectangle(
            screenshot,
            (lock_x, lock_y),
            (lock_x + lock_size, lock_y + lock_size),
            (0, 0, 255),
            1,
        )

    # Draw circles for Jiashi buttons
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

    # Draw fish name tooltip region (for auto-release)
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

    # Draw UNO卡牌 detection region
    try:
        uno_region = cfg.get_rect("UNO卡牌")
        x, y, w, h = uno_region
        cv2.rectangle(screenshot, (x, y), (x + w, y + h), (0, 255, 0), 2)
    except:
        pass

    # Save the debug image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use the centralized config to get the correct base path
    save_dir = cfg._get_application_path() / "debug_screenshots"

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    filename = f"visual_debug_{timestamp}.png"
    filepath = os.path.join(save_dir, filename)

    # Use cv2.imencode to handle potential non-ASCII paths gracefully
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
            # Use os.startfile for Windows, which uses the default viewer
            os.startfile(filepath)
        except AttributeError:
            # For non-Windows/Fallback
            import subprocess

            try:
                subprocess.call(["xdg-open", filepath])  # Linux
            except:
                try:
                    subprocess.call(["open", filepath])  # MacOS
                except:
                    # Fallback to OpenCV window if system viewer fails
                    print("Could not open default image viewer. Using OpenCV.")
                    cv2.imshow("Debug Overlay", screenshot)
                    cv2.waitKey(0)
                    cv2.destroyAllWindows()

    return filepath


def main():
    print("Starting Debug Overlay...")
    print(f"Screen Resolution: {cfg.screen_width}x{cfg.screen_height}")
    generate_debug_screenshot(show_image=True)


if __name__ == "__main__":
    main()
