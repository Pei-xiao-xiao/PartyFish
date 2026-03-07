import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from qfluentwidgets import setTheme, Theme
from src.gui.main_window import MainWindow
from src.gui.welcome_dialog import show_welcome_dialog
from src.gui.single_instance import SingleInstance
from src.config import cfg

# 路径修复：处理打包后的应用和脚本运行两种情况
if getattr(sys, "frozen", False):
    # 打包后的应用：资源在 _MEIPASS，用户数据在可执行文件目录
    resources_path = Path(sys._MEIPASS)
    application_path = Path(sys.executable).parent
else:
    resources_path = Path(__file__).parent
    application_path = Path(__file__).parent

if __name__ == "__main__":
    try:
        # 在应用启动早期设置路径
        cfg.set_base_path(resources_path, application_path)

        # 创建单例管理器
        single_instance = SingleInstance("PartyFish")

        # 检查是否已有实例在运行
        if single_instance.is_running():
            # 输出日志
            print("[单例检测] 检测到 PartyFish 已在运行，阻止双开")
            # 直接调用显示消息方法
            single_instance.show_running_message()
            sys.exit(0)

        app = QApplication(sys.argv)

        # 启动单例服务器
        if not single_instance.start_server():
            print("警告: 无法启动单例服务器")

        # 设置应用程序字体
        ui_font = cfg.get_ui_font()
        app.setFont(QFont(ui_font, 9))
        print(f"系统语言字体: {ui_font}")

        # 获取当前硬件信息
        from src.services.hardware_info import get_all_hardware_info

        current_hardware = get_all_hardware_info()

        # 获取保存的硬件信息
        saved_hardware = cfg.global_settings.get("hardware_info", {})

        # 检查是否需要显示欢迎窗口
        # 如果是第一次运行，或者硬件信息发生变化（CPU、内存、GPU），则显示欢迎窗口
        # 注意：不比较 account_name，因为用户可能切换 Windows 账号
        hardware_keys_to_check = ["cpu", "memory", "gpu"]
        hardware_changed = any(
            current_hardware.get(key) != saved_hardware.get(key)
            for key in hardware_keys_to_check
        )

        if (
            not cfg.global_settings.get("welcome_dialog_shown", False)
            or hardware_changed
        ):
            # 显示欢迎提示窗口
            show_welcome_dialog()
            # 更新硬件信息和显示标志
            cfg.global_settings["hardware_info"] = current_hardware
            cfg.global_settings["welcome_dialog_shown"] = True
            cfg.save()

        # 根据配置设置主题
        if cfg.theme == "Light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

        # 调试：显示当前字体
        font = app.font()
        print(f"当前字体: {font.family()}, 大小: {font.pointSize()}")

        w = MainWindow()
        w.show()

        sys.exit(app.exec())
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        # 仅在非打包环境下等待用户输入
        if not getattr(sys, "frozen", False):
            input("Press Enter to exit...")
