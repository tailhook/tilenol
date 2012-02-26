
from cairo import SolidPattern
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
            padding=Padding(2, 4, 8, 4)):
        self.font_face = font_face
        self.font_size = font_size
        self.inactive_color = inactive_color
        self.active_color = active_color
        self.padding = padding


    def draw(self, canvas):
        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
        x = self.padding.left
        between = self.padding.right + self.padding.left
        for g in self.gman.groups:
            sx, sy, w, h, _, _ = canvas.text_extents(g.name)
            canvas.set_source(self.active_color)
            canvas.move_to(x, self.height - self.padding.bottom)
            canvas.show_text(g.name)
            x += w + between

    def size(self, canvas):
        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
        width = 0
        for g in self.gman.groups:
            _, _, w, h, _, _ = canvas.text_extents(g.name)
            width += ext.width
            width += self.padding.left + self.padding.right
        return width
