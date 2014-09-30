#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

__author__ = "Niklas Fiekas"

__email__ = "niklas.fiekas@tu-clausthal.de"

import indexed

import ConfigParser
import mysql.connector
import sys
import datetime
import calendar
import os
import getpass
import message_queue

from PySide.QtCore import *
from PySide.QtGui import *

EPOCH_ORDINAL = 719163

MONTH_NAMES = ["Dezember", "Januar", "Februar", u"März", "April", "Mai", "Juni",
               "Juli", "August", "September", "Oktober", "November", "Dezember"]


def format_halves(*args):
    if len(args) == 1:
        num_full, num_half = args[0]
    else:
        num_full, num_half = args[0], args[1]

    num_full = int(num_full) + int(num_half) // 2
    if int(num_half) % 2 == 1:
        if num_full == 0:
            return u"½"
        else:
            return u"%d½" % num_full
    else:
        return str(num_full)

def map_pixel(pixmap, mapper):
    image = pixmap.toImage()

    for x in xrange(0, pixmap.width()):
        for y in xrange(0, pixmap.height()):
            pixel = image.pixel(x, y)
            tuple = mapper(qRed(pixel), qGreen(pixel), qBlue(pixel), qAlpha(pixel))
            image.setPixel(x, y, qRgba(tuple[0], tuple[1], tuple[2], tuple[3]))

    return QPixmap.fromImage(image)

def lighter(r, g, b, a):
    color = QColor(r, g, b, a).lighter(110)
    return color.red(), color.green(), color.blue(), color.alpha()

def darker(r, g, b, a):
    color = QColor(r, g, b, a).lighter(90)
    return color.red(), color.green(), color.blue(), color.alpha()


def contrasting_color(color):
    (r, g, b, a) = color.getRgb()
    brightness = r * 0.2126 + g * 0.7152 + b * 0.0722
    if brightness > 125:
        return QColor(38, 38, 38, a)
    else:
        return QColor(217, 217, 217, a)


def days_of_month(year, month):
    return calendar.monthrange(year, month)[1]


def qdate(d):
    return None if d is None else QDate(d.year, d.month, d.day)

def pydate(qd):
    return None if qd is None else datetime.date(qd.year(), qd.month(), qd.day())


def easter_sunday(year):
    g = year % 19
    c = year / 100
    h = (c - (c / 4) - ((9 * c + 13) / 25) + 19 * g + 15) % 30
    i = h - (h / 28) * (1 - (h / 28) * (29 / (h + 1)) * ((21 - g) / 11))
    day = i - ((year + (year / 4) + i + 2 - c + (c / 4)) % 7) + 28
    month = 3
    if day > 31:
        return QDate(year, month + 1, day - 31)
    else:
        return QDate(year, month, day)


HOLIDAY_NONE = 0
HOLIDAY_NEWYEAR = 1
HOLIDAY_GOOD_FRIDAY = 2
HOLIDAY_EASTER_MONDAY = 4
HOLIDAY_MAY_1 = 8
HOLIDAY_ASCENSION = 16
HOLIDAY_PENTECOST = 32
HOLIDAY_TAG_DER_DEUTSCHEN_EINHEIT = 64
HOLIDAY_CHRISTMAS = 128
HOLIDAY_WEEKEND = 256

def is_holiday(date):
    holiday = HOLIDAY_NONE

    easter = easter_sunday(date.year)
    date = qdate(date)

    if date.dayOfWeek() in (6, 7):
        holiday |= HOLIDAY_WEEKEND

    if date.addDays(2) == easter:
        holiday |= HOLIDAY_GOOD_FRIDAY
    elif date.addDays(-1) == easter:
        holiday |= HOLIDAY_EASTER_MONDAY
    elif date.addDays(-39) == easter:
        holiday |= HOLIDAY_ASCENSION
    elif date.addDays(-50) == easter:
        holiday |= HOLIDAY_PENTECOST

    if date.dayOfYear() == 1:
        holiday |= HOLIDAY_NEWYEAR
    elif date.month() == 5 and date.day() == 1:
        holiday |= HOLIDAY_MAY_1
    elif date.month() == 10 and date.day() == 3:
        holiday |= HOLIDAY_TAG_DER_DEUTSCHEN_EINHEIT
    elif date.month() == 12 and date.day() in (25, 26):
        holiday |= HOLIDAY_CHRISTMAS

    return holiday


class CalendarStrip(QWidget):
    def __init__(self, parent=None):
        super(CalendarStrip, self).__init__(parent)

        self._offset = 0.0

    def columnWidth(self):
        return min(self.width() / 45.0, 25.0)

    def offset(self):
        return self._offset

    def setOffset(self, offset):
        self._offset = float(offset)

    def visibleDays(self):
        start = int(self._offset - max([33]))
        end = int(self._offset + self.width() / self.columnWidth() + 1)

        for day in xrange(start, end):
            x = (day - self._offset) * self.columnWidth()
            yield x, datetime.date.fromordinal(day + EPOCH_ORDINAL)

    def currentDate(self):
        return datetime.date.fromordinal(int(self._offset) + EPOCH_ORDINAL)

    def dateFromX(self, x):
        return datetime.date.fromordinal(int(self._offset + EPOCH_ORDINAL + x / self.columnWidth()))

    def xFromDate(self, date):
        return (date.toordinal() - self._offset - EPOCH_ORDINAL) * self.columnWidth()


class CalendarHeader(CalendarStrip):

    leftClicked = Signal(int, int)

    todayClicked = Signal(int, int)

    rightClicked = Signal(int, int)

    def __init__(self, parent=None):
        super(CalendarHeader, self).__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Button state info.
        self.mousePos = None
        self.leftActive = False
        self.todayActive = False
        self.rightActive = False

        # Left button pixmaps.
        self.leftPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_previous.png"))
        self.lighterLeftPixmap = map_pixel(self.leftPixmap, lighter)
        self.darkerLeftPixmap = map_pixel(self.leftPixmap, darker)

        # Today button pixmaps.
        self.todayPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date.png"))
        self.lighterTodayPixmap = map_pixel(self.todayPixmap, lighter)
        self.darkerTodayPixmap = map_pixel(self.todayPixmap, darker)

        # Right button pixmaps.
        self.rightPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_next.png"))
        self.lighterRightPixmap = map_pixel(self.rightPixmap, lighter)
        self.darkerRightPixmap = map_pixel(self.rightPixmap, darker)

    def visibleLeftButtons(self):
        for x, date in self.visibleDays():
            if date.day == 1:
                yield date, QRect(x + 32, (40 - 32) / 2, 32, 32)

    def visibleTodayButtons(self):
        for x, date in self.visibleDays():
            if date.day == 1:
                yield date, QRect(x + 32 * 2, (40 - 32) / 2, 32, 32)

    def visibleRightButtons(self):
        for x, date in self.visibleDays():
            if date.day == 1:
                yield date, QRect(x + 32 * 3, (40 - 32) / 2, 32, 32)

    def updateButtons(self):
        for date, rect in self.visibleLeftButtons():
            self.update(rect)
        for date, rect in self.visibleTodayButtons():
            self.update(rect)
        for date, rect in self.visibleRightButtons():
            self.update(rect)

    def leaveEvent(self, event):
        self.mousePos = None
        self.updateButtons()

    def mouseMoveEvent(self, event):
        self.mousePos = event.pos()
        self.updateButtons()

    def mousePressEvent(self, event):
        self.mousePos = event.pos()
        self.leftActive = False

        for date, rect in self.visibleLeftButtons():
            if rect.contains(event.pos()):
                self.leftActive = True
                self.update(rect)

        for date, rect in self.visibleTodayButtons():
            if rect.contains(event.pos()):
                self.todayActive = True
                self.update(rect)

        for date, rect in self.visibleRightButtons():
            if rect.contains(event.pos()):
                self.rightActive = True
                self.update(rect)

    def mouseReleaseEvent(self, event):
        self.mousePos = event.pos()

        # Trigger left clicked signal.
        for date, rect in self.visibleLeftButtons():
            if rect.contains(event.pos()):
                self.leftClicked.emit(date.year, date.month)
                self.update(rect)

        # Trigger today clicked signal.
        for date, rect in self.visibleTodayButtons():
            if rect.contains(event.pos()):
                self.todayClicked.emit(date.year, date.month)
                self.update(rect)

        # Trigger right clicked signal.
        for date, rect in self.visibleRightButtons():
            if rect.contains(event.pos()):
                self.rightClicked.emit(date.year, date.month)
                self.update(rect)

        self.leftActive = False
        self.todayActive = False
        self.rightActive = False

    def paintEvent(self, event):
        painter = QPainter(self)

        opt = QStyleOptionHeader()
        opt.state = QStyle.State_Enabled | QStyle.State_Raised
        opt.textAlignment = Qt.AlignCenter

        for xStart, date in self.visibleDays():
            # Draw weak headers.
            if date.weekday() == 0:
                week = date.timetuple().tm_yday / 7 + 1
                if datetime.date(date.year, 1, 1).weekday() != 0:
                    week += 1

                opt.rect = QRect(xStart, 40, self.columnWidth() * 7, 20)
                opt.text = "Woche %d" % week

                painter.save()
                self.style().drawControl(QStyle.CE_Header, opt, painter, self)
                painter.restore()

            # Draw month headers.
            if date.day == 1:
                daysOfMonth = calendar.monthrange(date.year, date.month)
                opt.rect = QRect(xStart, 0, self.columnWidth() * daysOfMonth[1], 40)
                opt.text = ""
                painter.save()
                self.style().drawControl(QStyle.CE_Header, opt, painter, self)
                painter.restore()

                painter.save()
                font = self.font()
                font.setPointSizeF(font.pointSizeF() * 1.2)
                font.setBold(True)
                painter.setFont(font)

                painter.drawText(QRect(xStart + 32 * 5, 0, self.columnWidth() * daysOfMonth[1] - 32 * 5, 40),
                    Qt.AlignVCenter, "%s %d" % (MONTH_NAMES[date.month], date.year))
                painter.restore()

            # Draw day headers.
            opt.rect = QRect(xStart, 60, self.columnWidth(), 20)
            opt.text = str(date.day)
            painter.save()
            self.style().drawControl(QStyle.CE_Header, opt, painter, self)
            painter.restore()

        # Draw go left buttons.
        for date, rect in self.visibleLeftButtons():
            pixmapRect = QRect(rect.x() + (rect.width() - 16) / 2, rect.y() + (rect.height() - 16) / 2, 16, 16)
            if self.mousePos and rect.contains(self.mousePos):
                if self.leftActive:
                    painter.drawPixmap(pixmapRect, self.darkerLeftPixmap, QRect(0, 0, 16, 16))
                else:
                    painter.drawPixmap(pixmapRect, self.lighterLeftPixmap, QRect(0, 0, 16, 16))
            else:
                painter.drawPixmap(pixmapRect, self.leftPixmap, QRect(0, 0, 16, 16))

        # Draw today buttons.
        for date, rect in self.visibleTodayButtons():
            pixmapRect = QRect(rect.x() + (rect.width() - 16) / 2, rect.y() + (rect.height() - 16) / 2, 16, 16)
            if self.mousePos and rect.contains(self.mousePos):
                if self.todayActive:
                    painter.drawPixmap(pixmapRect, self.darkerTodayPixmap, QRect(0, 0, 16, 16))
                else:
                    painter.drawPixmap(pixmapRect, self.lighterTodayPixmap, QRect(0, 0, 16, 16))
            else:
                painter.drawPixmap(pixmapRect, self.todayPixmap, QRect(0, 0, 16, 16))

        # Draw go right buttons.
        for date, rect in self.visibleRightButtons():
            pixmapRect = QRect(rect.x() + (rect.width() - 16) / 2, rect.y() + (rect.height() - 16) / 2, 16, 16)
            if self.mousePos and rect.contains(self.mousePos):
                if self.rightActive:
                    painter.drawPixmap(pixmapRect, self.darkerRightPixmap, QRect(0, 0, 16, 16))
                else:
                    painter.drawPixmap(pixmapRect, self.lighterRightPixmap, QRect(0, 0, 16, 16))
            else:
                painter.drawPixmap(pixmapRect, self.rightPixmap, QRect(0, 0, 16, 16))

        painter.end()

    def sizeHint(self):
        return QSize(40 * 25, 80)


class HolidayOverlay(object):
    def __init__(self, app):
        self.app = app
        self._brush = QBrush(self.app.lightRed)

    def brush(self):
        return self._brush

    def matches(self, date):
        return is_holiday(date)


class SchoolHolidays(object):
    def __init__(self, app):
        self.app = app
        self._brush = QBrush(self.app.orange, Qt.BDiagPattern)

    def brush(self):
        return self._brush

    def matches(self, date):
        # Sommerferien 2014.
        if datetime.date(2014, 7, 31) <= date <= datetime.date(2014, 9, 10):
            return True

        # Herbstferien 2014.
        if datetime.date(2014, 10, 27) <= date <= datetime.date(2014, 11, 8):
            return True

        # Weichnatsferien 2014.
        if datetime.date(2014, 12, 22) <= date <= datetime.date(2015, 1, 5):
            return True

        # Winterferien 2015.
        if datetime.date(2015, 2, 2) <= date <= datetime.date(2015, 2, 3):
            return True

        # Osterferien 2015.
        if datetime.date(2015, 3, 25) <= date <= datetime.date(2015, 4, 10):
            return True

        # Pfingsferien 2015.
        if datetime.date(2015, 5, 15) <= date <= datetime.date(2015, 5, 26):
            return True

        # Sommerferien 2015.
        if datetime.date(2015, 7, 23) <= date <= datetime.date(2015, 9, 2):
            return True

        # Herbstferien 2015.
        if datetime.date(2015, 10, 19) <= date <= datetime.date(2015, 10, 31):
            return True

        # Weihnachtsferien 2015.
        if datetime.date(2015, 12, 23) <= date <= datetime.date(2016, 1, 6):
            return True

        return False


class CalendarBody(CalendarStrip):

    holidayClicked = Signal(int)

    dayClicked = Signal(int)

    cellClicked = Signal(int, int)

    dayRangeSelected = Signal(int, int)

    def __init__(self, app, parent=None):
        super(CalendarBody, self).__init__(parent)
        self.app = app
        self.setMouseTracking(True)

        self.overlays = [HolidayOverlay(self.app), SchoolHolidays(self.app)]

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenuRequested)

        self.mousePos = None
        self.mousePressPos = None

        self.app.holidayModel.modelReset.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Fill background.
        painter.fillRect(self.rect(), QBrush(self.app.white))

        # Calculate drag start day.
        if self.mousePressPos:
            dragStartDate = self.dateFromX(self.mousePressPos.x())
        else:
            dragStartDate = None

        # Calculate hovered day.
        if self.mousePos:
            hoveredDate = self.dateFromX(self.mousePos.x())
        else:
            hoveredDate = None

        # Gray out the past.
        gradient = QLinearGradient(0, 0, 1, 0)
        gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
        gradient.setColorAt(0, QColor(212, 208, 200, 0))
        gradient.setColorAt(1, QColor(212, 208, 200, 188))
        xEnd = self.xFromDate(datetime.date.today())
        xStart = xEnd - self.columnWidth() * 6
        rect = QRect(xStart, 0, xEnd - xStart, self.height())
        painter.fillRect(rect, QBrush(gradient))

        for x, date in self.visibleDays():
            rect = QRect(x, 0, self.columnWidth(), self.height())

            # Draw overlays.
            for overlay in self.overlays:
                if overlay.matches(date):
                    painter.fillRect(rect, overlay.brush())

            # Paint columns.
            if date.day == 1:
                painter.setPen(QPen())
            else:
                painter.setPen(QPen(self.app.gray))
            painter.drawLine(x, 0, x, self.height())

            # Highlight hovered day.
            if date == hoveredDate:
                painter.fillRect(rect, QBrush(QColor(180, 200, 220, 220)))
            elif (dragStartDate and hoveredDate and date >= min(hoveredDate, dragStartDate) and date <= max(hoveredDate, dragStartDate)):
                painter.fillRect(rect, QBrush(QColor(180, 200, 220, 100)))

        # Paint rows.
        painter.setPen(QPen(self.app.gray))
        for i in xrange(self.app.holidayModel.rowCount()):
            painter.drawLine(0, (15 + 25 + 15) * i + 15,
                self.width(), (15 + 25 + 15) * i + 15)
            painter.drawLine(0, (15 + 25 + 15) * i + 15 + 25,
                self.width(), (15 + 25 + 15) * i + 15 + 25)

        painter.setPen(QPen())

        # Draw holidays.
        for holiday, rect in self.visibleHolidays():
            painter.setPen(QPen())

            if holiday.type == TYPE_HOLIDAY and holiday.confirmed:
                color = self.app.green
            elif holiday.type == TYPE_HOLIDAY and not holiday.confirmed:
                color = self.app.blue
            elif holiday.type == TYPE_HEALTH:
                color = self.app.orange
            elif holiday.type == TYPE_BUSINESS_TRIP:
                color = self.app.purple
            elif holiday.type == TYPE_PLANNED:
                color = self.app.gray
            elif holiday.type == TYPE_FLEXITIME:
                color = self.app.lightGreen
            elif holiday.type == TYPE_SPECIAL:
                color = self.app.yellow

            if self.mousePos and rect.contains(self.mousePos):
                gradient = QRadialGradient(QPointF(0.5, 0.5), 0.5)
                gradient.setCoordinateMode(QGradient.ObjectBoundingMode)
                gradient.setColorAt(0, color.lighter(140))
                if self.mousePressPos:
                    gradient.setColorAt(1, color.lighter(80))
                else:
                    gradient.setColorAt(1, color)
                painter.setBrush(QBrush(gradient))
            else:
                painter.setBrush(QBrush(color))
            painter.drawRect(rect)

        # Draw names.
        ownContact = self.app.holidayModel.contactFromHandle()
        for x, date in self.visibleDays():
            if date.day == 1:
                for i, contact in enumerate(self.app.holidayModel.contactCache.values()):
                    if ownContact and (ownContact.id == contact.id or contact.department in ownContact.writableDepartments()):
                        text = u"%s (%s in %d)" % (contact.name, format_halves(contact.numHolidays(date.year)), date.year)
                    else:
                        text = contact.name
                    painter.drawText(QRect(x + 10, (15 + 25 + 15) * i + 15, self.columnWidth() * 20 - 10, 25), Qt.AlignVCenter, text)

        painter.end()

    def sizeHint(self):
        return QSize(40 * 25, self.app.holidayModel.rowCount() * (15 + 25 + 15))

    def mouseMoveEvent(self, event):
        self.mousePos = event.pos()
        self.update()

    def leaveEvent(self, event):
        self.mousePos = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mousePressPos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            dateTwo = self.dateFromX(event.pos().x())
            if self.mousePressPos:
                dateOne = self.dateFromX(self.mousePressPos.x())
            else:
                dateOne = dateTwo

            dragStartDate = min(dateOne, dateTwo)
            dragEndDate = max(dateOne, dateTwo)

            if dragStartDate == dragEndDate:
                for holiday, rect in self.visibleHolidays():
                    if rect.contains(event.pos()):
                        self.holidayClicked.emit(holiday.id)
            else:
                self.dayRangeSelected.emit(dragStartDate.toordinal() - EPOCH_ORDINAL, dragEndDate.toordinal() - EPOCH_ORDINAL)

        self.update()
        self.mousePressPos = None

    def mouseDoubleClickEvent(self, event):
        for holiday, rect in self.visibleHolidays():
            if rect.contains(event.pos()):
                return

        self.dayClicked.emit(int(self.offset() + event.pos().x() / self.columnWidth()))

    def onCustomContextMenuRequested(self, pos):
        contextMenu = QMenu()

        # Get day by x-position.
        day =  int(self.offset() + pos.x() / self.columnWidth())
        contextMenu.addAction(u"Eintragen", lambda: self.dayClicked.emit(day))

        # Get contact by y-position.
        index = max(pos.y() // (15 + 25 + 15), 0)
        try:
            contact = self.app.holidayModel.contactCache.values()[index]
            contextMenu.addAction(u"Eintragen für »%s«" % contact.name, lambda: self.cellClicked.emit(day, index))
        except IndexError:
            pass

        contextMenu.addSeparator()

        for holiday, rect in self.visibleHolidays():
            if rect.contains(pos):
                contextMenu.addAction("Bearbeiten (%d)" % holiday.id, lambda id=holiday.id: self.holidayClicked.emit(id))

        contextMenu.exec_(self.mapToGlobal(pos))

    def visibleHolidays(self):
        for holiday in self.app.holidayModel.holidayCache.values():
            try:
                y = self.app.holidayModel.contactCache.keys().index(holiday.contactId) * (15 + 25 + 15) + 15
            except ValueError:
                continue

            startX = (holiday.start.toordinal() - EPOCH_ORDINAL - self.offset()) * self.columnWidth()
            if holiday.startHalfDay:
                startX += self.columnWidth() / 2

            endX = (holiday.end.toordinal() + 1 - EPOCH_ORDINAL - self.offset()) * self.columnWidth()
            if holiday.endHalfDay:
                endX -= self.columnWidth() / 2

            yield holiday, QRect(startX, y, endX - startX, 25)


class VariantAnimation(QVariantAnimation):
    def updateCurrentValue(self, value):
        pass


class CalendarPane(QScrollArea):
    def __init__(self, app, parent=None):
        super(CalendarPane, self).__init__(parent)
        self.app = app
        self.setViewportMargins(0, 80, 0, 0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.app.holidayModel.modelReset.connect(self.updateWidgetSizes)

        self.offset = datetime.date.today().toordinal() - EPOCH_ORDINAL - 7

        self.header = CalendarHeader(self)
        self.header.leftClicked.connect(self.onLeftClicked)
        self.header.todayClicked.connect(self.onTodayClicked)
        self.header.rightClicked.connect(self.onRightClicked)
        self.header.setOffset(self.offset)

        self.setWidget(CalendarBody(app, self))
        self.widget().setOffset(self.offset)
        self.widget().holidayClicked.connect(self.onHolidayClicked)
        self.widget().dayClicked.connect(self.onDayClicked)
        self.widget().cellClicked.connect(self.onCellClicked)
        self.widget().dayRangeSelected.connect(self.onDayRangeSelected)

        self.animation = VariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.InOutQuad))
        self.animation.valueChanged.connect(self.onAnimate)
        self.animation.setDuration(1000)
        self.installEventFilter(self)

        self.animationEnabled = False

    def onLeftClicked(self, year, month):
        self.animationEnabled = False

        self.offset -= days_of_month(year - 1 if month == 1 else year, 12 if month == 1 else month - 1)

        self.animation.setStartValue(self.header.offset())
        self.animation.setEndValue(float(self.offset))
        self.animation.start()

        self.animationEnabled = True

    def onRightClicked(self, year, month):
        self.animationEnabled = False

        self.offset += days_of_month(year, month)

        self.animation.setStartValue(self.header.offset())
        self.animation.setEndValue(float(self.offset))
        self.animation.start()

        self.animationEnabled = True

    def onTodayClicked(self):
        self.animationEnabled = False

        today = datetime.date.today()
        self.offset = today.toordinal() - 7 - EPOCH_ORDINAL

        self.animation.setStartValue(self.header.offset())
        self.animation.setEndValue(float(self.offset))
        self.animation.start()

        self.animationEnabled = True

    def onDayRangeSelected(self, startOffset, endOffset):
        # Need a contact entry to create holiday entries.
        if not self.app.holidayModel.contactFromHandle():
            QMessageBox.warning(self, "Urlaubsplaner", u"Sie (%s) können keinen Urlaub eintragen, da Sie nicht in der Kontakttabelle verzeichnet sind." % getpass.getuser())
            return

        holiday = Holiday(self.app)
        holiday.start = datetime.date.fromordinal(startOffset + EPOCH_ORDINAL)
        holiday.end = datetime.date.fromordinal(endOffset + EPOCH_ORDINAL)
        holiday.contactId = self.app.holidayModel.contactFromHandle().id

        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def onHolidayClicked(self, holidayId):
        holiday = self.app.holidayModel.holidayCache[holidayId]
        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def onDayClicked(self, offset):
        self.onDayRangeSelected(offset, offset)

    def onCellClicked(self, day, index):
        # Need a contact entry to create holiday entries.
        ownContact = self.app.holidayModel.contactFromHandle()
        if not ownContact:
            QMessageBox.warning(self, "Urlaubsplaner", u"Sie (%s) können keinen Urlaub eintragen, da Sie nicht in der Kontakttabelle verzeichnet sind." % getpass.getuser())
            return

        # Get the relevant contact.
        contact = self.app.holidayModel.contactCache.values()[index]

        # Check write permissions.
        if ownContact.id != contact.id and contact.department not in ownContact.writableDepartments():
            QMessageBox.warning(self, "Urlaubsplaner", u"Sie (%s) haben keine Schreibrechte für die Abteilung von %s." % (ownContact.name, contact.name))
            return

        holiday = Holiday(self.app)
        holiday.start = datetime.date.fromordinal(day + EPOCH_ORDINAL)
        holiday.end = datetime.date.fromordinal(day + 7 + EPOCH_ORDINAL)
        holiday.contactId = contact.id

        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def resizeEvent(self, event):
        self.updateWidgetSizes()
        return super(CalendarPane, self).resizeEvent(event)

    def updateWidgetSizes(self):
        self.header.resize(self.width(), self.header.sizeHint().height())
        self.widget().resize(self.width(), max(self.widget().sizeHint().height(), self.height() - 80 - 5))

    def onAnimate(self, value):
        if not self.animationEnabled:
            return

        self.widget().setOffset(value)
        self.header.setOffset(value)
        self.widget().setOffset(value)

        self.widget().repaint()
        self.header.repaint()

    def eventFilter(self, watched, event):
        self.animationEnabled = False

        if event.type() == QEvent.KeyPress:
            date = datetime.date.fromordinal(self.offset + EPOCH_ORDINAL)

            if event.key() == Qt.Key_Right:
                self.offset += days_of_month(date.year, date.month)

                self.animation.setStartValue(self.header.offset())
                self.animation.setEndValue(float(self.offset))
                self.animation.start()
                return True
            elif event.key() == Qt.Key_Left:
                self.offset -= days_of_month(date.year - 1 if date.month == 1 else date.year, 12 if date.month == 1 else date.month - 1)

                self.animation.setStartValue(self.header.offset())
                self.animation.setEndValue(float(self.offset))
                self.animation.start()
                return True
            elif event.key() == Qt.Key_Home:
                self.onTodayClicked()
                return True

        self.animationEnabled = True

        return super(CalendarPane, self).eventFilter(watched, event)


class Application(QApplication):
    def initColors(self):
        self.white = QColor(255, 255, 255)
        self.lightRed = QColor(242, 219, 219, 150)
        self.orange = QColor(227, 108, 10)
        self.green = QColor(118, 146, 60)
        self.lightGreen = QColor(167, 185, 129)
        self.black = QColor(0, 0, 0)
        self.blue = QColor(54, 95, 145)
        self.yellow = QColor(255, 183, 0)
        self.purple = QColor(95, 73, 122)
        self.gray = QColor(191, 191, 191)

    def initResources(self):
        self.dateIcon = QIcon(os.path.join(os.path.dirname(__file__), "date.ico"))

        self.deleteIcon = QIcon(os.path.join(os.path.dirname(__file__), "bin_closed.png"))

    def initConfig(self):
        self.config = ConfigParser.ConfigParser()
        self.config.read(os.path.join(os.path.dirname(__file__), "config.ini"))

    def mysqlConnect(self):
        return mysql.connector.connect(
            user=self.config.get("MySQL", "User"),
            password=self.config.get("MySQL", "Password"),
            database=self.config.get("MySQL", "Database"),
            host=self.config.get("MySQL", "Host"))

    def initDb(self):
        self.db = self.mysqlConnect()

    def initMessageQueue(self):
        self.messageQueue = message_queue.MessageQueue(self.mysqlConnect())

    def initModel(self):
        self.holidayModel = HolidayModel(self)
        self.holidayModel.reloadContacts()
        self.holidayModel.reloadHolidays()


class Contact(object):
    def __init__(self, app):
        self.app = app

        self.id = None
        self.department = None
        self.name = None
        self.email = None
        self.handle = None

        self._writableDepartments = None

    def writableDepartments(self):
        if self._writableDepartments is not None:
            return self._writableDepartments

        departments = set()

        cursor = self.app.db.cursor()
        cursor.execute("SELECT department_id FROM department WHERE director = %(contact_id)s", {
            "contact_id": self.id,
        })
        for record in cursor:
            departments.add(int(record[0]))
        cursor.close()
        self.app.db.commit()

        self._writableDepartments = self.app.holidayModel.childDepartments(departments)
        return self._writableDepartments

    def numHolidays(self, year):
        days = set()
        firstHalfDays = set()
        secondHalfDays = set()

        for holiday in self.app.holidayModel.holidayCache.values():
            # Calculate for the current user only.
            if holiday.contactId != self.id:
                continue

            # Sum up only real holidays.
            if holiday.type != TYPE_HOLIDAY:
                continue

            # Skip holidays completely out of the current year.
            if holiday.end < datetime.date(year, 1, 1) or holiday.start > datetime.date(year, 12, 31):
                continue

            day = holiday.start
            while day <= holiday.end:
                # Days out of the current year do not count.
                if day.year != year:
                    day = day + datetime.timedelta(days=1)
                    continue

                # National holidays do not count.
                if is_holiday(day):
                    day = day + datetime.timedelta(days=1)
                    continue

                # Heiligabend and Silvester count only half a day.
                if day in (datetime.date(year, 12, 24), datetime.date(year, 12, 31)):
                    if day == holiday.start and holiday.startHalfDay:
                        pass
                    elif day == holiday.end and holiday.endHalfDay:
                        pass
                    else:
                        secondHalfDays.add(day)
                    day = day + datetime.timedelta(days=1)
                    continue

                # Count.
                if day == holiday.start and holiday.startHalfDay:
                    secondHalfDays.add(day)
                elif day == holiday.end and holiday.endHalfDay:
                    firstHalfDays.add(day)
                else:
                    days.add(day)

                day = day + datetime.timedelta(days=1)

        # Complete days cover half days.
        firstHalfDays.difference_update(days)
        secondHalfDays.difference_update(days)

        # Calculate sums.
        numHalfDays = len(firstHalfDays) + len(secondHalfDays)
        numDays = len(days) + numHalfDays // 2

        return numDays, numHalfDays % 2 == 1


TYPE_HOLIDAY = 0
TYPE_BUSINESS_TRIP = 1
TYPE_HEALTH = 2
TYPE_PLANNED = 3
TYPE_FLEXITIME = 4
TYPE_SPECIAL = 5

class Holiday(object):
    def __init__(self, app):
        self.app = app

        self.id = None
        self.contactId = None
        self.type = 0
        self.confirmed = False
        self.start = None
        self.startHalfDay = False
        self.end = None
        self.endHalfDay = False
        self.comment = ""

    def contact(self):
        return self.app.holidayModel.contactCache[self.contactId]


class HolidayModel(QObject):

    modelReset = Signal()

    def __init__(self, app):
        super(HolidayModel, self).__init__()
        self.app = app

        self.departmentId = None
        self.contactCache = indexed.IndexedOrderedDict()
        self.holidayCache = indexed.IndexedOrderedDict()

        self.app.messageQueue.received.connect(self.onMessageReceived)

    def childDepartments(self, departments):
        exhausted_departments = set()
        departments = set(departments)

        cursor = self.app.db.cursor()

        while departments:
            exhausted_departments.update(departments)
            cursor.execute("SELECT department_id FROM department WHERE location IN (" + ", ".join(str(id) for id in departments) + ")")
            for record in cursor:
                departments.add(int(record[0]))
            departments.difference_update(exhausted_departments)

        cursor.close()
        self.app.db.commit()

        return exhausted_departments

    def contactFromRecord(self, record):
        contact = Contact(self.app)
        contact.id = record[0]
        contact.department = record[1]
        contact.name = u"%s, %s" % (record[3], record[2])
        contact.email = record[4]
        contact.handle = record[5]
        return contact

    def reloadContacts(self, departmentId=None):
        self.contactCache.clear()

        cursor = self.app.db.cursor()
        cursor.execute("SELECT contact_id, department, firstname, name, email, login_id FROM contact WHERE login_id = %(login_id)s", {
            "login_id": getpass.getuser()
        })
        for record in cursor:
            self.contactCache[record[0]] = self.contactFromRecord(record)
        cursor.close()
        self.app.db.commit()

        if departmentId is not None:
            self.departmentId = departmentId

        if not self.departmentId:
            self.modelReset.emit()
            return

        departments = self.childDepartments([self.departmentId])
        if not departments:
            self.modelReset.emit()
            return

        cursor = self.app.db.cursor()
        cursor.execute("SELECT contact_id, department, firstname, name, email, login_id FROM contact WHERE department IN (" + ", ".join(str(id) for id in departments) + ") ORDER BY name ASC")
        for record in cursor:
            self.contactCache[record[0]] = self.contactFromRecord(record)

        cursor.close()
        self.app.db.commit()

        self.modelReset.emit()

    def reloadHolidays(self):
        self.holidayCache.clear()

        cursor = self.app.db.cursor()

        cursor.execute("SELECT id, contact_id, type, confirmed, start, start_half_day, end, end_half_day, comment FROM holiday")
        for record in cursor:
            holiday = Holiday(self.app)
            holiday.id = record[0]
            holiday.contactId = record[1]
            holiday.type = record[2]
            holiday.confirmed = record[3]
            holiday.start = record[4]
            holiday.startHalfDay = bool(record[5])
            holiday.end = record[6]
            holiday.endHalfDay = bool(record[7])
            holiday.comment = record[8]
            self.holidayCache[holiday.id] = holiday

        cursor.close()
        self.app.db.commit()

        self.modelReset.emit()

    def rowCount(self):
        return len(self.contactCache)

    def data(self, row):
        return self.contactCache.values()[row]

    def contactFromHandle(self, handle=getpass.getuser()):
        for contact in self.contactCache.viewvalues():
            if contact.handle == handle:
                return contact

    def save(self, holiday):
        record = {
            "contact_id": holiday.contactId,
            "type": holiday.type,
            "confirmed": holiday.confirmed,
            "start": holiday.start,
            "start_half_day": holiday.startHalfDay,
            "end": holiday.end,
            "end_half_day": holiday.endHalfDay,
            "comment": holiday.comment
        }

        cursor = self.app.db.cursor()

        if holiday.id:
            record["id"] = holiday.id
            cursor.execute("UPDATE holiday SET contact_id = %(contact_id)s, type = %(type)s, confirmed = %(confirmed)s, start = %(start)s, start_half_day = %(start_half_day)s, end = %(end)s, end_half_day = %(end_half_day)s, comment = %(comment)s WHERE id = %(id)s", record)

            self.app.messageQueue.publish("holiday", "update", holiday.id)
        else:
            cursor.execute("INSERT INTO holiday (contact_id, type, confirmed, start, start_half_day, end, end_half_day, comment) VALUES (%(contact_id)s, %(type)s, %(confirmed)s, %(start)s, %(start_half_day)s, %(end)s, %(end_half_day)s, %(comment)s)", record)
            holiday.id = cursor.lastrowid

            self.app.messageQueue.publish("holiday", "insert", holiday.id)

        cursor.close()
        self.app.db.commit()

        self.holidayCache[holiday.id] = holiday
        self.modelReset.emit()

    def delete(self, holidayId):
        del self.holidayCache[holidayId]

        cursor = self.app.db.cursor()
        cursor.execute("DELETE FROM holiday WHERE id = %(id)s", {
            "id": holidayId,
        })
        cursor.close()
        self.app.db.commit()

        self.app.messageQueue.publish("holiday", "delete", holidayId)

        self.modelReset.emit()

    def onMessageReceived(self, id, session, channel, message, extra):
        if channel == "holiday":
            self.reloadHolidays()


class KeyWidget(QWidget):
    def __init__(self, app):
        super(KeyWidget, self).__init__()
        self.app = app

    def drawRect(self, painter, x, brush):
        painter.setBrush(brush)
        painter.drawRect(x, (self.height() - 15) / 2, 20, 15)
        return x + 20 + 8

    def drawLabel(self, painter, x, text):
        metrics = QFontMetrics(painter.font())
        width = metrics.width(text)
        rect = QRect(x, (self.height() - metrics.height()) / 2, width, metrics.height())
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, text)
        return x + width + 12

    def drawKey(self, painter, x, brush, text):
        x = self.drawRect(painter, x, brush)
        x = self.drawLabel(painter, x, text)
        return x

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Urlaub (offen / genehmigt).
        x = self.drawKey(painter, 5, QBrush(self.app.green), "Urlaub")
        path = QPainterPath()
        path.moveTo(5, (self.height() - 15) / 2)
        path.lineTo(5 + 20, (self.height() - 15) / 2)
        path.lineTo(5, (self.height() - 15) / 2 + 15)
        path.lineTo(5, (self.height() - 15) / 2)
        painter.fillPath(path, QBrush(self.app.blue))

        # Weiter Urlaubstypen.
        x = self.drawKey(painter, x, QBrush(self.app.purple), "Dienstreise")
        x = self.drawKey(painter, x, QBrush(self.app.orange), "Krankheit")
        x = self.drawKey(painter, x, QBrush(self.app.gray), "Planung")
        x = self.drawKey(painter, x, QBrush(self.app.lightGreen), "Gleitzeit")
        x = self.drawKey(painter, x, QBrush(self.app.yellow), "Sonderurlaub")

        x += 40

        # Feiertage.
        self.drawRect(painter, x, QBrush(Qt.white))
        x = self.drawKey(painter, x, QBrush(self.app.lightRed), "Feiertag")

        # Schulferien.
        self.drawRect(painter, x, QBrush(Qt.white))
        x = self.drawKey(painter, x, QBrush(self.app.orange, Qt.BDiagPattern), "Schulferien Niedersachsen")

        painter.end()

    def sizeHint(self):
        return QSize(960, max(QFontMetrics(self.font()).height(), 15) + 5)


class MainWindow(QMainWindow):
    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.app = app

        centralWidget = QWidget()
        centralWidget.setContentsMargins(0, 0, 0, 0)
        vbox = QVBoxLayout(centralWidget)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(CalendarPane(self.app))
        vbox.addWidget(KeyWidget(self.app))

        self.setCentralWidget(centralWidget)
        self.setWindowIcon(self.app.dateIcon)
        self.setWindowTitle("Urlaubsplanung")

        self.initActions()
        self.initMenu()

        self.app.holidayModel.modelReset.connect(self.onHolidayModelReset)
        self.onHolidayModelReset()

    def initActions(self):
        self.reloadAction = QAction("Aktualisieren", self)
        self.reloadAction.setShortcut("F5")
        self.reloadAction.triggered.connect(self.onReloadAction)

        self.aboutAction = QAction(u"Über ...", self)
        self.aboutAction.setShortcut("F1")
        self.aboutAction.triggered.connect(self.onAboutAction)

        self.aboutQtAction = QAction(u"Über Qt ...", self)
        self.aboutQtAction.triggered.connect(self.onAboutQtAction)

        self.annualHolidaysAction = QAction("Jahresurlaub ...", self)
        self.annualHolidaysAction.triggered.connect(self.onAnnualHolidaysAction)

        self.createHolidayAction = QAction("Eintragen ...", self)
        self.createHolidayAction.setShortcut("Ctrl+N")
        self.createHolidayAction.triggered.connect(self.onCreateHolidayAction)

        # Load trail of departments.
        self.viewActionGroup = QActionGroup(self)
        self.viewActionGroup.setExclusive(True)

        contact = self.app.holidayModel.contactFromHandle()
        department = contact.department if contact else None

        cursor = self.app.db.cursor()
        while department:
            cursor.execute("SELECT name, location FROM department WHERE department_id = %(department_id)s", {
                "department_id": department,
            })

            record = cursor.fetchone()
            if not record:
                break

            action = self.viewActionGroup.addAction(record[0])
            action.triggered.connect(lambda id=department: self.app.holidayModel.reloadContacts(id))
            action.setCheckable(True)

            department = record[1]

        cursor.close()
        self.app.db.commit()

        if self.viewActionGroup.actions():
            self.viewActionGroup.actions()[0].trigger()

    def onHolidayModelReset(self):
        # Get the current user.
        contact = self.app.holidayModel.contactFromHandle()
        if not contact:
            self.setWindowTitle("Urlaubsplaner")
            return

        # Set the window title with the sum of holidays this year.
        year = datetime.date.today().year
        numDays, plusOneHalf = contact.numHolidays(year)
        if numDays == 0 and not plusOneHalf:
            self.setWindowTitle(u"Urlaubsplaner")
        elif numDays == 1:
            self.setWindowTitle(u"%s Tag Urlaub in %d" % (format_halves(numDays, plusOneHalf), year))
        else:
            self.setWindowTitle(u"%s Tage Urlaub in %d" % (format_halves(numDays, plusOneHalf), year))

    def onAboutAction(self):
        QMessageBox.about(self, self.windowTitle(),
            "<h1>Urlaubsplanung</h1>%s &lt;<a href=\"mailto:%s\">%s</a>&gt;" % (__author__, __email__, __email__))

    def onAboutQtAction(self):
        QMessageBox.aboutQt(self, self.windowTitle())

    def onAnnualHolidaysAction(self):
        contact = self.app.holidayModel.contactFromHandle()
        dialog = AnnualHolidaysDialog(self.app, contact, self)
        dialog.show()

    def onCreateHolidayAction(self):
        if not self.app.holidayModel.contactFromHandle():
            QMessageBox.warning(self, self.windowTitle(), u"Sie (%s) können keinen Urlaub eintragen, da Sie nicht in der Kontakttabelle verzeichnet sind." % getpass.getuser())
            return

        holiday = Holiday(self.app)
        holiday.start = datetime.date.today()
        holiday.end = datetime.date.today()
        holiday.contactId = self.app.holidayModel.contactFromHandle().id

        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def onReloadAction(self):
        self.app.holidayModel.reloadHolidays()

    def initMenu(self):
        mainMenu = self.menuBar().addMenu("Programm")
        mainMenu.addAction(self.reloadAction)
        mainMenu.addSeparator()
        mainMenu.addAction(self.aboutAction)
        mainMenu.addAction(self.aboutQtAction)

        holidaysMenu = self.menuBar().addMenu("Urlaub")
        holidaysMenu.addAction(self.annualHolidaysAction)
        holidaysMenu.addAction(self.createHolidayAction)

        viewMenu = self.menuBar().addMenu("Ansicht")
        for action in reversed(self.viewActionGroup.actions()):
            viewMenu.addAction(action)

    def sizeHint(self):
        return QSize(900, 600)


class AnnualHolidaysDialog(QDialog):
    def __init__(self, app, contact, parent=None):
        super(AnnualHolidaysDialog, self).__init__(parent)
        self.app = app
        self.app.holidayModel.modelReset.connect(self.onHolidayModelReset)
        self.contact = contact
        self.year = datetime.date.today().year

        self.initUi()
        self.initValues()

        self.setWindowTitle(u"Jahresurlaub / Übertrag")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def initUi(self):
        layout = QGridLayout(self)

        layout.addWidget(QLabel("%d:" % (self.year - 1)), 1, 0)
        self.numHolidaysPrevYearBox = QLabel("NaN")
        layout.addWidget(self.numHolidaysPrevYearBox, 1, 1)
        layout.addWidget(QLabel("von"), 1, 2)
        layout.addWidget(QLabel("unbekannt"), 1, 3)

        layout.addWidget(QLabel("%d:" % self.year), 2, 0)
        self.numHolidaysBox = QLabel("NaN")
        layout.addWidget(self.numHolidaysBox, 2, 1)
        layout.addWidget(QLabel("von"), 2, 2)
        layout.addWidget(QLabel("unbekannt"), 2, 3)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.onAccept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, 3, 0, 1, 4)

    def onHolidayModelReset(self):
        self.numHolidaysPrevYearBox.setText(format_halves(self.contact.numHolidays(self.year - 1)))
        self.numHolidaysBox.setText(format_halves(self.contact.numHolidays(self.year)))

    def initValues(self):
        self.onHolidayModelReset()

    def onAccept(self):
        pass


class HolidayDialog(QDialog):
    def __init__(self, app, holiday, parent=None):
        super(HolidayDialog, self).__init__(parent)
        self.app = app
        self.holiday = holiday

        # Check write permissions.
        self.writable = False
        ownContact = self.app.holidayModel.contactFromHandle()
        if ownContact:
            if holiday.contactId == ownContact.id:
                self.writable = True
            elif holiday.contact().department in ownContact.writableDepartments():
                self.writable = True

        self.initUi()
        self.initValues()
        self.onEndHalfDayBoxStatusMightHaveToChange()

        self.setWindowIcon(self.app.dateIcon)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

    def initUi(self):
        layout = QGridLayout(self)

        layout.addWidget(QLabel("Person:"), 0, 0)
        self.contactBox = QLabel()
        self.contactBox.setTextFormat(Qt.RichText)
        self.contactBox.setOpenExternalLinks(True)
        layout.addWidget(self.contactBox, 0, 1)

        layout.addWidget(QLabel("Beginn:"), 1, 0, Qt.AlignLeft)
        hbox = QHBoxLayout()
        self.startBox = QDateEdit()
        self.startBox.setEnabled(self.writable)
        self.startBox.dateChanged.connect(self.onStartDateChanged)
        self.startBox.dateChanged.connect(self.onEndHalfDayBoxStatusMightHaveToChange)
        hbox.addWidget(self.startBox)
        self.startHalfDayBox = QCheckBox("halber Tag")
        self.startHalfDayBox.setEnabled(self.writable)
        self.startHalfDayBox.clicked.connect(self.onEndHalfDayBoxStatusMightHaveToChange)
        hbox.addWidget(self.startHalfDayBox)
        layout.addLayout(hbox, 1, 1)

        layout.addWidget(QLabel("Ende:"), 2, 0, Qt.AlignLeft)
        hbox = QHBoxLayout()
        self.endBox = QDateEdit()
        self.endBox.setEnabled(self.writable)
        self.endBox.dateChanged.connect(self.onEndHalfDayBoxStatusMightHaveToChange)
        hbox.addWidget(self.endBox)
        self.endHalfDayBox = QCheckBox("halber Tag")
        hbox.addWidget(self.endHalfDayBox)
        layout.addLayout(hbox, 2, 1)

        layout.addWidget(QLabel("Kommentar:"), 3, 0, Qt.AlignTop)
        self.commentBox = QTextEdit()
        self.commentBox.setEnabled(self.writable)
        layout.addWidget(self.commentBox, 3, 1)

        layout.addWidget(QLabel("Typ:"), 4, 0)
        self.typeBox = TypeComboBox(self.app)
        self.typeBox.currentIndexChanged.connect(self.onTypeChanged)
        self.typeBox.setEnabled(self.writable)
        layout.addWidget(self.typeBox, 4, 1)
        self.confirmedBox = QCheckBox("Genehmigt")
        self.confirmedBox.setEnabled(self.writable)
        layout.addWidget(self.confirmedBox, 5, 1)

        hbox = QHBoxLayout()
        self.deleteButton = QPushButton(self.app.deleteIcon, u"Löschen")
        self.deleteButton.setEnabled(self.writable)
        self.deleteButton.clicked.connect(self.onDeleteClicked)
        self.deleteButton.setAutoDefault(False)
        hbox.addWidget(self.deleteButton, 0)
        hbox.addSpacing(1)
        self.cancelButton = QPushButton("Abbrechen")
        self.cancelButton.clicked.connect(self.reject)
        self.cancelButton.setAutoDefault(False)
        hbox.addWidget(self.cancelButton, 0)
        self.saveButton = QPushButton("Speichern")
        self.saveButton.clicked.connect(self.onAccept)
        hbox.addWidget(self.saveButton, 0)
        layout.addLayout(hbox, 6, 0, 1, 2)

    def onStartDateChanged(self, date):
        self.endBox.setMinimumDate(date)

    def onEndHalfDayBoxStatusMightHaveToChange(self):
        if self.startHalfDayBox.isChecked() and self.startBox.date() == self.endBox.date():
            self.endHalfDayBox.setChecked(False)
            self.endHalfDayBox.setEnabled(False)
        else:
            self.endHalfDayBox.setEnabled(self.writable)

    def onTypeChanged(self, index):
        if self.typeBox.type() == TYPE_HEALTH:
            self.confirmedBox.setChecked(True)
            self.confirmedBox.setEnabled(False)
        else:
            self.confirmedBox.setEnabled(self.writable)

    def initValues(self):
        contact = self.holiday.contact()
        if contact.email:
            self.contactBox.setText("<a href=\"mailto:%s\">%s &lt;%s&gt;</a>" %
                    (contact.email, contact.name, contact.email))
        else:
            self.contactBox.setText(contact.name)

        if not self.holiday.id:
            self.setWindowTitle("Urlaub eintragen")
        else:
            self.setWindowTitle("Urlaub: %s vom %s bis zum %s" % (
                 contact.name,
                 self.holiday.start.strftime("%d.%m.%Y"),
                 self.holiday.end.strftime("%d.%m.")))

        self.startBox.setDate(qdate(self.holiday.start))
        self.startHalfDayBox.setChecked(self.holiday.startHalfDay)
        self.endBox.setDate(qdate(self.holiday.end))
        self.endHalfDayBox.setChecked(self.holiday.endHalfDay)

        self.commentBox.setText(self.holiday.comment)

        self.typeBox.setType(self.holiday.type)
        self.confirmedBox.setChecked(self.holiday.confirmed)

    def onAccept(self):
        if not self.writable:
            self.accept()
            return

        self.holiday.start = pydate(self.startBox.date())
        self.holiday.startHalfDay = self.startHalfDayBox.isChecked()
        self.holiday.end = pydate(self.endBox.date())
        self.holiday.endHalfDay = self.endHalfDayBox.isChecked()
        self.holiday.comment = self.commentBox.toPlainText()
        self.holiday.type = self.typeBox.type()
        self.holiday.confirmed = self.confirmedBox.isChecked()
        self.app.holidayModel.save(self.holiday)
        self.accept()

    def onDeleteClicked(self):
        if not self.writable:
            self.reject()
            return

        if self.holiday.id:
            if QMessageBox.Yes == QMessageBox.question(self, self.windowTitle(),
                                                       u"Diesen Kalendereintrag wirklich löschen?",
                                                       QMessageBox.Yes | QMessageBox.No):
                self.app.holidayModel.delete(self.holiday.id)
                self.reject()
        else:
            self.reject()


class TypeComboBox(QComboBox):
    def __init__(self, app, parent=None):
        super(TypeComboBox, self).__init__(parent)
        self.app = app

        self.addItem("Urlaub", TYPE_HOLIDAY)
        self.addItem("Dienstreise", TYPE_BUSINESS_TRIP)
        self.addItem("Krankheit", TYPE_HEALTH)
        self.addItem("Planung", TYPE_PLANNED)
        self.addItem("Gleitzeit", TYPE_FLEXITIME)
        self.addItem("Sonderurlaub", TYPE_SPECIAL)

        for row, color in enumerate([self.app.green, self.app.purple, self.app.orange, self.app.gray, self.app.lightGreen, self.app.yellow]):
            index = self.model().index(row, 0)
            self.model().setData(index, color, Qt.BackgroundRole)
            self.model().setData(index, contrasting_color(color), Qt.ForegroundRole)

    def type(self):
        if self.currentIndex() == 0:
            return TYPE_HOLIDAY
        elif self.currentIndex() == 1:
            return TYPE_BUSINESS_TRIP
        elif self.currentIndex() == 2:
            return TYPE_HEALTH
        elif self.currentIndex() == 3:
            return TYPE_PLANNED
        elif self.currentIndex() == 4:
            return TYPE_FLEXITIME
        elif self.currentIndex() == 5:
            return TYPE_SPECIAL

    def setType(self, type):
        if type == TYPE_HOLIDAY:
            self.setCurrentIndex(0)
        elif type == TYPE_BUSINESS_TRIP:
            self.setCurrentIndex(1)
        elif type == TYPE_HEALTH:
            self.setCurrentIndex(2)
        elif type == TYPE_PLANNED:
            self.setCurrentIndex(3)
        elif type == TYPE_FLEXITIME:
            self.setCurrentIndex(4)
        elif type == TYPE_SPECIAL:
            self.setCurrentIndex(5)
        else:
            self.setCurrentIndex(-1)


if __name__ == "__main__":
    app = Application(sys.argv)
    app.initColors()
    app.initConfig()
    app.initResources()
    app.initDb()
    app.initMessageQueue()
    app.initModel()

    window = MainWindow(app)
    window.show()

    app.exec_()
