from functools import partial
from collections import namedtuple
import struct


fmtlen = {
    0: 0,
    8: 1,
    16: 2,
    32: 4,
    }
fmtchar = {
    8: 'B',
    16: 'H',
    32: 'L',
    }


class Rectangle(namedtuple('_Rectangle', 'x y width height')):
    __slots__ = ()


class Const(int):

    def __new__(cls, val, name):
        return super().__new__(cls, val)

    def __init__(self, val, name):
        self.name = name
        super().__init__(val)

    def __repr__(self):
        return '<{} {}:{}>'.format(self.__class__.__name__, self.name, self)

class Atom(Const):
    pass


class AtomWrapper(object):

    def __init__(self, connection, proto):
        self._conn = connection
        self.proto = proto
        self._atoms = {}
        for k, v in self.proto.enums['Atom'].items():
            atom = Atom(v, k)
            self._atoms[v] = atom
            setattr(self, k, atom)

    def __getattr__(self, name):
        assert name.isidentifier()
        props = self._conn.do_request(self.proto.requests['InternAtom'],
            only_if_exists=True,
            name=name,
            )
        atom = Atom(props['atom'], name)
        self._atoms[props['atom']] = atom
        setattr(self, name, atom)
        return atom

    def __getitem__(self, value):
        try:
            return self._atoms[value]
        except KeyError:
            props = self._conn.do_request(self.proto.requests['GetAtomName'],
                atom=value)
            atom = Atom(value, props['name'])
            self._atoms[value] = atom
            setattr(self, props['name'], atom)
            return atom


class EnumWrapper(object):

    def __init__(self, enums):
        for k, v in enums.items():
            setattr(self, k, Const(v, k))


class RawWrapper(object):

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return partial(self._conn.do_request, self._conn.proto.requests[name])


class Core(object):

    def __init__(self, connection):
        self._conn = connection
        self._conn.connection()
        self.proto = connection.proto
        self.atom = AtomWrapper(connection, self.proto)
        self.raw = RawWrapper(connection)
        for k, lst in self.proto.enums.items():
            setattr(self, k, EnumWrapper(lst))
        self.root = self._conn.init_data['roots'][0]
        self.root_window = self.root['root']
        pad = self._conn.init_data['bitmap_format_scanline_pad']
        assert pad % 8 == 0
        self.bitmap_stride = pad//8

    def init_keymap(self):
        self.keycode_to_keysym = {}
        self.keysym_to_keycode = {}
        idata = self._conn.init_data
        mapping = self.raw.GetKeyboardMapping(
            first_keycode=idata['min_keycode'],
            count=idata['max_keycode'] - idata['min_keycode'],
            )
        mapiter = iter(mapping['keysyms'])
        for row in zip(range(idata['min_keycode'], idata['max_keycode']),
                *(mapiter for i in range(mapping['keysyms_per_keycode']))):
            self.keycode_to_keysym[row[0]] = row[1]
            self.keysym_to_keycode[row[1]] = row[0]

    def create_toplevel(self, bounds, border=0, klass=None, params={}):
        wid = self._conn.new_xid()
        root = self.root
        self.raw.CreateWindow(**{
            'wid': wid,
            'root': root['root'],
            'depth': root['root_depth'],
            'parent': root['root'],
            'visual': root['root_visual'],
            'x': bounds.x,
            'y': bounds.y,
            'width': bounds.width,
            'height': bounds.height,
            'border_width': border,
            'class': klass,
            'params': params,
            })
        return wid

    def get_property(self, win, name):
        result = self.raw.GetProperty(
                delete=False,
                window=win,
                property=name,
                type=self.atom.Any,
                long_offset=0,
                long_length=65536)
        typ = self.atom[result['type']]
        if result['format'] == 0:
            return typ, None
        elif typ in (self.atom.STRING, self.atom.UTF8_STRING):
            return typ, result['value'].decode('utf-8')
        return typ, struct.unpack('<{}{}'.format(
            len(result['value']) // fmtlen[result['format']],
            fmtchar[result['format']]),
            result['value'])


