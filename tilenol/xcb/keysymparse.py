import re

keysym_re = re.compile(r"^#define\s+(XF86)?XK_(\w+)\s+(\S+)")


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
                code = int(m.group(3), 0)
                self.__dict__[name] = code
                self.name_to_code[name] = code
                self.code_to_name[code] = name

    def load_default(self):
        self.add_from_file('/usr/include/X11/keysymdef.h')
        self.add_from_file('/usr/include/X11/XF86keysym.h')

