from collections import namedtuple

from tilenol.screen import ScreenManager
from tilenol.events import EventDispatcher
from tilenol.ewmh import get_title
from tilenol.xcb import Core as XCore, Rectangle
from tilenol.commands import CommandDispatcher
from tilenol.event import Event
from tilenol.theme import Theme
from tilenol.window import DisplayWindow, Window
from tilenol.icccm import is_window_urgent
from .base import GadgetBase

from zorro.di import di, has_dependencies, dependency

WindowState = namedtuple('WindowState',
    ('title', 'icon', 'active', 'urgent', 'win'))


@has_dependencies
class State(object):

    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, gr):
        self._state = None
        self._group = gr

    def dirty(self):
        return self._state != self._read()

    def update(self):
        nval = self._read()
        if nval != self._state:
            self._state = nval
            return True

    def _read(self):
        cur = self.commander.get('window')
        gr = self._group
        subs = list(gr.current_layout.sublayouts())
        res = []
        for sec in subs:
            wins = sec.windows
            if wins:
                title = getattr(sec, 'title', sec.__class__.__name__)
                sect = [title]
                for win in wins:
                    sect.append(self._winstate(win, cur))
                res.append(sect)
        if gr.floating_windows:
            sect = ['floating']
            for win in gr.floating_windows:
                sect.append(self._winstate(win, cur))
        return res

    def _winstate(self, win, cur):
        return WindowState(
            title=get_title(win) or win.props.get("WM_CLASS") or hex(win),
            icon=getattr(win, 'icons', None),
            active=win is cur,
            urgent=is_window_urgent(win),
            win=win,
            )

    @property
    def sections(self):
        return self._state


@has_dependencies
class LeftBar(object):

    xcore = dependency(XCore, 'xcore')
    theme = dependency(Theme, 'theme')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, screen, width, groups, states):
        self.screen = screen
        self.width = width
        self._cairo = None
        self._img = None
        self.redraw = Event('leftbar.redraw')
        self.redraw.listen(self._redraw)
        self.repaint = Event('leftbar.repaint')
        self.repaint.listen(self._paint)
        self.screen.add_group_hook(self._group_hook)
        self.visible = False
        self.groups = groups
        self.states = states
        self._drawn_group = None

    def __zorro_di_done__(self):
        wid = self.xcore.create_toplevel(Rectangle(0, 0, 1, 1),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.BackPixel: self.theme.menu.background,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.EventMask: self.xcore.EventMask.Exposure,
            })
        self.window = di(self).inject(DisplayWindow(wid, self.paint))
        self.dispatcher.all_windows[wid] = self.window
        self.window.show()
        if self.screen.group:
            self._group_hook()
        self.commander.events['window'].listen(self._check_redraw)
        Window.any_window_changed.listen(self._check_redraw)

    def paint(self, rect):
        self.repaint.emit()

    def _check_redraw(self):
        st  = self.states.get(self.screen.group)
        if st is None or st.dirty:
            self.redraw.emit()

    def set_bounds(self, rect):
        self.bounds = rect
        self.window.set_bounds(rect)
        self._cairo = None
        self._img = None

    def _draw_section(self, title, y):
        ctx = self._cairo
        theme = self.theme.tabs
        ctx.set_source(theme.section_color_pat)
        sx, sy, tw, th, ax, ay = ctx.text_extents(title)
        y += theme.section_padding.top + th
        x = self.width - theme.section_padding.right - tw
        ctx.move_to(x, y)
        ctx.show_text(title)
        y += theme.section_padding.bottom
        return y

    def _draw_win(self, win, y):
        ctx = self._cairo
        theme = self.theme.tabs
        sx, sy, tw, th, ax, ay = ctx.text_extents(win.title)
        fh = th + theme.padding.top + theme.padding.bottom
        # Background
        if win.active:
            ctx.set_source(theme.active_bg_pat)
        elif win.urgent:
            ctx.set_source(theme.urgent_bg_pat)
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
        # Icon
        if hasattr(win.win, 'icons'):
            win.win.draw_icon(ctx,
                theme.margin.left + theme.padding.left,
                y + (th + theme.padding.top + theme.padding.bottom
                     - theme.icon_size)//2,
                theme.icon_size)
        # Title
        if win.active:
            ctx.set_source(theme.active_title_pat)
        elif win.urgent:
            ctx.set_source(theme.urgent_title_pat)
        else:
            ctx.set_source(theme.inactive_title_pat)
        x = theme.margin.left + theme.padding.left
        x += theme.icon_size + theme.icon_spacing
        ctx.move_to(x, y + theme.padding.top + th)
        y += th + theme.spacing + theme.padding.top + theme.padding.bottom
        ctx.show_text(win.title)
        ctx.fill()
        return y

    def _paint(self):
        self._img.draw(self.window)

    def _redraw(self):
        if not self.visible:
            return
        gr = self.screen.group
        st = self.states.get(gr)
        if st is None:
            st = self.states[gr] = di(self).inject(State(gr))
        if not st.update() and self._img and self._drawn_group == gr:
            return
        if self._img is None:
            self._img = self.xcore.pixbuf(self.width, self.bounds.height)
            self._cairo = self._img.context()
        theme = self.theme.tabs
        ctx = self._cairo
        ctx.set_source(theme.background_pat)
        ctx.rectangle(0, 0, self._img.width, self._img.height)
        ctx.fill()
        theme.font.apply(ctx)
        y = theme.margin.top
        for sec in st.sections:
            for win in sec:
                if isinstance(win, str):
                    y = self._draw_section(win, y)
                else:
                    y = self._draw_win(win, y)
        self._drawn_group = gr
        self.repaint.emit()

    def _group_hook(self):
        ngr = self.screen.group
        if ngr.name in self.groups:
            self.show()
        else:
            self.hide()
        self.redraw.emit()

    def show(self):
        if not self.visible:
            self.visible = True
            self.window.show()
            self.screen.slice_left(self)

    def hide(self):
        if self.visible:
            self.visible = False
            self.screen.unslice_left(self)
            self.window.hide()
            self._cairo = None
            self._img = None


@has_dependencies
class Tabs(GadgetBase):

    screens = dependency(ScreenManager, 'screen-manager')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, width=256, groups=()):
        self.bars = {}
        self.groups = set(groups)
        self.width = width
        self.states = {}

    def __zorro_di_done__(self):
        for s in self.screens.screens:
            bar = di(self).inject(LeftBar(s, self.width,
                                          self.groups, self.states))
            self.bars[s] = bar
            if s.group.name in self.groups:
                s.slice_left(bar)

    def cmd_toggle(self):
        gr = self.commander['group']
        if gr.name in self.groups:
            self.groups.remove(gr.name)
        else:
            self.groups.add(gr.name)
        self._update_bars()

    def cmd_show(self):
        gr = self.commander['group']
        self.groups.add(gr.name)
        self._update_bars()

    def cmd_hide(self):
        if gr.name in self.groups:
            self.groups.remove(gr.name)
        self._update_bars()

    def _update_bars(self):
        for s, bar in self.bars.items():
            if s.group.name in self.groups:
                bar.show()
            else:
                bar.hide()

