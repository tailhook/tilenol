from collections import namedtuple

from zorro.di import di, has_dependencies, dependency

from .xcb import Core
from .xcb.core import Rectangle


class SizeRequest(object):
    def __init__(self, x, y, width, height, border):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border = border

    @classmethod
    def from_notify(cls, notify):
        return cls(
            x=notify.x,
            y=notify.y,
            width=notify.width,
            height=notify.height,
            border=notify.border_width,
            )


@has_dependencies
class Window(object):

    xcore = dependency(Core, 'xcore')

    def __init__(self, wid):
        self.wid = wid
        self.frame = None

    @classmethod
    def from_notify(cls, notify):
        win = cls(notify.window)
        win.parent = notify.parent
        win.override = notify.override_redirect
        win.size_request = SizeRequest.from_notify(notify)
        return win

    def update_size_request(self, req):
        msk = self.xcore.ConfigWindow
        sr = self.size_request
        if req.value_mask & msk.X:
            sr.x = req.x
        if req.value_mask & msk.Y:
            sr.y = req.y
        if req.value_mask & msk.Width:
            sr.width = req.width
        if req.value_mask & msk.Height:
            sr.height = req.height

    def __index__(self):
        return self.wid

    def show(self):
        self.xcore.raw.MapWindow(window=self)
        if self.frame:
            self.frame.show()

    @property
    def toplevel(self):
        return self.parent == self.xcore.root_window

    def reparent(self):
        s = self.size_request
        self.frame = di(self).inject(Frame(self.xcore.create_toplevel(
            Rectangle(s.x, s.y, s.width, s.height),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.SubstructureRedirect
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow,
                self.xcore.CW.OverrideRedirect: True,
            }), self))
        self.xcore.raw.ReparentWindow(
            window=self,
            parent=self.frame,
            x=0, y=0)
        return self.frame

    def focus(self, ev):
        self.xcore.raw.SetInputFocus(
            focus=self,
            revert_to=getattr(self.xcore.atom, 'None'),
            time=ev.time,
            )


class Frame(Window):

    def __init__(self, wid, content):
        super().__init__(wid)
        self.content = content

    def focus(self, ev):
        self.content.focus(ev)
