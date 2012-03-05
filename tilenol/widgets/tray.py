import struct

from zorro.di import di, dependency, has_dependencies

from .base import Widget, Padding
from tilenol.xcb import Core, Rectangle
from tilenol.events import EventDispatcher
from tilenol.window import ClientMessageWindow, Window, Rectangle


class TrayIcon(Window):

    def destroyed(self):
        print("TRAY ICON")
        super().destroyed()
        self.systray.remove(self)


@has_dependencies
class Systray(Widget):

    xcore = dependency(Core, 'xcore')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')

    def __init__(self, *,
        padding=Padding(2, 2, 2, 2),
        spacing=2,
        right=False):
        super().__init__(right=right)
        self.padding = padding
        self.spacing = spacing
        self.icons = []

    def __zorro_di_done__(self):
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
                self.xcore.CW.BackPixel: 0x000000,
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

