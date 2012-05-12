import array
from collections import namedtuple
import struct
import logging

import cairo
from zorro.di import di, has_dependencies, dependency

from .xcb import Core, Rectangle, XError
from .icccm import SizeHints
from .commands import CommandDispatcher
from .ewmh import Ewmh
from .event import Event
from .theme import Theme


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


class BaseWindow(object):

    def __init__(self, wid):
        self.wid = wid

    def __index__(self):
        return self.wid


class Root(BaseWindow):
    """Root window

    Mostly used to ignore various root window events
    """

    def client_message(self, ev):
        pass

    def focus_in(self):
        pass

    def focus_out(self):
        pass


@has_dependencies
class Window(BaseWindow):

    xcore = dependency(Core, 'xcore')
    ewmh = dependency(Ewmh, 'ewmh')
    theme = dependency(Theme, 'theme')

    border_width = 0
    ignore_hints = False
    any_window_changed = Event('Window.any_window_changed')

    def __init__(self, wid):
        super().__init__(wid)
        self.frame = None
        self.want = State()
        self.done = State()
        self.real = State()
        self.props = {}
        self.lprops = LayoutProperties(self)
        self.property_changed = Event('window.property_changed')
        self.protocols = set()
        self.ignore_protocols = set()

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
        self.any_window_changed.emit()
        self.xcore.raw.MapWindow(window=self)
        if self.frame:
            self.ewmh.showing_window(self)
            self.frame.show()
        return True

    def hide(self):
        if not self.done.visible:
            return False
        self.done.visible = False
        self.any_window_changed.emit()
        if self.frame:
            self.ewmh.hiding_window(self)
            self.frame.hide()
        else:
            self.xcore.raw.UnmapWindow(window=self)
        return True

    def set_bounds(self, rect, force=False):
        if not force and self.done.size == rect:
            return False
        self.any_window_changed.emit()
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
            x=0, y=0,
            _ignore_error=True)  # already destroyed
        self.xcore.raw.ChangeSaveSet(window=self,
                                     mode=self.xcore.SetMode.Delete,
                                     _ignore_error=True)  # already destroyed


    def create_frame(self):
        s = self.want.size
        if self.lprops.floating:
            border_width = self.theme.window.border_width
            s.x = s.x - border_width
            s.y = s.y - border_width
        self.frame = di(self).inject(Frame(self.xcore.create_toplevel(s,
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.BackPixel: self.theme.window.background,
                self.xcore.CW.BorderPixel: self.theme.window.inactive_border,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.SubstructureRedirect
                    | self.xcore.EventMask.SubstructureNotify
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow
                    | self.xcore.EventMask.FocusChange
            }), self))
        self.frame.want.size = s
        self.frame.done.size = s
        self.frame.set_border(self.frame.border_width)
        return self.frame

    def update_property(self, atom):
        try:
            self._set_property(self.xcore.atom[atom].name,
                  *self.xcore.get_property(self, atom))
        except XError:
            log.debug("Error getting property for window %r", self)

    def focus(self):
        self.done.focus = True
        if "WM_TAKE_FOCUS" in self.protocols:
            self.send_event('ClientMessage',
                window=self,
                type=self.xcore.atom.WM_PROTOCOLS,
                format=32,
                data=struct.pack('<LL',
                    self.xcore.atom.WM_TAKE_FOCUS,
                    self.xcore.last_time),
                )
        else:
            self.xcore.raw.SetInputFocus(
                focus=self,
                revert_to=self.xcore.InputFocus.PointerRoot,
                time=self.xcore.last_time,
                )

    def _set_property(self, name, typ, value):
        if name == 'WM_NORMAL_HINTS':
            self.want.hints = SizeHints.from_property(typ, value)
        if name == 'WM_PROTOCOLS':
            self.protocols = set(self.xcore.atom[p].name
                                 for p in value
                                 if p not in self.ignore_protocols)
        if name in self.lprops.long_to_short:
            if isinstance(value, tuple) and len(value) == 1:
                value = value[0]
            super(LayoutProperties, self.lprops).__setattr__(
                self.lprops.long_to_short[name], value)
        elif name.startswith('_TN_LP_'):
            if isinstance(value, tuple) and len(value) == 1:
                value = value[0]
            super(LayoutProperties, self.lprops).__setattr__(
                name[len('_TN_LP_'):].lower(), value)
        elif name == '_NET_WM_ICON':
            icons = self.icons = []
            lst = list(value)
            def cvt(px):
                a = px >> 24
                k = a / 255.0
                r = (px >> 16) & 0xff
                g = (px >> 8) & 0xff
                b = px & 0xff
                return (a<<24) | (int(r*k)<<16) | (int(g*k)<<8) | int(b*k)
            while lst:
                w = lst.pop(0)
                h = lst.pop(0)
                idata = [cvt(px) for px in lst[:w*h]]
                del lst[:w*h]
                icons.append((w, h, idata))
            icons.sort()
        self.props[name] = value
        self.property_changed.emit()
        self.any_window_changed.emit()

    def draw_icon(self, canvas, x, y, size):
        for iw, ih, data in self.icons:
            if iw >= size or ih >= size:
                break
        scale = min(iw/size, ih/size)
        data = array.array('I', data)
        assert data.itemsize == 4
        surf = cairo.ImageSurface.create_for_data(memoryview(data),
            cairo.FORMAT_ARGB32, iw, ih, iw*4)
        pat = cairo.SurfacePattern(surf)
        pat.set_matrix(cairo.Matrix(
            xx=scale, yy=scale,
            x0=-x*scale, y0=-y*scale))
        pat.set_filter(cairo.FILTER_BEST)
        canvas.set_source(pat)
        canvas.rectangle(x, y, size, size)
        canvas.fill()

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
        elif value is None:
            self.xcore.raw.DeleteProperty(
                window=self,
                property=getattr(self.xcore.atom, name))
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
        if self.lprops.floating:
            return
        gr = self.group
        gr.remove_window(self)
        self.lprops.floating = True
        gr.add_window(self)

    cmd_make_floating = make_floating

    def make_tiled(self):
        if not self.lprops.floating:
            return
        gr = self.group
        gr.remove_window(self)
        self.lprops.floating = False
        gr.add_window(self)

    cmd_make_tiled = make_tiled

    def restack(self, stack_mode):
        self.stack_mode = stack_mode
        self.xcore.raw.ConfigureWindow(window=self, params={
            self.xcore.ConfigWindow.StackMode: stack_mode,
            })

    def set_border(self, width):
        self.border_width = width
        self.xcore.raw.ConfigureWindow(window=self, params={
                self.xcore.ConfigWindow.BorderWidth: width,
            })
        if self.done.size:
            self.set_bounds(self.done.size, force=True)

    def cmd_toggle_border(self):
        if self.frame:
            self.frame.toggle_border()


class DisplayWindow(Window):

    def __init__(self, wid, expose_handler, focus_in=None, focus_out=None):
        super().__init__(wid)
        self.expose_handler = expose_handler
        self._focus_in = focus_in
        self._focus_out = focus_out

    def expose(self, rect):
        self.expose_handler(rect)

    def focus_in(self):
        if self._focus_in:
            self._focus_in()

    def focus_out(self):
        if self._focus_out:
            self._focus_out()


@has_dependencies
class HintWindow(Window):

    cairo = None

    theme = dependency(Theme, 'theme')

    def __init__(self, wid, parent):
        super().__init__(wid)
        self.parent = parent
        self.redraw_ev = Event('hint.redraw')
        self.redraw_ev.listen(self.do_redraw)
        self.show_ev = Event('hint.show')
        self.show_ev.listen(self.do_show)

    def __zorro_di_done__(self):
        self.sizer = cairo.Context(
            cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
        sx, sy, w, h, ax, ay = self.sizer.text_extents('1')
        self.line_height = int(h - sy)
        self.font = self.theme.hint.font
        self.font.apply(self.sizer)
        self.padding = self.theme.hint.padding
        self.color = self.theme.hint.text_color_pat
        self.background = self.theme.hint.background_pat

        self._gc = self.xcore._conn.new_xid()  # TODO(tialhook) private api?
        self.xcore.raw.CreateGC(
            cid=self._gc,
            drawable=self.xcore.root_window,
            params={},
            )

    def set_text(self, text):
        self.text = text
        lines = text.split('\n')
        w = 0
        h = 0
        for line in lines:
            sx, sy, tw, th, ax, ay = self.sizer.text_extents(line)
            w = max(w, tw)
            h += th
        w += self.padding.left + self.padding.right
        h += self.padding.top + self.padding.bottom
        w = int(w)
        h = int(h)
        need_resize = (self.cairo is None or
                w != self.cairo.get_target().get_width() and
                h != self.cairo.get_target().get_height)
        if need_resize:
            self.cairo = cairo.Context(cairo.ImageSurface(
                cairo.FORMAT_ARGB32, w, h))
            self.font.apply(self.cairo)
            psz = self.parent.done.size
            self.set_bounds(Rectangle(
                (psz.width - w)//2 - self.border_width,
                (psz.height - h)//2 - self.border_width,
                w, h))
        self.redraw_ev.emit()

    def do_redraw(self):
        tgt = self.cairo.get_target()
        w = tgt.get_width()
        h = tgt.get_height()
        self.cairo.set_source(self.background)
        self.cairo.rectangle(0, 0, w, h)
        self.cairo.fill()
        self.cairo.set_source(self.color)
        y = self.padding.top + self.line_height
        for line in self.text.split('\n'):
            sx, sy, tw, th, ax, ay = self.sizer.text_extents(line)
            self.cairo.move_to((w - tw)//2, y)
            self.cairo.show_text(line)
            y += th
        self.show_ev.emit()

    def expose(self, rect):
        self.show_ev.emit()

    def do_show(self):
        tgt = self.cairo.get_target()
        w = tgt.get_width()
        h = tgt.get_height()
        self.xcore.raw.PutImage(
            format=self.xcore.ImageFormat.ZPixmap,
            drawable=self,
            gc=self._gc,
            width=w,
            height=h,
            dst_x=0,
            dst_y=0,
            left_pad=0,
            depth=24,
            data=bytes(tgt),
            )


class ClientMessageWindow(Window):

    def __init__(self, wid, msg_handler):
        super().__init__(wid)
        self.msg_handler = msg_handler

    def client_message(self, message):
        self.msg_handler(message)


@has_dependencies
class Frame(Window):

    commander = dependency(CommandDispatcher, 'commander')
    theme = dependency(Theme, 'theme')

    def __init__(self, wid, content):
        super().__init__(wid)
        self.content = content

    def __zorro_di_done__(self):
        self.border_width = self.theme.window.border_width

    def focus(self):
        self.done.focus = True
        if self.content.lprops.floating:
            self.restack(self.xcore.StackMode.TopIf)
        self.content.focus()

    def focus_out(self):
        self.done.focus = False
        self.real.focus = False
        self.content.done.focus = False
        self.content.real.focus = False
        win = self.commander.pop('window', None)
        assert win in (self.content, None)
        self.xcore.raw.ChangeWindowAttributes(window=self, params={
            self.xcore.CW.BorderPixel: self.theme.window.inactive_border,
        }, _ignore_error=True)

    def focus_in(self):
        self.real.focus = True
        self.content.real.focus = True
        assert self.commander.get('window') in (self.content, None)
        if not hasattr(self.content, 'group'):
            return
        self.commander['window'] = self.content
        self.commander['group'] = self.content.group
        self.commander['layout'] = self.content.group.current_layout
        self.commander['screen'] = self.content.group.screen
        self.xcore.raw.ChangeWindowAttributes(window=self, params={
            self.xcore.CW.BorderPixel: self.theme.window.active_border,
        }, _ignore_error=True)

    def pointer_enter(self):
        self.commander['pointer_window'] = self.content

    def pointer_leave(self):
        if self.commander.get('pointer_window') == self.content:
            del self.commander['pointer_window']

    def hide(self):
        if self.commander.get('window') == self.content:
            del self.commander['window']
        super().hide()

    def destroyed(self):
        if self.commander.get('window') is self.content:
            del self.commander['window']

    def configure_content(self, rect):
        hints = self.content.want.hints
        x = 0
        y = 0
        rw = rect.width - self.border_width*2
        rh = rect.height - self.border_width*2
        if hints and not self.content.ignore_hints:
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
        if hasattr(hints, 'width_inc'):
            incr = hints.width_inc
            base = getattr(hints, 'base_width',
                           getattr(hints, 'min_width', None))
            n = (width - base)//incr
            width = base + n*incr
        if hasattr(hints, 'max_width') and width > hints.max_width:
            width = hints.max_width
        if hasattr(hints, 'height_inc'):
            incr = hints.height_inc
            base = getattr(hints, 'base_height',
                           getattr(hints, 'min_height', None))
            n = (height - base)//incr
            height = base + n*incr
        if hasattr(hints, 'max_height') and height > hints.max_height:
            height = hints.max_height
        # TODO(tailhook) obey aspect ratio
        return width, height


    def set_bounds(self, rect, force=False):
        if not super().set_bounds(rect, force=force):
            return False
        self.configure_content(rect)
        return True

    def show(self):
        super().show()
        if self.done.size:
            self.configure_content(self.done.size)

    def add_hint(self):
        res = di(self).inject(HintWindow(self.xcore.create_window(
            Rectangle(0, 0, 1, 1),
            klass=self.xcore.WindowClass.InputOutput,
            parent=self,
            params={
                self.xcore.CW.BackPixel: self.theme.hint.background,
                self.xcore.CW.BorderPixel: self.theme.hint.border_color,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.SubstructureRedirect
                    | self.xcore.EventMask.SubstructureNotify
                    | self.xcore.EventMask.EnterWindow
                    | self.xcore.EventMask.LeaveWindow
                    | self.xcore.EventMask.FocusChange
            }), self))
        res.set_border(self.theme.hint.border_width)
        res.show()
        return res

    def toggle_border(self):
        if self.border_width == 0:
            self.set_border(self.theme.window.border_width)
        else:
            self.set_border(0)


