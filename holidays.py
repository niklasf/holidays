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
        start = int(self._offset - max([33]))
        end = int(self._offset + self.width() / self.columnWidth() + 1)

        for day in xrange(start, end):
            x = (day - self._offset) * self.columnWidth()
            yield x, datetime.date.fromordinal(day + EPOCH_ORDINAL)

    def sizeHint(self):
        return QSize(40 * 20, 80)

class CalendarHeader(CalendarStrip):

    leftClicked = Signal()

    rightClicked = Signal()

    def __init__(self, parent=None):
        super(CalendarHeader, self).__init__(parent)
        self.setMouseTracking(True)

        # Button state info.
        self.mousePos = None
        self.leftActive = False
        self.rightActive = False

        # Left button pixmaps.
        self.leftPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_previous.png"))
        self.lighterLeftPixmap = map_pixel(self.leftPixmap, lighter)
        self.darkerLeftPixmap = map_pixel(self.leftPixmap, darker)

        self.todayPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date.png"))

        # Right button pixmaps.
        self.rightPixmap = QPixmap(os.path.join(os.path.dirname(__file__), "date_next.png"))
        self.lighterRightPixmap = map_pixel(self.rightPixmap, lighter)
        self.darkerRightPixmap = map_pixel(self.rightPixmap, darker)

    def visibleLeftButtons(self):
        for x, date in self.visibleDays():
            if date.day == 1:
                yield QRect(x + 32, (40 - 32) / 2, 32, 32)

    def visibleRightButtons(self):
        for x, date in self.visibleDays():
            if date.day == 1:
                yield QRect(x + 96, (40 - 32) / 2, 32, 32)

    def updateButtons(self):
        for rect in self.visibleLeftButtons():
            self.update(rect)
        for rect in self.visibleRightButtons():
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

        for rect in self.visibleLeftButtons():
            if rect.contains(event.pos()):
                self.leftActive = True
                self.update(rect)

        for rect in self.visibleRightButtons():
            if rect.contains(event.pos()):
                self.rightActive = True
                self.update(rect)

    def mouseReleaseEvent(self, event):
        self.mousePos = event.pos()

        # Trigger left clicked signal.
        for rect in self.visibleLeftButtons():
            if rect.contains(event.pos()):
                self.leftClicked.emit()
                self.update(rect)

        # Trigger right clicked signal.
        for rect in self.visibleRightButtons():
            if rect.contains(event.pos()):
                self.rightClicked.emit()
                self.update(rect)

        self.leftActive = False
        self.rightActive = False

    def paintEvent(self, event):
        painter = QPainter(self)
        
        opt = QStyleOptionHeader()
        opt.textAlignment = Qt.AlignCenter
        
        for xStart, date in self.visibleDays():
            xEnd = xStart + self.columnWidth()
            
            if date.toordinal() % 7 == 4:
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
                
                painter.drawPixmap(QRect(xStart + 64, (40 - 16) / 2, 16, 16), self.todayPixmap, QRect(0, 0, 16, 16))
                
                painter.drawText(QRect(xStart + 128, 0, self.columnWidth() * daysOfMonth[1] - 64 - 128, 40),
                    Qt.AlignVCenter, "%s %d" % (MONTH_NAMES[date.month], date.year))
                painter.restore()
            
            opt.rect = QRect(xStart, 60, self.columnWidth(), 20)
            opt.text = str(date.day)
            painter.save()
            self.style().drawControl(QStyle.CE_Header, opt, painter, self)
            painter.restore()

        # Draw go left buttons.
        for rect in self.visibleLeftButtons():
            pixmapRect = QRect(rect.x() + (rect.width() - 16) / 2, rect.y() + (rect.height() - 16) / 2, 16, 16)
            if self.mousePos and rect.contains(self.mousePos):
                if self.leftActive:
                    painter.drawPixmap(pixmapRect, self.darkerLeftPixmap, QRect(0, 0, 16, 16))
                else:
                    painter.drawPixmap(pixmapRect, self.lighterLeftPixmap, QRect(0, 0, 16, 16))
            else:
                painter.drawPixmap(pixmapRect, self.leftPixmap, QRect(0, 0, 16, 16))

        # Draw go right buttons.
        for rect in self.visibleRightButtons():
            pixmapRect = QRect(rect.x() + (rect.width() - 16) / 2, rect.y() + (rect.height() - 16) / 2, 16, 16)
            if self.mousePos and rect.contains(self.mousePos):
                if self.rightActive:
                    painter.drawPixmap(pixmapRect, self.darkerRightPixmap, QRect(0, 0, 16, 16))
                else:
                    painter.drawPixmap(pixmapRect, self.lighterRightPixmap, QRect(0, 0, 16, 16))
            else:
                painter.drawPixmap(pixmapRect, self.rightPixmap, QRect(0, 0, 16, 16))

        painter.end()


class VariantAnimation(QVariantAnimation):
    def updateCurrentValue(self, value):
        pass

class CalendarPane(QScrollArea):
    def __init__(self, parent=None):
        super(CalendarPane, self).__init__(parent)
        self.setViewportMargins(0, 80, 0, 0)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.setWidgetResizable(True)
        self.setWidget(FancyWidget(Qt.DiagCrossPattern, QSize(1000, 40), self))
        

        self.header = CalendarHeader(self)
        self.header.leftClicked.connect(self.onLeftClicked)
        self.header.rightClicked.connect(self.onRightClicked)

        self.animation = VariantAnimation(self)
        self.animation.setEasingCurve(QEasingCurve(QEasingCurve.InOutQuad))
        self.animation.valueChanged.connect(self.onAnimate)
        self.animation.setDuration(1000)
        self.installEventFilter(self)

        self.flag = False

    def onLeftClicked(self):
        self.flag = False
        self.animation.setStartValue(self.widget().offset())
        self.animation.setEndValue(self.widget().offset() - 30)
        self.animation.start()
        self.flag = True

    def onRightClicked(self):
        self.flag = False
        self.animation.setStartValue(self.widget().offset())
        self.animation.setEndValue(self.widget().offset() + 30)
        self.animation.start()
        self.flag = True

    def resizeEvent(self, event):
        self.header.resize(self.width(), 80)

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