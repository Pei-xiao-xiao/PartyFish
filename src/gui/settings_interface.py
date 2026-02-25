from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QFileDialog,
    QProgressDialog,
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
    InfoBar,
    InfoBarPosition,
    MessageBox,
)
from src.config import cfg
from src.gui.components import KeyBindingWidget
from src.record_manager import record_manager


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
    record_only_hotkey_changed_signal = Signal(str)
    theme_changed_signal = Signal(str)
    account_list_changed_signal = Signal()  # 账号列表变化信号
    records_updated_signal = Signal()  # 记录更新信号，用于通知记录界面刷新数据
    reset_overlay_position_signal = Signal()  # 重置悬浮窗位置信号
    release_mode_changed_signal = Signal(str)  # 放生模式变化信号
    season_filter_changed_signal = Signal()  # 季节筛选变化信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")

        # Init Scroll Widget
        self.scrollWidget = QWidget()
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        # Init Layout
        self.vBoxLayout = QVBoxLayout(self.scrollWidget)
        self.vBoxLayout.setContentsMargins(36, 10, 36, 10)
        self.vBoxLayout.setSpacing(20)
        self.vBoxLayout.setAlignment(Qt.AlignTop)

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

        self.castTimeCard = self._create_double_spinbox_card(
            icon=FluentIcon.UPDATE,
            title=self.tr("抛竿时间"),
            content=self.tr("按下抛竿键的持续时间 (秒)"),
            config_key="cast_time",
        )
        self.fishingGroup.addSettingCard(self.castTimeCard)

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

        # 3. Save Button
        self.savePresetButton = PrimaryPushButton(self.tr("保存钓鱼配置"), self)
        self.vBoxLayout.addWidget(self.savePresetButton, 0, Qt.AlignRight)

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
        self.hotkeyGamepadLineEdit.setFixedWidth(80)
        self.hotkeyGamepadLineEdit.setPlaceholderText("手柄")
        gamepad_mappings = cfg.global_settings.get("gamepad_mappings", {})
        self.hotkeyGamepadLineEdit.setText(gamepad_mappings.get("toggle", ""))
        self.hotkeyCard.hBoxLayout.addWidget(
            self.hotkeyGamepadLineEdit, 0, Qt.AlignRight
        )
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
        self.debugGamepadLineEdit.setFixedWidth(80)
        self.debugGamepadLineEdit.setPlaceholderText("手柄")
        self.debugGamepadLineEdit.setText(gamepad_mappings.get("debug", ""))
        self.debugHotkeyCard.hBoxLayout.addWidget(
            self.debugGamepadLineEdit, 0, Qt.AlignRight
        )
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
        self.sellGamepadLineEdit.setFixedWidth(80)
        self.sellGamepadLineEdit.setPlaceholderText("手柄")
        self.sellGamepadLineEdit.setText(gamepad_mappings.get("sell", ""))
        self.sellHotkeyCard.hBoxLayout.addWidget(
            self.sellGamepadLineEdit, 0, Qt.AlignRight
        )
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

        self.vBoxLayout.addWidget(self.globalGroup)

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

        self.recordOnlyGroup = SettingCardGroup(
            self.tr("只记录模式"), self.scrollWidget
        )

        self.enableRecordOnlyCard = SwitchSettingCard(
            FluentIcon.VIDEO,
            self.tr("启用只记录模式"),
            self.tr("开启后只记录渔获信息，不执行钓鱼动作"),
        )
        self.recordOnlyGroup.addSettingCard(self.enableRecordOnlyCard)

        self.recordOnlyHotkeyCard = SettingCard(
            FluentIcon.COMMAND_PROMPT,
            self.tr("只记录热键"),
            self.tr("触发只记录模式的快捷键"),
            parent=self.recordOnlyGroup,
        )
        self.recordOnlyHotkeyLineEdit = KeyBindingWidget(self.recordOnlyHotkeyCard)
        self.recordOnlyHotkeyLineEdit.setFixedWidth(100)
        self.recordOnlyHotkeyLineEdit.setText(
            cfg.global_settings.get("record_only_hotkey", "F5")
        )
        self.recordOnlyHotkeyCard.hBoxLayout.addWidget(
            self.recordOnlyHotkeyLineEdit, 0, Qt.AlignRight
        )
        self.recordOnlyHotkeyCard.hBoxLayout.addSpacing(5)
        self.recordOnlyGamepadLineEdit = KeyBindingWidget(self.recordOnlyHotkeyCard)
        self.recordOnlyGamepadLineEdit.set_gamepad_mode(True)
        self.recordOnlyGamepadLineEdit.setFixedWidth(80)
        self.recordOnlyGamepadLineEdit.setPlaceholderText("手柄")
        self.recordOnlyGamepadLineEdit.setText(gamepad_mappings.get("record_only", ""))
        self.recordOnlyHotkeyCard.hBoxLayout.addWidget(
            self.recordOnlyGamepadLineEdit, 0, Qt.AlignRight
        )
        margins = self.recordOnlyHotkeyCard.hBoxLayout.contentsMargins()
        self.recordOnlyHotkeyCard.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )
        self.recordOnlyGroup.addSettingCard(self.recordOnlyHotkeyCard)

        self.vBoxLayout.addWidget(self.recordOnlyGroup)

        # 6. Release Group (合并自动放生和单条放生)
        self.releaseGroup = SettingCardGroup(self.tr("放生设置"), self.scrollWidget)

        self.autoReleaseEnabledCard = SwitchSettingCard(
            FluentIcon.DELETE,
            self.tr("启用自动放生"),
            self.tr("鱼桶满时自动放生指定品质的鱼"),
        )
        self.releaseGroup.addSettingCard(self.autoReleaseEnabledCard)

        self.singleReleaseEnabledCard = SwitchSettingCard(
            FluentIcon.DELETE,
            self.tr("启用单条放生"),
            self.tr("钓到鱼后自动放生指定品质的鱼"),
        )
        self.releaseGroup.addSettingCard(self.singleReleaseEnabledCard)

        self.enableFishNameProtectionCard = SwitchSettingCard(
            FluentIcon.CARE_UP_SOLID,
            self.tr("启用放生保护"),
            self.tr("保护配置文件中的鱼不被放生"),
        )
        self.releaseGroup.addSettingCard(self.enableFishNameProtectionCard)

        self.releaseStandardCard = SwitchSettingCard(
            FluentIcon.CANCEL, self.tr("放生标准品质"), self.tr("白色")
        )
        self.releaseGroup.addSettingCard(self.releaseStandardCard)

        self.releaseUncommonCard = SwitchSettingCard(
            FluentIcon.CANCEL, self.tr("放生非凡品质"), self.tr("绿色")
        )
        self.releaseGroup.addSettingCard(self.releaseUncommonCard)

        self.releaseRareCard = SwitchSettingCard(
            FluentIcon.CANCEL, self.tr("放生稀有品质"), self.tr("蓝色")
        )
        self.releaseGroup.addSettingCard(self.releaseRareCard)

        self.releaseEpicCard = SwitchSettingCard(
            FluentIcon.CANCEL, self.tr("放生史诗品质"), self.tr("紫色")
        )
        self.releaseGroup.addSettingCard(self.releaseEpicCard)

        self.releaseLegendaryCard = SwitchSettingCard(
            FluentIcon.CANCEL, self.tr("放生传奇品质"), self.tr("黄色")
        )
        self.releaseGroup.addSettingCard(self.releaseLegendaryCard)

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

        # Create Account Card
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

        # Delete Account Card
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

        # 5. Load initial values and connect signals
        self._load_settings_to_ui()
        self._connect_signals()

        # Style
        self.setStyleSheet("QScrollArea {background-color: transparent; border: none;}")
        self.scrollWidget.setStyleSheet("QWidget {background-color: transparent;}")

    def _create_double_spinbox_card(self, icon, title, content, config_key):
        card = SettingCard(icon, title, content, parent=self.fishingGroup)
        spinbox = DoubleSpinBox(card)
        spinbox.setRange(0.01, 10.0)
        spinbox.setSingleStep(0.1)
        card.hBoxLayout.addWidget(spinbox, 0, Qt.AlignRight)
        margins = card.hBoxLayout.contentsMargins()
        card.hBoxLayout.setContentsMargins(
            margins.left(), margins.top(), 16, margins.bottom()
        )

        # Convert snake_case to camelCase for attribute name
        parts = config_key.split("_")
        attr_name = parts[0] + "".join(x.title() for x in parts[1:]) + "SpinBox"
        setattr(self, attr_name, spinbox)
        return card

    def _connect_signals(self):
        self.presetComboBox.currentTextChanged.connect(self._load_settings_to_ui)
        self.savePresetButton.clicked.connect(self._save_preset_settings)

        # Global settings auto-save
        self.hotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.debugHotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.sellHotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.unoHotkeyLineEdit.editingFinished.connect(self._save_global_settings)
        self.recordOnlyHotkeyLineEdit.editingFinished.connect(
            self._save_global_settings
        )

        self.jiashiCard.checkedChanged.connect(self._save_global_settings)
        self.autoClickSellCard.checkedChanged.connect(self._save_global_settings)
        self.antiAfkCard.checkedChanged.connect(self._save_global_settings)
        self.soundAlertCard.checkedChanged.connect(self._save_global_settings)
        self.fishRecognitionCard.checkedChanged.connect(self._save_global_settings)
        self.seasonFilterCard.checkedChanged.connect(self._on_season_filter_changed)
        self.legendaryScreenshotCard.checkedChanged.connect(self._save_global_settings)
        self.firstCatchScreenshotCard.checkedChanged.connect(self._save_global_settings)

        self.enableRecordOnlyCard.checkedChanged.connect(self._save_global_settings)
        self.recordOnlyHotkeyLineEdit.editingFinished.connect(
            self._save_global_settings
        )
        self.recordOnlyGamepadLineEdit.editingFinished.connect(
            self._save_gamepad_mappings
        )

        self.enableGamepadCard.checkedChanged.connect(self._save_global_settings)
        self.hotkeyGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.debugGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)
        self.sellGamepadLineEdit.editingFinished.connect(self._save_gamepad_mappings)

        self.unoMaxCardsSpinBox.valueChanged.connect(self._save_global_settings)

        self.autoReleaseEnabledCard.checkedChanged.connect(
            self._on_auto_release_changed
        )
        self.enableFishNameProtectionCard.checkedChanged.connect(
            self._save_global_settings
        )
        self.releaseStandardCard.checkedChanged.connect(self._save_global_settings)
        self.releaseUncommonCard.checkedChanged.connect(self._save_global_settings)
        self.releaseRareCard.checkedChanged.connect(self._save_global_settings)
        self.releaseEpicCard.checkedChanged.connect(self._save_global_settings)
        self.releaseLegendaryCard.checkedChanged.connect(self._save_global_settings)

        self.singleReleaseEnabledCard.checkedChanged.connect(
            self._on_single_release_changed
        )

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

    def _on_theme_changed(self, theme):
        self.theme_changed_signal.emit(theme)
        self._save_global_settings()

    def _on_season_filter_changed(self):
        self._save_global_settings()
        self.season_filter_changed_signal.emit()

    def _load_settings_to_ui(self, preset_name_to_load=None):
        # Block signals to prevent recursive calls while updating the UI
        self.presetComboBox.blockSignals(True)

        # Determine which preset to load
        preset_name = (
            preset_name_to_load
            if preset_name_to_load
            else self.presetComboBox.currentText()
        )
        if not preset_name:
            preset_name = cfg.current_preset_name  # Fallback to global current

        # Update the ComboBox to ensure it reflects the state
        self.presetComboBox.setCurrentText(preset_name)

        # Load preset-specific settings
        current_preset = cfg.presets.get(preset_name, {})

        self.castTimeSpinBox.setValue(current_preset.get("cast_time", 2.0))
        self.reelInTimeSpinBox.setValue(current_preset.get("reel_in_time", 2.0))
        self.releaseTimeSpinBox.setValue(current_preset.get("release_time", 1.0))
        self.cycleIntervalSpinBox.setValue(current_preset.get("cycle_interval", 0.5))
        self.maxPullsSpinBox.setValue(current_preset.get("max_pulls", 20))

        # Load global settings
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

        self.enableRecordOnlyCard.setChecked(
            cfg.global_settings.get("enable_record_only", False)
        )
        self.recordOnlyHotkeyLineEdit.setText(
            cfg.global_settings.get("record_only_hotkey", "F5")
        )
        self.enableGamepadCard.setChecked(
            cfg.global_settings.get("enable_gamepad", False)
        )
        gamepad_mappings = cfg.global_settings.get("gamepad_mappings", {})
        self.hotkeyGamepadLineEdit.setText(gamepad_mappings.get("toggle", ""))
        self.debugGamepadLineEdit.setText(gamepad_mappings.get("debug", ""))
        self.sellGamepadLineEdit.setText(gamepad_mappings.get("sell", ""))
        self.recordOnlyGamepadLineEdit.setText(gamepad_mappings.get("record_only", ""))

        self._update_release_cards_state()

        # Unblock signals
        self.presetComboBox.blockSignals(False)

    def _save_preset_settings(self):
        """Save only the fishing preset settings."""
        preset_name = self.presetComboBox.currentText()
        if preset_name in cfg.presets:
            cfg.presets[preset_name]["cast_time"] = self.castTimeSpinBox.value()
            cfg.presets[preset_name]["reel_in_time"] = self.reelInTimeSpinBox.value()
            cfg.presets[preset_name]["release_time"] = self.releaseTimeSpinBox.value()
            cfg.presets[preset_name][
                "cycle_interval"
            ] = self.cycleIntervalSpinBox.value()
            cfg.presets[preset_name]["max_pulls"] = self.maxPullsSpinBox.value()

        # Update current preset in config to match the one being edited
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
        """Save global settings immediately."""
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
        cfg.global_settings["release_standard"] = self.releaseStandardCard.isChecked()
        cfg.global_settings["release_uncommon"] = self.releaseUncommonCard.isChecked()
        cfg.global_settings["release_rare"] = self.releaseRareCard.isChecked()
        cfg.global_settings["release_epic"] = self.releaseEpicCard.isChecked()
        cfg.global_settings["release_legendary"] = self.releaseLegendaryCard.isChecked()
        cfg.global_settings["jitter_range"] = self.jitterSlider.value()
        cfg.global_settings["theme"] = self.themeComboBox.currentText()

        cfg.global_settings["enable_record_only"] = (
            self.enableRecordOnlyCard.isChecked()
        )
        new_record_only_hotkey = self.recordOnlyHotkeyLineEdit.text()
        if cfg.global_settings.get("record_only_hotkey") != new_record_only_hotkey:
            cfg.global_settings["record_only_hotkey"] = new_record_only_hotkey
            self.record_only_hotkey_changed_signal.emit(new_record_only_hotkey)

        cfg.global_settings["enable_gamepad"] = self.enableGamepadCard.isChecked()

        cfg.save()

    def _save_gamepad_mappings(self):
        """Save gamepad button mappings."""
        if "gamepad_mappings" not in cfg.global_settings:
            cfg.global_settings["gamepad_mappings"] = {}

        cfg.global_settings["gamepad_mappings"][
            "toggle"
        ] = self.hotkeyGamepadLineEdit.text()
        cfg.global_settings["gamepad_mappings"][
            "debug"
        ] = self.debugGamepadLineEdit.text()
        cfg.global_settings["gamepad_mappings"][
            "sell"
        ] = self.sellGamepadLineEdit.text()
        cfg.global_settings["gamepad_mappings"][
            "record_only"
        ] = self.recordOnlyGamepadLineEdit.text()

        cfg.save()
        self.gamepad_mapping_changed_signal.emit()

    def _on_auto_release_changed(self, checked):
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

        if cfg.create_account(account_name):
            InfoBar.success(
                title=self.tr("创建成功"),
                content=self.tr(f"账号 '{account_name}' 已创建"),
                duration=2000,
                position=InfoBarPosition.TOP,
                parent=self.window(),
            )
            self.newAccountLineEdit.clear()
            self._refresh_delete_account_list()
            # 通知首页刷新账号列表
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
