
from cairo import SolidPattern, LINE_JOIN_ROUND
from zorro.di import dependency, has_dependencies

from tilenol.groups import GroupManager
from .base import Widget
from tilenol.theme import Theme


@has_dependencies
class Groupbox(Widget):

    gman = dependency(GroupManager, 'group-manager')
    theme = dependency(Theme, 'theme')

    def __init__(self, *, right=False):
        super().__init__(right=right)

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.inactive_color = bar.dim_color_pat
        self.active_color = bar.text_color_pat
        self.selected_color = bar.active_border_pat
        self.padding = bar.text_padding
        self.border_width = bar.border_width
        self.gman.group_changed.listen(self.bar.redraw.emit)
        self.gman.window_added.listen(self.bar.redraw.emit)

    def draw(self, canvas, l, r):
        assert not self.right, "Sorry, right not implemented"
        self.font.apply(canvas)
        canvas.set_line_join(LINE_JOIN_ROUND)
        canvas.set_line_width(self.border_width)
        x = l
        between = self.padding.right + self.padding.left
        for g in self.gman.groups:
            sx, sy, w, h, ax, ay = canvas.text_extents(g.name)
            if g.empty:
                canvas.set_source(self.inactive_color)
            else:
                canvas.set_source(self.active_color)
            canvas.move_to(x + self.padding.left,
                           self.height - self.padding.bottom)
            canvas.show_text(g.name)
            if self.gman.current_group is g:
                canvas.set_source(self.selected_color)
                canvas.rectangle(x + 2, 2, ax + between - 4, self.height - 4)
                canvas.stroke()
            x += ax + between
        return x, r
