from zorro.di import has_dependencies, dependency

from .xcb import Core, Rectangle
from .commands import CommandDispatcher


class Drag(object):

    def __init__(self, win, x, y):
        self.win = win
        if self.win.frame:
            self.win = self.win.frame
        self.hint = self.win.add_hint()
        self.start(x, y)
        self.update_hint()

    def moved_to(self, x, y):
        self.motion(x + self.x, y + self.y)
        self.update_hint()

    def update_hint(self):
        sz = self.win.done.size
        txt = '{}, {} {}x{}'.format(*sz)
        if hasattr(self.win, 'content'):
            hints = self.win.content.want.hints
        else:
            hints = self.win.want.hints
        if hints:
            bw = getattr(hints, 'base_width', 0)
            bh = getattr(hints, 'base_height', 0)
            if hasattr(hints, 'width_inc'):
                if hasattr(hints, 'height_inc'):
                    txt += '\n{} cols {} rows'.format(
                        (sz.width - bw)//hints.width_inc,
                        (sz.height - bh)//hints.height_inc,
                        )
                else:
                    txt += '\n{} cols'.format((sz.width - bw)//hints.width_inc)
            elif hasattr(hints, 'height_inc'):
                txt += '\n{} rows'.format((sz.height - bh)//hints.height_inc)
        self.hint.set_text(txt)
        hsz = self.hint.done.size
        wsz = self.win.done.size
        self.hint.set_bounds(Rectangle(
            (wsz.width - hsz.width)//2,
            (wsz.height - hsz.height)//2,
            hsz.width, hsz.height))

    def stop(self):
        self.hint.destroy()


class DragMove(Drag):

    def start(self, x, y):
        sz = self.win.done.size
        self.x = sz.x - x
        self.y = sz.y - y

    def motion(self, x, y):
        sz = self.win.done.size
        self.win.set_bounds(Rectangle(x, y, sz.width, sz.height))


class DragSizeBottomRight(Drag):

    def start(self, x, y):
        sz = self.win.done.size
        self.x = sz.width - x
        self.y = sz.height - y

    def motion(self, x, y):
        sz = self.win.done.size
        self.win.set_bounds(Rectangle(sz.x, sz.y, x, y))


class DragSizeTopRight(Drag):

    def start(self, x, y):
        sz = self.win.done.size
        self.x = sz.width - x
        self.y = sz.y - y
        self.bottom = sz.height + sz.y

    def motion(self, x, y):
        sz = self.win.done.size
        self.win.set_bounds(Rectangle(sz.x, y, x, self.bottom - y))

class DragSizeBottomLeft(Drag):

    def start(self, x, y):
        sz = self.win.done.size
        self.x = sz.x - x
        self.y = sz.height - y
        self.right = sz.x + sz.width

    def motion(self, x, y):
        sz = self.win.done.size
        self.win.set_bounds(Rectangle(x, sz.y, self.right - x, y))


class DragSizeTopLeft(Drag):

    def start(self, x, y):
        sz = self.win.done.size
        self.x = sz.x - x
        self.y = sz.y - y
        self.bottom = sz.height + sz.y
        self.right = sz.width + sz.x

    def motion(self, x, y):
        sz = self.win.done.size
        self.win.set_bounds(Rectangle(x, y, self.right - x, self.bottom - y))


@has_dependencies
class MouseRegistry(object):

    core = dependency(Core, 'xcore')
    commander = dependency(CommandDispatcher, 'commander')

    drag_classes = { # (is_right, is_bottom): Class
        (True, True): DragSizeBottomRight,
        (True, False): DragSizeTopRight,
        (False, False): DragSizeTopLeft,
        (False, True): DragSizeBottomLeft,
        }

    def __init__(self):
        self.drag = None

    def init_buttons(self):
        self.mouse_buttons = [
            (getattr(self.core.ModMask, '4'), 1),
            (getattr(self.core.ModMask, '4'), 3),
            ]

    def init_modifiers(self):
        # TODO(tailhook) probably calculate them instead of hardcoding
        caps = self.core.ModMask.Lock  # caps lock
        num = getattr(self.core.ModMask, '2')  # mod2 is usually numlock
        mode = getattr(self.core.ModMask, '5')  # mod5 is usually mode_switch
        self.extra_modifiers = [0,
            caps,
            num,
            mode,
            caps|num,
            num|mode,
            caps|num|mode,
            ]
        self.modifiers_mask = ~(caps|num|mode)

    def register_buttons(self, win):
        self.init_modifiers()
        for mod, button in self.mouse_buttons:
            for extra in self.extra_modifiers:
                self.core.raw.GrabButton(
                    modifiers=mod|extra,
                    button=button,
                    owner_events=True,
                    grab_window=win,
                    event_mask=self.core.EventMask.ButtonRelease
                             | self.core.EventMask.PointerMotion,
                    confine_to=0,
                    keyboard_mode=self.core.GrabMode.Async,
                    pointer_mode=self.core.GrabMode.Async,
                    cursor=0,  # TODO(tailhook) make apropriate cursor
                    )

    def dispatch_button_press(self, ev):
        if 'window' not in self.commander:
            return
        win = self.commander['window']
        if not win.floating:
            win.make_floating()
        else:
            win.frame.restack(self.core.StackMode.TopIf)
        if ev.detail == 1:
            self.drag = DragMove(win, ev.root_x, ev.root_y)
        elif ev.detail == 3:
            sz = win.done.size
            right = (ev.root_x - sz.x) * 2 >= sz.width
            bottom = (ev.root_y - sz.y) * 2 >= sz.height
            self.drag = self.drag_classes[right, bottom](
                win, ev.root_x, ev.root_y)

    def dispatch_button_release(self, ev):
        if not self.drag:
            return
        self.drag.moved_to(ev.root_x, ev.root_y)
        self.drag.stop()
        self.drag = None

    def dispatch_motion(self, ev):
        if not self.drag:
            return
        self.drag.moved_to(ev.root_x, ev.root_y)

