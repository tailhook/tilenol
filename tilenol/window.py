from collections import namedtuple
import struct
import logging

from zorro.di import di, has_dependencies, dependency

from .xcb import Core, Rectangle, XError
from .icccm import SizeHints
from .commands import CommandDispatcher
from .ewmh import Ewmh


log = logging.getLogger(__name__)


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

    short_to_long = {
        'group': '_NET_WM_DESKTOP',
        }
    long_to_short = {v: k for k, v in short_to_long.items()}

    def __init__(self, window):
        super().__setattr__('window', window)

    def __getattr__(self, name):
        return None

    def __setattr__(self, name, value):
        if getattr(self, name) != value:
            super().__setattr__(name, value)
            if name in self.short_to_long:
                self.window.set_property(self.short_to_long[name], value)
            else:
                self.window.set_property('_TN_LP_' + name.upper(), value)


@has_dependencies
class Window(object):

    xcore = dependency(Core, 'xcore')
    ewmh = dependency(Ewmh, 'ewmh')

    floating = None
    border_width = 0

    def __init__(self, wid):
        self.wid = wid
        self.frame = None
        self.want = State()
        self.done = State()
        self.real = State()
        self.props = {}
        self.lprops = LayoutProperties(self)

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
        sz = self.done.size
        if sz is None:
            sz = sr
        self.send_event('ConfigureNotify',
            window=self,
            event=self,
            x=sz.x,
            y=sz.y,
            width=sz.width,
            height=sz.height,
            border_width=0,
            above_sibling=0,
            override_redirect=False,
            )

    def send_event(self, event_type, event_mask=0, **kw):
        self.xcore.send_event(event_type, event_mask, self, **kw)

    def __index__(self):
        return self.wid

    def show(self):
        if self.done.visible:
            return False
        self.done.visible = True
        self.xcore.raw.MapWindow(window=self)
        if self.frame:
            self.ewmh.showing_window(self)
            self.frame.show()
        return True

    def hide(self):
        if not self.done.visible:
            return False
        self.done.visible = False
        if self.frame:
            self.ewmh.hiding_window(self)
            self.frame.hide()
        else:
            self.xcore.raw.UnmapWindow(window=self)
        return True

    def set_bounds(self, rect):
        if self.done.size == rect:
            return False
        if self.frame:
            self.frame.set_bounds(rect)
        else:
            self.done.size = rect
            self.xcore.raw.ConfigureWindow(window=self, params={
                self.xcore.ConfigWindow.X: rect.x & 0xFFFF,
                self.xcore.ConfigWindow.Y: rect.y & 0xFFFF,
                self.xcore.ConfigWindow.Width: rect.width-self.border_width*2,
                self.xcore.ConfigWindow.Height: rect.height-self.border_width*2,
                })
        return True

    @property
    def toplevel(self):
        return self.parent == self.xcore.root_window

    def reparent_to(self, window):
        self.xcore.raw.ChangeSaveSet(window=self,
                                     mode=self.xcore.SetMode.Insert)
        self.xcore.raw.ReparentWindow(
            window=self,
            parent=window,
            x=0, y=0)

    def reparent_frame(self):
        self.reparent_to(self.frame)

    def reparent_root(self):
        self.xcore.raw.ReparentWindow(
            window=self,
            parent=self.xcore.root_window,
            x=0, y=0)
        self.xcore.raw.ChangeSaveSet(window=self,
                                     mode=self.xcore.SetMode.Delete)


    def create_frame(self):
        s = self.want.size
        self.frame = di(self).inject(Frame(self.xcore.create_toplevel(
            Rectangle(s.x, s.y, s.width, s.height),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.BackPixel: 0x000000,
                self.xcore.CW.BorderPixel: 0x808080,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.SubstructureRedirect
                    | self.xcore.EventMask.SubstructureNotify
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow
                    | self.xcore.EventMask.FocusChange
            }), self))
        self.xcore.raw.ConfigureWindow(window=self.frame, params={
                self.xcore.ConfigWindow.BorderWidth: 2,
            })
        return self.frame

    def update_property(self, atom):
        try:
            self._set_property(self.xcore.atom[atom].name,
                  *self.xcore.get_property(self, atom))
        except XError:
            log.exception("Error getting property for window %r", self)

    def focus(self):
        self.done.focus = True
        self.xcore.raw.SetInputFocus(
            focus=self,
            revert_to=self.xcore.InputFocus.PointerRoot,
            time=self.xcore.last_event.time,
            )

    def _set_property(self, name, typ, value):
        if name == 'WM_NORMAL_HINTS':
            self.want.hints = SizeHints.from_property(typ, value)
        if name in self.lprops.long_to_short:
            if isinstance(value, tuple) and len(value) == 1:
                value = value[0]
            super(LayoutProperties, self.lprops).__setattr__(
                self.lprops.long_to_short[name], value)
        elif name.startswith('_TN_LP_'):
            if isinstance(value, tuple) and len(value) == 1:
                value = value[0]
            super(LayoutProperties, self.lprops).__setattr__(
                name[len('_TN_LP_'):], value)
        elif name == '_NET_WM_ICON':
            icons = self.icons = []
            lst = list(value)
            while lst:
                w = lst.pop(0)
                h = lst.pop(0)
                idata = lst[:w*h]
                del lst[:w*h]
                icons.append((w, h, idata))
            icons.sort()
        self.props[name] = value

    def set_property(self, name, value):
        if isinstance(value, int):
            self.xcore.raw.ChangeProperty(
                window=self,
                mode=self.xcore.PropMode.Replace,
                property=getattr(self.xcore.atom, name),
                type=self.xcore.atom.CARDINAL,
                format=32,
                data_len=1,
                data=struct.pack('<L', value))
        elif isinstance(value, Window):
            self.xcore.raw.ChangeProperty(
                window=self,
                mode=self.xcore.PropMode.Replace,
                property=getattr(self.xcore.atom, name),
                type=self.xcore.atom.WINDOW,
                format=32,
                data_len=1,
                data=struct.pack('<L', value))
        elif isinstance(value, (str, bytes)):
            if isinstance(value, str):
                value = value.encode('utf-8')
            self.xcore.raw.ChangeProperty(
                window=self,
                mode=self.xcore.PropMode.Replace,
                property=getattr(self.xcore.atom, name),
                type=self.xcore.atom.UTF8_STRING,
                format=8,
                data=value)
        else:
            raise NotImplementedError(value)

    def destroyed(self):
        if self.frame:
            return self.frame.destroy()

    def destroy(self):
        self.xcore.raw.DestroyWindow(window=self)

    def cmd_close(self):
        delw = self.xcore.atom.WM_DELETE_WINDOW
        if delw in self.props.get('WM_PROTOCOLS', ()):
            self.send_event('ClientMessage',
                window=self,
                type=self.xcore.atom.WM_PROTOCOLS,
                format=32,
                data=struct.pack('<LL', delw, 0),
                )
        else:
            log.warning("Can't close window gracefully, you can kill it")

    def cmd_kill(self):
        self.xcore.raw.KillClient(resource=self)

    def make_floating(self):
        if self.floating:
            return
        gr = self.group
        gr.remove_window(self)
        self.floating = True
        gr.add_window(self)

    cmd_make_floating = make_floating

    def make_tiled(self):
        if not self.floating:
            return
        gr = self.group
        gr.remove_window(self)
        self.floating = False
        gr.add_window(self)

    cmd_make_tiled = make_tiled

    def restack(self, stack_mode):
        self.stack_mode = stack_mode
        self.xcore.raw.ConfigureWindow(window=self, params={
            self.xcore.ConfigWindow.StackMode: stack_mode,
            })


class DisplayWindow(Window):

    def __init__(self, wid, expose_handler):
        super().__init__(wid)
        self.expose_handler = expose_handler

    def expose(self, rect):
        self.expose_handler(rect)


class ClientMessageWindow(Window):

    def __init__(self, wid, msg_handler):
        super().__init__(wid)
        self.msg_handler = msg_handler

    def client_message(self, message):
        self.msg_handler(message)


@has_dependencies
class Frame(Window):

    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, wid, content):
        super().__init__(wid)
        self.content = content
        self.border_width = 2

    def focus(self):
        self.done.focus = True
        if self.content.floating:
            self.restack(self.xcore.StackMode.TopIf)
        self.content.focus()

    def focus_out(self):
        self.done.focus = False
        self.real.focus = False
        self.content.done.focus = False
        self.content.real.focus = False
        assert self.commander.get('window') in (self.content, None)
        self.commander.pop('window', None)
        self.xcore.raw.ChangeWindowAttributes(window=self, params={
            self.xcore.CW.BorderPixel: 0x808080,
        })

    def focus_in(self):
        self.real.focus = True
        self.content.real.focus = True
        assert self.commander.get('window') in (self.content, None)
        self.commander['window'] = self.content
        self.xcore.raw.ChangeWindowAttributes(window=self, params={
            self.xcore.CW.BorderPixel: 0x0000FF,
        })

    def destroyed(self):
        if self.commander.get('window') is self.content:
            del self.commander['window']

    def configure_content(self, rect):
        hints = self.content.want.hints
        x = 0
        y = 0
        rw = rect.width - self.border_width*2
        rh = rect.height - self.border_width*2
        if hints:
            width, height = self._apply_hints(rw, rh, hints)
            if width < rw:
                x = rw//2 - width//2
            if height < rh:
                y = rh//2 - height//2
            # TODO(tailhook) obey gravity
        else:
            width = rw
            height = rh
        self.content.done.size = Rectangle(x, y, width, height)
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
