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
        # we have limit on the size of the bar until BIG-REQUESTS or SHM
        self.width = min(rect.width, (1 << 16) // self.height)
        stride = self.xcore.bitmap_stride
        self.img = cairo.ImageSurface(cairo.FORMAT_ARGB32,
            int(ceil(self.width/stride)*stride), self.height)
        self.cairo = cairo.Context(self.img)
        if self.window and not self.window.set_bounds(rect):
            self.redraw.emit()

    def create_window(self):
        self._gc = self.xcore._conn.new_xid()  # TODO(tialhook) private api?
        self.xcore.raw.CreateGC(
            cid=self._gc,
            drawable=self.xcore.root_window,
            params={},
            )
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
        self.xcore.raw.PutImage(
            format=self.xcore.ImageFormat.ZPixmap,
            drawable=self.window,
            gc=self._gc,
            width=self.img.get_width(),
            height=self.img.get_height(),
            dst_x=0,
            dst_y=0,
            left_pad=0,
            depth=24,
            data=bytes(self.img),
            )



