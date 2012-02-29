import struct
from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core, Rectangle


@has_dependencies
class Ewmh(object):

    xcore = dependency(Core, 'xcore')
    dispatcher = dependency(object, 'event-dispatcher')

    def __zorro_di_done__(self):
        self.window = Window(self.xcore.create_toplevel(
            Rectangle(0, 0, 1, 1),
            klass=self.xcore.WindowClass.InputOnly,
            params={}))
        di(self).inject(self.window)
        self.xcore.raw.ChangeProperty(
            window=self.xcore.root_window,
            mode=self.xcore.PropMode.Replace,
            property=self.xcore.atom._NET_SUPPORTING_WM_CHECK,
            type=self.xcore.atom.WINDOW,
            format=32,
            data_len=1,
            data=struct.pack('<L', self.window))
        self.xcore.raw.ChangeProperty(
            window=self.window,
            mode=self.xcore.PropMode.Replace,
            property=self.xcore.atom._NET_SUPPORTING_WM_CHECK,
            type=self.xcore.atom.WINDOW,
            format=32,
            data_len=1,
            data=struct.pack('<L', self.window))
        self.xcore.raw.ChangeProperty(
            window=self.window,
            mode=self.xcore.PropMode.Replace,
            property=self.xcore.atom._NET_WM_NAME,
            type=self.xcore.atom.UTF8_STRING,
            format=8,
            data=b'tilenol')

    def showing_window(self, win):
        self.xcore.raw.ChangeProperty(
            window=win,
            mode=self.xcore.PropMode.Replace,
            property=self.xcore.atom.WM_STATE,
            type=self.xcore.atom.CARD32,
            format=32,
            data_len=2,
            data=struct.pack('<LL', 1, 0))

    def hiding_window(self, win):
        self.xcore.raw.ChangeProperty(
            window=win,
            mode=self.xcore.PropMode.Replace,
            property=self.xcore.atom.WM_STATE,
            type=self.xcore.atom.CARD32,
            format=32,
            data_len=2,
            data=struct.pack('<LL', 0, 0))


from .window import Window # cyclic dependency
