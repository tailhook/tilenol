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

class State(object):
    size = None
    visible = False

class DoneState(State):
    layouted = False


@has_dependencies
class Window(object):

    xcore = dependency(Core, 'xcore')

    def __init__(self, wid):
        self.wid = wid
        self.frame = None
        self.want = State()
        self.done = DoneState()
        self.real = State()
        self.props = {}

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.wid)

    @classmethod
    def from_notify(cls, notify):
        win = cls(notify.window)
        win.parent = notify.parent
        win.override = notify.override_redirect
        win.want.size = SizeRequest.from_notify(notify)
        return win

    def update_size_request(self, req):
        msk = self.xcore.ConfigWindow
        sr = self.want.size
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
        if self.done.visible:
            return False
        self.done.visible = True
        self.xcore.raw.MapWindow(window=self)
        if self.frame:
            self.frame.show()
        return True

    def set_bounds(self, rect):
        if self.done.size == rect:
            return False
        self.done.size = rect
        if self.frame:
            self.frame.set_bounds(rect)
        else:
            self.xcore.raw.ConfigureWindow(window=self, params={
                self.xcore.ConfigWindow.X: rect.x,
                self.xcore.ConfigWindow.Y: rect.y,
                self.xcore.ConfigWindow.Width: rect.width,
                self.xcore.ConfigWindow.Height: rect.height,
                })
        return True

    @property
    def toplevel(self):
        return self.parent == self.xcore.root_window

    def reparent(self):
        s = self.want.size
        self.frame = di(self).inject(Frame(self.xcore.create_toplevel(
            Rectangle(s.x, s.y, s.width, s.height),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.SubstructureRedirect
                    | self.xcore.EventMask.SubstructureNotify # temp
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow,
            }), self))
        self.xcore.raw.ChangeWindowAttributes(
            window=self,
            params={
                self.xcore.CW.EventMask: self.xcore.EventMask.PropertyChange
                    | self.xcore.EventMask.Exposure, # temp
            })
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

    def set_property(self, name, typ, value):
        self.props[name] = value


class Frame(Window):

    def __init__(self, wid, content):
        super().__init__(wid)
        self.content = content

    def focus(self, ev):
        self.content.focus(ev)

    def set_bounds(self, rect):
        if not super().set_bounds(rect):
            return False
        self.xcore.raw.ConfigureWindow(window=self.content, params={
            self.xcore.ConfigWindow.X: 0,
            self.xcore.ConfigWindow.Y: 0,
            self.xcore.ConfigWindow.Width: rect.width,
            self.xcore.ConfigWindow.Height: rect.height,
            })
        return True
