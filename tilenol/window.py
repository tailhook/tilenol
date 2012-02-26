from collections import namedtuple

from zorro.di import di, has_dependencies, dependency

from .xcb import Core
from .xcb.core import Rectangle
from .icccm import SizeHints


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
    hints = None


class LayoutProperties(object):

    def clear(self):
        self.__dict__.clear()

    # TODO(tailhook) expose layout properties to x properties


@has_dependencies
class Window(object):

    xcore = dependency(Core, 'xcore')

    def __init__(self, wid):
        self.wid = wid
        self.frame = None
        self.want = State()
        self.done = State()
        self.real = State()
        self.props = {}
        self.lprops = LayoutProperties()

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

    def hide(self):
        if not self.done.visible:
            return False
        self.done.visible = False
        if self.frame:
            self.frame.hide()
        else:
            self.xcore.raw.UnmapWindow(window=self)
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
                self.xcore.CW.BackPixel: 0x0000FF,
                self.xcore.CW.OverrideRedirect: True,
            }), self))
        self.xcore.raw.ChangeWindowAttributes(
            window=self,
            params={
                self.xcore.CW.EventMask: self.xcore.EventMask.PropertyChange
            })
        self.xcore.raw.ReparentWindow(
            window=self,
            parent=self.frame,
            x=0, y=0)
        return self.frame

    def focus(self, ev):
        self.xcore.raw.SetInputFocus(
            focus=self,
            revert_to=self.xcore.InputFocus.Parent,
            time=ev.time,
            )

    def set_property(self, name, typ, value):
        if name == 'WM_NORMAL_HINTS':
            self.want.hints = SizeHints.from_property(typ, value)
        self.props[name] = value

    def destroyed(self):
        if self.frame:
            return self.frame.destroy()

    def destroy(self):
        self.xcore.raw.DestroyWindow(window=self)


class DisplayWindow(Window):

    def __init__(self, wid, expose_handler):
        super().__init__(wid)
        self.expose_handler = expose_handler

    def expose(self, rect):
        self.expose_handler(rect)


class Frame(Window):

    def __init__(self, wid, content):
        super().__init__(wid)
        self.content = content

    def focus(self, ev):
        self.content.focus(ev)

    def configure_content(self, rect):
        hints = self.content.want.hints
        x = 2
        y = 2
        if hints:
            width, height = self._apply_hints(rect.width-4, rect.height-4, hints)
            if width < rect.width:
                x = rect.width//2 - width//2
            if height < rect.height:
                y = rect.height//2 - height//2
            # TODO(tailhook) obey gravity
        else:
            width = rect.width
            height = rect.height
        self.xcore.raw.ConfigureWindow(window=self.content, params={
            self.xcore.ConfigWindow.X: x,
            self.xcore.ConfigWindow.Y: y,
            self.xcore.ConfigWindow.Width: width,
            self.xcore.ConfigWindow.Height: height,
            })


    def _apply_hints(self, width, height, hints):
        if hasattr(hints, 'max_width') and width < hints.min_width:
            width = hints.min_width
        elif hasattr(hints, 'max_height') and width > hints.max_width:
            width = hints.max_width
        elif hasattr(hints, 'width_inc'):
            incr = hints.width_inc
            base = getattr(hints, 'base_width',
                           getattr(hints, 'min_width', None))
            n = (width - base)//incr
            width = base + n*incr
        if hasattr(hints, 'max_height') and height < hints.min_height:
            height = hints.min_height
        elif hasattr(hints, 'max_height') and height > hints.max_height:
            height = hints.max_height
        elif hasattr(hints, 'height_inc'):
            incr = hints.height_inc
            base = getattr(hints, 'base_height',
                           getattr(hints, 'min_height', None))
            n = (height - base)//incr
            height = base + n*incr
        # TODO(tailhook) obey aspect ratio
        return width, height


    def set_bounds(self, rect):
        if not super().set_bounds(rect):
            return False
        self.configure_content(rect)
        return True
