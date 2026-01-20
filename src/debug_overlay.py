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
        recognition_results.append(f"鱼饵数量: {bait_amount if bait_amount is not None else '无法识别'}")
    except Exception as e:
        recognition_results.append(f"鱼饵数量: 错误 ({e})")
    
    # 2. 抛竿检测 (F1/F2)
    for template_name in ['F1_grayscale', 'F2_grayscale']:
        for region_name in ['cast_rod', 'cast_rod_ice', 'wait_bite']:
            try:
                region = cfg.get_rect(region_name)
                result = vision.find_template_with_score(template_name, region=region)
                if result:
                    score, pos = result
                    if score >= 0.5:  # 只显示有一定置信度的结果
                        recognition_results.append(f"{region_name}/{template_name}: {score:.2f}")
            except:
                pass
    
    # 3. 星星检测
    try:
        star_region = cfg.get_rect('reel_in_star')
        result = vision.find_template_with_score('star_grayscale', region=star_region)
        if result:
            score, pos = result
            recognition_results.append(f"收杆星星: {score:.2f}")
    except:
        pass
    
    # 4. 收鱼检测
    try:
        shangyu_region = cfg.get_rect('shangyu')
        result = vision.find_template_with_score('shangyu_grayscale', region=shangyu_region)
        if result:
            score, pos = result
            recognition_results.append(f"收鱼按钮: {score:.2f}")
    except:
        pass
    
    # 5. 统一弹窗检测（感叹号）
    try:
        popup_region = cfg.get_rect('popup_exclamation')
        result = vision.find_template_with_score('exclamation_grayscale', region=popup_region)
        if result:
            score, pos = result
            recognition_results.append(f"弹窗感叹号: {score:.2f}")
    except:
        pass

    print("Drawing debug overlay...")
    # Modify the screenshot in-place using the new vision method
    # 传递识别结果给绘图函数
    vision.draw_debug_rects(screenshot, debug_config, recognition_results)
    
    # Draw circles for Jiashi buttons
    jiashi_yes_pos = cfg.get_center_anchored_pos(cfg.BTN_JIASHI_YES)
    jiashi_no_pos = cfg.get_center_anchored_pos(cfg.BTN_JIASHI_NO)
    
    cv2.circle(screenshot, jiashi_yes_pos, 10, (0, 255, 0), 2)  # Green circle for YES
    cv2.putText(screenshot, 'YES', (jiashi_yes_pos[0] + 15, jiashi_yes_pos[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    
    cv2.circle(screenshot, jiashi_no_pos, 10, (0, 0, 255), 2)   # Red circle for NO
    cv2.putText(screenshot, 'NO', (jiashi_no_pos[0] + 15, jiashi_no_pos[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    
    # Save the debug image
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Use the centralized config to get the correct base path
    save_dir = cfg._get_base_path() / 'debug_screenshots'
    
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        
    filename = f"visual_debug_{timestamp}.png"
    filepath = os.path.join(save_dir, filename)
    
    # Use cv2.imencode to handle potential non-ASCII paths gracefully
    is_success, buffer = cv2.imencode(".png", screenshot)
    if is_success:
        with open(filepath, 'wb') as f:
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
                subprocess.call(['xdg-open', filepath]) # Linux
             except:
                try:
                    subprocess.call(['open', filepath]) # MacOS
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

