import os
import re
import logging

log = logging.getLogger(__name__)
keysym_re = re.compile(
    r"^#define\s+(XF86)?XK_(\w+)\s+"
    r"(?:(0x[a-fA-F0-9]+)|_EVDEV\((0x[0-9a-fA-F]+)\))"
)


class Keysyms(object):
    __slots__ = ('name_to_code', 'code_to_name', '__dict__')

    def __init__(self):
        self.name_to_code = {}
        self.code_to_name = {}

    def add_from_file(self, filename):
        with open(filename, 'rt') as f:
            for line in f:
                m = keysym_re.match(line)
                if not m:
                    continue
                name = (m.group(1) or '') + m.group(2)

                if m.group(3):
                    try:
                        code = int(m.group(3), 0)
                    except ValueError:
                        log.warn("Bad code %r for key %r", code, name)
                        continue
                elif m.group(4):
                    try:
                        code = int(m.group(4), 0)
                    except ValueError:
                        log.warn("Bad code %r for evdev key %r", code, name)
                        continue
                else:
                    continue

                self.__dict__[name] = code
                self.name_to_code[name] = code
                self.code_to_name[code] = name

    def load_default(self):
        xproto_dir = os.environ.get("XPROTO_DIR", "/usr/include/X11")
        self.add_from_file(xproto_dir + '/keysymdef.h')
        self.add_from_file(xproto_dir + '/XF86keysym.h')

