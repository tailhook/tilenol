import logging

from zorro.di import di, has_dependencies, dependency

from .keyregistry import KeyRegistry
from .window import Window, Frame
from .xcb import Core, Rectangle, XError
from .groups import GroupManager


log = logging.getLogger(__name__)


@has_dependencies
class EventDispatcher(object):

    keys = dependency(KeyRegistry, 'key-registry')
    xcore = dependency(Core, 'xcore')
    groupman = dependency(GroupManager, 'group-manager')

    def __init__(self):
        self.windows = {}
        self.frames = {}
        self.all_windows = {}
        self.focused = None

    def dispatch(self, ev):
        meth = getattr(self, 'handle_'+ev.__class__.__name__, None)
        if meth:
            meth(ev)
        else:
            print("EVENT", ev)

    def handle_KeyPressEvent(self, ev):
        self.keys.dispatch_event(ev)

    def handle_KeyReleaseEvent(self, ev):
        pass  # nothing to do at the moment

    def handle_MapRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %x",
                ev.window)
        else:
            win.want.visible = True
            if not win.done.layouted:
                if self.groupman.add_window(win):
                    win.done.layouted = True

            # TODO(tailhook) find a better place

    def handle_EnterNotifyEvent(self, ev):
        try:
            win = self.frames[ev.event]
        except KeyError:
            log.warning("Enter notify for non-existent window %x",
                ev.window)
        else:
            win.focus(ev)
            self.focused = win

    def handle_MapNotifyEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Map notify for non-existent window %x",
                ev.window)
        else:
            win.real.visible = True

    def handle_UnmapNotifyEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Unmap notify for non-existent window %x",
                ev.window)
        else:
            win.real.visible = False

    def handle_CreateNotifyEvent(self, ev):
        win = di(self).inject(Window.from_notify(ev))
        if win.wid in self.frames:
            return
        if win.wid in self.windows:
            log.warning("Create notify for already existent window %x",
                win.wid)
            # TODO(tailhook) clean up old window
        self.windows[win.wid] = win
        self.all_windows[win.wid] = win
        if win.toplevel and not win.override:
            frm = win.reparent()
            self.frames[frm.wid] = frm
            self.all_windows[frm.wid] = frm

    def handle_ConfigureRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %x",
                ev.window)
        else:
            win.update_size_request(ev)

    def handle_PropertyNotifyEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Property notify event for non-existent window %x",
                ev.window)
        else:
            try:
                win.set_property(self.xcore.atom[ev.atom].name,
                      *self.xcore.get_property(ev.window, ev.atom))
            except XError:
                log.exception("Error getting property for window %x",
                    ev.window)
