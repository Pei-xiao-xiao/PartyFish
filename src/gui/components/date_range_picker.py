# coding: utf-8
from enum import Enum
from typing import Optional, Tuple

from PySide6.QtCore import (
    Qt,
    Signal,
    QDate,
    QPoint,
    QRect,
    QRectF,
    QPropertyAnimation,
    QEasingCurve,
    QParallelAnimationGroup,
)
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QAction, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QDialog,
    QDialogButtonBox,
    QGraphicsDropShadowEffect,
    QApplication,
    QFrame,
    QScrollArea,
    QSizePolicy,
)

from qfluentwidgets import (
    themeColor,
    isDarkTheme,
    FluentIcon as FIF,
    PushButton,
    TransparentToolButton,
    StrongBodyLabel,
    BodyLabel,
)


class SelectionState(Enum):
    NONE = 0
    START_SELECTED = 1
    COMPLETE = 2


class YearMonthPicker(QWidget):
    monthSelected = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(280)
        self._currentYear = QDate.currentDate().year()
        self._initUI()

    def _initUI(self):
        self.vLayout = QVBoxLayout(self)
        self.vLayout.setContentsMargins(8, 8, 8, 8)
        self.vLayout.setSpacing(8)

        yearWidget = QWidget()
        yearLayout = QHBoxLayout(yearWidget)
        yearLayout.setContentsMargins(0, 0, 0, 0)

        self.prevYearBtn = TransparentToolButton(FIF.CARE_LEFT_SOLID, self)
        self.prevYearBtn.setFixedSize(28, 28)
        self.yearLabel = StrongBodyLabel(str(self._currentYear))
        self.yearLabel.setAlignment(Qt.AlignCenter)
        self.yearLabel.setFixedWidth(80)
        self.nextYearBtn = TransparentToolButton(FIF.CARE_RIGHT_SOLID, self)
        self.nextYearBtn.setFixedSize(28, 28)

        yearLayout.addWidget(self.prevYearBtn)
        yearLayout.addWidget(self.yearLabel)
        yearLayout.addWidget(self.nextYearBtn)

        self.vLayout.addWidget(yearWidget)

        self.monthGrid = QWidget()
        self.monthLayout = QGridLayout(self.monthGrid)
        self.monthLayout.setSpacing(4)
        self.monthLayout.setContentsMargins(0, 0, 0, 0)

        self.monthBtns = []
        monthNames = [
            "一月",
            "二月",
            "三月",
            "四月",
            "五月",
            "六月",
            "七月",
            "八月",
            "九月",
            "十月",
            "十一月",
            "十二月",
        ]
        for i, name in enumerate(monthNames):
            btn = PushButton(name)
            btn.setFixedSize(60, 32)
            btn.clicked.connect(lambda checked, m=i + 1: self._onMonthClicked(m))
            self.monthLayout.addWidget(btn, i // 4, i % 4)
            self.monthBtns.append(btn)

        self.vLayout.addWidget(self.monthGrid)

        self.prevYearBtn.clicked.connect(self._onPrevYear)
        self.nextYearBtn.clicked.connect(self._onNextYear)

        self._applyStyle()

    def _applyStyle(self):
        is_dark = isDarkTheme()
        bg = "#2B313B" if is_dark else "#FFFFFF"
        border = "#495264" if is_dark else "#E5E7EB"
        self.setStyleSheet(
            f"""
            YearMonthPicker {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
        """
        )

    def setYear(self, year: int):
        self._currentYear = year
        self.yearLabel.setText(str(year))

    def _onPrevYear(self):
        self._currentYear -= 1
        self.yearLabel.setText(str(self._currentYear))

    def _onNextYear(self):
        self._currentYear += 1
        self.yearLabel.setText(str(self._currentYear))

    def _onMonthClicked(self, month: int):
        self.monthSelected.emit(self._currentYear, month)
        self.close()

    def showAt(self, globalPos: QPoint):
        self.move(globalPos)
        self.show()


class DateRangeCalendar(QWidget):
    dateClicked = Signal(QDate)
    hoverChanged = Signal(QDate)
    monthClicked = Signal()
    prevMonthRequested = Signal()
    nextMonthRequested = Signal()
    prevYearRequested = Signal()
    nextYearRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._currentMonth = QDate.currentDate().year(), QDate.currentDate().month()
        self._startDate: Optional[QDate] = None
        self._endDate: Optional[QDate] = None
        self._hoverDate: Optional[QDate] = None
        self._state = SelectionState.NONE
        self._recordDates: set[str] = set()

        self.cellSize = 40
        self.headerHeight = 36
        self.weekdayHeight = 28
        self._initColors()
        self._initUI()

    def _initColors(self):
        is_dark = isDarkTheme()
        tc = themeColor()

        self._bgColor = QColor(0x2B, 0x31, 0x3B) if is_dark else QColor(255, 255, 255)
        self._textColor = (
            QColor(0xE5, 0xE7, 0xEB) if is_dark else QColor(0x1F, 0x29, 0x37)
        )
        self._secondaryTextColor = (
            QColor(0x94, 0xA3, 0xB8) if is_dark else QColor(0x64, 0x74, 0x8B)
        )
        self._hoverBgColor = (
            QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 8)
        )
        self._rangeBgColor = (
            QColor(tc.red(), tc.green(), tc.blue(), 40)
            if is_dark
            else QColor(tc.red(), tc.green(), tc.blue(), 30)
        )
        self._selectedBgColor = tc
        self._borderColor = (
            QColor(0x49, 0x52, 0x64) if is_dark else QColor(0xE5, 0xE7, 0xEB)
        )

    def _initUI(self):
        self.mainLayout = QVBoxLayout(self)
        self.mainLayout.setContentsMargins(8, 4, 8, 4)
        self.mainLayout.setSpacing(0)

        self.headerWidget = QWidget()
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(0, 0, 0, 4)
        self.headerLayout.setSpacing(2)

        self.prevYearBtn = QPushButton("《")
        self.prevYearBtn.setFixedSize(32, 28)
        self.prevYearBtn.setFlat(True)
        self.prevYearBtn.setFont(QFont("Microsoft YaHei", 12, QFont.Black))
        self.prevYearBtn.clicked.connect(self.prevYearRequested)

        self.prevMonthBtn = QPushButton("〈")
        self.prevMonthBtn.setFixedSize(28, 28)
        self.prevMonthBtn.setFlat(True)
        self.prevMonthBtn.setFont(QFont("Microsoft YaHei", 12, QFont.Black))
        self.prevMonthBtn.clicked.connect(self.prevMonthRequested)

        self.titleLabel = QLabel()
        self.titleLabel.setAlignment(Qt.AlignCenter)
        self.titleLabel.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        self.titleLabel.mousePressEvent = self._onTitleClicked
        self.titleLabel.setCursor(Qt.PointingHandCursor)

        self.nextMonthBtn = QPushButton("〉")
        self.nextMonthBtn.setFixedSize(28, 28)
        self.nextMonthBtn.setFlat(True)
        self.nextMonthBtn.setFont(QFont("Microsoft YaHei", 12, QFont.Black))
        self.nextMonthBtn.clicked.connect(self.nextMonthRequested)

        self.nextYearBtn = QPushButton("》")
        self.nextYearBtn.setFixedSize(32, 28)
        self.nextYearBtn.setFlat(True)
        self.nextYearBtn.setFont(QFont("Microsoft YaHei", 12, QFont.Black))
        self.nextYearBtn.clicked.connect(self.nextYearRequested)

        self.headerLayout.addWidget(self.prevYearBtn)
        self.headerLayout.addWidget(self.prevMonthBtn)
        self.headerLayout.addWidget(self.titleLabel, 1)
        self.headerLayout.addWidget(self.nextMonthBtn)
        self.headerLayout.addWidget(self.nextYearBtn)

        self.calendarView = _CalendarView(self)
        self.calendarView.dateClicked.connect(self.dateClicked)
        self.calendarView.hoverChanged.connect(self.hoverChanged)

        self.mainLayout.addWidget(self.headerWidget)
        self.mainLayout.addWidget(self.calendarView, 1)

        self._updateTitle()
        self.setMinimumSize(
            self.cellSize * 7 + 20,
            self.headerHeight + self.weekdayHeight + self.cellSize * 6 + 20,
        )

    def _onTitleClicked(self, event):
        if event.button() == Qt.LeftButton:
            self.monthClicked.emit()

    def _updateTitle(self):
        year, month = self._currentMonth
        monthNames = [
            "一月",
            "二月",
            "三月",
            "四月",
            "五月",
            "六月",
            "七月",
            "八月",
            "九月",
            "十月",
            "十一月",
            "十二月",
        ]
        self.titleLabel.setText(f"{year}年 {monthNames[month - 1]}")

    def applyTheme(self):
        self._initColors()
        self.calendarView._initColors()
        self.calendarView.update()
        self.update()

    def setCurrentMonth(self, year: int, month: int):
        self._currentMonth = (year, month)
        self._updateTitle()
        self.calendarView._currentMonth = (year, month)
        self.calendarView.update()

    def currentMonth(self) -> Tuple[int, int]:
        return self._currentMonth

    def setStartDate(self, date: Optional[QDate]):
        self._startDate = date
        self.calendarView._startDate = date
        if date:
            self._state = SelectionState.START_SELECTED
        else:
            self._state = SelectionState.NONE
        self.calendarView.update()

    def setEndDate(self, date: Optional[QDate]):
        self._endDate = date
        self.calendarView._endDate = date
        if date and self._startDate:
            self._state = SelectionState.COMPLETE
        self.calendarView.update()

    def setRange(self, start: Optional[QDate], end: Optional[QDate]):
        self._startDate = start
        self._endDate = end
        self.calendarView._startDate = start
        self.calendarView._endDate = end
        if start and end:
            self._state = SelectionState.COMPLETE
        elif start:
            self._state = SelectionState.START_SELECTED
        else:
            self._state = SelectionState.NONE
        self.calendarView.update()

    def startDate(self) -> Optional[QDate]:
        return self._startDate

    def endDate(self) -> Optional[QDate]:
        return self._endDate

    def state(self) -> SelectionState:
        return self._state

    def setRecordDates(self, dates: set[str]):
        self._recordDates = dates
        self.calendarView._recordDates = dates
        self.calendarView.update()

    def recordDates(self) -> set[str]:
        return self._recordDates

    def prevMonth(self):
        year, month = self._currentMonth
        month -= 1
        if month < 1:
            month = 12
            year -= 1
        self.setCurrentMonth(year, month)

    def nextMonth(self):
        year, month = self._currentMonth
        month += 1
        if month > 12:
            month = 1
            year += 1
        self.setCurrentMonth(year, month)

    def prevYear(self):
        year, month = self._currentMonth
        self.setCurrentMonth(year - 1, month)

    def nextYear(self):
        year, month = self._currentMonth
        self.setCurrentMonth(year + 1, month)


class _CalendarView(QWidget):
    dateClicked = Signal(QDate)
    hoverChanged = Signal(QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._currentMonth = QDate.currentDate().year(), QDate.currentDate().month()
        self._startDate: Optional[QDate] = None
        self._endDate: Optional[QDate] = None
        self._hoverDate: Optional[QDate] = None
        self._recordDates: set[str] = set()

        self.cellSize = 40
        self.headerHeight = 0
        self.weekdayHeight = 28
        self.setMinimumSize(self.cellSize * 7, self.weekdayHeight + self.cellSize * 6)
        self.setMouseTracking(True)
        self._initColors()

    def _initColors(self):
        is_dark = isDarkTheme()
        tc = themeColor()

        self._bgColor = QColor(0x2B, 0x31, 0x3B) if is_dark else QColor(255, 255, 255)
        self._textColor = (
            QColor(0xE5, 0xE7, 0xEB) if is_dark else QColor(0x1F, 0x29, 0x37)
        )
        self._secondaryTextColor = (
            QColor(0x94, 0xA3, 0xB8) if is_dark else QColor(0x64, 0x74, 0x8B)
        )
        self._hoverBgColor = (
            QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 8)
        )
        self._rangeBgColor = (
            QColor(tc.red(), tc.green(), tc.blue(), 40)
            if is_dark
            else QColor(tc.red(), tc.green(), tc.blue(), 30)
        )
        self._selectedBgColor = tc

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        self._drawBackground(painter)
        self._drawWeekdays(painter)
        self._drawDays(painter)

    def _drawBackground(self, painter: QPainter):
        painter.fillRect(self.rect(), self._bgColor)

    def _drawWeekdays(self, painter: QPainter):
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        painter.setFont(QFont("Microsoft YaHei", 10))
        painter.setPen(self._secondaryTextColor)

        y = 2
        for i, day in enumerate(weekdays):
            x = i * self.cellSize
            rect = QRect(x, y, self.cellSize, self.weekdayHeight - 4)
            painter.drawText(rect, Qt.AlignCenter, day)

    def _drawDays(self, painter: QPainter):
        year, month = self._currentMonth
        firstDay = QDate(year, month, 1)
        daysInMonth = firstDay.daysInMonth()
        startOffset = firstDay.dayOfWeek() - 1

        normalFont = QFont("Microsoft YaHei", 10)
        recordFont = QFont("Microsoft YaHei", 12, QFont.Bold)

        for day in range(1, daysInMonth + 1):
            date = QDate(year, month, day)
            rect = self._dateToRect(date)

            if not rect.isValid():
                continue

            cellRect = QRect(
                rect.x() + 2, rect.y() + 2, rect.width() - 4, rect.height() - 4
            )

            isStart = self._startDate and date == self._startDate
            isEnd = self._endDate and date == self._endDate
            isInRange = self._isInRange(date)
            isHover = self._hoverDate and date == self._hoverDate
            dateStr = date.toString("yyyy-MM-dd")
            hasRecord = dateStr in self._recordDates

            if isStart or isEnd:
                self._drawEndpoint(painter, cellRect, isStart)
            elif isInRange:
                self._drawInRange(painter, cellRect)
            elif isHover:
                self._drawHover(painter, cellRect)

            if isStart or isEnd:
                textColor = QColor(255, 255, 255)
                painter.setFont(normalFont)
            elif hasRecord:
                textColor = QColor(0x3B, 0xA5, 0xD8)
                painter.setFont(recordFont)
            else:
                textColor = self._textColor
                painter.setFont(normalFont)

            painter.setPen(textColor)
            painter.drawText(cellRect, Qt.AlignCenter, str(day))

    def _dateToRect(self, date: QDate) -> QRect:
        year, month = self._currentMonth
        if date.year() != year or date.month() != month:
            return QRect()

        firstDay = QDate(year, month, 1)
        startOffset = firstDay.dayOfWeek() - 1

        col = (startOffset + date.day() - 1) % 7
        row = (startOffset + date.day() - 1) // 7

        x = col * self.cellSize
        y = self.weekdayHeight + row * self.cellSize

        return QRect(x, y, self.cellSize, self.cellSize)

    def _posToDate(self, pos: QPoint) -> Optional[QDate]:
        year, month = self._currentMonth

        col = pos.x() // self.cellSize
        row = (pos.y() - self.weekdayHeight) // self.cellSize

        if not (0 <= col < 7 and row >= 0):
            return None

        firstDay = QDate(year, month, 1)
        startOffset = firstDay.dayOfWeek() - 1

        dayIndex = row * 7 + col - startOffset + 1
        daysInMonth = firstDay.daysInMonth()

        if 1 <= dayIndex <= daysInMonth:
            return QDate(year, month, dayIndex)
        return None

    def _isInRange(self, date: QDate) -> bool:
        if not self._startDate:
            return False
        if self._endDate:
            return self._startDate <= date <= self._endDate
        return False

    def _drawEndpoint(self, painter: QPainter, rect: QRect, isStart: bool):
        tc = themeColor()
        painter.setBrush(QBrush(tc))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

    def _drawInRange(self, painter: QPainter, rect: QRect):
        painter.setBrush(QBrush(self._rangeBgColor))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)

    def _drawHover(self, painter: QPainter, rect: QRect):
        painter.setBrush(QBrush(self._hoverBgColor))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(rect)

    def mouseMoveEvent(self, event):
        date = self._posToDate(event.pos())
        if date and date != self._hoverDate:
            self._hoverDate = date
            self.hoverChanged.emit(date)
        self.update()

    def leaveEvent(self, event):
        self._hoverDate = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        date = self._posToDate(event.pos())
        if date:
            self.dateClicked.emit(date)


class DateRangePickerBase(QWidget):
    rangeChanged = Signal(QDate, QDate)
    cancelled = Signal()

    QUICK_OPTIONS = [
        (7, "近7天"),
        (14, "近14天"),
        (30, "近30天"),
        (90, "近90天"),
        ("week", "本周"),
        ("month", "本月"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._startDate: Optional[QDate] = None
        self._endDate: Optional[QDate] = None
        self._state = SelectionState.NONE

        self._initUI()

    def _initUI(self):
        self.vLayout = QVBoxLayout(self)
        self.vLayout.setContentsMargins(0, 0, 0, 0)
        self.vLayout.setSpacing(0)

        self.headerWidget = QWidget()
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setContentsMargins(16, 12, 16, 12)

        self.startDateLabel = BodyLabel("开始日期: 未选择")
        self.endDateLabel = BodyLabel("结束日期: 未选择")

        self.headerLayout.addWidget(self.startDateLabel)
        self.headerLayout.addStretch()
        self.headerLayout.addWidget(self.endDateLabel)

        self.calendarWidget = QWidget()
        self.calendarLayout = QHBoxLayout(self.calendarWidget)
        self.calendarLayout.setContentsMargins(8, 0, 8, 8)
        self.calendarLayout.setSpacing(8)

        self.leftCalendar = DateRangeCalendar()
        self.rightCalendar = DateRangeCalendar()

        self.calendarLayout.addWidget(self.leftCalendar, 1)
        self.calendarLayout.addWidget(self.rightCalendar, 1)

        self.quickSelectWidget = QWidget()
        self.quickSelectLayout = QHBoxLayout(self.quickSelectWidget)
        self.quickSelectLayout.setContentsMargins(16, 8, 16, 8)
        self.quickSelectLayout.setSpacing(8)

        quickLabel = BodyLabel("快捷选择:")
        self.quickSelectLayout.addWidget(quickLabel)

        self.quickBtns = []
        for key, text in self.QUICK_OPTIONS:
            btn = PushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, k=key: self._onQuickSelect(k))
            self.quickSelectLayout.addWidget(btn)
            self.quickBtns.append(btn)

        self.quickSelectLayout.addStretch()

        self.buttonWidget = QWidget()
        self.buttonLayout = QHBoxLayout(self.buttonWidget)
        self.buttonLayout.setContentsMargins(16, 8, 16, 16)

        self.clearBtn = PushButton("清除")
        self.confirmBtn = PushButton("确定")
        self.confirmBtn.setEnabled(False)

        self.buttonLayout.addStretch()
        self.buttonLayout.addWidget(self.clearBtn)
        self.buttonLayout.addWidget(self.confirmBtn)

        self.vLayout.addWidget(self.headerWidget)
        self.vLayout.addWidget(self.calendarWidget)
        self.vLayout.addWidget(self.quickSelectWidget)
        self.vLayout.addWidget(self.buttonWidget)

        self._connectSignals()
        self._syncCalendars()

    def _connectSignals(self):
        self.leftCalendar.prevMonthRequested.connect(self.leftCalendar.prevMonth)
        self.leftCalendar.nextMonthRequested.connect(self.leftCalendar.nextMonth)
        self.leftCalendar.prevYearRequested.connect(self.leftCalendar.prevYear)
        self.leftCalendar.nextYearRequested.connect(self.leftCalendar.nextYear)

        self.rightCalendar.prevMonthRequested.connect(self.rightCalendar.prevMonth)
        self.rightCalendar.nextMonthRequested.connect(self.rightCalendar.nextMonth)
        self.rightCalendar.prevYearRequested.connect(self.rightCalendar.prevYear)
        self.rightCalendar.nextYearRequested.connect(self.rightCalendar.nextYear)

        self.leftCalendar.dateClicked.connect(self._onDateClicked)
        self.rightCalendar.dateClicked.connect(self._onDateClicked)

        self.leftCalendar.hoverChanged.connect(self._onHoverChanged)
        self.rightCalendar.hoverChanged.connect(self._onHoverChanged)

        self.leftCalendar.monthClicked.connect(
            lambda: self._showYearMonthPicker(self.leftCalendar)
        )
        self.rightCalendar.monthClicked.connect(
            lambda: self._showYearMonthPicker(self.rightCalendar)
        )

        self.clearBtn.clicked.connect(self._onClear)
        self.confirmBtn.clicked.connect(self._onConfirm)

    def _showYearMonthPicker(self, calendar: DateRangeCalendar):
        year, month = calendar.currentMonth()
        picker = YearMonthPicker(self)
        picker.setYear(year)
        picker.monthSelected.connect(lambda y, m: calendar.setCurrentMonth(y, m))
        globalPos = calendar.mapToGlobal(QPoint(10, 40))
        picker.showAt(globalPos)

    def _syncCalendars(self):
        today = QDate.currentDate()
        self.leftCalendar.setCurrentMonth(today.year(), today.month())
        nextMonth = today.addMonths(1)
        self.rightCalendar.setCurrentMonth(nextMonth.year(), nextMonth.month())

    def _onDateClicked(self, date: QDate):
        if self._state == SelectionState.NONE:
            self._startDate = date
            self._endDate = None
            self._state = SelectionState.START_SELECTED
        elif self._state == SelectionState.START_SELECTED:
            if date < self._startDate:
                self._endDate = self._startDate
                self._startDate = date
            else:
                self._endDate = date
            self._state = SelectionState.COMPLETE
        else:
            self._startDate = date
            self._endDate = None
            self._state = SelectionState.START_SELECTED

        self._updateCalendars()
        self._updateLabels()
        self._updateQuickBtnState()
        self.confirmBtn.setEnabled(self._state == SelectionState.COMPLETE)

    def _onHoverChanged(self, date: QDate):
        pass

    def _onQuickSelect(self, key):
        today = QDate.currentDate()

        if isinstance(key, int):
            self._endDate = today
            self._startDate = today.addDays(-key + 1)
        elif key == "week":
            daysToMonday = today.dayOfWeek() - 1
            self._startDate = today.addDays(-daysToMonday)
            self._endDate = today
        elif key == "month":
            self._startDate = QDate(today.year(), today.month(), 1)
            self._endDate = today

        self._state = SelectionState.COMPLETE
        self._updateCalendars()
        self._updateLabels()
        self._updateQuickBtnState(key)
        self.confirmBtn.setEnabled(True)

    def _updateQuickBtnState(self, activeKey=None):
        for i, (key, _) in enumerate(self.QUICK_OPTIONS):
            self.quickBtns[i].blockSignals(True)
            self.quickBtns[i].setChecked(key == activeKey)
            self.quickBtns[i].blockSignals(False)

    def _updateCalendars(self):
        self.leftCalendar.setRange(self._startDate, self._endDate)
        self.rightCalendar.setRange(self._startDate, self._endDate)

    def _updateLabels(self):
        if self._startDate:
            self.startDateLabel.setText(
                f"开始日期: {self._startDate.toString('yyyy-MM-dd')}"
            )
        else:
            self.startDateLabel.setText("开始日期: 未选择")

        if self._endDate:
            self.endDateLabel.setText(
                f"结束日期: {self._endDate.toString('yyyy-MM-dd')}"
            )
        else:
            self.endDateLabel.setText("结束日期: 未选择")

    def _onClear(self):
        self._startDate = None
        self._endDate = None
        self._state = SelectionState.NONE
        self._updateCalendars()
        self._updateLabels()
        self._updateQuickBtnState()
        self.confirmBtn.setEnabled(False)

    def _onConfirm(self):
        if self._startDate and self._endDate:
            self.rangeChanged.emit(self._startDate, self._endDate)

    def setRange(self, start: Optional[QDate], end: Optional[QDate]):
        self._startDate = start
        self._endDate = end
        if start and end:
            self._state = SelectionState.COMPLETE
        elif start:
            self._state = SelectionState.START_SELECTED
        else:
            self._state = SelectionState.NONE
        self._updateCalendars()
        self._updateLabels()
        self.confirmBtn.setEnabled(self._state == SelectionState.COMPLETE)

    def getRange(self) -> Tuple[Optional[QDate], Optional[QDate]]:
        return self._startDate, self._endDate

    def setRecordDates(self, dates: set[str]):
        self.leftCalendar.setRecordDates(dates)
        self.rightCalendar.setRecordDates(dates)

    def applyTheme(self):
        self.leftCalendar.applyTheme()
        self.rightCalendar.applyTheme()


class DateRangeDialog(QDialog):
    rangeSelected = Signal(QDate, QDate)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择日期范围")
        self.setModal(True)
        self.setFixedSize(640, 420)

        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.picker = DateRangePickerBase(self)
        layout.addWidget(self.picker)

        self.picker.rangeChanged.connect(self._onRangeChanged)
        self.picker.cancelled.connect(self.reject)

        self._applyStyle()

    def _applyStyle(self):
        is_dark = isDarkTheme()
        bg = "#2B313B" if is_dark else "#FFFFFF"
        self.setStyleSheet(f"background-color: {bg}; border-radius: 8px;")

    def setRange(self, start: Optional[QDate], end: Optional[QDate]):
        self.picker.setRange(start, end)

    def setRecordDates(self, dates: set[str]):
        self.picker.setRecordDates(dates)

    def getRange(self) -> Tuple[Optional[QDate], Optional[QDate]]:
        return self.picker.getRange()

    def _onRangeChanged(self, start: QDate, end: QDate):
        self.rangeSelected.emit(start, end)
        self.accept()


class DateRangePicker(PushButton):
    rangeChanged = Signal(QDate, QDate)

    def __init__(self, parent=None, placeholder: str = "选择日期范围"):
        super().__init__(parent)
        self._startDate: Optional[QDate] = None
        self._endDate: Optional[QDate] = None
        self._placeholder = placeholder
        self._recordDates: set[str] = set()

        self.setText(placeholder)
        self.setFixedHeight(33)
        self.setMinimumWidth(200)

        self.clicked.connect(self._showDialog)

    def _showDialog(self):
        dialog = DateRangeDialog(self.window())
        if self._startDate and self._endDate:
            dialog.setRange(self._startDate, self._endDate)
        if self._recordDates:
            dialog.setRecordDates(self._recordDates)

        if dialog.exec() == QDialog.Accepted:
            start, end = dialog.getRange()
            if start and end:
                self._startDate = start
                self._endDate = end
                self.setText(
                    f"{start.toString('yyyy-MM-dd')} ~ {end.toString('yyyy-MM-dd')}"
                )
                self.rangeChanged.emit(start, end)

    def setRange(self, start: Optional[QDate], end: Optional[QDate]):
        self._startDate = start
        self._endDate = end
        if start and end:
            self.setText(
                f"{start.toString('yyyy-MM-dd')} ~ {end.toString('yyyy-MM-dd')}"
            )
        else:
            self.setText(self._placeholder)

    def setRecordDates(self, dates: set[str]):
        self._recordDates = dates

    def getRange(self) -> Tuple[Optional[QDate], Optional[QDate]]:
        return self._startDate, self._endDate

    def clear(self):
        self._startDate = None
        self._endDate = None
        self.setText(self._placeholder)
