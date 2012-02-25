from collections import OrderedDict
from math import floor

from tilenol.xcb import Rectangle
from . import Layout


class Stack(object):
    """Single stack for tile layout

    It's customized by subclassing, not by instantiating

    :var weight: the bigger weight is, the bigger part of screen this stack
        occupies
    :var tile: whether to tile windows or just switch between them
    :var limit: limit number of windows inside the stack
    :var priority: windows are placed into stacks with smaller priority first
    """
    weight = 1
    tile = True
    limit = None
    priority = 100
    vertical = True

    def __init__(self):
        self.visible_windows = []  # layout focus API
        self.windows = []
        self.box = Rectangle(0, 0, 100, 100)  # just to have something

    def add(self, win):
        self.windows.append(win)
        if self.tile:
            self.visible_windows.append(win)
        else:
            # TODO(tailhook) check if we should leave top (focused) window
            self.visible_windows = [win]

    def remove(self, win):
        self.windows.remove(win)
        self.visible_windows.remove(win)
        if not self.visible_windows and self.windows:
            # TODO(tailhook) may be select next window instead of first one
            self.visible_windows = self.windows[0]

    def layout(self):
        if self.tile:
            vc = len(self.visible_windows)
            if self.vertical:
                rstart = start = self.box.y
            else:
                rstart = start = self.box.x
            for n, w in enumerate(self.visible_windows, 1):
                if self.vertical:
                    end = rstart + int(floor(n/vc*self.box.height))
                    w.set_bounds(Rectangle(
                        self.box.x, start, self.box.width, end-start))
                else:
                    end = rstart + int(floor(n/vc*self.box.width))
                    w.set_bounds(Rectangle(
                        start, self.box.y, end-start, self.box.height))
                w.show()
                start = end
        elif self.visible_windows:
            win = self.visible_windows[0]
            win.set_bounds(self.box)
            win.show()
            for i in self.windows:
                if i is not win:
                    i.hide()


    @property
    def empty(self):
        return not self.windows

    @property
    def full(self):
        return self.limit is not None and len(self.windows) >= self.limit


class Tile(Layout):
    """Tiling layout

    It's customized by subclassing, not by instantiating. Class definition
    should consist of at least one stack

    :var fixed: whether to skip empty stacks or reserve place for them
    """
    fixed = False
    vertical = True

    def __init__(self):
        self.boxes_dirty = False
        stacks = []
        for stack_class in self.get_defined_classes(Stack).values():
            stack = stack_class()
            stacks.append(stack)
        self.stack_list = stacks[:]
        stacks.sort(key=lambda s: s.priority)
        self.stacks = OrderedDict((s.__class__.__name__, s) for s in stacks)

    def set_bounds(self, bounds):
        self.bounds = bounds
        self.boxes_dirty = True
        self.dirty = True

    def _assign_boxes(self, box):
        if self.fixed:
            all_stacks = self.stack_list
        else:
            all_stacks = [s for s in self.stack_list if not s.empty]
        totw = sum(s.weight for s in all_stacks)
        curw = 0
        if self.vertical:
            rstart = start = box.x
            totalpx = box.width
        else:
            rstart = start = box.y
            totalpx = box.height
        for s in all_stacks:
            curw += s.weight
            end = rstart + int(floor(curw/totw*totalpx))
            if self.vertical:
                s.box = Rectangle(start, box.y, end-start, box.height)
            else:
                s.box = Rectangle(box.x, start, box.width, end-start)
            start = end

    def add(self, win):  # layout API
        for s in self.stacks.values():
            if not s.full:
                if not self.fixed and s.empty:
                    self.boxes_dirty = True
                s.add(win)
                win.lprops.stack = s.__class__.__name__
                self.dirty = True
                return True
        return False  # no empty stacks, reject it, so it will be floating

    def remove(self, win):  # layout API
        self.stacks[win.lprops.stack].remove(win)
        win.lprops.clear()

    def sublayouts(self):  # layout focus API
        return self.stacks.values()

    def layout(self):
        if self.boxes_dirty:
            self._assign_boxes(self.bounds)
            self.boxes_dirty = False
        for s in self.stack_list:
            s.layout()

