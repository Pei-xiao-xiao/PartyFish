import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, Theme
from src.gui.main_window import MainWindow
from src.gui.welcome_dialog import show_welcome_dialog
from src.config import cfg

# --- Path Fix ---
# Determine the base path in a way that is robust for both script and bundled app
if getattr(sys, 'frozen', False):
    # If the application is run as a bundle, the PyInstaller bootloader
    # creates a temp folder and stores path in _MEIPASS
    # BUT, we want the path to the executable itself
    application_path = Path(sys.executable).parent
else:
    application_path = Path(__file__).parent
# --- End Path Fix ---

if __name__ == "__main__":
    try:
        # Set this path in the config object EARLY, before any other part of the app uses it
        cfg.set_base_path(application_path)
        
        app = QApplication(sys.argv)
        
        # 获取当前硬件信息
        from src.gui.welcome_dialog import get_account_name, get_cpu_info, get_memory_info, get_gpu_info
        current_hardware = {
            "account_name": get_account_name(),
            "cpu": get_cpu_info(),
            "memory": get_memory_info(),
            "gpu": get_gpu_info()
        }
        
        # 获取保存的硬件信息
        saved_hardware = cfg.global_settings.get("hardware_info", {})
        
        # 检查是否需要显示欢迎窗口
        # 如果是第一次运行，或者硬件信息发生变化，则显示欢迎窗口
        if not cfg.global_settings.get("welcome_dialog_shown", False) or current_hardware != saved_hardware:
            # 显示欢迎提示窗口
            show_welcome_dialog()
            # 更新硬件信息和显示标志
            cfg.global_settings["hardware_info"] = current_hardware
            cfg.global_settings["welcome_dialog_shown"] = True
            cfg.save()
        
        # Set theme based on config
        if cfg.theme == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)
            
        w = MainWindow()
        w.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")

