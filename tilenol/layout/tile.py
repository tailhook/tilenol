from collections import OrderedDict
from math import floor
from functools import wraps

from zorro.di import has_dependencies, dependency, di

from tilenol.xcb import Rectangle
from tilenol.commands import CommandDispatcher
from . import Layout


class BaseStack(object):
    """Single stack for tile layout

    It's customized by subclassing, not by instantiating

    :var weight: the bigger weight is, the bigger part of screen this stack
        occupies
    :var limit: limit number of windows inside the stack
    :var priority: windows are placed into stacks with smaller priority first
    """
    weight = 1
    limit = None
    priority = 100

    def __init__(self, parent):
        self.parent = parent
        self.windows = []
        self.box = Rectangle(0, 0, 100, 100)

    @property
    def empty(self):
        return not self.windows

    @property
    def full(self):
        return self.limit is not None and len(self.windows) >= self.limit

    def up(self):
        self.windows.append(self.windows.pop(0))
        print(self.windows)
        self.parent.dirty()

    def down(self):
        self.windows.insert(0, self.windows.pop())
        print(self.windows)
        self.parent.dirty()


class Stack(BaseStack):
    """Single window visibility stack"""


    @property
    def visible_windows(self):
        for i in self.windows:
            yield i
            break

    def add(self, win):
        self.windows.insert(0, win)
        self.parent.dirty()

    def remove(self, win):
        if self.windows[0] is win:
            self.parent.dirty()
        self.windows.remove(win)

    def layout(self):
        if not self.windows:
            return
        win = self.windows[0]
        win.set_bounds(self.box)
        win.show()
        for i in self.windows[1:]:
            i.hide()


class TileStack(BaseStack):
    """Tiling stack"""
    vertical = True

    def __init__(self, parent):
        super().__init__(parent)
        self.visible_windows = self.windows

    def add(self, win):
        self.windows.append(win)
        self.parent.dirty()

    def remove(self, win):
        self.windows.remove(win)
        self.parent.dirty()

    def layout(self):
        vc = len(self.windows)
        if self.vertical:
            rstart = start = self.box.y
        else:
            rstart = start = self.box.x
        for n, w in enumerate(self.windows, 1):
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


def stackcommand(fun):
    @wraps(fun)
    def wrapper(self, *args):
        try:
            win = self.commander['window']
        except KeyError:
            return
        stack = win.lprops.stack
        if stack is None:
            return
        return fun(self, self.stacks[stack], win, *args)
    return wrapper


@has_dependencies
class Split(Layout):
    """Split layout

    It's customized by subclassing, not by instantiating. Class definition
    should consist of at least one stack

    :var fixed: whether to skip empty stacks or reserve place for them
    """
    fixed = False
    vertical = True

    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self):
        super().__init__()
        self.boxes_dirty = False
        stacks = []
        for stack_class in self.get_defined_classes(BaseStack).values():
            stack = stack_class(self)
            stacks.append(stack)
        self.stack_list = stacks[:]
        stacks.sort(key=lambda s: s.priority)
        self.stacks = OrderedDict((s.__class__.__name__, s) for s in stacks)

    def set_bounds(self, bounds):
        self.bounds = bounds
        self.boxes_dirty = True

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

    @stackcommand
    def cmd_up(self, stack, win):
        stack.up()

    @stackcommand
    def cmd_down(self, stack, win):
        stack.down()

