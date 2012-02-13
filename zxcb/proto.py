import socket
import re
import errno
import struct
from math import ceil
from functools import partial
from collections import namedtuple, deque

from zorro import channel, Lock, gethub, Condition

from .auth import read_auth


class XError(Exception):

    def __init__(self, typ, params):
        self.typ = typ
        self.params = dict(params)

    def __str__(self):
        return '{}{!r}'.format(self.typ.name, self.params)


class Channel(channel.PipelinedReqChannel):
    MAJOR_VERSION = 11
    MINOR_VERSION = 0
    BUFSIZE = 4096

    def __init__(self, *, unixsock, event_dispatcher):
        super().__init__()
        self.unixsock = unixsock
        self.event_dispatcher = event_dispatcher
        if unixsock:
            self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        else:
            self._sock = socket.socket(socket.AF_INET,
                socket.SOCK_STREAM, socket.IPPROTO_TCP)
        self._sock.setblocking(0)
        try:
            if unixsock:
                self._sock.connect(unixsock)
            else:
                self._sock.connect((host, port))
        except socket.error as e:
            if e.errno == errno.EINPROGRESS:
                gethub().do_write(self._sock)
            else:
                raise
        self._start()

    def connect(self, auth_type, auth_key):
        buf = bytearray()
        buf.extend(struct.pack('<BxHHHH2x',
            0o154, #little endian
            self.MAJOR_VERSION,
            self.MINOR_VERSION,
            len(auth_type),
            len(auth_key)))
        if isinstance(auth_type, str):
            auth_type = auth_type.encode('ascii')
        buf.extend(auth_type)
        buf.extend(b'\x00'*(4 - len(auth_type) % 4))
        buf.extend(auth_key)
        return self.request(buf).get()

    def sender(self):
        buf = bytearray()

        add_chunk = buf.extend
        wait_write = gethub().do_write

        while True:
            if not buf:
                self.wait_requests()
            if not self._alive:
                return
            wait_write(self._sock)
            for chunk in self.get_pending_requests():
                add_chunk(chunk)
            try:
                bytes = self._sock.send(buf)
            except socket.error as e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    continue
                else:
                    raise
            if not bytes:
                raise EOFError()
            del buf[:bytes]

    def receiver(self):
        buf = bytearray()

        sock = self._sock
        wait_read = gethub().do_read
        add_chunk = buf.extend
        pos = 0

        while True:
            wait_read(sock)
            try:
                bytes = sock.recv(self.BUFSIZE)
                if not bytes:
                    raise EOFError()
                add_chunk(bytes)
            except socket.error as e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    continue
                else:
                    raise
            if len(buf)-pos >= 8:
                res, maj, min, ln = struct.unpack_from('<BxHHH', buf, pos)
                ln = ln*4+8
                if len(buf)-pos < ln:
                    break
                self.produce(buf[pos:pos+ln])
                pos += ln
                break

        while True:
            if pos*2 > len(buf):
                del buf[:pos]
                pos = 0
            wait_read(sock)
            try:
                bytes = sock.recv(self.BUFSIZE)
                if not bytes:
                    raise EOFError()
                add_chunk(bytes)
            except socket.error as e:
                if e.errno in (errno.EAGAIN, errno.EINTR):
                    continue
                else:
                    raise
            while len(buf)-pos >= 8:
                opcode, seq, ln = struct.unpack_from('<BxHL', buf, pos)
                # TODO(tailhook) check seq
                if opcode > 1:
                    if len(buf) - pos < 32:
                        break
                    self.event_dispatcher(seq,
                        buf[pos:pos+2] + buf[pos+4:pos+32])
                    pos += 32
                else:
                    ln = ln*4+32
                    if len(buf)-pos < ln:
                        break
                    val = buf[pos:pos+2]
                    val.extend(buf[pos+8:pos+ln])
                    pos += ln
                    self.produce(val)


class Connection(object):

    def __init__(self, proto, display=":0",
        auth_file="~/.Xauthority", auth_type=None, auth_key=None):
        self.proto = proto
        host, port = display.split(':')
        maj, min = map(int, port.split('.'))
        assert host == "", "Only localhost supported so far"
        assert min == 0, 'Subdisplays are not not supported so far'
        if auth_type is None:
            for auth in read_auth():
                if auth.family == socket.AF_UNIX and maj == auth.number:
                    auth_type = auth.name
                    auth_key = auth.data
                    break
            else:
                raise RuntimeError("Can't find X auth type")
        self.unixsock = '/tmp/.X11-unix/X{:d}'.format(maj)
        self.auth_type = auth_type
        self.auth_key = auth_key
        self._channel = None
        self._channel_lock = Lock()
        self._condition = Condition()
        self.events = deque()

    def connection(self):
        if self._channel is None:
            with self._channel_lock:
                if self._channel is None:
                    chan = Channel(unixsock=self.unixsock,
                                   event_dispatcher=self.event_dispatcher)
                    data = chan.connect(self.auth_type, self.auth_key)
                    value, pos = self.proto.types['Setup'].read_from(data)
                    assert pos == len(data)
                    self.init_data = value
                    assert self.init_data['status'] == 1
                    assert self.init_data['protocol_major_version'] == 11
                    self._init_values()
                    self._channel = chan
        return self._channel

    def _init_values(self):
        d = self.init_data
        base = self.init_data["resource_id_base"]
        mask = self.init_data["resource_id_mask"]
        inc = mask & -mask
        self.xid_generator = iter(range(base, base | mask, inc))

    def parse_error(self, buf):
        typ = self.proto.errors_by_num[buf[1]]
        err, pos = typ.read_from(buf, 6)
        assert len(buf) == max(pos, 26)
        raise XError(typ, err)

    def do_request(self, rtype, **kw):
        conn = self.connection()
        for i in list(kw):
            n = i + '_len'
            if n in rtype.items:
                kw[n] = len(kw[i])
        buf = bytearray()
        rtype.write_to(buf, kw)
        if rtype.reply:
            buf = conn.request(buf).get()
            if buf[0] == 0:
                self.parse_error(buf)
            assert buf[0] == 1
            val, pos = rtype.reply.read_from(buf, 1)
            assert max(pos, 26) == len(buf)
            return val
        else:
            conn.push(buf)

    def new_xid(self):
        return next(self.xid_generator)

    def event_dispatcher(self, seq, buf):
        etype = self.proto.events_by_num[buf[0] & 127]
        ev, pos = etype.read_from(buf, 1)
        assert pos < 32
        self.events.append(etype.type(seq, **ev))
        self._condition.notify()

    def get_events(self):
        while True:
            while self.events:
                yield self.events.popleft()
            self._condition.wait()

