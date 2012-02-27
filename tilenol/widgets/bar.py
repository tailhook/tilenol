from math import ceil

import cairo
from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core, Rectangle
from tilenol.screen import ScreenManager
from tilenol.window import DisplayWindow
from tilenol.events import EventDispatcher


@has_dependencies
class Bar(object):

    xcore = dependency(Core, 'xcore')
    screenman = dependency(ScreenManager, 'screen-manager')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')

    def __init__(self, widgets,
                 screen_no=0,
                 height=24,
                 background=0x000000,
                 ):
        self.widgets = widgets
        self.screen_no = screen_no
        self.height = height
        self.background = background
        for w in widgets:
            w.height = self.height

    def __zorro_di_done__(self):
        scr = self.screenman.screens[self.screen_no]
        scr.add_top_bar(self)
        scr.add_listener(self.update_screen)
        self.update_screen(scr)

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
                CW.EventMask: EM.Exposure,
                CW.OverrideRedirect: True,
                CW.BackPixel: self.background
            }), self.expose)
        di(self).inject(self.window)
        self.dispatcher.register_window(self.window)
        self.window.show()

    def expose(self, rect):
        region = self.cairo
        l = 0
        r = self.width
        for i in self.widgets:
            self.cairo.save()
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



