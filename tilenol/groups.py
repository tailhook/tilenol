from zorro.di import has_dependencies, dependency, di

from .screen import ScreenManager
from .event import Event
from .commands import CommandDispatcher


@has_dependencies
class GroupManager(object):

    screenman = dependency(ScreenManager, 'screen-manager')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, groups):
        self.groups = list(groups)
        self.current_group = self.groups[0]
        self.by_name = {g.name: g for g in self.groups}
        self.group_changed = Event('group-manager.group_changed')
        self.window_added = Event('group-manager.window_added')


    def __zorro_di_done__(self):
        # TODO(tailhook) implement several screens
        for g in self.groups:
            di(self).inject(g)
        scr = self.screenman.screens[0]
        self.bounds = scr.inner_bounds
        self.current_group.set_bounds(self.bounds)
        self.commander['group'] = self.current_group
        self.commander['layout'] = self.current_group.current_layout
        scr.add_listener(self.update_screen)

    def update_screen(self, screen):
        self.bounds = screen.inner_bounds
        self.current_group.set_bounds(self.bounds)

    def add_window(self, win):
        self.current_group.add_window(win)
        self.window_added.emit()

    def cmd_switch(self, name):
        ngr = self.by_name[name]
        if ngr is self.current_group:
            return
        self.current_group.hide()
        self.current_group = ngr
        self.current_group.set_bounds(self.bounds)
        ngr.show()
        self.commander['group'] = self.current_group
        self.commander['layout'] = self.current_group.current_layout
        self.group_changed.emit()


@has_dependencies
class Group(object):

    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, name, layout_class):
        self.name = name
        self.default_layout = layout_class
        self.current_layout = layout_class()
        self.floating_windows = []
        self.all_windows = []

    def __zorro_di_done__(self):
        di(self).inject(self.current_layout)

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)

    @property
    def empty(self):
        return not self.all_windows

    def add_window(self, win):
        if win.floating:
            # Ensure that floating windows are always above others
            win.frame.restack(win.xcore.StackMode.Above)
            self.floating_windows.append(win)
            win.show()
        else:
            # Ensure that non-floating windows are always below floating
            win.frame.restack(win.xcore.StackMode.Below)
            self.current_layout.add(win)
        win.group = self
        self.all_windows.append(win)

    def remove_window(self, win):
        assert win.group == self
        if win in self.floating_windows:
            self.floating_windows.remove(win)
        else:
            self.current_layout.remove(win)
        self.all_windows.remove(win)
        del win.group

    def hide(self):
        self.current_layout.hide_all()
        for win in self.floating_windows:
            win.hide()

    def set_bounds(self, rect):
        self.current_layout.set_bounds(rect)
        #for win in self.floating_windows:
        #    win.set_screen(rect)

    def show(self):
        self.current_layout.show_all()
        for win in self.floating_windows:
            #win.set_screen(self.bounds)
            win.show()

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
