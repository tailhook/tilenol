import sys
import binascii
import socket
import struct

from .xproto import Proto


proto = Proto()
proto.load_xml('xproto')

MAJOR_VERSION = 11
MINOR_VERSION = 0

typ = sys.argv[1]
key = binascii.unhexlify(sys.argv[2].encode('ascii'))

sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect('/tmp/.X11-unix/X0')
sock.send(struct.pack('<BxHHHH2x',
    0o154, #little endian
    MAJOR_VERSION,
    MINOR_VERSION,
    len(typ),
    len(key)) + typ.encode('ascii') + b'\x00'*(4 - len(typ) % 4) + key)
data = sock.recv(4096)
print(proto.types['Setup'].unpack_from(data))
