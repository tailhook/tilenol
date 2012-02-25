from zorro.di import has_dependencies, dependency

from .screen import ScreenManager


@has_dependencies
class GroupManager(object):

    screenman = dependency(ScreenManager, 'screen-manager')

    def __init__(self, groups):
        self.groups = list(groups)
        self.current_group = self.groups[0]
        self.by_name = {g.name: g for g in self.groups}

    def __zorro_di_done__(self):
        # TODO(tailhook) implement several screens
        scr = self.screenman.screens[0]
        self.bounds = scr.inner_bounds
        self.current_group.set_bounds(self.bounds)
        scr.add_listener(self.update_screen)

    def update_screen(self, screen):
        self.bounds = screen.inner_bounds
        self.current_group.set_bounds(self.bounds)

    def add_window(self, win):
        self.current_group.add_window(win)

    def cmd_switch(self, name):
        ngr = self.by_name[name]
        if ngr is self.current_group:
            return
        self.current_group.hide()
        self.current_group = ngr
        self.current_group.set_bounds(self.bounds)
        ngr.show()


class Group(object):

    def __init__(self, name, layout_class):
        self.name = name
        self.default_layout = layout_class
        self.current_layout = layout_class()
        self.floating_windows = []

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)

    def add_window(self, win):
        self.current_layout.add(win)
        win.group = self
        # TODO(tailhook) may be optimize dirty flag?
        if self.current_layout.dirty:
            self.current_layout.layout()

    def remove_window(self, win):
        assert win.group == self
        self.current_layout.remove(win)
        del win.group
        # TODO(tailhook) may be optimize dirty flag?
        if self.current_layout.dirty:
            self.current_layout.layout()

    def hide(self):
        self.current_layout.hide_all()
        for win in self.floating_windows:
            win.hide()

    def set_bounds(self, rect):
        self.current_layout.set_bounds(rect)
        # TODO(tailhook) constrain floating windows

    def show(self):
        self.current_layout.show_all()
        for win in self.floating_windows:
            win.show()
