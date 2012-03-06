import array

from zorro.di import di, has_dependencies, dependency
from cairo import SolidPattern
import cairo

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

    def __zorro_di_done__(self):
        self.dispatcher.events['window'].listen(self.window_changed)
        self.oldwin = None

    def window_changed(self):
        if self.oldwin is not None:
            self.oldwin.property_changed.unlisten(self.bar.redraw.emit)
        win = self.dispatcher.get('window', None)
        if win is not None:
            win.property_changed.listen(self.bar.redraw.emit)
        self.oldwin = win
        self.bar.redraw.emit()

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


@has_dependencies
class Icon(Widget):

    dispatcher = dependency(CommandDispatcher, 'commander')

    def __init__(self, *,
            padding=Padding(2, 2, 2, 2),
            right=False):
        super().__init__(right=right)
        self.padding = padding

    def __zorro_di_done__(self):
        self.dispatcher.events['window'].listen(self.window_changed)
        self.oldwin = None

    def window_changed(self):
        if self.oldwin is not None:
            self.oldwin.property_changed.unlisten(self.bar.redraw.emit)
        win = self.dispatcher.get('window', None)
        if win is not None:
            win.property_changed.listen(self.bar.redraw.emit)
        self.oldwin = win
        self.bar.redraw.emit()

    def draw(self, canvas, l, r):
        win = self.dispatcher.get('window', None)
        if not win or not getattr(win, 'icons', None):
            return l, r
        h = self.height - self.padding.bottom - self.padding.top
        for iw, ih, data in win.icons:
            if iw >= h or ih >= h:
                break
        scale = min(iw/h, ih/h)
        data = array.array('I', data)
        assert data.itemsize == 4
        surf = cairo.ImageSurface.create_for_data(memoryview(data),
            cairo.FORMAT_ARGB32, iw, ih, iw*4)
        if self.right:
            x = r - self.padding.right - h
        else:
            x = l + self.padding.left
        y = self.padding.top
        pat = cairo.SurfacePattern(surf)
        pat.set_matrix(cairo.Matrix(
            xx=scale, yy=scale,
            x0=-x*scale, y0=-y*scale))
        pat.set_filter(cairo.FILTER_GOOD)
        canvas.set_source(pat)
        canvas.rectangle(x, y, h, h)
        canvas.scale(scale, scale)
        canvas.fill()
        if self.right:
            return l, r - h - self.padding.left - self.padding.right
        else:
            return l + h + self.padding.left + self.padding.right, r


