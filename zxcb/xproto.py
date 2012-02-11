import os.path
import struct
import socket
import re
import errno
from xml.etree.ElementTree import parse, tostring
from collections import namedtuple, OrderedDict

from zorro import channel, Lock, gethub


re_ident = re.compile('^[a-zA-Z]\w+$')


class Basic(object):

    def __init__(self, name):
        self.name = name

    def clone(self, name):
        return self.__class__(name)


class Simple(Basic):

    def __init__(self, name, typ):
        super().__init__(name)
        self.typ = typ

    def clone(self, name):
        return self.__class__(name, self.typ)

    def read_from(self, buf, pos=0):
        if self.typ.endswith('x'):
            value = None
        else:
            value, = struct.unpack_from('<'+self.typ, buf, pos)
        pos += struct.calcsize('<'+self.typ)
        return value, pos


class Xid(Simple):

    def __init__(self, name):
        super().__init__(name, 'L')

    def clone(self, name):
        return self.__class__(name)


class Struct(Basic):

    def __init__(self, name, items):
        super().__init__(name)
        self.items = items

    def clone(self, name):
        return self.__class__(name, self.items)

    def read_from(self, buf, pos=0):
        data = OrderedDict()
        oldpos = pos
        for name, field in self.items.items():
            if hasattr(field, 'rich_read_from'):
                value, pos = field.rich_read_from(buf, pos, data)
            else:
                value, pos = field.read_from(buf, pos)
            if value is None:
                continue
            data[name] = value
            oldpos=pos
        return data, pos


class Event(Struct):

    def __init__(self, name, number, fields):
        super().__init__(name, fields)
        self.number = number

    def clone(self, name, number):
        return self.__class__(name, number, self.items)

class Request(Struct):

    def __init__(self, name, opcode, reqfields, repfields):
        super().__init__(name, reqfields)
        self.opcode = opcode
        self.reply = Struct(self.name + 'Reply', repfields)

    def clone(self, name, opcode):
        return self.__class__(name, opcode, self.items)


class Error(Struct):

    def __init__(self, name, number, fields):
        super().__init__(name, fields)
        self.number = number

    def clone(self, name, number):
        return self.__class__(name, number, self.items)


class Union(Basic):

    def __init__(self, name, choices):
        self.name = name
        self.choices = choices


class List(object):

    def __init__(self, code, type):
        self.code = code
        self.type = type

    def rich_read_from(self, buf, pos, data):
        assert self.code
        ln = eval(self.code, {}, data)
        res = []
        for i in range(ln):
            value, pos = self.type.read_from(buf, pos)
            res.append(value)
        return res, pos

class String(object):

    def __init__(self, code):
        self.code = code

    def rich_read_from(self, buf, pos, data):
        assert self.code
        ln = eval(self.code, {}, data)
        value = buf[pos:pos+ln]
        return value, pos+ln


class Proto(object):
    path = '/usr/share/xcb'

    def __init__(self, path=path):
        self.path = path
        self.types = {}
        self.enums = {}
        self.events = {}
        self.errors = {}
        self.requests = {}
        self.simple_types()

    def add_type(self, typ):
        assert typ.name not in self.types
        self.types[typ.name] = typ

    def simple_types(self):
        self.add_type(Simple('BYTE', 'B'))
        self.add_type(Simple('void', 'B'))
        self.add_type(Simple('BOOL', 'B'))
        self.add_type(Simple('CARD8', 'B'))
        self.add_type(Simple('CARD16', 'H'))
        self.add_type(Simple('CARD32', 'L'))
        self.add_type(Simple('INT8', 'b'))
        self.add_type(Simple('INT16', 'h'))
        self.add_type(Simple('INT32', 'l'))

    def load_xml(self, name):
        with open(os.path.join(self.path, name + '.xml'), 'rb') as f:
            xml = parse(f)
        for el in xml.iterfind('*'):
            getattr(self, '_parse_' + el.tag)(el)

    def _parse_items(self, el):
        items = OrderedDict()
        for field in el.iterfind('*'):
            if field.tag == 'field':
                items[field.attrib['name']] = self.types[field.attrib['type']]
            elif field.tag == 'pad':
                items[len(items)] = Simple(len(items), '{}x'.format(field.attrib['bytes']))
            elif field.tag == 'list':
                if field.find('*') is not None:
                    expr = self._parse_expr(field.find('*'))
                    code = compile(expr, "XPROTO", "eval")
                else:
                    code = None
                if field.attrib['type'] == 'char':
                    typ = String(code)
                else:
                    typ = List(code, self.types[field.attrib['type']])
                items[field.attrib['name']] = typ
            elif field.tag == 'valueparam':
                print(field.tag)
                # TODO(tailhook) implement valueparam. What's this?
            elif field.tag == 'exprfield':
                print(field.tag)
                # TODO(tailhook) implement exprfield
            elif field.tag == 'reply':
                pass  # just skip it
            else:
                raise NotImplementedError(field)
        return items

    def _parse_struct(self, el):
        items = self._parse_items(el)
        self.add_type(Struct(name=el.attrib['name'], items=items))

    def _parse_event(self, el):
        items = self._parse_items(el)
        self.events[el.attrib['name']] = Event(
            el.attrib['name'], int(el.attrib['number']), items)

    def _parse_error(self, el):
        items = self._parse_items(el)
        self.errors[el.attrib['name']] = Error(
            el.attrib['name'], int(el.attrib['number']), items)

    def _parse_eventcopy(self, el):
        self.add_type(self.events[el.attrib['ref']].clone(
            el.attrib['name'], int(el.attrib['number'])))

    def _parse_errorcopy(self, el):
        self.errors[el.attrib['name']] = (self.errors[el.attrib['ref']]
            .clone(el.attrib['name'], int(el.attrib['number'])))

    def _parse_request(self, el):
        req = self._parse_items(el)
        repel = el.find('reply')
        if repel is not None:
            rep = self._parse_items(repel)
        else:
            rep = None
        self.requests[el.attrib['name']] = Request(el.attrib['name'],
            el.attrib['opcode'], req, rep)

    def _parse_expr(self, xml):
        if xml.tag == 'fieldref':
            assert re_ident.match(xml.text), xml.text
            return xml.text
        elif xml.tag == 'op':
            assert xml.attrib['op'] in '+-*/'
            return '(' + xml.attrib['op'].join(
                map(self._parse_expr, xml.iterfind('*'))) + ')'
        elif xml.tag == 'value':
            return str(int(xml.text))
        else:
            print(tostring(xml))
            raise NotImplementedError(xml.tag)


    def _parse_xidtype(self, el):
        self.add_type(Xid(el.attrib['name']))

    def _parse_xidunion(self, el):
        # TODO(tailhook) record types
        self.add_type(Xid(el.attrib['name']))

    def _parse_typedef(self, el):
        self.add_type(self.types[el.attrib['oldname']].clone(el.attrib['newname']))

    def _parse_enum(self, el):
        items = OrderedDict()
        maxv = 0
        for choice in el.iterfind('*'):
            assert choice.tag == 'item'
            val = choice.find('value')
            if val is None:
                bit = choice.find('bit')
                if bit is None:
                    maxv += 1
                    val = maxv
                else:
                    val = 1 << int(bit.text)
            else:
                val = int(choice.find('value').text)
            if val > maxv:
                maxv = val
            items[choice.attrib['name']] = val
        self.enums[el.attrib['name']] = items

    def _parse_union(self, el):
        # TODO(tailhook) implement unions
        self.add_type(Union(el.attrib['name'], []))


class Channel(channel.PipelinedReqChannel):
    MAJOR_VERSION = 11
    MINOR_VERSION = 0
    BUFSIZE = 4096

    def __init__(self, *, unixsock, auth_type, auth_key):
        super().__init__()
        self.unixsock = unixsock
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
        buf = bytearray()
        buf.extend(struct.pack('<BxHHHH2x',
            0o154, #little endian
            self.MAJOR_VERSION,
            self.MINOR_VERSION,
            len(auth_type),
            len(auth_key)))
        buf.extend(auth_type.encode('ascii'))
        buf.extend(b'\x00'*(4 - len(auth_type) % 4))
        buf.extend(auth_key)
        val = self.request(buf).get()
        print("HANDSHAKE", val)

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

        handshake_done = False
        while not handshake_done:
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
                res, maj, min, ln = struct.unpack_from('<BxHHH', buf, pos)
                ln = ln*4+8
                if len(buf)-pos < ln:
                    break
                self.produce(buf[pos:pos+ln])
                pos += ln
                handshake_done = True
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
            while len(buf)-pos >= 16:
                length, resp_to = struct.unpack_from('<i4xi', buf, pos)
                if len(buf)-pos < length:
                    break
                self.produce(resp_to, buf[pos:pos+length])
                pos += length


class Connection(object):

    def __init__(self, proto, display=":0", *, auth_type, auth_key):
        self.proto = proto
        host, port = display.split(':')
        maj, min = port.split('.')
        assert host == "", "Only localhost supported so far"
        assert min == '0', 'Subdisplays are not not supported so far'
        self.unixsock = '/tmp/.X11-unix/X' + maj
        self.auth_type = auth_type
        self.auth_key = auth_key
        self._channel = None
        self._channel_lock = Lock()

    def connection(self):
        if not self._channel:
            with self._channel_lock:
                if not self._channel:
                    self._channel = Channel(unixsock=self.unixsock,
                        auth_type=self.auth_type, auth_key=self.auth_key)
        return self._channel

    def InternAtom(self, hello):
        self.connection()
        print("HELLO")
