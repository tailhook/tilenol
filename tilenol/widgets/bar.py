from math import ceil

import cairo
from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core, Rectangle
from tilenol.screen import ScreenManager
from tilenol.window import DisplayWindow
from tilenol.events import EventDispatcher
from tilenol.event import Event
from tilenol.theme import Theme


@has_dependencies
class Bar(object):

    xcore = dependency(Core, 'xcore')
    screenman = dependency(ScreenManager, 'screen-manager')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    theme = dependency(Theme, 'theme')


    def __init__(self, widgets, screen_no=0):
        self.widgets = widgets
        self.screen_no = screen_no
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
        scr = self.screenman.screens[self.screen_no]
        scr.add_top_bar(self)
        scr.add_listener(self.update_screen)
        self.update_screen(scr)
        self.redraw.emit()

    def update_screen(self, screen):
        # we have limit on the size of the bar until BIG-REQUESTS or SHM
        self.width = min(screen.bounds.width, (1 << 16) // self.height)
        stride = self.xcore.bitmap_stride
        self.img = cairo.ImageSurface(cairo.FORMAT_ARGB32,
            int(ceil(self.width/stride)*stride), self.height)
        self.cairo = cairo.Context(self.img)

    def create_window(self):
        self._gc = self.xcore._conn.new_xid()  # TODO(tialhook) private api?
        self.xcore.raw.CreateGC(
            cid=self._gc,
            drawable=self.xcore.root_window,
            params={},
            )
        EM = self.xcore.EventMask
        CW = self.xcore.CW
        self.window = DisplayWindow(self.xcore.create_toplevel(
            Rectangle(0, 0, self.width, self.height),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                CW.EventMask: EM.Exposure | EM.SubstructureNotify,
                CW.OverrideRedirect: True,
            }), self.expose)
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
            self.cairo.new_path()
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



