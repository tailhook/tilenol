import logging

from zorro.di import di, has_dependencies, dependency

from .keyregistry import KeyRegistry
from .mouseregistry import MouseRegistry
from .window import Window
from .xcb import Core, Rectangle, XError
from .groups import GroupManager
from .commands import CommandDispatcher
from .classify import Classifier
from .screen import ScreenManager
from .event import Event


log = logging.getLogger(__name__)


@has_dependencies
class EventDispatcher(object):

    keys = dependency(KeyRegistry, 'key-registry')
    mouse = dependency(MouseRegistry, 'mouse-registry')
    xcore = dependency(Core, 'xcore')
    groupman = dependency(GroupManager, 'group-manager')
    screenman = dependency(ScreenManager, 'screen-manager')
    classifier = dependency(Classifier, 'classifier')

    def __init__(self):
        self.windows = {}
        self.frames = {}
        self.all_windows = {}
        self.active_field = None
        self.mapping_notify = Event('mapping_notify')
        self.mapping_notify.listen(self._mapping_notify_delayed)

    def dispatch(self, ev):
        meth = getattr(self, 'handle_'+ev.__class__.__name__, None)
        if meth:
            meth(ev)
        else:
            log.warning("Unknown event ``%r''", ev)

    def register_window(self, win):
        self.all_windows[win.wid] = win

    def handle_KeyPressEvent(self, ev):
        if not self.keys.dispatch_event(ev):
            if self.active_field:
                self.active_field.handle_keypress(ev)

    def handle_KeyReleaseEvent(self, ev):
        pass  # nothing to do at the moment

    def handle_ButtonPressEvent(self, ev):
        self.mouse.dispatch_button_press(ev)

    def handle_ButtonReleaseEvent(self, ev):
        self.mouse.dispatch_button_release(ev)

    def handle_MotionNotifyEvent(self, ev):
        self.mouse.dispatch_motion(ev)

    def handle_MapRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %r",
                ev.window)
        else:
            win.want.visible = True
            if win.frame is None:
                frm = win.create_frame()
                self.frames[frm.wid] = frm
                self.all_windows[frm.wid] = frm
            win.reparent_frame()
            if not hasattr(win, 'group'):
                self.classifier.apply(win)
                self.groupman.add_window(win)

    def handle_EnterNotifyEvent(self, ev):
        if self.mouse.drag:
            return
        try:
            win = self.frames[ev.event]
        except KeyError:
            log.warning("Enter notify for non-existent window %r", ev.event)
        else:
            if ev.mode != self.xcore.NotifyMode.Grab:
                win.pointer_enter()
            if self.active_field:
                return
            if(win.props.get("WM_HINTS") is None
                or win.props.get('WM_HINTS')[0] & 1):
                win.focus()

    def handle_LeaveNotifyEvent(self, ev):
        if self.mouse.drag:
            return
        try:
            win = self.frames[ev.event]
        except KeyError:
            log.warning("Leave notify for non-existent window %r", ev.event)
        else:
            if ev.mode != self.xcore.NotifyMode.Grab:
                win.pointer_leave()

    def handle_MapNotifyEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Map notify for non-existent window %r",
                ev.window)
        else:
            win.real.visible = True

    def handle_UnmapNotifyEvent(self, ev):
        if ev.event not in self.frames:
            return # do not need to track unmapping of unmanaged windows
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Unmap notify for non-existent window %r",
                ev.window)
        else:
            win.real.visible = False
            win.done.visible = False
            if win.frame:
                win.ewmh.hiding_window(win)
                win.frame.hide()
                win.reparent_root()
            if hasattr(win, 'group'):
                win.group.remove_window(win)

    def handle_FocusInEvent(self, ev):
        try:
            win = self.all_windows[ev.event]
        except KeyError:
            if(ev.event == self.xcore.root_window
                    and ev.mode not in (self.xcore.NotifyMode.Grab,
                                        self.xcore.NotifyMode.Ungrab)
                    and ev.detail == getattr(self.xcore.NotifyDetail, 'None')):
                self.xcore.raw.SetInputFocus(
                    focus=self.xcore.root_window,
                    revert_to=self.xcore.InputFocus.PointerRoot,
                    time=self.xcore.last_time,
                    )
                return
            log.warning("Focus request for non-existent window %r",
                ev.event)
        else:
            if(ev.mode not in (self.xcore.NotifyMode.Grab,
                               self.xcore.NotifyMode.Ungrab)
               and ev.detail != self.xcore.NotifyDetail.Pointer):
                win.focus_in()

    def handle_FocusOutEvent(self, ev):
        try:
            win = self.all_windows[ev.event]
        except KeyError:
            log.warning("Focus request for non-existent window %r",
                ev.event)
        else:
            if(ev.mode not in (self.xcore.NotifyMode.Grab,
                               self.xcore.NotifyMode.Ungrab)
               and ev.detail != self.xcore.NotifyDetail.Pointer):
                win.focus_out()

    def handle_CreateNotifyEvent(self, ev):
        win = di(self).inject(Window.from_notify(ev))
        if win.wid in self.windows:
            log.warning("Create notify for already existent window %r",
                win.wid)
            # TODO(tailhook) clean up old window
        if win.wid in self.all_windows:
            return
        win.done.size = win.want.size
        self.xcore.raw.ChangeWindowAttributes(window=win, params={
                self.xcore.CW.EventMask: self.xcore.EventMask.PropertyChange
            })
        self.windows[win.wid] = win
        self.all_windows[win.wid] = win
        try:
            for name in self.xcore.raw.ListProperties(window=win)['atoms']:
                win.update_property(name)
        except XError:
            log.warning("Window destroyed immediately %d", win.wid)

    def handle_ConfigureNotifyEvent(self, ev):
        pass

    def handle_ReparentNotifyEvent(self, ev):
        pass

    def handle_DestroyNotifyEvent(self, ev):
        try:
            win = self.all_windows.pop(ev.window)
        except KeyError:
            log.warning("Destroy notify for non-existent window %r",
                ev.window)
        else:
            self.windows.pop(win.wid, None)
            self.frames.pop(win.wid, None)
            if hasattr(win, 'group'):
                win.group.remove_window(win)
            win.destroyed()

    def handle_ConfigureRequestEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Configure request for non-existent window %r",
                ev.window)
        else:
            win.update_size_request(ev)

    def handle_PropertyNotifyEvent(self, ev):
        try:
            win = self.windows[ev.window]
        except KeyError:
            log.warning("Property notify event for non-existent window %r",
                ev.window)
        else:
            win.update_property(ev.atom)

    def handle_ExposeEvent(self, ev):
        try:
            win = self.all_windows[ev.window]
        except KeyError:
            log.warning("Expose event for non-existent window %r",
                ev.window)
        else:
            win.expose(Rectangle(ev.x, ev.y, ev.width, ev.height))

    def handle_ClientMessageEvent(self, ev):
        type = self.xcore.atom[ev.type]
        import struct
        print("ClientMessage", ev, repr(type), struct.unpack('<5L', ev.data))
        self.all_windows[ev.window].client_message(ev)

    def handle_ScreenChangeNotifyEvent(self, ev):
        # We only poll for events and use Xinerama for screen querying
        # because some drivers (nvidia) doesn't provide xrandr data
        # correctly
        info = self.xcore.xinerama.QueryScreens()['screen_info']
        self.screenman.update(list(
            Rectangle(scr['x_org'], scr['y_org'],
                scr['width'], scr['height']) for scr in info))
        self.groupman.check_screens()

    # This notify event is CrtcNotify from xrandr
    handle_NotifyEvent = handle_ScreenChangeNotifyEvent

    def handle_MappingNotifyEvent(self, ev):
        self.mapping_notify.emit()

    def _mapping_notify_delayed(self):
        self.keys.reconfigure_keys()

