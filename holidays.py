#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

import sys
import math
import datetime
import calendar
import os

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

def days_of_month(year, month):
    return calendar.monthrange(year, month)[1]

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
    def __init__(self, parent=None):
        super(CalendarBody, self).__init__(parent)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QBrush(QColor(255, 255, 255)))

        for x, date in self.visibleDays():
            if date.day == 1:
                painter.setPen(QPen())
            else:
                painter.setPen(QPen(QColor(200, 200, 200)))

            painter.drawLine(x, 0, x, self.height())

        painter.end()

    def sizeHint(self):
        return QSize(40 * 25, 1000)

class VariantAnimation(QVariantAnimation):
    def updateCurrentValue(self, value):
        pass

class CalendarPane(QScrollArea):
    def __init__(self, parent=None):
        super(CalendarPane, self).__init__(parent)
        self.setViewportMargins(0, 80, 0, 0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        today = datetime.date.today()
        self.offset = datetime.date(today.year, today.month, 1).toordinal() - EPOCH_ORDINAL

        self.header = CalendarHeader(self)
        self.header.leftClicked.connect(self.onLeftClicked)
        self.header.todayClicked.connect(self.onTodayClicked)
        self.header.rightClicked.connect(self.onRightClicked)
        self.header.setOffset(self.offset)

        self.setWidget(CalendarBody(self))
        self.widget().setOffset(self.offset)

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

    def resizeEvent(self, event):
        self.header.resize(self.width(), self.header.sizeHint().height())
        self.widget().resize(self.width(), max(self.widget().sizeHint().height(), self.height()))

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

if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = CalendarPane()
    w.show()

    app.exec_()
