from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QFileDialog,
    QProgressDialog,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread
from datetime import datetime
from pathlib import Path
from qfluentwidgets import (
    ScrollArea,
    SettingCardGroup,
    SettingCard,
    FluentIcon,
    DoubleSpinBox,
    SpinBox,
    SwitchSettingCard,
    Slider,
    BodyLabel,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    LineEdit,
    CheckBox,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    MessageBoxBase,
    SubtitleLabel,
    SegmentedWidget,
)
from src.config import cfg
from src.gui.components import KeyBindingWidget
from src.services.record_manager import record_manager


class ServerRegionDialog(MessageBoxBase):
    """区服选择对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel("选择区服", self)
        self.contentLabel = BodyLabel("请选择该账号的区服类型：", self)

        self.regionCombo = ComboBox(self)
        self.regionCombo.addItems(["国服 (00:00 重置)", "国际服 (12:00 重置)"])
        self.regionCombo.setCurrentIndex(0)
        self.regionCombo.setFixedWidth(200)

        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)
        self.viewLayout.addWidget(self.regionCombo)

        self.yesButton.setText("确定")
        self.cancelButton.setText("取消")

        self.widget.setMinimumWidth(300)

    def get_selected_region(self):
        """返回选择的区服：'CN' 或 'Global'"""
        return "CN" if self.regionCombo.currentIndex() == 0 else "Global"


class SmartDoubleSpinBox(DoubleSpinBox):
    """智能格式化 DoubleSpinBox，自动去除末尾多余的 0"""

    def textFromValue(self, value):
        """格式化显示值，去除末尾多余的 0，但保留至少 2 位小数"""
        # 先格式化为 3 位小数
        text = f"{value:.3f}"
        # 去除末尾的 0
        text = text.rstrip("0")
        # 确保至少保留 2 位小数（如果是 x.0 则变成 x.00）
        if "." in text:
            integer_part, decimal_part = text.split(".")
            if len(decimal_part) < 2:
                text = f"{integer_part}.{decimal_part.ljust(2, '0')}"
        return text


class ImportWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(bool, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path

    def run(self):
        success, message = record_manager.import_records(
            self.file_path, self.progress.emit
        )
        self.finished.emit(success, message)


class SettingsInterface(ScrollArea):
    hotkey_changed_signal = Signal(str)
    debug_hotkey_changed_signal = Signal(str)
    sell_hotkey_changed_signal = Signal(str)
    uno_hotkey_changed_signal = Signal(str)
    theme_changed_signal = Signal(str)
    account_list_changed_signal = Signal()
    records_updated_signal = Signal()
    reset_overlay_position_signal = Signal()
    release_mode_changed_signal = Signal(str)
    season_filter_changed_signal = Signal()
    gamepad_mapping_changed_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self._loading_ui = False

        # 初始化滚动控件
        self.scrollWidget = QWidget()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # 初始化布局
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 10)
        self.vBoxLayout.setSpacing(12)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

        # 添加分段控件
        self.segmentedWidget = SegmentedWidget(self.scrollWidget)
        self.segmentedWidget.addItem("fishing", "钓鱼设置")
        self.segmentedWidget.addItem("function", "功能设置")
        self.segmentedWidget.addItem("data", "数据管理")
        self.segmentedWidget.setCurrentItem("fishing")
        self.segmentedWidget.currentItemChanged.connect(self._onSegmentChanged)
        self.vBoxLayout.addWidget(self.segmentedWidget)

        # 1. Preset Selection Group
        self.presetGroup = SettingCardGroup(self.tr("预设配置"), self.scrollWidget)
        self.presetCard = SettingCard(
            FluentIcon.TAG,
            self.tr("当前预设"),
            self.tr("选择一套预设进行编辑"),
            parent=self.presetGroup,
        )
        self.presetComboBox = ComboBox(self.presetCard)
        self.presetComboBox.addItems(cfg.presets.keys())
        self.presetComboBox.setCurrentText(cfg.current_preset_name)
        self.presetComboBox.setFixedWidth(150)
        self.presetCard.hBoxLayout.addWidget(self.presetComboBox, 0, Qt.AlignRight)
        margins = self.presetCard.hBoxLayout.contentsMargins()
        self.presetCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.presetGroup.addSettingCard(self.presetCard)
        self.vBoxLayout.addWidget(self.presetGroup)

        # 2. Fishing Config Group
        self.fishingGroup = SettingCardGroup(self.tr("钓鱼参数配置"), self.scrollWidget)

        self.reelInTimeCard = self._create_double_spinbox_card(
            icon=FluentIcon.SPEED_HIGH,
            title=self.tr("收线时间"),
            content=self.tr("按下收线键的持续时间 (秒)"),
            config_key="reel_in_time",
        )
        self.fishingGroup.addSettingCard(self.reelInTimeCard)

        self.releaseTimeCard = self._create_double_spinbox_card(
            icon=FluentIcon.SPEED_OFF,
            title=self.tr("放线时间"),
            content=self.tr("松开按键的持续时间 (秒)"),
            config_key="release_time",
        )
        self.fishingGroup.addSettingCard(self.releaseTimeCard)

        self.cycleIntervalCard = self._create_double_spinbox_card(
            icon=FluentIcon.HISTORY,
            title=self.tr("循环间隔"),
            content=self.tr("两次循环之间的等待时间 (秒)"),
            config_key="cycle_interval",
        )
        self.fishingGroup.addSettingCard(self.cycleIntervalCard)

        self.maxPullsCard = SettingCard(
            FluentIcon.SYNC,
            self.tr("最大拉杆次数"),
            self.tr("单次钓鱼过程中的最大拉杆尝试次数"),
        )
        self.maxPullsSpinBox = SpinBox(self.maxPullsCard)
        self.maxPullsSpinBox.setRange(1, 100)
        self.maxPullsCard.hBoxLayout.addWidget(self.maxPullsSpinBox, 0, Qt.AlignRight)
        margins = self.maxPullsCard.hBoxLayout.contentsMargins()
        self.maxPullsCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.fishingGroup.addSettingCard(self.maxPullsCard)

        self.vBoxLayout.addWidget(self.fishingGroup)

        # 3. Save and Reset Buttons
        self.saveResetButtonWidget = QWidget(self)
        self.saveResetButtonLayout = QHBoxLayout(self.saveResetButtonWidget)
        self.saveResetButtonLayout.setContentsMargins(0, 0, 0, 0)
        self.saveResetButtonLayout.setSpacing(10)
        self.saveResetButtonLayout.addStretch(1)

        self.resetFishingConfigButton2 = PushButton(
            self.tr("恢复默认"), self.saveResetButtonWidget
        )
        self.resetFishingConfigButton2.setFixedWidth(100)
        self.savePresetButton = PrimaryPushButton(
            self.tr("保存钓鱼配置"), self.saveResetButtonWidget
        )
        self.savePresetButton.setFixedWidth(120)

        self.saveResetButtonLayout.addWidget(self.resetFishingConfigButton2)
        self.saveResetButtonLayout.addWidget(self.savePresetButton)

        self.vBoxLayout.addWidget(self.saveResetButtonWidget, 0, Qt.AlignRight)

        # 4. Global Settings Group
        self.globalGroup = SettingCardGroup(self.tr("全局配置"), self.scrollWidget)

        self.enableGamepadCard = SwitchSettingCard(
            FluentIcon.GAME,
            self.tr("启用手柄支持"),
            self.tr("开启后可使用手柄按键触发功能"),
        )
        self.globalGroup.addSettingCard(self.enableGamepadCard)

        self.hotkeyCard = SettingCard(
            FluentIcon.SETTING,
            self.tr("启动/暂停快捷键"),
            self.tr("设置用于启动和暂停脚本的全局快捷键。"),
        )
        self.hotkeyLineEdit = KeyBindingWidget(self.hotkeyCard)
        self.hotkeyLineEdit.setFixedWidth(100)
        self.hotkeyCard.hBoxLayout.addWidget(self.hotkeyLineEdit, 0, Qt.AlignRight)
        self.hotkeyCard.hBoxLayout.addSpacing(5)
        self.hotkeyGamepadLineEdit = KeyBindingWidget(self.hotkeyCard)
        self.hotkeyGamepadLineEdit.set_gamepad_mode(True)
        self.hotkeyGamepadLineEdit.setFixedWidth(100)
        self.hotkeyGamepadLineEdit.setPlaceholderText("手柄")
        toggle_gamepad_mapping = cfg.get_gamepad_mapping("toggle")
        self.hotkeyGamepadLineEdit.set_gamepad_binding(toggle_gamepad_mapping)
        self.hotkeyCard.hBoxLayout.addWidget(
            self.hotkeyGamepadLineEdit, 0, Qt.AlignRight
        )
        self.hotkeyCard.hBoxLayout.addSpacing(5)
        self.hotkeyGamepadModeCombo = self._create_gamepad_mode_combo(
            self.hotkeyCard, toggle_gamepad_mapping.get("mode", "press")
        )
        self.hotkeyCard.hBoxLayout.addWidget(
            self.hotkeyGamepadModeCombo, 0, Qt.AlignRight
        )
        self.hotkeyCard.hBoxLayout.addSpacing(5)
        self.hotkeyGamepadHoldSpinBox = self._create_gamepad_hold_spinbox(
            self.hotkeyCard, toggle_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.hotkeyCard.hBoxLayout.addWidget(
            self.hotkeyGamepadHoldSpinBox, 0, Qt.AlignRight
        )
        self.hotkeyGamepadModeCombo.hide()
        self.hotkeyGamepadHoldSpinBox.hide()
        margins = self.hotkeyCard.hBoxLayout.contentsMargins()
        self.hotkeyCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.hotkeyCard)

        self.debugHotkeyCard = SettingCard(
            FluentIcon.DEVELOPER_TOOLS,
            self.tr("调试快捷键"),
            self.tr("设置用于触发调试功能的全局快捷键。"),
        )
        self.debugHotkeyLineEdit = KeyBindingWidget(self.debugHotkeyCard)
        self.debugHotkeyLineEdit.setFixedWidth(100)
        self.debugHotkeyCard.hBoxLayout.addWidget(
            self.debugHotkeyLineEdit, 0, Qt.AlignRight
        )
        self.debugHotkeyCard.hBoxLayout.addSpacing(5)
        self.debugGamepadLineEdit = KeyBindingWidget(self.debugHotkeyCard)
        self.debugGamepadLineEdit.set_gamepad_mode(True)
        self.debugGamepadLineEdit.setFixedWidth(100)
        self.debugGamepadLineEdit.setPlaceholderText("手柄")
        debug_gamepad_mapping = cfg.get_gamepad_mapping("debug")
        self.debugGamepadLineEdit.set_gamepad_binding(debug_gamepad_mapping)
        self.debugHotkeyCard.hBoxLayout.addWidget(
            self.debugGamepadLineEdit, 0, Qt.AlignRight
        )
        self.debugHotkeyCard.hBoxLayout.addSpacing(5)
        self.debugGamepadModeCombo = self._create_gamepad_mode_combo(
            self.debugHotkeyCard, debug_gamepad_mapping.get("mode", "press")
        )
        self.debugHotkeyCard.hBoxLayout.addWidget(
            self.debugGamepadModeCombo, 0, Qt.AlignRight
        )
        self.debugHotkeyCard.hBoxLayout.addSpacing(5)
        self.debugGamepadHoldSpinBox = self._create_gamepad_hold_spinbox(
            self.debugHotkeyCard,
            debug_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )
        self.debugHotkeyCard.hBoxLayout.addWidget(
            self.debugGamepadHoldSpinBox, 0, Qt.AlignRight
        )
        self.debugGamepadModeCombo.hide()
        self.debugGamepadHoldSpinBox.hide()
        margins = self.debugHotkeyCard.hBoxLayout.contentsMargins()
        self.debugHotkeyCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.debugHotkeyCard)

        self.sellHotkeyCard = SettingCard(
            FluentIcon.SHOPPING_CART,
            self.tr("卖鱼快捷键"),
            self.tr("设置用于一键卖鱼的快捷键。"),
        )
        self.sellHotkeyLineEdit = KeyBindingWidget(self.sellHotkeyCard)
        self.sellHotkeyLineEdit.setFixedWidth(100)
        self.sellHotkeyCard.hBoxLayout.addWidget(
            self.sellHotkeyLineEdit, 0, Qt.AlignRight
        )
        self.sellHotkeyCard.hBoxLayout.addSpacing(5)
        self.sellGamepadLineEdit = KeyBindingWidget(self.sellHotkeyCard)
        self.sellGamepadLineEdit.set_gamepad_mode(True)
        self.sellGamepadLineEdit.setFixedWidth(100)
        self.sellGamepadLineEdit.setPlaceholderText("手柄")
        sell_gamepad_mapping = cfg.get_gamepad_mapping("sell")
        self.sellGamepadLineEdit.set_gamepad_binding(sell_gamepad_mapping)
        self.sellHotkeyCard.hBoxLayout.addWidget(
            self.sellGamepadLineEdit, 0, Qt.AlignRight
        )
        self.sellHotkeyCard.hBoxLayout.addSpacing(5)
        self.sellGamepadModeCombo = self._create_gamepad_mode_combo(
            self.sellHotkeyCard, sell_gamepad_mapping.get("mode", "press")
        )
        self.sellHotkeyCard.hBoxLayout.addWidget(
            self.sellGamepadModeCombo, 0, Qt.AlignRight
        )
        self.sellHotkeyCard.hBoxLayout.addSpacing(5)
        self.sellGamepadHoldSpinBox = self._create_gamepad_hold_spinbox(
            self.sellHotkeyCard,
            sell_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )
        self.sellHotkeyCard.hBoxLayout.addWidget(
            self.sellGamepadHoldSpinBox, 0, Qt.AlignRight
        )
        self.sellGamepadModeCombo.hide()
        self.sellGamepadHoldSpinBox.hide()
        margins = self.sellHotkeyCard.hBoxLayout.contentsMargins()
        self.sellHotkeyCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.sellHotkeyCard)

        self.jiashiCard = SwitchSettingCard(
            FluentIcon.CARE_UP_SOLID,
            self.tr("自动加时"),
            self.tr("检测到加时弹窗时自动点击'是'"),
        )
        self.globalGroup.addSettingCard(self.jiashiCard)

        self.autoClickSellCard = SwitchSettingCard(
            FluentIcon.ROBOT,
            self.tr("自动卖鱼点击"),
            self.tr("使用快捷键卖鱼时，识别后是否自动点击卖出按钮"),
        )
        self.globalGroup.addSettingCard(self.autoClickSellCard)

        self.antiAfkCard = SwitchSettingCard(
            FluentIcon.VIEW,
            self.tr("视觉防挂机"),
            self.tr("检测挂机弹窗并自动点击恢复"),
        )
        self.globalGroup.addSettingCard(self.antiAfkCard)

        self.soundAlertCard = SwitchSettingCard(
            FluentIcon.MUSIC, self.tr("提示音效"), self.tr("没鱼饵或鱼桶满时播放提示音")
        )
        self.globalGroup.addSettingCard(self.soundAlertCard)

        self.fishRecognitionCard = SwitchSettingCard(
            FluentIcon.SEARCH,
            self.tr("鱼类识别"),
            self.tr("开启时识别鱼类信息并记录，关闭时仅执行钓鱼动作"),
        )
        self.globalGroup.addSettingCard(self.fishRecognitionCard)

        self.seasonFilterCard = SwitchSettingCard(
            FluentIcon.CALENDAR,
            self.tr("季节筛选"),
            self.tr("关闭后图鉴筛选时不考虑季节条件"),
        )
        self.globalGroup.addSettingCard(self.seasonFilterCard)

        self.legendaryScreenshotCard = SwitchSettingCard(
            FluentIcon.CAMERA,
            self.tr("传奇截图"),
            self.tr("钓到传奇品质鱼类时自动截图保存"),
        )
        self.globalGroup.addSettingCard(self.legendaryScreenshotCard)

        self.firstCatchScreenshotCard = SwitchSettingCard(
            FluentIcon.CAMERA,
            self.tr("首次捕获截图"),
            self.tr("首次捕获新鱼类时自动截图保存"),
        )
        self.globalGroup.addSettingCard(self.firstCatchScreenshotCard)

        self.jitterCard = SettingCard(
            FluentIcon.SYNC, "时间抖动范围", "设置操作时间的随机波动百分比 (0% - 30%)"
        )
        self.jitterSlider = Slider(Qt.Orientation.Horizontal)
        self.jitterLabel = BodyLabel("0%")
        self.jitterSlider.setRange(0, 30)
        self.jitterCard.hBoxLayout.addStretch(1)
        self.jitterCard.hBoxLayout.addWidget(self.jitterSlider)
        self.jitterCard.hBoxLayout.addSpacing(15)
        self.jitterCard.hBoxLayout.addWidget(self.jitterLabel)
        self.globalGroup.addSettingCard(self.jitterCard)

        self.themeCard = SettingCard(
            FluentIcon.PALETTE, self.tr("主题设置"), self.tr("选择应用的主题模式")
        )
        self.themeComboBox = ComboBox(self.themeCard)
        self.themeComboBox.addItems(["Light", "Dark"])
        self.themeComboBox.setFixedWidth(120)
        self.themeCard.hBoxLayout.addWidget(self.themeComboBox, 0, Qt.AlignRight)
        margins = self.themeCard.hBoxLayout.contentsMargins()
        self.themeCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.themeCard)

        # 重置悬浮窗位置卡片
        self.resetOverlayCard = SettingCard(
            FluentIcon.ALIGNMENT,
            self.tr("重置悬浮窗位置"),
            self.tr("将悬浮窗重置到屏幕中心"),
            parent=self.globalGroup,
        )
        self.resetOverlayButton = PushButton(self.tr("重置"), self.resetOverlayCard)
        self.resetOverlayButton.setFixedWidth(80)
        self.resetOverlayCard.hBoxLayout.addWidget(
            self.resetOverlayButton, 0, Qt.AlignRight
        )
        margins = self.resetOverlayCard.hBoxLayout.contentsMargins()
        self.resetOverlayCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.resetOverlayCard)

        # 恢复默认热键按钮
        self.resetHotkeyConfigCard = SettingCard(
            FluentIcon.UPDATE,
            self.tr("恢复默认热键"),
            self.tr("将所有快捷键恢复为默认值"),
            parent=self.globalGroup,
        )
        self.resetHotkeyConfigButton = PushButton(
            self.tr("恢复"), self.resetHotkeyConfigCard
        )
        self.resetHotkeyConfigButton.setFixedWidth(80)
        self.resetHotkeyConfigCard.hBoxLayout.addWidget(
            self.resetHotkeyConfigButton, 0, Qt.AlignRight
        )
        margins = self.resetHotkeyConfigCard.hBoxLayout.contentsMargins()
        self.resetHotkeyConfigCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.globalGroup.addSettingCard(self.resetHotkeyConfigCard)

        self.vBoxLayout.addWidget(self.globalGroup)

        # 4.5 鱼饵选择设置组
        self.baitGroup = SettingCardGroup(self.tr("鱼饵设置"), self.scrollWidget)

        self.baitSelectionCard = SettingCard(
            FluentIcon.CALORIES,
            self.tr("鱼饵选择"),
            self.tr("勾选要使用的鱼饵，用完自动切换"),
            parent=self.baitGroup,
        )
        self.baitSelectionWidget = QWidget(self.baitSelectionCard)
        self.baitSelectionLayout = QHBoxLayout(self.baitSelectionWidget)
        self.baitSelectionLayout.setContentsMargins(0, 0, 0, 0)
        self.baitSelectionLayout.setSpacing(12)

        self.baitCheckBoxes = {}
        for bait_name in ["蔓越莓", "蓝莓", "橡果", "蘑菇", "蜂蜜"]:
            checkbox = CheckBox(self.tr(bait_name), self.baitSelectionCard)
            self.baitCheckBoxes[bait_name] = checkbox
            self.baitSelectionLayout.addWidget(checkbox)

        self.baitSelectionCard.hBoxLayout.addWidget(
            self.baitSelectionWidget, 0, Qt.AlignRight
        )
        margins = self.baitSelectionCard.hBoxLayout.contentsMargins()
        self.baitSelectionCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.baitGroup.addSettingCard(self.baitSelectionCard)

        self.vBoxLayout.addWidget(self.baitGroup)

        # 5. UNO Function Group
        self.unoGroup = SettingCardGroup(self.tr("UNO 功能"), self.scrollWidget)

        self.unoHotkeyCard = SettingCard(
            FluentIcon.COMMAND_PROMPT,
            self.tr("UNO 热键"),
            self.tr("触发 UNO 识别的快捷键"),
            parent=self.unoGroup,
        )
        self.unoHotkeyLineEdit = KeyBindingWidget(self.unoHotkeyCard)
        self.unoHotkeyLineEdit.setText(cfg.global_settings.get("uno_hotkey", "F3"))
        self.unoHotkeyCard.hBoxLayout.addWidget(
            self.unoHotkeyLineEdit, 0, Qt.AlignRight
        )
        self.unoHotkeyCard.hBoxLayout.addSpacing(5)
        self.unoGamepadLineEdit = KeyBindingWidget(self.unoHotkeyCard)
        self.unoGamepadLineEdit.set_gamepad_mode(True)
        self.unoGamepadLineEdit.setFixedWidth(100)
        self.unoGamepadLineEdit.setPlaceholderText("手柄")
        uno_gamepad_mapping = cfg.get_gamepad_mapping("uno")
        self.unoGamepadLineEdit.set_gamepad_binding(uno_gamepad_mapping)
        self.unoHotkeyCard.hBoxLayout.addWidget(
            self.unoGamepadLineEdit, 0, Qt.AlignRight
        )
        self.unoHotkeyCard.hBoxLayout.addSpacing(5)
        self.unoGamepadModeCombo = self._create_gamepad_mode_combo(
            self.unoHotkeyCard, uno_gamepad_mapping.get("mode", "press")
        )
        self.unoHotkeyCard.hBoxLayout.addWidget(
            self.unoGamepadModeCombo, 0, Qt.AlignRight
        )
        self.unoHotkeyCard.hBoxLayout.addSpacing(5)
        self.unoGamepadHoldSpinBox = self._create_gamepad_hold_spinbox(
            self.unoHotkeyCard, uno_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.unoHotkeyCard.hBoxLayout.addWidget(
            self.unoGamepadHoldSpinBox, 0, Qt.AlignRight
        )
        self.unoGamepadModeCombo.hide()
        self.unoGamepadHoldSpinBox.hide()
        margins = self.unoHotkeyCard.hBoxLayout.contentsMargins()
        self.unoHotkeyCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.unoGroup.addSettingCard(self.unoHotkeyCard)

        self.unoMaxCardsCard = SettingCard(
            FluentIcon.TAG,
            self.tr("最大牌数"),
            self.tr("达到此牌数时停止"),
            parent=self.unoGroup,
        )
        self.unoMaxCardsSpinBox = SpinBox(self.unoMaxCardsCard)
        self.unoMaxCardsSpinBox.setRange(1, 100)
        self.unoMaxCardsSpinBox.setValue(cfg.global_settings.get("uno_max_cards", 35))
        self.unoMaxCardsCard.hBoxLayout.addWidget(
            self.unoMaxCardsSpinBox, 0, Qt.AlignRight
        )
        margins = self.unoMaxCardsCard.hBoxLayout.contentsMargins()
        self.unoMaxCardsCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.unoGroup.addSettingCard(self.unoMaxCardsCard)

        self.vBoxLayout.addWidget(self.unoGroup)

        # 6. Release Group (合并自动放生和单条放生)
        self.releaseGroup = SettingCardGroup(self.tr("放生设置"), self.scrollWidget)

        self.releaseModeCard = SettingCard(
            FluentIcon.DELETE,
            self.tr("放生模式"),
            self.tr("勾选启用的放生行为"),
            parent=self.releaseGroup,
        )
        self.releaseModeWidget = QWidget(self.releaseModeCard)
        self.releaseModeLayout = QHBoxLayout(self.releaseModeWidget)
        self.releaseModeLayout.setContentsMargins(0, 0, 0, 0)
        self.releaseModeLayout.setSpacing(12)

        self.autoReleaseEnabledCard = CheckBox(
            self.tr("桶满放生"), self.releaseModeCard
        )
        self.singleReleaseEnabledCard = CheckBox(
            self.tr("单条放生"), self.releaseModeCard
        )
        self.enableFishNameProtectionCard = CheckBox(
            self.tr("放生保护"), self.releaseModeCard
        )

        self.releaseModeLayout.addWidget(self.autoReleaseEnabledCard)
        self.releaseModeLayout.addWidget(self.singleReleaseEnabledCard)
        self.releaseModeLayout.addWidget(self.enableFishNameProtectionCard)
        self.releaseModeLayout.addStretch(1)
        self.releaseModeCard.hBoxLayout.addWidget(
            self.releaseModeWidget, 0, Qt.AlignRight
        )
        margins = self.releaseModeCard.hBoxLayout.contentsMargins()
        self.releaseModeCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.releaseGroup.addSettingCard(self.releaseModeCard)

        self.releaseQualityCard = SettingCard(
            FluentIcon.CANCEL,
            self.tr("放生品质"),
            self.tr("勾选后会自动放生对应品质"),
            parent=self.releaseGroup,
        )
        self.releaseQualityWidget = QWidget(self.releaseQualityCard)
        self.releaseQualityLayout = QHBoxLayout(self.releaseQualityWidget)
        self.releaseQualityLayout.setContentsMargins(0, 0, 0, 0)
        self.releaseQualityLayout.setSpacing(12)

        self.releaseStandardCard = CheckBox(self.tr("标准"), self.releaseQualityCard)
        self.releaseUncommonCard = CheckBox(self.tr("非凡"), self.releaseQualityCard)
        self.releaseRareCard = CheckBox(self.tr("稀有"), self.releaseQualityCard)
        self.releaseEpicCard = CheckBox(self.tr("史诗"), self.releaseQualityCard)
        self.releaseLegendaryCard = CheckBox(self.tr("传奇"), self.releaseQualityCard)

        self.releaseQualityLayout.addWidget(self.releaseStandardCard)
        self.releaseQualityLayout.addWidget(self.releaseUncommonCard)
        self.releaseQualityLayout.addWidget(self.releaseRareCard)
        self.releaseQualityLayout.addWidget(self.releaseEpicCard)
        self.releaseQualityLayout.addWidget(self.releaseLegendaryCard)
        self.releaseQualityLayout.addStretch(1)
        self.releaseQualityCard.hBoxLayout.addWidget(
            self.releaseQualityWidget, 0, Qt.AlignRight
        )
        margins = self.releaseQualityCard.hBoxLayout.contentsMargins()
        self.releaseQualityCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.releaseGroup.addSettingCard(self.releaseQualityCard)

        self.vBoxLayout.addWidget(self.releaseGroup)

        # 8. Record Management Group
        self.recordGroup = SettingCardGroup(self.tr("记录管理"), self.scrollWidget)

        self.exportRecordCard = SettingCard(
            FluentIcon.DOWNLOAD,
            self.tr("导出记录"),
            self.tr("导出当前账号的钓鱼记录"),
            parent=self.recordGroup,
        )
        self.exportRecordButton = PrimaryPushButton("导出", self.exportRecordCard)
        self.exportRecordButton.setFixedWidth(80)
        self.exportRecordCard.hBoxLayout.addWidget(
            self.exportRecordButton, 0, Qt.AlignRight
        )
        margins = self.exportRecordCard.hBoxLayout.contentsMargins()
        self.exportRecordCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.recordGroup.addSettingCard(self.exportRecordCard)

        self.importRecordCard = SettingCard(
            FluentIcon.UP,
            self.tr("导入记录"),
            self.tr("从文件导入钓鱼记录"),
            parent=self.recordGroup,
        )
        self.importRecordButton = PushButton("导入", self.importRecordCard)
        self.importRecordButton.setFixedWidth(80)
        self.importRecordCard.hBoxLayout.addWidget(
            self.importRecordButton, 0, Qt.AlignRight
        )
        margins = self.importRecordCard.hBoxLayout.contentsMargins()
        self.importRecordCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.recordGroup.addSettingCard(self.importRecordCard)

        self.vBoxLayout.addWidget(self.recordGroup)

        # 6. Account Management Group
        self.accountGroup = SettingCardGroup(self.tr("账号管理"), self.scrollWidget)

        # 创建账号卡片
        self.createAccountCard = SettingCard(
            FluentIcon.ADD,
            self.tr("创建新账号"),
            self.tr("输入新账号名称并点击创建"),
            parent=self.accountGroup,
        )
        self.newAccountLineEdit = LineEdit(self.createAccountCard)
        self.newAccountLineEdit.setPlaceholderText("账号名称")
        self.newAccountLineEdit.setFixedWidth(150)
        self.createAccountButton = PrimaryPushButton("创建", self.createAccountCard)
        self.createAccountButton.setFixedWidth(80)
        self.createAccountCard.hBoxLayout.addWidget(
            self.newAccountLineEdit, 0, Qt.AlignRight
        )
        self.createAccountCard.hBoxLayout.addSpacing(10)
        self.createAccountCard.hBoxLayout.addWidget(
            self.createAccountButton, 0, Qt.AlignRight
        )
        margins = self.createAccountCard.hBoxLayout.contentsMargins()
        self.createAccountCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.accountGroup.addSettingCard(self.createAccountCard)

        # 删除账号卡片
        self.deleteAccountCard = SettingCard(
            FluentIcon.DELETE,
            self.tr("删除账号"),
            self.tr("选择要删除的账号（不能删除当前账号）"),
            parent=self.accountGroup,
        )
        self.deleteAccountComboBox = ComboBox(self.deleteAccountCard)
        self.deleteAccountComboBox.setFixedWidth(150)
        self.deleteAccountButton = PushButton("删除", self.deleteAccountCard)
        self.deleteAccountButton.setFixedWidth(80)
        self._refresh_delete_account_list()  # 必须在按钮创建后调用
        self.deleteAccountCard.hBoxLayout.addWidget(
            self.deleteAccountComboBox, 0, Qt.AlignRight
        )
        self.deleteAccountCard.hBoxLayout.addSpacing(10)
        self.deleteAccountCard.hBoxLayout.addWidget(
            self.deleteAccountButton, 0, Qt.AlignRight
        )
        margins = self.deleteAccountCard.hBoxLayout.contentsMargins()
        self.deleteAccountCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.accountGroup.addSettingCard(self.deleteAccountCard)

        self.vBoxLayout.addWidget(self.accountGroup)

        # 保持各组紧凑并将多余空间推到底部。
        for group in (
            self.presetGroup,
            self.fishingGroup,
            self.globalGroup,
            self.baitGroup,
            self.unoGroup,
            self.releaseGroup,
            self.recordGroup,
            self.accountGroup,
        ):
            group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        self.vBoxLayout.addStretch(1)

        # 5. Load initial values and connect signals
        self._load_settings_to_ui()
        self._update_gamepad_hold_controls()
        self._connect_signals()

        # 设置组分类
        self.groupCategories = {
            "fishing": [
                self.presetGroup,
                self.fishingGroup,
                self.saveResetButtonWidget,
                self.baitGroup,
                self.releaseGroup,
            ],
            "function": [self.globalGroup, self.unoGroup],
            "data": [self.recordGroup, self.accountGroup],
        }

        # 初始显示钓鱼设置
        self._onSegmentChanged("fishing")

        # 样式
        self.setStyleSheet("QScrollArea {background-color: transparent; border: none;}")
        self.scrollWidget.setStyleSheet("QWidget {background-color: transparent;}")

    def _create_double_spinbox_card(self, icon, title, content, config_key):
        card = SettingCard(icon, title, content, parent=self.fishingGroup)
        spinbox = SmartDoubleSpinBox(card)
        spinbox.setRange(0.001, 10.0)
        spinbox.setSingleStep(0.001)
        spinbox.setDecimals(3)
        card.hBoxLayout.addWidget(spinbox, 0, Qt.AlignRight)
        margins = card.hBoxLayout.contentsMargins()
        card.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )

        # 将 snake_case 转换为 camelCase 作为属性名
        parts = config_key.split("_")
        attr_name = parts[0] + "".join(x.title() for x in parts[1:]) + "SpinBox"
        setattr(self, attr_name, spinbox)
        return card

    @staticmethod
    def _gamepad_mode_to_text(mode):
        return "长按" if mode == "hold" else "单击"

    @staticmethod
    def _gamepad_mode_from_text(text):
        return "hold" if text == "长按" else "press"

    def _create_gamepad_mode_combo(self, parent, mode="press"):
        combo = ComboBox(parent)
        combo.addItems(["单击", "长按"])
        combo.setFixedWidth(72)
        combo.setCurrentText(self._gamepad_mode_to_text(mode))
        return combo

    def _create_gamepad_hold_spinbox(self, parent, hold_ms=None):
        spinbox = SpinBox(parent)
        spinbox.setRange(cfg.GAMEPAD_HOLD_MS_MIN, cfg.GAMEPAD_HOLD_MS_MAX)
        spinbox.setSingleStep(100)
        spinbox.setSuffix(" ms")
        spinbox.setFixedWidth(84)
        spinbox.setValue(cfg.normalize_gamepad_hold_ms(hold_ms))
        return spinbox

    def _update_gamepad_hold_controls(self):
        controls = (
            (self.hotkeyGamepadModeCombo, self.hotkeyGamepadHoldSpinBox),
            (self.debugGamepadModeCombo, self.debugGamepadHoldSpinBox),
            (self.sellGamepadModeCombo, self.sellGamepadHoldSpinBox),
            (self.unoGamepadModeCombo, self.unoGamepadHoldSpinBox),
        )

        for combo, spinbox in controls:
            spinbox.setEnabled(
                self._gamepad_mode_from_text(combo.currentText()) == "hold"
            )

    def _apply_captured_gamepad_binding(self, mode_combo, hold_spinbox, mode, hold_ms):
        mode_combo.setCurrentText(self._gamepad_mode_to_text(mode))
        hold_spinbox.setValue(cfg.normalize_gamepad_hold_ms(hold_ms))

    def _connect_signals(self):
        self.presetComboBox.currentTextChanged.connect(self._load_settings_to_ui)
        self.savePresetButton.clicked.connect(self._save_preset_settings)

        # 全局设置自动保存
        self.hotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.debugHotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.sellHotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.unoHotkeyLineEdit.editingFinished.connect(self._save_global_settings)

        self.jiashiCard.checkedChanged.connect(self._save_global_settings)
        self.autoClickSellCard.checkedChanged.connect(self._save_global_settings)
        self.antiAfkCard.checkedChanged.connect(self._save_global_settings)
        self.soundAlertCard.checkedChanged.connect(self._save_global_settings)
        self.fishRecognitionCard.checkedChanged.connect(self._save_global_settings)
        self.seasonFilterCard.checkedChanged.connect(self._on_season_filter_changed)
        self.legendaryScreenshotCard.checkedChanged.connect(self._save_global_settings)
        self.firstCatchScreenshotCard.checkedChanged.connect(self._save_global_settings)

        self.enableGamepadCard.checkedChanged.connect(self._save_global_settings)
        self.hotkeyGamepadLineEdit.gamepad_binding_captured.connect(
            lambda _button, mode, hold_ms: self._apply_captured_gamepad_binding(
                self.hotkeyGamepadModeCombo,
                self.hotkeyGamepadHoldSpinBox,
                mode,
                hold_ms,
            )
        )
        self.debugGamepadLineEdit.gamepad_binding_captured.connect(
            lambda _button, mode, hold_ms: self._apply_captured_gamepad_binding(
                self.debugGamepadModeCombo,
                self.debugGamepadHoldSpinBox,
                mode,
                hold_ms,
            )
        )
        self.sellGamepadLineEdit.gamepad_binding_captured.connect(
            lambda _button, mode, hold_ms: self._apply_captured_gamepad_binding(
                self.sellGamepadModeCombo, self.sellGamepadHoldSpinBox, mode, hold_ms
            )
        )
        self.unoGamepadLineEdit.gamepad_binding_captured.connect(
            lambda _button, mode, hold_ms: self._apply_captured_gamepad_binding(
                self.unoGamepadModeCombo, self.unoGamepadHoldSpinBox, mode, hold_ms
            )
        )
        self.hotkeyGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.debugGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.sellGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.unoGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.hotkeyGamepadModeCombo.currentTextChanged.connect(
            self._save_gamepad_mappings
        )
        self.hotkeyGamepadModeCombo.currentTextChanged.connect(
            self._update_gamepad_hold_controls
        )
        self.debugGamepadModeCombo.currentTextChanged.connect(
            self._save_gamepad_mappings
        )
        self.debugGamepadModeCombo.currentTextChanged.connect(
            self._update_gamepad_hold_controls
        )
        self.sellGamepadModeCombo.currentTextChanged.connect(
            self._save_gamepad_mappings
        )
        self.sellGamepadModeCombo.currentTextChanged.connect(
            self._update_gamepad_hold_controls
        )
        self.unoGamepadModeCombo.currentTextChanged.connect(self._save_gamepad_mappings)
        self.unoGamepadModeCombo.currentTextChanged.connect(
            self._update_gamepad_hold_controls
        )
        self.hotkeyGamepadHoldSpinBox.valueChanged.connect(self._save_gamepad_mappings)
        self.debugGamepadHoldSpinBox.valueChanged.connect(self._save_gamepad_mappings)
        self.sellGamepadHoldSpinBox.valueChanged.connect(self._save_gamepad_mappings)
        self.unoGamepadHoldSpinBox.valueChanged.connect(self._save_gamepad_mappings)

        self.unoMaxCardsSpinBox.valueChanged.connect(self._save_global_settings)

        self.autoReleaseEnabledCard.toggled.connect(self._on_auto_release_changed)
        self.enableFishNameProtectionCard.toggled.connect(self._save_global_settings)
        self.releaseStandardCard.toggled.connect(self._save_global_settings)
        self.releaseUncommonCard.toggled.connect(self._save_global_settings)
        self.releaseRareCard.toggled.connect(self._save_global_settings)
        self.releaseEpicCard.toggled.connect(self._save_global_settings)
        self.releaseLegendaryCard.toggled.connect(self._save_global_settings)

        # 鱼饵复选框信号
        for checkbox in self.baitCheckBoxes.values():
            checkbox.stateChanged.connect(self._save_global_settings)

        self.singleReleaseEnabledCard.toggled.connect(self._on_single_release_changed)

        self.jitterSlider.valueChanged.connect(
            lambda v: self.jitterLabel.setText(f"{v}%")
        )
        self.jitterSlider.sliderReleased.connect(self._save_global_settings)

        self.themeComboBox.currentTextChanged.connect(self._on_theme_changed)

        # 账号管理信号
        self.createAccountButton.clicked.connect(self._on_create_account)
        self.deleteAccountButton.clicked.connect(self._on_delete_account)

        # 记录管理信号
        self.exportRecordButton.clicked.connect(self._on_export_record)
        self.importRecordButton.clicked.connect(self._on_import_record)

        # 重置悬浮窗位置信号
        self.resetOverlayButton.clicked.connect(self._on_reset_overlay_position)

        # 恢复默认配置信号
        self.resetFishingConfigButton2.clicked.connect(self._on_reset_fishing_config)
        self.resetHotkeyConfigButton.clicked.connect(self._on_reset_hotkey_config)

    def _on_theme_changed(self, theme):
        if self._loading_ui:
            return
        self.theme_changed_signal.emit(theme)
        self._save_global_settings()

    def _on_season_filter_changed(self):
        if self._loading_ui:
            return
        self._save_global_settings()
        self.season_filter_changed_signal.emit()

    def _load_settings_to_ui(self, preset_name_to_load=None):
        self._loading_ui = True
        # 阻止信号以防止更新 UI 时递归调用
        self.presetComboBox.blockSignals(True)

        # 确定要加载的预设
        preset_name = (
            preset_name_to_load
            if preset_name_to_load
            else self.presetComboBox.currentText()
        )
        if not preset_name:
            preset_name = cfg.current_preset_name  # 回退到全局当前预设

        # 更新 ComboBox 以确保它反映状态
        self.presetComboBox.setCurrentText(preset_name)

        # 加载预设特定设置
        current_preset = cfg.presets.get(preset_name, {})

        self.reelInTimeSpinBox.setValue(current_preset.get("reel_in_time", 2.0))
        self.releaseTimeSpinBox.setValue(current_preset.get("release_time", 1.0))
        self.cycleIntervalSpinBox.setValue(current_preset.get("cycle_interval", 0.5))
        self.maxPullsSpinBox.setValue(current_preset.get("max_pulls", 20))

        # 加载全局设置
        self.hotkeyLineEdit.setText(cfg.global_settings.get("hotkey", "F2"))
        self.debugHotkeyLineEdit.setText(cfg.global_settings.get("debug_hotkey", "F10"))
        self.unoHotkeyLineEdit.setText(cfg.global_settings.get("uno_hotkey", "F3"))
        self.unoMaxCardsSpinBox.setValue(cfg.global_settings.get("uno_max_cards", 35))
        self.sellHotkeyLineEdit.setText(cfg.global_settings.get("sell_hotkey", "F4"))
        self.jiashiCard.setChecked(cfg.global_settings.get("enable_jiashi", True))
        self.autoClickSellCard.setChecked(
            cfg.global_settings.get("auto_click_sell", True)
        )
        self.antiAfkCard.setChecked(cfg.global_settings.get("enable_anti_afk", False))
        self.soundAlertCard.setChecked(
            cfg.global_settings.get("enable_sound_alert", False)
        )
        self.fishRecognitionCard.setChecked(
            cfg.global_settings.get("enable_fish_recognition", True)
        )
        self.seasonFilterCard.setChecked(
            cfg.global_settings.get("enable_season_filter", True)
        )
        self.legendaryScreenshotCard.setChecked(
            cfg.global_settings.get("enable_legendary_screenshot", True)
        )
        self.firstCatchScreenshotCard.setChecked(
            cfg.global_settings.get("enable_first_catch_screenshot", True)
        )
        self.autoReleaseEnabledCard.setChecked(
            cfg.global_settings.get("auto_release_enabled", False)
        )
        self.enableFishNameProtectionCard.setChecked(
            cfg.global_settings.get("enable_fish_name_protection", False)
        )
        self.releaseStandardCard.setChecked(
            cfg.global_settings.get("release_standard", True)
        )
        self.releaseUncommonCard.setChecked(
            cfg.global_settings.get("release_uncommon", False)
        )
        self.releaseRareCard.setChecked(cfg.global_settings.get("release_rare", False))
        self.releaseEpicCard.setChecked(cfg.global_settings.get("release_epic", False))
        self.releaseLegendaryCard.setChecked(
            cfg.global_settings.get("release_legendary", False)
        )
        # 单条放生总开关
        release_mode = cfg.global_settings.get("release_mode", "off")
        self.singleReleaseEnabledCard.setChecked(release_mode == "single")
        jitter_value = cfg.global_settings.get("jitter_range", 0)
        self.jitterSlider.setValue(jitter_value)
        self.jitterLabel.setText(f"{jitter_value}%")
        self.themeComboBox.setCurrentText(cfg.global_settings.get("theme", "Dark"))

        self.enableGamepadCard.setChecked(
            cfg.global_settings.get("enable_gamepad", False)
        )
        toggle_gamepad_mapping = cfg.get_gamepad_mapping("toggle")
        debug_gamepad_mapping = cfg.get_gamepad_mapping("debug")
        sell_gamepad_mapping = cfg.get_gamepad_mapping("sell")
        uno_gamepad_mapping = cfg.get_gamepad_mapping("uno")
        self.hotkeyGamepadLineEdit.set_gamepad_binding(toggle_gamepad_mapping)
        self.debugGamepadLineEdit.set_gamepad_binding(debug_gamepad_mapping)
        self.sellGamepadLineEdit.set_gamepad_binding(sell_gamepad_mapping)
        self.unoGamepadLineEdit.set_gamepad_binding(uno_gamepad_mapping)
        self.hotkeyGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(toggle_gamepad_mapping.get("mode", "press"))
        )
        self.hotkeyGamepadHoldSpinBox.setValue(
            toggle_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.debugGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(debug_gamepad_mapping.get("mode", "press"))
        )
        self.debugGamepadHoldSpinBox.setValue(
            debug_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.sellGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(sell_gamepad_mapping.get("mode", "press"))
        )
        self.sellGamepadHoldSpinBox.setValue(
            sell_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.unoGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(uno_gamepad_mapping.get("mode", "press"))
        )
        self.unoGamepadHoldSpinBox.setValue(
            uno_gamepad_mapping.get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self._update_gamepad_hold_controls()

        # 加载鱼饵选择
        selected_baits = cfg.global_settings.get("selected_baits", [])
        for bait_name, checkbox in self.baitCheckBoxes.items():
            checkbox.setChecked(bait_name in selected_baits)

        self._update_release_cards_state()

        # 解除信号阻止
        self.presetComboBox.blockSignals(False)
        self._loading_ui = False

    def _save_preset_settings(self):
        """仅保存钓鱼预设设置。"""
        preset_name = self.presetComboBox.currentText()
        if preset_name in cfg.presets:
            cfg.presets[preset_name]["reel_in_time"] = self.reelInTimeSpinBox.value()
            cfg.presets[preset_name]["release_time"] = self.releaseTimeSpinBox.value()
            cfg.presets[preset_name][
                "cycle_interval"
            ] = self.cycleIntervalSpinBox.value()
            cfg.presets[preset_name]["max_pulls"] = self.maxPullsSpinBox.value()

        # 更新配置中的当前预设以匹配正在编辑的预设
        cfg.load_preset(preset_name)

        cfg.save()

        InfoBar.success(
            title=self.tr("保存成功"),
            content=self.tr(f"预设 '{preset_name}' 已更新。"),
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _save_global_settings(self):
        if self._loading_ui:
            return
        """立即保存全局设置。"""
        new_hotkey = self.hotkeyLineEdit.text()
        if cfg.global_settings.get("hotkey") != new_hotkey:
            cfg.global_settings["hotkey"] = new_hotkey
            self.hotkey_changed_signal.emit(new_hotkey)

        new_debug_hotkey = self.debugHotkeyLineEdit.text()
        if cfg.global_settings.get("debug_hotkey") != new_debug_hotkey:
            cfg.global_settings["debug_hotkey"] = new_debug_hotkey
            self.debug_hotkey_changed_signal.emit(new_debug_hotkey)

        new_sell_hotkey = self.sellHotkeyLineEdit.text()
        if cfg.global_settings.get("sell_hotkey") != new_sell_hotkey:
            cfg.global_settings["sell_hotkey"] = new_sell_hotkey
            self.sell_hotkey_changed_signal.emit(new_sell_hotkey)

        new_uno_hotkey = self.unoHotkeyLineEdit.text()
        if cfg.global_settings.get("uno_hotkey") != new_uno_hotkey:
            cfg.global_settings["uno_hotkey"] = new_uno_hotkey
            self.uno_hotkey_changed_signal.emit(new_uno_hotkey)

        cfg.global_settings["uno_max_cards"] = self.unoMaxCardsSpinBox.value()

        cfg.global_settings["enable_jiashi"] = self.jiashiCard.isChecked()
        cfg.global_settings["auto_click_sell"] = self.autoClickSellCard.isChecked()
        cfg.global_settings["enable_anti_afk"] = self.antiAfkCard.isChecked()
        cfg.global_settings["enable_sound_alert"] = self.soundAlertCard.isChecked()
        cfg.global_settings["enable_fish_recognition"] = (
            self.fishRecognitionCard.isChecked()
        )
        cfg.global_settings["enable_season_filter"] = self.seasonFilterCard.isChecked()
        cfg.global_settings["enable_legendary_screenshot"] = (
            self.legendaryScreenshotCard.isChecked()
        )
        cfg.global_settings["enable_first_catch_screenshot"] = (
            self.firstCatchScreenshotCard.isChecked()
        )
        cfg.global_settings["auto_release_enabled"] = (
            self.autoReleaseEnabledCard.isChecked()
        )
        # 同步 release_mode 配置
        if self.autoReleaseEnabledCard.isChecked():
            cfg.global_settings["release_mode"] = "auto"
        elif cfg.global_settings.get("release_mode") == "auto":
            # 如果当前是 auto 模式但被关闭了，切换到 off
            cfg.global_settings["release_mode"] = "off"
        cfg.global_settings["enable_fish_name_protection"] = (
            self.enableFishNameProtectionCard.isChecked()
        )

        # 保存鱼饵选择
        selected_baits = [
            bait_name
            for bait_name, checkbox in self.baitCheckBoxes.items()
            if checkbox.isChecked()
        ]
        cfg.global_settings["selected_baits"] = selected_baits
        cfg.global_settings["release_standard"] = self.releaseStandardCard.isChecked()
        cfg.global_settings["release_uncommon"] = self.releaseUncommonCard.isChecked()
        cfg.global_settings["release_rare"] = self.releaseRareCard.isChecked()
        cfg.global_settings["release_epic"] = self.releaseEpicCard.isChecked()
        cfg.global_settings["release_legendary"] = self.releaseLegendaryCard.isChecked()
        cfg.global_settings["jitter_range"] = self.jitterSlider.value()
        cfg.global_settings["theme"] = self.themeComboBox.currentText()

        cfg.global_settings["enable_gamepad"] = self.enableGamepadCard.isChecked()
        self.gamepad_mapping_changed_signal.emit()

        cfg.save()

    def _save_gamepad_mappings(self):
        if self._loading_ui:
            return
        """保存手柄按钮映射。"""
        toggle_binding = self.hotkeyGamepadLineEdit.get_gamepad_binding()
        debug_binding = self.debugGamepadLineEdit.get_gamepad_binding()
        sell_binding = self.sellGamepadLineEdit.get_gamepad_binding()
        uno_binding = self.unoGamepadLineEdit.get_gamepad_binding()

        cfg.set_gamepad_mapping(
            "toggle",
            toggle_binding.get("button", ""),
            toggle_binding.get("mode", "press"),
            toggle_binding.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )
        cfg.set_gamepad_mapping(
            "debug",
            debug_binding.get("button", ""),
            debug_binding.get("mode", "press"),
            debug_binding.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )
        cfg.set_gamepad_mapping(
            "sell",
            sell_binding.get("button", ""),
            sell_binding.get("mode", "press"),
            sell_binding.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )
        cfg.set_gamepad_mapping(
            "uno",
            uno_binding.get("button", ""),
            uno_binding.get("mode", "press"),
            uno_binding.get("hold_ms", cfg.GAMEPAD_HOLD_MS),
        )

        cfg.save()
        self.gamepad_mapping_changed_signal.emit()

    def _on_auto_release_changed(self, checked):
        if self._loading_ui:
            return
        """处理自动放生开关变化，同步放生模式"""
        # 保存配置
        cfg.global_settings["auto_release_enabled"] = checked

        # 同步 release_mode
        if checked:
            cfg.global_settings["release_mode"] = "auto"
            # 关闭单条放生（不触发信号避免循环）
            self.singleReleaseEnabledCard.blockSignals(True)
            self.singleReleaseEnabledCard.setChecked(False)
            self.singleReleaseEnabledCard.blockSignals(False)
        else:
            # 如果关闭自动放生，且当前是自动放生模式，才切换到关闭模式
            # 避免覆盖单条放生模式的设置
            if cfg.global_settings.get("release_mode") == "auto":
                cfg.global_settings["release_mode"] = "off"

        cfg.save()

        # 根据放生模式启用/禁用相关开关
        self._update_release_cards_state()

        # 发射信号通知主页更新
        self.release_mode_changed_signal.emit(
            cfg.global_settings.get("release_mode", "off")
        )

    def _update_release_cards_state(self):
        """根据放生模式更新放生相关卡片的启用状态"""
        release_mode = cfg.global_settings.get("release_mode", "off")

        # 自动放生和单条放生开关始终可点击，用于切换模式
        self.autoReleaseEnabledCard.setEnabled(True)
        self.singleReleaseEnabledCard.setEnabled(True)

        # 品质开关和放生保护在任意放生模式开启时都启用
        if release_mode == "off":
            self.releaseStandardCard.setEnabled(False)
            self.releaseUncommonCard.setEnabled(False)
            self.releaseRareCard.setEnabled(False)
            self.releaseEpicCard.setEnabled(False)
            self.releaseLegendaryCard.setEnabled(False)
            self.enableFishNameProtectionCard.setEnabled(False)
        else:
            # 单条或自动放生模式都启用品质开关和放生保护
            self.releaseStandardCard.setEnabled(True)
            self.releaseUncommonCard.setEnabled(True)
            self.releaseRareCard.setEnabled(True)
            self.releaseEpicCard.setEnabled(True)
            self.releaseLegendaryCard.setEnabled(True)
            self.enableFishNameProtectionCard.setEnabled(True)

    def _on_single_release_changed(self, checked):
        if self._loading_ui:
            return
        """处理单条放生开关变化，同步放生模式"""
        # 保存配置
        if checked:
            cfg.global_settings["release_mode"] = "single"
            # 关闭自动放生
            cfg.global_settings["auto_release_enabled"] = False
            # 取消自动放生开关的选中状态（不触发信号避免循环）
            self.autoReleaseEnabledCard.blockSignals(True)
            self.autoReleaseEnabledCard.setChecked(False)
            self.autoReleaseEnabledCard.blockSignals(False)
        else:
            # 如果关闭单条放生，且当前是单条放生模式，才切换到关闭模式
            # 避免覆盖自动放生模式的设置
            if cfg.global_settings.get("release_mode") == "single":
                cfg.global_settings["release_mode"] = "off"

        cfg.save()

        # 根据放生模式启用/禁用相关开关
        self._update_release_cards_state()

        # 发射信号通知主页更新
        self.release_mode_changed_signal.emit(
            cfg.global_settings.get("release_mode", "off")
        )

    def update_release_mode_from_main(self, mode):
        """从主页更新放生模式"""
        # 更新自动放生开关状态
        if mode == "auto":
            self.autoReleaseEnabledCard.setChecked(True)
            self.singleReleaseEnabledCard.setChecked(False)
        elif mode == "single":
            self.autoReleaseEnabledCard.setChecked(False)
            self.singleReleaseEnabledCard.setChecked(True)
        else:
            self.autoReleaseEnabledCard.setChecked(False)
            self.singleReleaseEnabledCard.setChecked(False)

        # 更新卡片启用状态
        self._update_release_cards_state()

    def _refresh_delete_account_list(self):
        """刷新删除账号下拉框的列表"""
        self.deleteAccountComboBox.blockSignals(True)
        self.deleteAccountComboBox.clear()
        accounts = cfg.get_accounts()
        # 过滤掉当前账号（不能删除当前账号）
        deletable_accounts = [a for a in accounts if a != cfg.current_account]
        if deletable_accounts:
            self.deleteAccountComboBox.addItems(deletable_accounts)
            self.deleteAccountButton.setEnabled(True)
        else:
            self.deleteAccountComboBox.addItem("无可删除账号")
            self.deleteAccountButton.setEnabled(False)
        self.deleteAccountComboBox.blockSignals(False)

    def _on_create_account(self):
        """创建新账号"""
        account_name = self.newAccountLineEdit.text().strip()

        if not account_name:
            InfoBar.warning(
                title=self.tr("创建失败"),
                content=self.tr("请输入账号名称"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
            return

        dialog = ServerRegionDialog(self.window())
        dialog.titleLabel.setText(self.tr("选择区服"))
        dialog.contentLabel.setText(
            self.tr(f"请为账号 '{account_name}' 选择区服类型：")
        )
        dialog.yesButton.setText(self.tr("创建"))
        dialog.cancelButton.setText(self.tr("取消"))

        if dialog.exec():
            server_region = dialog.get_selected_region()

            if cfg.create_account(account_name, server_region):
                InfoBar.success(
                    title=self.tr("创建成功"),
                    content=self.tr(
                        f"账号 '{account_name}' 已创建（{self.tr('国服') if server_region == 'CN' else self.tr('国际服')}）"
                    ),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )
                self.newAccountLineEdit.clear()
                self._refresh_delete_account_list()
                self.account_list_changed_signal.emit()
            else:
                InfoBar.warning(
                    title=self.tr("创建失败"),
                    content=self.tr(f"账号 '{account_name}' 已存在"),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )

    def _on_delete_account(self):
        """删除账号"""
        account_name = self.deleteAccountComboBox.currentText()

        if not account_name or account_name == "无可删除账号":
            return

        # 确认对话框
        w = MessageBox(
            self.tr("确认删除"),
            self.tr(
                f"确定要删除账号 '{account_name}' 吗？\n\n⚠️ 该账号的所有钓鱼记录和销售数据将被永久删除！"
            ),
            self.window(),
        )
        w.yesButton.setText(self.tr("删除"))
        w.cancelButton.setText(self.tr("取消"))

        if w.exec():
            if cfg.delete_account(account_name):
                InfoBar.success(
                    title=self.tr("删除成功"),
                    content=self.tr(f"账号 '{account_name}' 已删除"),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )
                self._refresh_delete_account_list()
                # 通知首页刷新账号列表
                self.account_list_changed_signal.emit()
            else:
                InfoBar.error(
                    title=self.tr("删除失败"),
                    content=self.tr("无法删除当前正在使用的账号"),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )

    def refresh_account_ui(self):
        """外部调用：刷新账号管理 UI（当账号切换时）"""
        self._refresh_delete_account_list()
        self._load_settings_to_ui(cfg.current_preset_name)

    def _on_export_record(self):
        """导出记录"""
        # 显示文件选择对话框
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出记录",
            f"钓鱼记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "CSV Files (*.csv);;TXT Files (*.txt)",
        )

        if not file_path:
            return

        from pathlib import Path

        file_path = Path(file_path)

        # 确定文件格式
        format_type = "csv" if file_path.suffix.lower() == ".csv" else "txt"

        # 调用记录管理模块导出记录
        success = record_manager.export_records(file_path, format_type)

        if success:
            InfoBar.success(
                title=self.tr("导出成功"),
                content=self.tr(f"记录已成功导出到: {file_path}"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
        else:
            InfoBar.error(
                title=self.tr("导出失败"),
                content=self.tr("导出记录失败，请检查日志"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

    def _on_import_record(self):
        """导入记录"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入记录", "", "CSV Files (*.csv);;TXT Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        file_path = Path(file_path)

        progress = QProgressDialog("正在导入记录...", None, 0, 100, self.window())
        progress.setWindowTitle("导入记录")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setCancelButton(None)
        progress.setAutoClose(False)
        progress.setValue(0)
        progress.show()

        worker = ImportWorker(file_path)
        self._import_worker = worker  # 保持引用

        def on_progress(current, total):
            if total > 0:
                value = int(current * 100 / total)
                progress.setValue(value)

        def on_finished(success, message):
            progress.setValue(100)
            progress.close()
            self._import_worker = None
            if success:
                InfoBar.success(
                    title=self.tr("导入成功"),
                    content=self.tr(message),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )
                self.account_list_changed_signal.emit()
                self.records_updated_signal.emit()
            else:
                InfoBar.error(
                    title=self.tr("导入失败"),
                    content=self.tr(message),
                    duration=2000,
                    position=InfoBarPosition.TOP,
                    parent=self.window(),
                )

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        worker.start()

    def _on_reset_overlay_position(self):
        """重置悬浮窗位置"""
        self.reset_overlay_position_signal.emit()
        InfoBar.success(
            title=self.tr("重置成功"),
            content=self.tr("悬浮窗位置已重置到屏幕中心"),
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _on_reset_fishing_config(self):
        """恢复默认钓鱼参数配置"""
        preset_name = self.presetComboBox.currentText()
        default_presets = cfg._get_default_presets()

        if preset_name in default_presets:
            default_config = default_presets[preset_name]
            self.reelInTimeSpinBox.setValue(default_config["reel_in_time"])
            self.releaseTimeSpinBox.setValue(default_config["release_time"])
            self.cycleIntervalSpinBox.setValue(default_config["cycle_interval"])
            self.maxPullsSpinBox.setValue(default_config["max_pulls"])

            InfoBar.success(
                title=self.tr("恢复成功"),
                content=self.tr(f"已恢复预设 '{preset_name}' 的默认钓鱼参数"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
        else:
            InfoBar.warning(
                title=self.tr("恢复失败"),
                content=self.tr(f"预设 '{preset_name}' 无默认配置"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )

    def _on_reset_hotkey_config(self):
        """恢复默认热键配置"""
        default_hotkeys = {
            "hotkey": "F2",
            "debug_hotkey": "F10",
            "sell_hotkey": "F4",
            "uno_hotkey": "F3",
        }

        default_gamepad_mappings = cfg.DEFAULT_GAMEPAD_MAPPINGS

        # 恢复键盘热键
        self.hotkeyLineEdit.setText(default_hotkeys["hotkey"])
        self.debugHotkeyLineEdit.setText(default_hotkeys["debug_hotkey"])
        self.sellHotkeyLineEdit.setText(default_hotkeys["sell_hotkey"])
        self.unoHotkeyLineEdit.setText(default_hotkeys["uno_hotkey"])

        # 恢复手柄按键映射
        self.hotkeyGamepadLineEdit.set_gamepad_binding(
            default_gamepad_mappings["toggle"]
        )
        self.debugGamepadLineEdit.set_gamepad_binding(default_gamepad_mappings["debug"])
        self.sellGamepadLineEdit.set_gamepad_binding(default_gamepad_mappings["sell"])
        self.unoGamepadLineEdit.set_gamepad_binding(default_gamepad_mappings["uno"])
        self.hotkeyGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(default_gamepad_mappings["toggle"].get("mode"))
        )
        self.hotkeyGamepadHoldSpinBox.setValue(
            default_gamepad_mappings["toggle"].get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.debugGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(default_gamepad_mappings["debug"].get("mode"))
        )
        self.debugGamepadHoldSpinBox.setValue(
            default_gamepad_mappings["debug"].get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.sellGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(default_gamepad_mappings["sell"].get("mode"))
        )
        self.sellGamepadHoldSpinBox.setValue(
            default_gamepad_mappings["sell"].get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self.unoGamepadModeCombo.setCurrentText(
            self._gamepad_mode_to_text(default_gamepad_mappings["uno"].get("mode"))
        )
        self.unoGamepadHoldSpinBox.setValue(
            default_gamepad_mappings["uno"].get("hold_ms", cfg.GAMEPAD_HOLD_MS)
        )
        self._update_gamepad_hold_controls()

        # 保存更改
        self._save_global_settings()
        self._save_gamepad_mappings()

        InfoBar.success(
            title=self.tr("恢复成功"),
            content=self.tr("所有热键已恢复为默认值"),
            duration=2000,
            position=InfoBarPosition.TOP,
            parent=self.window(),
        )

    def _onSegmentChanged(self, key):
        """切换设置分类显示"""
        for category, widgets in self.groupCategories.items():
            visible = category == key
            for widget in widgets:
                widget.setVisible(visible)

        # 强制布局更新
        self.vBoxLayout.update()
        self.scrollWidget.updateGeometry()
        self.scrollWidget.adjustSize()
