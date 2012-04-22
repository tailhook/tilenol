import struct

from zorro.di import di, dependency, has_dependencies

from .base import Widget
from tilenol.xcb import Core, Rectangle
from tilenol.events import EventDispatcher
from tilenol.window import ClientMessageWindow, Window, Rectangle
from tilenol.theme import Theme


class TrayIcon(Window):

    def destroyed(self):
        super().destroyed()
        self.systray.remove(self)


@has_dependencies
class Systray(Widget):

    xcore = dependency(Core, 'xcore')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    theme = dependency(Theme, 'theme')

    def __init__(self, *, right=False):
        super().__init__(right=right)
        self.icons = []

    def __zorro_di_done__(self):
        self.padding = self.theme.bar.box_padding
        self.spacing = self.theme.bar.icon_spacing
        self.create_window()

    def create_window(self):
        self.window = di(self).inject(ClientMessageWindow(
            self.xcore.create_toplevel(
                Rectangle(0, 0, 1, 1),
                klass=self.xcore.WindowClass.InputOnly,
                params={}),
            self.systray_message))
        self.window.show()
        self.dispatcher.register_window(self.window)
        self.xcore.raw.SetSelectionOwner(
            owner=self.window.wid,
            selection=self.xcore.atom._NET_SYSTEM_TRAY_S0,
            time=0,
            )
        print("OWNER", self.xcore.raw.GetSelectionOwner(
            selection=self.xcore.atom._NET_SYSTEM_TRAY_S0,
            ))
        self.xcore.send_event('ClientMessage',
            self.xcore.EventMask.StructureNotify,
            self.xcore.root_window,
            window=self.xcore.root_window,
            type=self.xcore.atom.MANAGER,
            format=32,
            data=struct.pack('<LLL',
                0,
                self.xcore.atom._NET_SYSTEM_TRAY_S0,
                self.window.wid,
                ))

    def systray_message(self, msg):
        assert msg.type == self.xcore.atom._NET_SYSTEM_TRAY_OPCODE
        tm, op, wid, _, _ = struct.unpack('<LLLLL', msg.data)
        if op == 0:  # REQUEST_DOCK
            win = self.dispatcher.windows[wid]
            win.__class__ = TrayIcon
            win.systray = self
            win.reparent_to(self.bar.window)
            self.xcore.raw.ChangeWindowAttributes(window=win, params={
                self.xcore.CW.BackPixel: self.theme.bar.background,
                self.xcore.CW.EventMask:
                    self.xcore.EventMask.ResizeRedirect,
            })
            self.icons.append(win)
            win.show()
            self.bar.redraw.emit()
        elif op == 1:  # BEGIN_MESSAGE
            pass
        elif op == 2:  # CANCEL_MESSAGE
            pass

    def remove(self, icon):
        self.icons.remove(icon)
        self.bar.redraw.emit()

    def draw(self, canvas, l, r):
        l = int(l)
        r = int(r)
        t = self.padding.top
        h = self.bar.height - self.padding.bottom - t
        if self.right:
            r -= self.padding.right
            for i in reversed(self.icons):
                i.set_bounds(Rectangle(r-h, t, h, h))
                r -= h + self.spacing
            r += self.spacing
            r -= self.padding.left
        else:
            l += self.padding.left
            for i in self.icons:
                i.set_bounds(Rectangle(l, t, h, h))
                l += h + self.spacing
            l -= self.spacing
            l += self.padding.right
        return l, r

