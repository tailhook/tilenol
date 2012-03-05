from zorro.di import di, has_dependencies, dependency
from cairo import SolidPattern

from .base import Widget, Padding
from tilenol.commands import CommandDispatcher


@has_dependencies
class Title(Widget):

    dispatcher = dependency(CommandDispatcher, 'commander')

    def __init__(self, *,
            font_face="Consolas",
            font_size=18,
            color=SolidPattern(1, 1, 1),
            padding=Padding(2, 4, 7, 4),
            right=False):
        super().__init__(right=right)
        self.font_face = font_face
        self.font_size = font_size
        self.color = color
        self.padding = padding

    def draw(self, canvas, l, r):
        win = self.dispatcher.get('window', None)
        if not win:
            return r, r
        canvas.set_source(self.color)
        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
        canvas.move_to(l + self.padding.left,
                       self.height - self.padding.bottom)
        canvas.show_text(win.props.get('_NET_WM_NAME')
            or win.props.get('WM_NAME'))
        return r, r
