import datetime

from zorro.di import dependency, has_dependencies
from cairo import SolidPattern

from  .base import Widget, Padding


class Clock(Widget):

    def __init__(self, *,
            font_face="Consolas",
            font_size=18,
            color=SolidPattern(1, 1, 1),
            format="%H:%M:%S %d.%m.%Y",
            padding=Padding(2, 4, 8, 4),
            right=False):
        super().__init__(right=right)
        self.font_face = font_face
        self.font_size = font_size
        self.color = color
        self.padding = padding
        self.format = format

    def _time(self):
        return datetime.datetime.now().strftime(self.format)

    def draw(self, canvas):
        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
        canvas.set_source(self.color)
        tm = self._time()
        _, _, w, h, _, _ = canvas.text_extents(tm)
        if self.right:
            l, t, r, b = canvas.clip_extents()
            canvas.move_to(r - self.padding.right - w,
                           self.height - self.padding.bottom)
        else:
            canvas.move_to(self.padding.left, self.height - self.padding.bottom)
        canvas.show_text(tm)
        return w
