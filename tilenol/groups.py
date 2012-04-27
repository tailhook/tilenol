from itertools import chain

from zorro.di import has_dependencies, dependency, di

from .screen import ScreenManager
from .event import Event
from .icccm import is_window_urgent
from .commands import CommandDispatcher
from .config import Config


@has_dependencies
class GroupManager(object):

    screenman = dependency(ScreenManager, 'screen-manager')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, groups):
        self.groups = list(groups)
        self.by_name = {g.name: g for g in self.groups}
        self.group_changed = Event('group-manager.group_changed')
        for g in self.groups:
            g.manager = self

    def __zorro_di_done__(self):
        # TODO(tailhook) implement several screens
        for g in self.groups:
            di(self).inject(g)
        self.current_groups = {}
        for i, s in enumerate(self.screenman.screens):
            gr = self.groups[i]
            self.current_groups[s] = gr
            gr.screen = s
            gr.show()
            if i == 0:
                self.commander['group'] = gr
                self.commander['screen'] = s
                self.commander['layout'] = g.current_layout

    def add_window(self, win):
        if(isinstance(win.lprops.group, int)
           and win.lprops.group < len(self.groups)):
            ngr = self.groups[win.lprops.group]
        elif 'group' in self.commander:
            ngr = self.commander['group']
        else:
            ngr = self.current_groups[self.screenman.screens[0]]
        ngr.add_window(win)
        win.lprops.group = self.groups.index(ngr)

    def cmd_switch(self, name):
        ngr = self.by_name[name]
        ogr = self.commander['group']
        if ngr is ogr:
            return
        if ngr in self.current_groups.values():
            ogr.screen, ngr.screen = ngr.screen, ogr.screen
            self.current_groups[ngr.screen] = ngr
            self.current_groups[ogr.screen] = ogr
        else:
            ogr.hide()
            s = ogr.screen
            ogr.screen = None
            self.current_groups[s] = ngr
            ngr.screen = s
            ngr.show()
        self.commander['group'] = ngr
        self.commander['layout'] = ngr.current_layout
        self.commander['screen'] = ngr.screen
        self.group_changed.emit()

    def cmd_move_window_to(self, name):
        ngr = self.by_name[name]
        if 'window' not in self.commander:
            return
        win = self.commander['window']
        if ngr is win.group:
            return
        win.group.remove_window(win)
        win.hide()
        ngr.add_window(win)
        win.lprops.group = self.groups.index(ngr)


@has_dependencies
class Group(object):

    commander = dependency(CommandDispatcher, 'commander')
    config = dependency(Config, 'config')

    def __init__(self, name, layout_class):
        self.name = name
        self.default_layout = layout_class
        self.current_layout = layout_class()
        self.current_layout.group = self
        self.floating_windows = []
        self.all_windows = []
        self._screen = None

    def __zorro_di_done__(self):
        di(self).inject(self.current_layout)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)

    @property
    def empty(self):
        return not self.all_windows

    def focus(self):
        all = list(self.current_layout.all_visible_windows())
        all.extend(self.floating_windows)
        if all:
            all[0].focus()
        else:
            self.commander['layout'] = self.current_layout
            self.commander['group'] = self
            self.commander['screen'] = self.screen
        self.manager.group_changed.emit()

    def add_window(self, win):
        if win.lprops.floating:
            # Ensure that floating windows are always above others
            win.frame.restack(win.xcore.StackMode.Above)
            self.floating_windows.append(win)
            if self.screen:
                win.show()
        else:
            # Ensure that non-floating windows are always below floating
            win.frame.restack(win.xcore.StackMode.Below)
            self.current_layout.add(win)
        win.group = self
        self.all_windows.append(win)
        self.check_focus()

    def remove_window(self, win):
        assert win.group == self
        if win in self.floating_windows:
            self.floating_windows.remove(win)
        else:
            self.current_layout.remove(win)
        self.all_windows.remove(win)
        del win.group

    def hide(self):
        self.current_layout.hide()
        for win in self.floating_windows:
            win.hide()

    @property
    def screen(self):
        return self._screen

    @screen.setter
    def screen(self, screen):
        if self._screen:
            self._screen.updated.unlisten(self.update_size)
        self._screen = screen
        if screen is not None:
            screen.set_group(self)
            screen.updated.listen(self.update_size)
            self.set_bounds(screen.inner_bounds)

    def update_size(self):
        self.set_bounds(self.screen.inner_bounds)

    def set_bounds(self, rect):
        self.current_layout.set_bounds(rect)
        #for win in self.floating_windows:
        #    win.set_screen(rect)

    def show(self):
        self.current_layout.show()
        for win in self.floating_windows:
            # TODO(tailhook) fix bounds when showing at different screen
            #win.set_screen(self.bounds)
            win.show()
        self.check_focus()

    def check_focus(self):
        if 'window' not in self.commander:
            try:
                win = next(iter(chain(
                    self.current_layout.all_visible_windows(),
                    self.floating_windows,
                    )))
            except StopIteration:
                pass
            else:
                win.frame.focus()

    @property
    def has_urgent_windows(self):
        return any(is_window_urgent(win) for win in self.all_windows)

    def cmd_focus_next(self):
        all = list(self.current_layout.all_visible_windows())
        all.extend(self.floating_windows)
        try:
            win = self.commander['window']
        except KeyError:
            nwin = all[0]
        else:
            idx = all.index(win)
            if idx + 1 >= len(all):
                nwin = all[0]
            else:
                nwin = all[idx+1]
        nwin.frame.focus()

    def cmd_focus_prev(self):
        all = list(self.current_layout.all_visible_windows())
        all.extend(self.floating_windows)
        try:
            win = self.commander['window']
        except KeyError:
            nwin = all[-1]
        else:
            idx = all.index(win)
            if idx > 0:
                nwin = all[idx - 1]
            else:
                nwin = all[-1]
        nwin.frame.focus()

    def cmd_set_layout(self, name):
        if self.screen:
            self.hide()
        lay = self.config.all_layouts()[name]
        self.current_layout = di(self).inject(lay())
        self.current_layout.group = self
        for win in self.all_windows:
            if not win.lprops.floating:
                self.current_layout.add(win)
        if self.screen:
            self.set_bounds(self.screen.inner_bounds)
            self.show()
