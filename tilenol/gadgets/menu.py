import os
import shlex
import subprocess
from itertools import islice

from zorro.di import has_dependencies, dependency, di

from .base import GadgetBase, TextField
from tilenol.commands import CommandDispatcher
from tilenol.window import DisplayWindow
from tilenol.events import EventDispatcher
from tilenol.event import Event


@has_dependencies
class Select(GadgetBase):

    commander = dependency(CommandDispatcher, 'commander')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')

    def __init__(self, max_lines=10):
        self.window = None
        self.max_lines = max_lines
        self.redraw = Event('menu.redraw')
        self.redraw.listen(self._redraw)

    def __zorro_di_done__(self):
        self.line_height = self.theme.menu.line_height

    def cmd_show(self):
        if self.window:
            self.cmd_hide()
        self._current_items = self.items()
        show_lines = min(len(self._current_items) + 1, self.max_lines)
        h = self.theme.menu.line_height
        self.height = h*self.max_lines
        bounds = self.commander['screen'].bounds._replace(height=h)
        self._img = self.xcore.pixbuf(bounds.width, h)
        wid = self.xcore.create_toplevel(bounds,
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.BackPixel: self.theme.menu.background,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.FocusChange
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow
                    | self.xcore.EventMask.KeymapState
                    | self.xcore.EventMask.KeyPress,
            })
        self.window = di(self).inject(DisplayWindow(wid, self.draw))
        self.dispatcher.all_windows[wid] = self.window
        self.dispatcher.frames[wid] = self.window  # dirty hack
        self.window.show()
        self.window.focus()
        self.text_field = di(self).inject(TextField(
            self.redraw,
            self.theme.menu,
            ))
        self.dispatcher.active_field = self.text_field
        self._items = self.items()

    def cmd_hide(self):
        self.xcore.raw.DestroyWindow(window=self.window)
        if self.dispatcher.active_field == self.text_field:
            self.dispatcher.active_field = None
        self.text_field = None
        self.window = None

    def draw(self, rect=None):
        self._img.draw(self.window)

    def match_lines(self, value):
        for line in self._items:
            if line.startswith(value):
                yield line, [(1, value), (0, line[len(value):])]

    def _redraw(self):
        lines = list(islice(self.match_lines(self.text_field.value),
                            self.max_lines))
        newh = (len(lines)+1)*self.line_height
        if newh != self.height:
            # don't need to render, need resize
            self.height = newh
            bounds = self.commander['screen'].bounds._replace(height=newh)
            self._img = self.xcore.pixbuf(bounds.width, newh)
            self.window.set_bounds(bounds)
        ctx = self._img.context()
        ctx.set_source(self.theme.menu.background_pat)
        ctx.rectangle(0, 0, self._img.width, self._img.height)
        ctx.fill()
        sx, sy, _, _, ax, ay = ctx.text_extents(self.text_field.value)
        self.text_field.draw(ctx)
        th = self.theme.menu
        pad = th.padding
        y = self.line_height
        for text, opcodes in lines:
            ctx.move_to(pad.left, y + self.line_height - pad.bottom)
            for op, tx in opcodes:
                ctx.set_source(th.highlight_pat if op else th.text_pat)
                ctx.show_text(tx)
            y += self.line_height
        self.draw()


class SelectExecutable(Select):

    def __init__(self, *,
            env_var='PATH',
            update_cmd='bash -lc ${env_var}',
            **kw):
        super().__init__(**kw)
        self.env_var = env_var
        self.paths = list(filter(bool, map(str.strip,
            os.environ.get(self.env_var, '').split(':'))))
        if update_cmd:
            self.update_cmd = shlex.split(update_cmd.format_map(self.__dict__))

    def items(self):
        names = set()
        for i in self.paths:
            try:
                lst = os.listdir(i)
            except OSError:
                continue
            names.update(lst)
        return sorted(names)

    def cmd_refresh(self):
        data = subprocess.check_output(self.update_cmd)
        self.paths = filter(bool, map(str.strip,
            data.decode('ascii').split(':')))


