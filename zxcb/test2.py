import sys
import binascii
import socket
import struct
import os
from zorro import Hub

from .xproto import Proto, Connection


proto = Proto()
proto.load_xml('xproto')

MAJOR_VERSION = 11
MINOR_VERSION = 0

typ = sys.argv[1]
key = binascii.unhexlify(sys.argv[2].encode('ascii'))

def main():

    hub = Hub()
    @hub.run
    def real_main():
        pr = Proto()
        pr.load_xml('xproto')
        conn = Connection(pr, os.environ['DISPLAY'],
            auth_type=typ, auth_key=key)
        print("hello", conn.InternAtom('hello'))

if __name__ == "__main__":
    main()

"""
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/tmp/.X11-unix/X0')
sock.send(struct.pack('<BxHHHH2x',
    0o154, #little endian
    MAJOR_VERSION,
    MINOR_VERSION,
    len(typ),
    len(key)) + typ.encode('ascii') + b'\x00'*(4 - len(typ) % 4) + key)
data = sock.recv(4096)
val, pos = proto.types['Setup'].read_from(data)
print(val['length']*4, pos, data[pos:pos+16])
"""
