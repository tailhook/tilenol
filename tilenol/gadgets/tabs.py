from tilenol.screen import ScreenManager
from tilenol.events import EventDispatcher
from tilenol.ewmh import get_title
from tilenol.xcb import Core as XCore, Rectangle
from tilenol.commands import CommandDispatcher
from tilenol.event import Event
from tilenol.theme import Theme
from tilenol.window import DisplayWindow
from .base import GadgetBase

from zorro.di import di, has_dependencies, dependency


@has_dependencies
class LeftBar(object):

    xcore = dependency(XCore, 'xcore')
    theme = dependency(Theme, 'theme')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, screen, width):
        self.screen = screen
        self.width = width
        self._cairo = None
        self._img = None
        self._oldgroup = None
        self._subscribed_windows = set()
        self.redraw = Event('leftbar.redraw')
        self.redraw.listen(self._redraw)
        self.screen.add_group_hook(self._group_hook)

    def __zorro_di_done__(self):
        wid = self.xcore.create_toplevel(Rectangle(0, 0, 1, 1),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.BackPixel: self.theme.menu.background,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask: self.xcore.EventMask.Exposure,
            })
        self.window = di(self).inject(DisplayWindow(wid, self.draw))
        self.dispatcher.all_windows[wid] = self.window
        self.window.show()
        if self.screen.group:
            self._group_hook()
        self.commander.events['window'].listen(self._redraw)

    def draw(self, rect):
        self.redraw.emit()

    def set_bounds(self, rect):
        self.bounds = rect
        self.window.set_bounds(rect)
        self._cairo = None
        self._img = None

    def _redraw(self):
        drawn_windows = set()
        if self._img is None:
            self._img = self.xcore.pixbuf(self.width, self.bounds.height)
            self._cairo = self._img.context()
        theme = self.theme.tabs
        ctx = self._cairo
        ctx.set_source(theme.background_pat)
        ctx.rectangle(0, 0, self._img.width, self._img.height)
        ctx.fill()
        theme.font.apply(ctx)
        gr = self.screen.group
        y = theme.margin.top
        focused = self.commander.get('window')
        for win in gr.all_windows:
            title = get_title(win) or win.props.get("WM_CLASS") or hex(win)
            drawn_windows.add(win)
            sx, sy, tw, th, ax, ay = ctx.text_extents(title)
            fh = th + theme.padding.top + theme.padding.bottom
            if focused is win:
                ctx.set_source(theme.active_bg_pat)
            else:
                ctx.set_source(theme.inactive_bg_pat)
            ctx.move_to(self.width, y)
            ctx.line_to(theme.margin.left + theme.border_radius, y)
            ctx.curve_to(theme.margin.left + theme.border_radius/3, y,
                theme.margin.left, y + theme.border_radius/3,
                theme.margin.left, y + theme.border_radius)
            ctx.line_to(theme.margin.left, y + fh - theme.border_radius)
            ctx.curve_to(theme.margin.left, y + fh - theme.border_radius/3,
                theme.margin.left + theme.border_radius/3, y + fh,
                theme.margin.left + theme.border_radius, y + fh)
            ctx.line_to(self.width, y + fh)
            ctx.close_path()
            ctx.fill()
            if focused is win:
                ctx.set_source(theme.active_title_pat)
            else:
                ctx.set_source(theme.inactive_title_pat)
            ctx.move_to(theme.margin.left + theme.padding.left,
                        y + theme.padding.top + th)
            y += th + theme.spacing + theme.padding.top + theme.padding.bottom
            ctx.show_text(title)
            ctx.fill()
        self._img.draw(self.window)
        # update subscriptions
        unsub = self._subscribed_windows - drawn_windows
        for w in unsub:
            w.property_changed.unlisten(self.redraw.emit)
        sub = drawn_windows - self._subscribed_windows
        for w in sub:
            w.property_changed.listen(self.redraw.emit)
        self._subscribed_windows = drawn_windows

    def _group_hook(self):
        if self._oldgroup:
            self._oldgroup.windows_changed.unlisten(self.redraw.emit)
        self.screen.group.windows_changed.listen(self.redraw.emit)
        self._oldgroup = self.screen.group


@has_dependencies
class Tabs(GadgetBase):

    screens = dependency(ScreenManager, 'screen-manager')

    def __init__(self, width=256):
        self.bars = {}
        self.width = width

    def __zorro_di_done__(self):
        for s in self.screens.screens:
            bar = di(self).inject(LeftBar(s, self.width))
            self.bars[s] = bar
            s.slice_left(bar)

