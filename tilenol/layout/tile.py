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

    :var size: size (e.g. width) of stack in pixels, if None weight is used
    :var min_size: minimum size of stack to start to ignore pixel sizes
    :var weight: the bigger weight is, the bigger part of screen this stack
        occupies (if width is unspecified or screen size is too small)
    :var limit: limit number of windows inside the stack
    :var priority: windows are placed into stacks with smaller priority first
    """
    size = None
    min_size = 32
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

    def shift_up(self):
        self.windows.append(self.windows.pop(0))
        self.parent.dirty()

    def shift_down(self):
        self.windows.insert(0, self.windows.pop())
        self.parent.dirty()


class Stack(BaseStack):
    """Single window visibility stack"""


    @property
    def visible_windows(self):
        for i in self.windows:
            yield i
            break

    def add(self, win):
        win.lprops.stack = self.__class__.__name__
        self.windows.insert(0, win)
        self.parent.dirty()

    def remove(self, win):
        if self.windows[0] is win:
            self.parent.dirty()
        del win.lprops.stack
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

    @property
    def visible_windows(self):
        return self.windows

    def add(self, win):
        win.lprops.stack = self.__class__.__name__
        self.windows.append(win)
        self.parent.dirty()

    def remove(self, win):
        del win.lprops.stack
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
        self.auto_stacks = []
        self.stack_list = []
        self.stacks = {}
        for stack_class in self.get_defined_classes(BaseStack).values():
            stack = stack_class(self)
            self.stacks[stack.__class__.__name__] = stack
            self.stack_list.append(stack)
            if stack.priority is not None:
                self.auto_stacks.append(stack)
        self.auto_stacks.sort(key=lambda s: s.priority)

    def set_bounds(self, bounds):
        self.bounds = bounds
        self.dirty()

    def _assign_boxes(self, box):
        if self.fixed:
            all_stacks = self.stack_list
        else:
            all_stacks = [s for s in self.stack_list if not s.empty]
        curw = 0
        if self.vertical:
            rstart = start = box.x
            totalpx = box.width
        else:
            rstart = start = box.y
            totalpx = box.height
        totpx = sum((s.size or s.min_size) for s in all_stacks)
        totw = sum(s.weight for s in all_stacks if s.size is None)
        skip_pixels = totpx > totalpx or (not totw and totpx != totalpx)
        if skip_pixels:
            totw = sum(s.weight for s in all_stacks)
        else:
            totalpx -= sum(s.size for s in all_stacks if s.size is not None)
        pxoff = 0
        for s in all_stacks:
            if s.size is not None and not skip_pixels:
                end = start + s.size
                pxoff += s.size
            else:
                curw += s.weight
                end = rstart + pxoff + int(floor(curw/totw*totalpx))
            if self.vertical:
                s.box = Rectangle(start, box.y, end-start, box.height)
            else:
                s.box = Rectangle(box.x, start, box.width, end-start)
            start = end

    def add(self, win):  # layout API
        if win.lprops.stack is not None:
            s = self.stacks.get(win.lprops.stack)
            if s is not None and not s.full:
                s.add(win)
                return True
        for s in self.auto_stacks:
            if not s.full:
                s.add(win)
                return True
        return False  # no empty stacks, reject it, so it will be floating

    def remove(self, win):  # layout API
        self.stacks[win.lprops.stack].remove(win)

    def sublayouts(self):  # layout focus API
        return self.stacks.values()

    def layout(self):
        self._assign_boxes(self.bounds)
        for s in self.stack_list:
            s.layout()

    def swap_window(self, source, target, win):
        if target.full:
            other = target.windows[0]
            target.remove(other)
            source.remove(win)
            target.add(win)
            source.add(other)
        else:
            source.remove(win)
            target.add(win)

    @stackcommand
    def cmd_up(self, stack, win):
        if self.vertical:
            stack.shift_up()
        else:
            idx = self.stack_list.index(stack)
            if idx > 0:
                self.swap_window(stack, self.stack_list[idx-1], win)

    @stackcommand
    def cmd_down(self, stack, win):
        if self.vertical:
            stack.shift_down()
        else:
            idx = self.stack_list.index(stack)
            if idx < len(self.stacks)-1:
                self.swap_window(stack, self.stack_list[idx+1], win)

    @stackcommand
    def cmd_left(self, stack, win):
        if not self.vertical:
            stack.shift_up()
        else:
            idx = self.stack_list.index(stack)
            if idx > 0:
                self.swap_window(stack, self.stack_list[idx-1], win)

    @stackcommand
    def cmd_right(self, stack, win):
        if not self.vertical:
            stack.shift_down()
        else:
            idx = self.stack_list.index(stack)
            if idx < len(self.stacks)-1:
                self.swap_window(stack, self.stack_list[idx+1], win)

