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
        self.window.set_property('_NET_SUPPORTING_WM_CHECK', self.window)
        self.window.set_property('_NET_WM_NAME', 'tilenol')

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


def match_type(*types):
    types = tuple('_NET_WM_WINDOW_TYPE_' + typ.upper() for typ in types)
    assert all(typ.isidentifier() for typ in types)
    def type_checker(win):
        for typ in types:
            rtype = getattr(win.xcore.atom, typ)
            if rtype in win.props.get('_NET_WM_WINDOW_TYPE', ()):
                return True
    return type_checker

def get_title(win):
    return (win.props.get('_NET_WM_NAME')
            or win.props.get('WM_NAME')
            or win.lprops.custom_name)


from .window import Window # cyclic dependency
