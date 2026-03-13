"""
硬件信息获取模块
用于获取系统的硬件信息
"""

import os
import psutil

try:
    import wmi

    WMI_AVAILABLE = True
except ImportError:
    WMI_AVAILABLE = False


def get_account_name():
    """获取当前登录账号名"""
    try:
        return os.getlogin()
    except Exception:
        return "未知账号"


def get_cpu_info():
    """获取CPU型号"""
    cpu_list = []
    if WMI_AVAILABLE:
        try:
            # 使用wmi库获取CPU信息
            c = wmi.WMI()
            for processor in c.Win32_Processor():
                if processor.Name:
                    cpu_name = processor.Name.strip()
                    if cpu_name not in cpu_list:  # 避免重复
                        cpu_list.append(cpu_name)
            if cpu_list:
                return "; ".join(cpu_list)
        except Exception as e:
            print(f"wmi获取CPU信息失败: {e}")
    else:
        print("wmi库未安装，无法获取CPU信息")

    return "未知CPU"


def get_memory_info():
    """获取内存信息"""
    try:
        # 使用 psutil 库获取内存信息
        total_memory = psutil.virtual_memory().total
        # 转换为 GB
        total_memory_gb = total_memory / (1024**3)
        return f"{total_memory_gb:.1f} GB"
    except Exception as e:
        print(f"psutil 获取内存信息失败：{e}")
        return "未知内存"


def get_gpu_info():
    """获取GPU型号"""
    gpu_list = []
    if WMI_AVAILABLE:
        try:
            # 使用wmi库获取GPU信息
            c = wmi.WMI()
            for gpu in c.Win32_VideoController():
                if gpu.Name:
                    gpu_list.append(gpu.Name.strip())
            if gpu_list:
                return "; ".join(gpu_list)
        except Exception as e:
            print(f"wmi获取GPU信息失败: {e}")
    else:
        print("wmi库未安装，无法获取GPU信息")

    return "未知GPU"


def get_all_hardware_info():
    """
    获取所有硬件信息

    Returns:
        dict: 包含所有硬件信息的字典
    """
    return {
        "account_name": get_account_name(),
        "cpu": get_cpu_info(),
        "memory": get_memory_info(),
        "gpu": get_gpu_info(),
    }
