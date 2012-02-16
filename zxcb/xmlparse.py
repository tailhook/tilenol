import os.path
import struct
import keyword
from math import ceil
from collections import namedtuple, OrderedDict
from xml.etree.ElementTree import parse, tostring


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

    def write_to(self, buf, value):
        if self.typ.endswith('x'):
            buf += struct.pack(self.typ)
        else:
            buf += struct.pack('<'+self.typ, value)



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

    def write_to(self, buf, value):
        for name, field in self.items.items():
            if isinstance(name, int):
                field.write_to(buf, None)
            else:
                try:
                    field.write_to(buf, value[name])
                except struct.error:
                    raise ValueError("Wrong value for field {!r}".format(name))


class Event(Struct):

    def __init__(self, name, number, fields):
        super().__init__(name, fields)
        self.number = number
        allfields = ['seq']
        allfields.extend(f + '_' if keyword.iskeyword(f) else f
            for f in fields if isinstance(f, str))
        self.type = namedtuple(self.name + 'Event', allfields)

    def clone(self, name, number):
        return self.__class__(name, number, self.items)


class Request(Struct):

    def __init__(self, name, opcode, reqfields, repfields):
        super().__init__(name, reqfields)
        self.opcode = int(opcode)
        if repfields:
            self.reply = Struct(self.name + 'Reply', repfields)
            fields = ['seq']
            fields.extend(f + '_' if keyword.iskeyword(f) else f
                for f in repfields if isinstance(f, str))
            self.reply_type = namedtuple(self.name + 'Reply', fields)
        else:
            self.reply = None

    def clone(self, name, opcode):
        return self.__class__(name, opcode, self.items)

    def write_to(self, buf, value):
        super().write_to(buf, value)
        assert len(buf) > 1
        ln = int(ceil((len(buf)+3)/4))
        buf.insert(0, self.opcode)
        buf[2:2] = struct.pack('<H', ln)
        buf += b'\x00'*(ln*4 - len(buf))


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

    def write_to(self, buf, value):
        assert self.code is None
        buf.extend(memoryview(value))

class String(object):

    def __init__(self, code):
        self.code = code

    def rich_read_from(self, buf, pos, data):
        assert self.code
        ln = eval(self.code, {}, data)
        value = buf[pos:pos+ln]
        return value, pos+ln

    def write_to(self, buf, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        buf += value


class Params(object):

    def __init__(self, mask_type):
        self.mask_type = mask_type

    def write_to(self, buf, dic):
        mask = 0
        pos = len(buf)
        lst = []
        for k in sorted(dic):
            mask |= k
            lst.append(dic[k])
        self.mask_type.write_to(buf, mask)
        buf += struct.pack('<{0}L'.format(len(lst)), *lst)


class Proto(object):
    path = '/usr/share/xcb'

    def __init__(self, path=path):
        self.path = path
        self.types = {}
        self.enums = {}
        self.events = {}
        self.events_by_num = {}
        self.errors = {}
        self.errors_by_num = {}
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
                items['params'] = Params(self.types[
                    field.attrib['value-mask-type']])
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
        ev = Event(el.attrib['name'], int(el.attrib['number']), items)
        self.events[ev.name] = ev
        self.events_by_num[ev.number] = ev

    def _parse_error(self, el):
        items = self._parse_items(el)
        er = Error(el.attrib['name'], int(el.attrib['number']), items)
        self.errors[er.name] = er
        self.errors_by_num[er.number] = er

    def _parse_eventcopy(self, el):
        er = self.events[el.attrib['ref']]
        ner = er.clone(el.attrib['name'], int(el.attrib['number']))
        self.events[ner.name] = ner
        self.events_by_num[ner.number] = ner

    def _parse_errorcopy(self, el):
        er = self.errors[el.attrib['ref']]
        ner = er.clone(el.attrib['name'], int(el.attrib['number']))
        self.errors[ner.name] = ner
        self.errors_by_num[ner.number] = ner

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
            assert xml.text.isidentifier(), xml.text
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
