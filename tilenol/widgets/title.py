import array

from zorro.di import di, has_dependencies, dependency
from cairo import SolidPattern
import cairo

from .base import Widget
from tilenol.commands import CommandDispatcher
from tilenol.theme import Theme
from tilenol.ewmh import get_title


@has_dependencies
class Title(Widget):

    dispatcher = dependency(CommandDispatcher, 'commander')
    theme = dependency(Theme, 'theme')

    stretched = True

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.color = bar.text_color_pat
        self.font = bar.font
        self.padding = bar.text_padding
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
        self.font.apply(canvas)
        canvas.move_to(l + self.padding.left,
                       self.height - self.padding.bottom)
        canvas.show_text(get_title(win) or '')
        return r, r


@has_dependencies
class Icon(Widget):

    dispatcher = dependency(CommandDispatcher, 'commander')
    theme = dependency(Theme, 'theme')

    def __zorro_di_done__(self):
        self.padding = self.theme.bar.box_padding
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


