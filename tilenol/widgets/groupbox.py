from collections import namedtuple

from cairo import LINE_JOIN_ROUND
from zorro.di import di, dependency, has_dependencies

from tilenol.groups import GroupManager
from tilenol.commands import CommandDispatcher
from .base import Widget
from tilenol.theme import Theme
from tilenol.window import Window


GroupState = namedtuple(
    'GroupState',
    ('name', 'empty', 'active', 'visible', 'urgent')
)


@has_dependencies
class State(object):

    commander = dependency(CommandDispatcher, 'commander')
    gman = dependency(GroupManager, 'group-manager')

    def __init__(self):
        self._state = None

    def dirty(self):
        return self._state != self._read()

    def update(self):
        nval = self._read()
        if nval != self._state:
            self._state = nval
            return True

    def _read(self):
        cur = self.commander.get('group')
        visgr = self.gman.current_groups.values()
        return tuple(GroupState(g.name, g.empty, g is cur, g in visgr,
                                g.has_urgent_windows)
                     for g in self.gman.groups)

    @property
    def groups(self):
        return self._state


@has_dependencies
class Groupbox(Widget):

    theme = dependency(Theme, 'theme')

    def __init__(self, *, filled=False, first_letter=False, right=False):
        super().__init__(right=right)
        self.filled = filled
        self.first_letter = first_letter

    def __zorro_di_done__(self):
        self.state = di(self).inject(State())
        bar = self.theme.bar
        self.font = bar.font
        self.inactive_color = bar.dim_color_pat
        self.urgent_color = bar.bright_color_pat
        self.active_color = bar.text_color_pat
        self.selected_color = bar.active_border_pat
        self.subactive_color = bar.subactive_border_pat
        self.padding = bar.text_padding
        self.border_width = bar.border_width
        self.state.gman.group_changed.listen(self.bar.redraw.emit)
        Window.any_window_changed.listen(self.check_state)

    def check_state(self):
        if self.state.dirty:
            self.bar.redraw.emit()

    def draw(self, canvas, l, r):
        self.state.update()
        assert not self.right, "Sorry, right not implemented"
        self.font.apply(canvas)
        canvas.set_line_join(LINE_JOIN_ROUND)
        canvas.set_line_width(self.border_width)
        x = l
        between = self.padding.right + self.padding.left
        for gs in self.state.groups:
            gname = gs.name
            if self.first_letter:
                gname = gname[0]
            sx, sy, w, h, ax, ay = canvas.text_extents(gname)
            if gs.active:
                canvas.set_source(self.selected_color)
                if self.filled:
                    canvas.rectangle(x, 0, ax + between, self.height)
                    canvas.fill()
                else:
                    canvas.rectangle(
                        x + 2, 2, ax + between - 4, self.height - 4
                    )
                    canvas.stroke()
            elif gs.visible:
                canvas.set_source(self.subactive_color)
                if self.filled:
                    canvas.rectangle(x, 0, ax + between, self.height)
                    canvas.fill()
                else:
                    canvas.rectangle(
                        x + 2, 2, ax + between - 4, self.height - 4
                    )
                    canvas.stroke()
            if gs.urgent:
                canvas.set_source(self.urgent_color)
            elif gs.empty:
                canvas.set_source(self.inactive_color)
            else:
                canvas.set_source(self.active_color)
            canvas.move_to(x + self.padding.left,
                           self.height - self.padding.bottom)
            canvas.show_text(gname)
            x += ax + between
        return x, r
