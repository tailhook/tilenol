from tilenol.event import Event
from .xcb import Rectangle


class ScreenManager(object):

    def __init__(self, rectangles):
        self.screens = []
        for rect in rectangles:
            scr = Screen()
            scr.set_bounds(rect)
            self.screens.append(scr)


class Screen(object):

    def __init__(self):
        self.topbars = []
        self.bottombars = []
        self.updated = Event('screen.updated')

    def set_bounds(self, rect):
        self.bounds = rect
        x, y, w, h = rect
        for bar in self.topbars:
            bar.set_bounds(Rectangle(x, y, w, bar.height))
            y += bar.height
            h -= bar.height
        for bar in self.bottombars:
            h -= bar.height
            bar.set_bounds(Rectangle(x, y+h, w, bar.height))
        self.inner_bounds = Rectangle(x, y, w, h)
        self.updated.emit()

    def add_top_bar(self, bar):
        if bar not in self.topbars:
            self.topbars.append(bar)
        self.set_bounds(self.bounds)

    def add_bottom_bar(self, bar):
        if bar not in self.bottombars:
            self.bottombars.append(bar)
        self.set_bounds(self.bounds)

