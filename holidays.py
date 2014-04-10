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

class CalendarStrip(QWidget):
    def __init__(self, parent=None):
        super(CalendarStrip, self).__init__(parent)
        
        self._offset = 0

    def columnWidth(self):
        return min(self.width() / 30.0, 20.0)

    def offset(self):
        return self._offset

    def setOffset(self, offset):
        self._offset = offset

    def visibleDays(self):
        return range(
            int(self._offset - max([33])),
            int(self._offset + self.width() / self.columnWidth() + 1))

    def sizeHint(self):
        return QSize(40 * 20, 80)

class CalendarHeader(CalendarStrip):
    def __init__(self, parent=None):
        super(CalendarHeader, self).__init__(parent)

        self.leftPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_previous.png"))
        self.todayPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date.png"))
        self.rightPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_next.png"))

    def paintEvent(self, event):
        painter = QPainter(self)
        
        opt = QStyleOptionHeader()
        opt.textAlignment = Qt.AlignCenter
        
        for day in self.visibleDays():
            date = datetime.date.fromordinal(day + EPOCH_ORDINAL)
            xStart = (day - self.offset()) * self.columnWidth()
            xEnd = (day - self.offset() + 1) * self.columnWidth()
            
            if day % 7 == 4:
                opt.rect = QRect(xStart, 40, self.columnWidth() * 7, 20)
                opt.text = str("Woche %d" % (date.timetuple().tm_yday / 7 + 1))
                painter.save()
                self.style().drawControl(QStyle.CE_Header, opt, painter, self)
                painter.restore()

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
                
                painter.drawPixmap(QRect(xStart + 32, (40 - 16) / 2, 16, 16), self.leftPixmap, QRect(0, 0, 16, 16))
                
                painter.drawPixmap(QRect(xStart + 64, (40 - 16) / 2, 16, 16), self.todayPixmap, QRect(0, 0, 16, 16))
                
                painter.drawPixmap(QRect(xStart + 96, (40 - 16) / 2, 16, 16), self.rightPixmap, QRect(0, 0, 16, 16))
                
                painter.drawText(QRect(xStart + 128, 0, self.columnWidth() * daysOfMonth[1] - 64 - 128, 40),
                    Qt.AlignVCenter, "%s %d" % (MONTH_NAMES[date.month], date.year))
                painter.restore()
            
            opt.rect = QRect(xStart, 60, self.columnWidth(), 20)
            opt.text = str(date.day)
            painter.save()
            self.style().drawControl(QStyle.CE_Header, opt, painter, self)
            painter.restore()

        painter.end()


class VariantAnimation(QVariantAnimation):
    def updateCurrentValue(self, value):
        pass

class CalendarPane(QScrollArea):
    def __init__(self, parent=None):
        super(CalendarPane, self).__init__(parent)
        self.setViewportMargins(0, 80, 0, 0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWidget(FancyWidget(Qt.DiagCrossPattern, QSize(1000, 40), self))

        self.header = CalendarHeader(self)

        self.animation = VariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.InOutQuad))
        self.animation.valueChanged.connect(self.onAnimate)
        self.animation.setDuration(1000)
        self.installEventFilter(self)

        self.flag = False

    def onAnimate(self, value):
        if not self.flag:
            print "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            return
        print value
        self.widget().setOffset(value)
        self.header.setOffset(value)
        self.header.repaint()

    def eventFilter(self, watched, event):
        self.flag = False
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Right:
                self.animation.setStartValue(self.widget().offset())
                self.animation.setEndValue(self.widget().offset() + 30)
                self.animation.start()
            elif event.key() == Qt.Key_Left:
                self.animation.setStartValue(self.widget().offset())
                self.animation.setEndValue(self.widget().offset() - 30)
                self.animation.start()
        self.flag = True

        return super(CalendarPane, self).eventFilter(watched, event)

class FancyWidget(QWidget):
    def __init__(self, style, size, parent=None):
        super(FancyWidget, self).__init__(parent)
        self.style = style
        self.dim = size

        self._offset = 0.0

    def setOffset(self, offset):
        self._offset = offset
        self.repaint()

    def offset(self):
        return self._offset

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QBrush(QColor(255, 255, 255)))
        painter.end()

    def sizeHint(self):
        return self.dim


if __name__ == "__main__":
    app = QApplication(sys.argv)

    w = CalendarPane()
    w.show()

    app.exec_()