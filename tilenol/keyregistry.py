import re
import logging

from zorro.di import has_dependencies, dependency

from .xcb import Keysyms, Core
from .config import Config
from .commands import CommandDispatcher


hotkey_re = re.compile('^<[^>]+>|.$')
log = logging.getLogger(__name__)


@has_dependencies
class KeyRegistry(object):

    keysyms = dependency(Keysyms, 'keysyms')
    xcore = dependency(Core, 'xcore')
    config = dependency(Config, 'config')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self):
        self.keys = {}

    def configure_hotkeys(self):
        self.xcore.init_keymap()
        for key, cmd in self.config.keys():
            self.add_key(key, self.commander.callback(*cmd))
        self.register_keys(self.xcore.root_window)

    def reconfigure_keys(self):
        if self.keys:
            self.unregister_keys(self.xcore.root_window)
        self.keys = {}
        self.configure_hotkeys()

    def parse_key(self, keystr):
        mod = 0
        if keystr[0] == '<':
            keystr = keystr[1:-1]
            if '-' in keystr:
                mstr, sym = keystr.split('-')
                if 'S' in mstr:
                    mod |= self.xcore.ModMask.Shift
                if 'C' in mstr:
                    mod |= self.xcore.ModMask.Control
                if 'W' in mstr:
                    mod |= getattr(self.xcore.ModMask, '4')
            else:
                sym = keystr
        else:
            if sym.lower() != sym:
                mod = self.xcore.ModMask.Shift
            sym = sym.lower()
        code = self.keysyms.name_to_code[sym]
        return mod, code

    def add_key(self, keystr, handler):
        m = hotkey_re.match(keystr)
        if not m:
            raise ValueError(keystr)
        modmask, keysym = self.parse_key(m.group(0))
        self.keys[modmask, keysym] = handler

    def init_modifiers(self):
        # TODO(tailhook) probably calculate them instead of hardcoding
        caps = self.xcore.ModMask.Lock  # caps lock
        num = getattr(self.xcore.ModMask, '2')  # mod2 is usually numlock
        mode = getattr(self.xcore.ModMask, '5')  # mod5 is usually mode_switch
        self.extra_modifiers = [0,
            caps,
            num,
            mode,
            caps|num,
            num|mode,
            caps|num|mode,
            ]
        self.modifiers_mask = ~(caps|num|mode)

    def register_keys(self, win):
        self.init_modifiers()
        for mod, key in self.keys:
            try:
                kcode = self.xcore.keysym_to_keycode[key]
            except KeyError:
                log.warning("No mapping for key ``%s''",
                    self.keysyms.code_to_name[key])
                continue
            for extra in self.extra_modifiers:
                self.xcore.raw.GrabKey(
                    owner_events=False,
                    grab_window=win,
                    modifiers=mod|extra,
                    key=kcode,
                    keyboard_mode=self.xcore.GrabMode.Async,
                    pointer_mode=self.xcore.GrabMode.Async,
                    )

    def unregister_keys(self, win):
        self.xcore.raw.UngrabKey(
            grab_window=win,
            modifiers=self.xcore.ModMask.Any,
            key=self.xcore.Grab.Any,
            )

    def dispatch_event(self, event):
        try:
            kcode = self.xcore.keycode_to_keysym[event.detail]
            handler = self.keys[event.state & self.modifiers_mask, kcode]
        except KeyError:
            return False
        else:
            try:
                handler()
            except Exception as e:
                log.exception("Error handling keypress %r", event,
                    exc_info=(type(e), e, e.__traceback__))

