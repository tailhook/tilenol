from math import ceil

import cairo
from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core, Rectangle
from tilenol.window import DisplayWindow
from tilenol.events import EventDispatcher
from tilenol.event import Event
from tilenol.theme import Theme


@has_dependencies
class Bar(object):

    xcore = dependency(Core, 'xcore')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    theme = dependency(Theme, 'theme')


    def __init__(self, widgets, position='top'):
        self.widgets = widgets
        self.position = position
        self.bounds = None
        self.window = None
        self.redraw = Event('bar.redraw')
        self.redraw.listen(self.expose)

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.height = bar.height
        self.background = bar.background_pat
        inj = di(self).clone()
        inj['bar'] = self
        for w in self.widgets:
            w.height = self.height
            inj.inject(w)

    def set_bounds(self, rect):
        self.bounds = rect
        self.width = rect.width
        stride = self.xcore.bitmap_stride
        self.img = self.xcore.pixbuf(self.width, self.height)
        self.cairo = self.img.context()
        if self.window and not self.window.set_bounds(rect):
            self.redraw.emit()

    def create_window(self):
        EM = self.xcore.EventMask
        CW = self.xcore.CW
        self.window = DisplayWindow(self.xcore.create_toplevel(self.bounds,
            klass=self.xcore.WindowClass.InputOutput,
            params={
                CW.EventMask: EM.Exposure | EM.SubstructureNotify,
                CW.OverrideRedirect: True,
            }), self.expose)
        self.window.want.size = self.bounds
        di(self).inject(self.window)
        self.dispatcher.register_window(self.window)
        self.window.show()

    def expose(self, rect=None):
        # TODO(tailhook) set clip region to specified rectangle
        self.cairo.set_source(self.background)
        self.cairo.rectangle(0, 0, self.width, self.height)
        self.cairo.fill()
        l = 0
        r = self.width
        for i in self.widgets:
            self.cairo.save()
            self.cairo.rectangle(l, 0, r-l, self.height)
            self.cairo.clip()
            l, r = i.draw(self.cairo, l, r)
            self.cairo.restore()
        self.img.draw(0, 0, self.window)


