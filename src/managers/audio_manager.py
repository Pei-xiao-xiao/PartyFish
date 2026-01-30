"""
音频管理器
负责管理应用中的所有音频播放功能
"""

from PySide6.QtCore import QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioManager:
    """音频管理器类"""

    def __init__(self, main_window):
        """
        初始化音频管理器

        Args:
            main_window: MainWindow 实例
        """
        self.window = main_window
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

    def play_sound_alert(self, alert_type):
        """播放提示音"""
        try:
            from src.config import cfg

            base_path = cfg._get_base_path()
            if alert_type == "no_bait":
                sound_file = base_path / "data" / "audio" / "no_bait.mp3"
            elif alert_type == "inventory_full":
                sound_file = base_path / "data" / "audio" / "inventory_full.mp3"
            else:
                return

            self.player.setSource(QUrl.fromLocalFile(str(sound_file)))
            self.player.play()
            self.window.append_log(f"播放提示音: {sound_file.name}")
        except Exception as e:
            self.window.append_log(f"播放提示音失败: {e}")

    def play_control_sound(self, sound_type):
        """播放控制音效（启动/暂停）"""
        try:
            from src.config import cfg

            if not cfg.global_settings.get("control_sound_enabled", False):
                return
            base_path = cfg._get_base_path()
            sound_file = base_path / "data" / "audio" / f"{sound_type}.mp3"
            self.player.setSource(QUrl.fromLocalFile(str(sound_file)))
            self.player.play()
        except Exception as e:
            self.window.append_log(f"播放控制音效失败: {e}")
