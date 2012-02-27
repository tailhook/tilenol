
from cairo import SolidPattern, LINE_JOIN_ROUND
from zorro.di import dependency, has_dependencies

from tilenol.groups import GroupManager
from .base import Widget, Padding


@has_dependencies
class Groupbox(Widget):

    gman = dependency(GroupManager, 'group-manager')

    def __init__(self, *,
            font_face="Consolas",
            font_size=18,
            inactive_color=SolidPattern(0.5, 0.5, 0.5),
            active_color=SolidPattern(1, 1, 1),
            selected_color=SolidPattern(0.3, 0.3, 0.6),
            padding=Padding(2, 6, 7, 4),
            right=False):
        super().__init__(right=right)
        self.font_face = font_face
        self.font_size = font_size
        self.inactive_color = inactive_color
        self.active_color = active_color
        self.selected_color = selected_color
        self.padding = padding


    def draw(self, canvas, l, r):
        assert not self.right, "Sorry, right not implemented"
        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
        canvas.set_line_join(LINE_JOIN_ROUND)
        canvas.set_line_width(2)
        x = l + self.padding.left
        between = self.padding.right + self.padding.left
        for g in self.gman.groups:
            sx, sy, w, h, _, _ = canvas.text_extents(g.name)
            if g.empty:
                canvas.set_source(self.inactive_color)
            else:
                canvas.set_source(self.active_color)
            canvas.move_to(x, self.height - self.padding.bottom)
            canvas.show_text(g.name)
            if self.gman.current_group is g:
                canvas.set_source(self.selected_color)
                canvas.rectangle(l + 2, 2, w + between - 4, self.height - 4)
                canvas.stroke()
            x += w + between
        return x - self.padding.left, r
