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
        self.leftslices = []
        self.rightslices = []
        self.updated = Event('screen.updated')
        self.bars_visible = True
        self.group_hooks = []

    def add_group_hook(self, fun):
        self.group_hooks.append(fun)

    def remove_group_hook(self, fun):
        self.group_hooks.remove(fun)

    def set_group(self, group):
        self.group = group
        for h in self.group_hooks:
            h()

    def cmd_focus(self):
        self.group.focus()

    def set_bounds(self, rect):
        self.bounds = rect
        x, y, w, h = rect
        if self.bars_visible:
            for bar in self.topbars:
                bar.set_bounds(Rectangle(x, y, w, bar.height))
                y += bar.height
                h -= bar.height
            for bar in self.bottombars:
                h -= bar.height
                bar.set_bounds(Rectangle(x, y+h, w, bar.height))
            for gadget in self.leftslices:
                gadget.set_bounds(Rectangle(x, y, gadget.width, h))
                x += gadget.width
                w -= gadget.width
            for gadget in self.rightslices:
                w -= gadget.width
                gadget.set_bounds(Rectangle(x+w, y, gadget.width, h))
        self.inner_bounds = Rectangle(x, y, w, h)
        self.updated.emit()

    def all_bars(self):
        for bar in self.topbars:
            yield bar
        for bar in self.bottombars:
            yield bar

    def add_top_bar(self, bar):
        if bar not in self.topbars:
            self.topbars.append(bar)
        self.set_bounds(self.bounds)

    def add_bottom_bar(self, bar):
        if bar not in self.bottombars:
            self.bottombars.append(bar)
        self.set_bounds(self.bounds)

    def slice_left(self, obj):
        if obj not in self.leftslices:
            self.leftslices.append(obj)
        self.set_bounds(self.bounds)

    def unslice_left(self, obj):
        if obj in self.leftslices:
            self.leftslices.remove(obj)
        self.set_bounds(self.bounds)

    def slice_right(self, obj):
        if obj not in self.rightslices:
            self.rightslices.append(obj)
        self.set_bounds(self.bounds)

    def unslice_right(self, obj):
        if obj in self.rightslices:
            self.leftslices.remove(obj)
        self.set_bounds(self.bounds)

    def cmd_toggle_bars(self):
        if self.bars_visible:
            self.cmd_hide_bars()
        else:
            self.cmd_show_bars()

    def cmd_hide_bars(self):
        for bar in self.all_bars():
            bar.window.hide()
        self.bars_visible = False
        self.inner_bounds = self.bounds
        self.updated.emit()

    def cmd_show_bars(self):
        for bar in self.all_bars():
            bar.window.show()
        self.bars_visible = True
        self.set_bounds(self.bounds)

