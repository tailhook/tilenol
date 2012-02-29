import os.path
import socket
import re
import errno
import struct
import traceback
import logging
from math import ceil
from functools import partial
from collections import namedtuple, deque

from zorro import channel, Lock, gethub, Condition, Future

from .auth import read_auth


log = logging.getLogger(__name__)


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

    def __init__(self, *, unixsock, event_dispatcher, proto):
        super().__init__()
        self.unixsock = unixsock
        self.request_id = 0
        self.event_dispatcher = event_dispatcher
        self.proto = proto
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

    def request(self, input):
        if not self._alive:
            raise channel.PipeError()
        val = Future()
        self._pending.append((input, val, None))
        self._cond.notify()
        return val

    def push(self, input):
        """For requests which do not need an answer"""
        self._pending.append((input, None, traceback.extract_stack()))
        self._cond.notify()

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
            for inp, fut, tb in self.get_pending_requests():
                self._producing.append((self.request_id, fut, tb))
                self.request_id += 1
                add_chunk(inp)
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

    def produce(self, seq, value):
        if not self._alive:
            raise ShutdownException()
        assert seq <= self.request_id
        request_id, fut, tb = self._producing.popleft()
        while request_id < seq:
            if fut is not None:
                fut.throw(RuntimeError("Request ignored"))
            assert fut is None
            request_id, fut, tb = self._producing.popleft()
        assert seq == request_id, (seq, request_id)
        if fut is not None:
            fut.set(value)
        else:
            assert value[0] == 0
            typ = self.proto.errors_by_num[value[1]]
            err, pos = typ.read_from(value, 6)
            assert len(value) == max(pos, 30)
            lst = traceback.format_list(tb)
            lst.extend(traceback.format_exception_only(
                XError, XError(typ, err)))
            log.error("Error in asynchronous request\n%s", ''.join(lst))

    def _stop_producing(self):
        prod = self._producing
        del self._producing
        for rid, fut, tb in prod:
            if fut is not None:
                fut.throw(channel.PipeError())


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
                self._producing.popleft()[1].set(buf[pos:pos+ln])
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
                if opcode != 1:
                    if len(buf) - pos < 32:
                        break
                    val = buf[pos:pos+2] + buf[pos+4:pos+32]
                    pos += 32
                else:
                    ln = ln*4+32
                    if len(buf)-pos < ln:
                        break
                    val = buf[pos:pos+2]
                    val.extend(buf[pos+8:pos+ln])
                    pos += ln
                if opcode > 1:
                    self.event_dispatcher(seq, val)
                else:
                    self.produce(seq, val)


class Connection(object):

    def __init__(self, proto, display=None,
        auth_file=None, auth_type=None, auth_key=None):
        self.proto = proto
        if display is None:
            display = os.environ.get('DISPLAY', ':0')
        if auth_file is None and auth_type is None:
            auth_file = os.environ.get('XAUTHORITY')
            if auth_file is None:
                auth_file = os.path.expanduser('~/.XAuthority')
        host, port = display.split(':')
        if '.' in port:
            maj, min = map(int, port.split('.'))
        else:
            maj = int(port)
            min = 0
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
                                   proto=self.proto,
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
        assert len(buf) == max(pos, 30), (len(buf), pos, buf)
        raise XError(typ, err)

    def do_request(self, rtype, **kw):
        conn = self.connection()
        for i in list(kw):
            n = i + '_len'
            if n in rtype.items and n not in kw:
                kw[n] = len(kw[i])
        buf = bytearray()
        rtype.write_to(buf, kw)
        if rtype.reply:
            buf = conn.request(buf).get()
            if buf[0] == 0:
                self.parse_error(buf)
            assert buf[0] == 1
            val, pos = rtype.reply.read_from(buf, 1)
            assert max(ceil((pos-2)/4)*4+2, 26) == len(buf), (pos, len(buf))
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

