import os.path
import struct
from collections import namedtuple


Auth = namedtuple('Auth', 'family address number name data')


def read_auth(filename=os.path.expanduser("~/.Xauthority")):
    def rstr():
        val, = struct.unpack('>H', f.read(2))
        return f.read(val)
    with open(filename, 'rb') as f:
        family, = struct.unpack('<H', f.read(2))
        yield Auth(family, rstr(), int(rstr()), rstr(), rstr())
