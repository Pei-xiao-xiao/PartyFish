"""
手柄控制器模块
使用 pygame 实现手柄输入监听
"""

import threading
import time
from PySide6.QtCore import QObject, Signal


class GamepadController(QObject):
    gamepad_button_pressed = Signal(str)
    gamepad_connected = Signal(str)
    gamepad_disconnected = Signal(str)

    BUTTON_NAMES = {
        0: "A",
        1: "B",
        2: "X",
        3: "Y",
        4: "LB",
        5: "RB",
        6: "Back",
        7: "Start",
        8: "LS",
        9: "RS",
        10: "Guide",
        11: "DpadUp",
        12: "DpadDown",
        13: "DpadLeft",
        14: "DpadRight",
    }

    AXIS_NAMES = {
        0: "LeftStickX",
        1: "LeftStickY",
        2: "RightStickX",
        3: "RightStickY",
        4: "LeftTrigger",
        5: "RightTrigger",
    }

    def __init__(self):
        super().__init__()
        self._running = False
        self._thread = None
        self._joystick = None
        self._joystick_id = None
        self._pygame_initialized = False
        self._button_states = {}
        self._axis_states = {}
        self._axis_threshold = 0.5

    def _init_pygame(self):
        try:
            import pygame
            pygame.init()
            pygame.joystick.init()
            self._pygame_initialized = True
            return True
        except Exception as e:
            print(f"[Gamepad] Failed to initialize pygame: {e}")
            return False

    def start_listening(self):
        if self._running:
            return

        if not self._pygame_initialized:
            if not self._init_pygame():
                return

        self._running = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def stop_listening(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _listen_loop(self):
        import pygame

        while self._running:
            try:
                for event in pygame.event.get():
                    if event.type == pygame.JOYDEVICEADDED:
                        self._on_joystick_connected(event.device_index)
                    elif event.type == pygame.JOYDEVICEREMOVED:
                        self._on_joystick_disconnected()
                    elif event.type == pygame.JOYBUTTONDOWN:
                        if self._joystick and event.instance_id == self._joystick_id:
                            button_name = self.BUTTON_NAMES.get(event.button, f"Button{event.button}")
                            self._button_states[event.button] = True
                            self.gamepad_button_pressed.emit(button_name)
                    elif event.type == pygame.JOYBUTTONUP:
                        if self._joystick and event.instance_id == self._joystick_id:
                            self._button_states[event.button] = False
                    elif event.type == pygame.JOYAXISMOTION:
                        if self._joystick and event.instance_id == self._joystick_id:
                            self._handle_axis_motion(event.axis, event.value)
                    elif event.type == pygame.JOYHATMOTION:
                        if self._joystick and event.instance_id == self._joystick_id:
                            self._handle_hat_motion(event.value)

                if not self._joystick:
                    joystick_count = pygame.joystick.get_count()
                    if joystick_count > 0:
                        self._on_joystick_connected(0)

                time.sleep(0.01)
            except Exception as e:
                print(f"[Gamepad] Error in listen loop: {e}")
                time.sleep(0.1)

    def _on_joystick_connected(self, device_index):
        import pygame
        try:
            self._joystick = pygame.joystick.Joystick(device_index)
            self._joystick.init()
            self._joystick_id = self._joystick.get_instance_id()
            name = self._joystick.get_name()
            print(f"[Gamepad] Connected: {name}")
            self.gamepad_connected.emit(name)
        except Exception as e:
            print(f"[Gamepad] Failed to connect joystick: {e}")

    def _on_joystick_disconnected(self):
        if self._joystick:
            name = self._joystick.get_name()
            print(f"[Gamepad] Disconnected: {name}")
            self.gamepad_disconnected.emit(name)
            self._joystick = None
            self._joystick_id = None
            self._button_states.clear()
            self._axis_states.clear()

    def _handle_axis_motion(self, axis, value):
        axis_name = self.AXIS_NAMES.get(axis, f"Axis{axis}")
        prev_state = self._axis_states.get(axis, 0.0)

        if axis in [4, 5]:
            if value > self._axis_threshold and prev_state <= self._axis_threshold:
                self.gamepad_button_pressed.emit(axis_name)
        else:
            if value > self._axis_threshold and prev_state <= self._axis_threshold:
                self.gamepad_button_pressed.emit(f"{axis_name}+")
            elif value < -self._axis_threshold and prev_state >= -self._axis_threshold:
                self.gamepad_button_pressed.emit(f"{axis_name}-")

        self._axis_states[axis] = value

    def _handle_hat_motion(self, value):
        x, y = value
        if y == 1:
            self.gamepad_button_pressed.emit("DpadUp")
        elif y == -1:
            self.gamepad_button_pressed.emit("DpadDown")
        if x == 1:
            self.gamepad_button_pressed.emit("DpadRight")
        elif x == -1:
            self.gamepad_button_pressed.emit("DpadLeft")

    def is_connected(self):
        return self._joystick is not None

    def get_joystick_name(self):
        if self._joystick:
            return self._joystick.get_name()
        return None

    @staticmethod
    def get_available_joysticks():
        try:
            import pygame
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            
            joysticks = []
            for i in range(pygame.joystick.get_count()):
                joy = pygame.joystick.Joystick(i)
                joysticks.append((i, joy.get_name()))
            return joysticks
        except Exception:
            return []


gamepad_controller = GamepadController()
