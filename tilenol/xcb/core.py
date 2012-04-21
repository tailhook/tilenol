from functools import partial
from collections import namedtuple
import struct

from zorro.util import cached_property

try:
    from .shm import ShmPixbuf
except ImportError:
    import warnings
    warnings.warn('Shm is not available, expect poor performance.')

try:
    from .pixbuf import Pixbuf
except ImportError:
    import warnings
    warnings.warn('Cairo is not available, no drawing would work')


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
            only_if_exists=False,
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

    def __init__(self, conn, proto, opcode=None):
        self._conn = conn
        self._proto = proto
        self._opcode = opcode

    def __getattr__(self, name):
        return partial(self._conn.do_request,
            self._proto.requests[name], _opcode=self._opcode)


class Core(object):

    def __init__(self, connection):
        self._conn = connection
        self._conn.connection()
        self.proto = connection.proto.subprotos['xproto']
        self.atom = AtomWrapper(connection, self.proto)
        self.raw = RawWrapper(connection, self.proto)
        for k, lst in self.proto.enums.items():
            setattr(self, k, EnumWrapper(lst))
        for k, v in connection.proto.subprotos.items():
            if not v.extension:
                continue
            ext = connection.query_extension(k)
            if not ext['present']:
                continue
            setattr(self, k, RawWrapper(self._conn, v, ext['major_opcode']))
        self.root = self._conn.init_data['roots'][0]
        self.root_window = self.root['root']
        pad = self._conn.init_data['bitmap_format_scanline_pad']
        assert pad % 8 == 0
        self.bitmap_stride = pad//8
        self.current_event = None
        self.last_event = None
        self.last_time = 0
        self._event_iterator = self._events()

    def init_keymap(self):
        self.keycode_to_keysym = {}
        self.shift_keycode_to_keysym = {}
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
            self.shift_keycode_to_keysym[row[0]] = row[2]
            self.keysym_to_keycode[row[1]] = row[0]

        caps = self.ModMask.Lock  # caps lock
        num = getattr(self.ModMask, '2')  # mod2 is usually numlock
        mode = getattr(self.ModMask, '5')  # mod5 is usually mode_switch
        self.modifiers_mask = ~(caps|num|mode)

    def create_toplevel(self, bounds, border=0, klass=None, params={}):
        return self.create_window(bounds,
            border=border,
            klass=klass,
            parent=self.root_window,
            params=params)

    def create_window(self, bounds, border=0, klass=None, parent=0, params={}):
        wid = self._conn.new_xid()
        root = self.root
        self.raw.CreateWindow(**{
            'wid': wid,
            'root': root['root'],
            'depth': 0,
            'parent': parent or root['root'],
            'visual': 0,
            'x': bounds.x,
            'y': bounds.y,
            'width': bounds.width,
            'height': bounds.height,
            'border_width': border,
            'class': klass,
            'params': params,
            })
        return wid

    def send_event(self, event_type, event_mask, dest, **kw):
        etype = self.proto.events[event_type]
        buf = bytearray([etype.number])
        etype.write_to(buf, kw)
        buf[2:2] = b'\x00\x00'
        buf += b'\x00'*(32 - len(buf))
        self.raw.SendEvent(
            propagate=False,
            destination=dest,
            event_mask=event_mask,
            event=buf,
            )


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

    def _events(self):
        for i in self._conn.get_events():
            try:
                self.current_event = i
                self.last_event = i
                if hasattr(i, 'time'):
                    self.last_time = i.time
                yield i
            finally:
                self.current_event = None

    def get_events(self):
        return self._event_iterator

    def pixbuf(self, width, height):
        if width*height < 1024:
            return Pixbuf(width, height, self)
        elif hasattr(self, 'shm') and ShmPixbuf:
            return ShmPixbuf(width, height, self)
        elif hasattr(self, 'bigreq') or width*height*4 < 260000:
            return Pixbuf(width, height, self)

    @cached_property
    def pixbuf_gc(self):
        res = self._conn.new_xid()
        self.raw.CreateGC(
            cid=res,
            drawable=self.root_window,
            params={},
            )
        return res



