import logging

from zorro.di import di, has_dependencies, dependency

from .keyregistry import KeyRegistry
from .window import Window, Frame


log = logging.getLogger(__name__)


@has_dependencies
class EventDispatcher(object):

    keys = dependency(KeyRegistry, 'key-registry')

    def __init__(self):
        self.windows = {}
        self.frames = {}

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
            win.show()

    def handle_EnterNotifyEvent(self, ev):
        try:
            win = self.frames[ev.event]
        except KeyError:
            log.warning("Enter notify for non-existent window %x",
                ev.window)
        else:
            win.focus(ev)


    def handle_MapNotifyEvent(self, ev):
        pass  # TODO(tailhook) mark window as visible

    def handle_CreateNotifyEvent(self, ev):
        win = di(self).inject(Window.from_notify(ev))
        if win.wid in self.frames:
            return
        if win.wid in self.windows:
            log.warning("Create notify for already existent window %x",
                win.wid)
            # TODO(tailhook) clean up old window
        self.windows[win.wid] = win
        if win.toplevel and not win.override:
            frm = win.reparent()
            self.frames[frm.wid] = frm

    def handle_ConfigureRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %x",
                ev.window)
        else:
            win.update_size_request(ev)
