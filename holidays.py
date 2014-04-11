#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

__author__ = "Niklas Fiekas"

__email__ = "niklas.fiekas@tu-clausthal.de"

import indexed

import ConfigParser
import mysql.connector
import sys
import math
import datetime
import calendar
import os
import getpass

from PySide.QtCore import *
from PySide.QtGui import *

EPOCH_ORDINAL = 719163

MONTH_NAMES = ["Dezember", "Januar", "Februar", u"März", "April", "Mai", "Juni",
               "Juli", "August", "September", "November", "Oktober", "Dezember"]


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
    elif date.addDays(-49) == easter:
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
        return min(self.width() / 30.0, 25.0)

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
        opt.textAlignment = Qt.AlignCenter

        for xStart, date in self.visibleDays():
            xEnd = xStart + self.columnWidth()

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


class CalendarBody(CalendarStrip):

    holidayClicked = Signal(int)

    dayClicked = Signal(int)

    def __init__(self, app, parent=None):
        super(CalendarBody, self).__init__(parent)
        self.app = app
        self.setMouseTracking(True)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.onCustomContextMenuRequested)

        self.mousePos = None
        self.mousePressPos = None

        self.app.holidayModel.modelReset.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)

        # Fill background.
        painter.fillRect(self.rect(), QBrush(self.app.white))

        # Paint rows.
        painter.setPen(QPen(self.app.gray))
        for i in xrange(self.app.holidayModel.rowCount()):
            painter.drawLine(0, (15 + 25 + 15) * i + 15,
                self.width(), (15 + 25 + 15) * i + 15)
            painter.drawLine(0, (15 + 25 + 15) * i + 15 + 25,
                self.width(), (15 + 25 + 15) * i + 15 + 25)

        for x, date in self.visibleDays():
            rect = QRect(x, 0, self.columnWidth(), self.height())

            # Paint columns.
            if date.day == 1:
                painter.setPen(QPen())
            else:
                painter.setPen(QPen(self.app.gray))
            painter.drawLine(x, 0, x, self.height())

            # Highlight national holidays.
            if is_holiday(date):
                painter.fillRect(rect, QBrush(self.app.lightRed))

            # Gray out the past.
            if date < datetime.date.today():
                painter.fillRect(rect, QBrush(Qt.Dense7Pattern))

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

            if self.mousePos and rect.contains(self.mousePos):
                if self.mousePressPos:
                    painter.setBrush(QBrush(color.lighter(90)))
                else:
                    painter.setBrush(QBrush(color.lighter(110)))
            else:
                painter.setBrush(QBrush(color))
            painter.drawRect(rect)

        # Draw names.
        for x, date in self.visibleDays():
            if date.day == 1:
                for i, contact in enumerate(self.app.holidayModel.contactCache.values()):
                    painter.drawText(QRect(x + 10, (15 + 25 + 15) * i + 15, self.columnWidth() * 20 - 10, 25), Qt.AlignVCenter, contact.name)

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
        self.mousePressPos = None

        if event.button() == Qt.LeftButton:
            self.update()

            for holiday, rect in self.visibleHolidays():
                if rect.contains(event.pos()):
                    self.holidayClicked.emit(holiday.id)

    def mouseDoubleClickEvent(self, event):
        for holiday, rect in self.visibleHolidays():
            if rect.contains(event.pos()):
                return

        self.onDayClicked(event.pos())

    def onDayClicked(self, pos):
        self.dayClicked.emit(int(self.offset() + pos.x() / self.columnWidth()))

    def onCustomContextMenuRequested(self, pos):
        contextMenu = QMenu()

        contextMenu.addAction(u"Eintragen", lambda: self.onDayClicked(pos))
        contextMenu.addSeparator()

        for holiday, rect in self.visibleHolidays():
            if rect.contains(pos):
                contextMenu.addAction("Bearbeiten (%d)" % holiday.id, lambda: self.holidayClicked.emit(holiday.id))

        contextMenu.exec_(self.mapToGlobal(pos))

    def visibleHolidays(self):
        for holiday in self.app.holidayModel.holidayCache.values():
            try:
                y = self.app.holidayModel.contactCache.keys().index(holiday.contactId) * (15 + 25 + 15) + 15
            except KeyError:
                continue

            startX = (holiday.start.toordinal() - EPOCH_ORDINAL - self.offset()) * self.columnWidth()
            endX = (holiday.end.toordinal() + 1 - EPOCH_ORDINAL - self.offset()) * self.columnWidth()
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

        today = datetime.date.today()
        self.offset = datetime.date(today.year, today.month, 1).toordinal() - EPOCH_ORDINAL

        self.header = CalendarHeader(self)
        self.header.leftClicked.connect(self.onLeftClicked)
        self.header.todayClicked.connect(self.onTodayClicked)
        self.header.rightClicked.connect(self.onRightClicked)
        self.header.setOffset(self.offset)

        self.setWidget(CalendarBody(app, self))
        self.widget().setOffset(self.offset)
        self.widget().holidayClicked.connect(self.onHolidayClicked)
        self.widget().dayClicked.connect(self.onDayClicked)

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
        self.offset = datetime.date(today.year, today.month, 1).toordinal() - EPOCH_ORDINAL

        self.animation.setStartValue(self.header.offset())
        self.animation.setEndValue(float(self.offset))
        self.animation.start()

        self.animationEnabled = True

    def onHolidayClicked(self, holidayId):
        holiday = self.app.holidayModel.holidayCache[holidayId]
        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def onDayClicked(self, offset):
        if not self.app.holidayModel.contactFromHandle():
            QMessageBox.warning(self, "Urlaubsplaner", u"Sie (%s) können keinen Urlaub eintragen, da Sie nicht in der Kontakttabelle verzeichnet sind." % getpass.getuser())
            return

        holiday = Holiday(self.app)
        holiday.start = datetime.date.fromordinal(offset + EPOCH_ORDINAL)
        holiday.end = datetime.date.fromordinal(offset + EPOCH_ORDINAL + 7)
        holiday.contactId = self.app.holidayModel.contactFromHandle().id

        dialog = HolidayDialog(self.app, holiday, self)
        dialog.show()

    def resizeEvent(self, event):
        self.updateWidgetSizes()

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

        self.animationEnabled = True

        return super(CalendarPane, self).eventFilter(watched, event)


class Application(QApplication):
    def initColors(self):
        self.white = QColor(255, 255, 255)
        self.lightRed = QColor(242, 219, 219, 100)
        self.orange = QColor(227, 108, 10)
        self.green = QColor(118, 146, 60)
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

    def initDb(self):
        self.db = mysql.connector.connect(
            user=self.config.get("MySQL", "User"),
            password=self.config.get("MySQL", "Password"),
            database=self.config.get("MySQL", "Database"),
            host=self.config.get("MySQL", "Host"),
            autocommit=True)

    def initModel(self):
        self.holidayModel = HolidayModel(self)
        self.holidayModel.reload()


class Contact(object):
    def __init__(self, app):
        self.app = app

        self.id = None
        self.name = None
        self.email = None
        self.handle = None


TYPE_HOLIDAY = 0
TYPE_BUSINESS_TRIP = 1
TYPE_HEALTH = 2

class Holiday(object):
    def __init__(self, app):
        self.app = app

        self.id = None
        self.contactId = None
        self.type = 0
        self.confirmed = False
        self.start = None
        self.end = None
        self.comment = ""

    def contact(self):
        return self.app.holidayModel.contactCache[self.contactId]


class HolidayModel(QObject):

    modelReset = Signal()

    def __init__(self, app):
        super(HolidayModel, self).__init__()
        self.app = app

        self.contactCache = indexed.IndexedOrderedDict()
        self.holidayCache = indexed.IndexedOrderedDict()

    def reload(self):
        self.contactCache.clear()
        self.holidayCache.clear()

        cursor = self.app.db.cursor()
        cursor.execute("SELECT contact_id, firstname, name, email, login_id FROM contact WHERE department = 18 OR login_id = '10179939' ORDER BY name ASC")
        for record in cursor:
            contact = Contact(self.app)
            contact.id = record[0]
            contact.name = "%s, %s" % (record[2], record[1])
            contact.email = record[3]
            contact.handle = record[4]
            self.contactCache[contact.id] = contact

        cursor.execute("SELECT id, contact_id, type, confirmed, start, end, comment FROM holiday")
        for record in cursor:
            holiday = Holiday(self.app)
            holiday.id = record[0]
            holiday.contactId = record[1]
            holiday.type = record[2]
            holiday.confirmed = record[3]
            holiday.start = record[4]
            holiday.end = record[5]
            holiday.comment = record[6]
            self.holidayCache[holiday.id] = holiday

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
            "end": holiday.end,
            "comment": holiday.comment
        }

        cursor = self.app.db.cursor()

        if holiday.id:
            record["id"] = holiday.id
            cursor.execute("UPDATE holiday SET contact_id = %(contact_id)s, type = %(type)s, confirmed = %(confirmed)s, start = %(start)s, end = %(end)s, comment = %(comment)s WHERE id = %(id)s", record)
        else:
            cursor.execute("INSERT INTO holiday (contact_id, type, confirmed, start, end, comment) VALUES (%(contact_id)s, %(type)s, %(confirmed)s, %(start)s, %(end)s, %(comment)s)", record)
            holiday.id = cursor.lastrowid
            self.holidayCache[holiday.id] = holiday

        self.modelReset.emit()

    def delete(self, holidayId):
        del self.holidayCache[holidayId]

        cursor = self.app.db.cursor()
        cursor.execute("DELETE FROM holiday WHERE id = %(id)s", {
            "id": holidayId,
        })

        self.modelReset.emit()


class MainWindow(QMainWindow):
    def __init__(self, app):
        super(MainWindow, self).__init__()
        self.app = app

        self.setCentralWidget(CalendarPane(self.app))
        self.setWindowIcon(self.app.dateIcon)
        self.setWindowTitle("Urlaubsplanung")

        self.initActions()
        self.initMenu()

    def initActions(self):
        self.reloadAction = QAction("Aktualisieren", self)
        self.reloadAction.setShortcut("F5")
        self.reloadAction.triggered.connect(self.onReloadAction)

        self.aboutAction = QAction(u"Über ...", self)
        self.aboutAction.setShortcut("F1")
        self.aboutAction.triggered.connect(self.onAboutAction)

        self.aboutQtAction =  QAction(u"Über Qt ...", self)
        self.aboutQtAction.triggered.connect(self.onAboutQtAction)

        self.createHolidayAction = QAction("Neu", self)
        self.createHolidayAction.setShortcut("Ctrl+N")
        self.createHolidayAction.triggered.connect(self.onCreateHolidayAction)

    def onAboutAction(self):
        QMessageBox.about(self, self.windowTitle(),
            "<h1>Urlaubsplanung</h1>%s &lt;<a href=\"mailto:%s\">%s</a>&gt;" % (__author__, __email__, __email__))

    def onAboutQtAction(self):
        QMessageBox.aboutQt(self, self.windowTitle())

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
        self.app.holidayModel.reload()

    def initMenu(self):
        mainMenu = self.menuBar().addMenu("Programm")
        mainMenu.addAction(self.reloadAction)
        mainMenu.addSeparator()
        mainMenu.addAction(self.aboutAction)
        mainMenu.addAction(self.aboutQtAction)

        holidaysMenu = self.menuBar().addMenu("Urlaube")
        holidaysMenu.addAction(self.createHolidayAction)

    def sizeHint(self):
        return QSize(900, 600)


class HolidayDialog(QDialog):
    def __init__(self, app, holiday, parent=None):
        super(HolidayDialog, self).__init__(parent)
        self.app = app
        self.holiday = holiday

        self.initUi()
        self.initValues()

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
        self.startBox = QDateEdit()
        self.startBox.dateChanged.connect(self.onStartDateChanged)
        layout.addWidget(self.startBox, 1, 1)
        
        layout.addWidget(QLabel("Ende:"), 2, 0, Qt.AlignLeft)
        self.endBox = QDateEdit()
        layout.addWidget(self.endBox, 2, 1)
        
        layout.addWidget(QLabel("Kommentar:"), 3, 0, Qt.AlignTop)
        self.commentBox = QTextEdit()
        layout.addWidget(self.commentBox, 3, 1)
        
        layout.addWidget(QLabel("Typ:"), 4, 0)
        self.typeBox = TypeComboBox(self.app)
        self.typeBox.currentIndexChanged.connect(self.onTypeChanged)
        layout.addWidget(self.typeBox, 4, 1)
        self.confirmedBox = QCheckBox("Genehmigt")
        layout.addWidget(self.confirmedBox, 5, 1)

        hbox = QHBoxLayout()
        self.deleteButton = QPushButton(self.app.deleteIcon, u"Löschen")
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

    def onTypeChanged(self, index):
        if self.typeBox.type() == TYPE_HEALTH:
            self.confirmedBox.setChecked(True)
            self.confirmedBox.setEnabled(False)
        else:
            self.confirmedBox.setEnabled(True)

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
        self.endBox.setDate(qdate(self.holiday.end))

        self.commentBox.setText(self.holiday.comment)

        self.typeBox.setType(self.holiday.type)
        self.confirmedBox.setChecked(self.holiday.confirmed)

    def onAccept(self):
        self.holiday.start = pydate(self.startBox.date())
        self.holiday.end = pydate(self.endBox.date())
        self.holiday.comment = self.commentBox.toPlainText()
        self.holiday.type = self.typeBox.type()
        self.holiday.confirmed = self.confirmedBox.isChecked()
        self.app.holidayModel.save(self.holiday)
        self.accept()

    def onDeleteClicked(self):
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

        for row, color in enumerate([self.app.green, self.app.purple, self.app.orange]):
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

    def setType(self, type):
        if type == TYPE_HOLIDAY:
            self.setCurrentIndex(0)
        elif type == TYPE_BUSINESS_TRIP:
            self.setCurrentIndex(1)
        elif type == TYPE_HEALTH:
            self.setCurrentIndex(2)
        else:
            self.setCurrentIndex(-1)


if __name__ == "__main__":
    app = Application(sys.argv)
    app.initColors()
    app.initConfig()
    app.initResources()
    app.initDb()
    app.initModel()

    window = MainWindow(app)
    window.show()

    app.exec_()
