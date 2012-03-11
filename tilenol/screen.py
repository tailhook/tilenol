from zorro.di import di, has_dependencies, dependency

from tilenol.event import Event
from .xcb import Rectangle
from tilenol.commands import CommandDispatcher


@has_dependencies
class ScreenManager(object):

    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, rectangles):
        self.screens = []
        for i, rect in enumerate(rectangles):
            scr = Screen()
            scr.set_bounds(rect)
            self.screens.append(scr)

    def __zorro_di_done__(self):
        inj = di(self)
        for i, scr in enumerate(self.screens):
            inj.inject(scr)
            self.commander['screen.{}'.format(i)] = scr


class Screen(object):

    def __init__(self):
        self.topbars = []
        self.bottombars = []
        self.updated = Event('screen.updated')

    def cmd_focus(self):
        self.group.focus()

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

