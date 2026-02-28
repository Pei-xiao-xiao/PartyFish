"""
测试手柄控制器
"""
import sys
import time

# 测试 pygame 初始化
print("测试 1: 初始化 pygame...")
try:
    import pygame
    pygame.init()
    pygame.joystick.init()
    print("✓ pygame 初始化成功")
except Exception as e:
    print(f"✗ pygame 初始化失败：{e}")
    sys.exit(1)

# 测试手柄检测
print("\n测试 2: 检测手柄...")
joystick_count = pygame.joystick.get_count()
print(f"检测到的手柄数量：{joystick_count}")

if joystick_count > 0:
    for i in range(joystick_count):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        print(f"  手柄 {i}: {joy.get_name()}")
        print(f"    按钮数量：{joy.get_numbuttons()}")
        print(f"    轴数量：{joy.get_numaxes()}")
else:
    print("警告：未检测到手柄，请连接手柄后重试")

# 测试事件循环
print("\n测试 3: 测试手柄事件监听 (按 Ctrl+C 停止)...")
print("请按动手柄按钮测试...")

running = True
try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.JOYDEVICEADDED:
                print(f"[事件] 手柄连接：{event.device_index}")
            elif event.type == pygame.JOYDEVICEREMOVED:
                print(f"[事件] 手柄断开：{event.instance_id}")
            elif event.type == pygame.JOYBUTTONDOWN:
                print(f"[事件] 按钮按下：{event.button}")
            elif event.type == pygame.JOYBUTTONUP:
                print(f"[事件] 按钮释放：{event.button}")
            elif event.type == pygame.JOYAXISMOTION:
                print(f"[事件] 轴移动：轴{event.axis} 值{event.value}")
            elif event.type == pygame.JOYHATMOTION:
                print(f"[事件] 方向帽：{event.value}")
        
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\n测试结束")

pygame.quit()
print("✓ 测试完成")
