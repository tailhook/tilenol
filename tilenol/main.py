from functools import partial
import sys
import subprocess
import os.path
import signal
import logging

from zorro.di import DependencyInjector, di, has_dependencies, dependency

from .xcb import Connection, Proto, Core, Keysyms, Rectangle
from .keyregistry import KeyRegistry
from .mouseregistry import MouseRegistry
from .ewmh import Ewmh
from .window import Window
from .events import EventDispatcher
from .commands import CommandDispatcher, EnvCommands
from .config import Config
from .groups import Group, GroupManager
from .screen import ScreenManager
from .classify import Classifier


log = logging.getLogger(__name__)


def child_handler(sig, frame):
    while True:
        try:
            pid, result = os.waitpid(-1, os.WNOHANG)
            if pid is 0:
                break
        except OSError:
            break

@has_dependencies
class Tilenol(object):

    xcore = dependency(Core, 'xcore')
    dispatcher = dependency(EventDispatcher, 'event-dispatcher')
    config = dependency(Config, 'config')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self, options):
        pass
        # extract options needed

    def register_hotkeys(self, keys):
        for key, cmd in self.config.keys():
            keys.add_key(key, self.commander.callback(*cmd))
        keys.register_keys(self.root_window)

    def run(self):

        proto = Proto()
        proto.load_xml('xproto')
        self.conn = conn = Connection(proto)
        conn.connection()
        self.root_window = Window(conn.init_data['roots'][0]['root'])

        inj = DependencyInjector()
        inj['xcore'] = xcore = Core(conn)
        inj['keysyms'] = keysyms = Keysyms()
        keysyms.load_default()
        inj['config'] = inj.inject(Config())
        # TODO(tailhook) query xinerama screens
        inj['screen-manager'] = ScreenManager([Rectangle(0, 0,
            xcore.root['width_in_pixels'], xcore.root['height_in_pixels'])])

        inj['commander'] = cmd = inj.inject(CommandDispatcher())
        cmd['env'] = EnvCommands()
        cmd['tilenol'] = self
        keys = KeyRegistry()
        inj['key-registry'] = inj.inject(keys)
        mouse = MouseRegistry()
        inj['mouse-registry'] = inj.inject(mouse)

        from .layout.examples import Tile, Max, InstantMsg, Gimp
        gman = inj.inject(GroupManager(map(inj.inject, (
                Group('1', Tile),
                Group('2', Max),
                Group('3', Tile),
                Group('4', Tile),
                Group('5', Tile),
                Group('g', Gimp),
                Group('i', InstantMsg),
                Group('m', Max),
            ))))
        cmd['groups'] = gman
        inj['group-manager'] = gman
        inj['classifier'] = inj.inject(Classifier())
        inj['classifier'].default_rules()
        inj['event-dispatcher'] = inj.inject(EventDispatcher())
        inj['ewmh'] = Ewmh()
        inj.inject(inj['ewmh'])

        inj.inject(self)

        self.xcore.init_keymap()
        self.register_hotkeys(keys)
        mouse.init_buttons()
        mouse.register_buttons(self.root_window)
        self.setup_events()

        from .widgets import Bar, Groupbox, Clock, Sep
        self.bar = inj.inject(Bar([
            Groupbox(),
            Sep(),
            Clock(right=True),
            Sep(right=True),
            ]))
        self.bar.create_window()

        signal.signal(signal.SIGCHLD, child_handler)
        self.loop()

    def setup_events(self):
        EM = self.xcore.EventMask
        self.xcore.raw.ChangeWindowAttributes(
            window=self.root_window,
            params={
                self.xcore.CW.EventMask: EM.StructureNotify
                                       | EM.SubstructureNotify
                                       | EM.SubstructureRedirect
            })
        attr = self.xcore.raw.GetWindowAttributes(window=self.root_window)
        if not (attr['your_event_mask'] & EM.SubstructureRedirect):
            print("Probably another window manager is running", file=sys.stderr)
            return

    def loop(self):
        for i in self.xcore.get_events():
            try:
                self.dispatcher.dispatch(i)
            except Exception:
                log.exception("Error handling event %r", i)

    def cmd_restart(self):
        os.execv(sys.executable, [sys.executable] + sys.argv)
