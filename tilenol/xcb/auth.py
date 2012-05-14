import os.path
import struct
from collections import namedtuple


Auth = namedtuple('Auth', 'family address number name data')


def read_auth(filename=os.path.expanduser("~/.Xauthority")):
    def rstr():
        val, = struct.unpack('>H', f.read(2))
        return f.read(val)
    with open(filename, 'rb') as f:
        while True:
            head = f.read(2)
            if not head:
                break
            family, = struct.unpack('<H', head)
            yield Auth(family, rstr(), int(rstr()), rstr(), rstr())


if __name__ == '__main__':
    for item in read_auth():
        print(item)
