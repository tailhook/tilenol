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
        for field in self.items.values():
            if hasattr(field, 'add_data'):
                field.add_data(value)  # hack for valueparam
        for name, field in self.items.items():
            if isinstance(name, int):
                field.write_to(buf, None)
            else:
                try:
                    field.write_to(buf, value[name])
                except struct.error:
                    raise ValueError("Wrong value for field {!r}".format(name))


class Event(Struct):

    def __init__(self, name, number, fields, no_seq=False):
        super().__init__(name, fields)
        self.number = number
        self.no_seq = no_seq
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


class Error(Struct):

    def __init__(self, name, number, fields):
        super().__init__(name, fields)
        self.number = number

    def clone(self, name, number):
        return self.__class__(name, number, self.items)


class Union(Basic):
    """Union is only used for ClientMessage"""

    def __init__(self, name, choices):
        self.name = name
        self.choices = choices

    def write_to(self, buf, value):
        buf += value

    def read_from(self, buf, pos):
        return buf[pos:], len(buf)

class List(object):

    def __init__(self, code, type):
        self.code = code
        self.type = type

    def rich_read_from(self, buf, pos, data):
        assert self.code
        ln = eval(self.code, {'length': (len(buf) - pos)//4}, data)
        res = []
        for i in range(ln):
            value, pos = self.type.read_from(buf, pos)
            res.append(value)
        return res, pos

    def write_to(self, buf, value):
        assert self.code is None
        buf.extend(memoryview(value))


class Bytes(object):

    def __init__(self, code):
        self.code = code

    def rich_read_from(self, buf, pos, data):
        assert self.code
        ln = eval(self.code, {}, data)
        value = buf[pos:pos+ln]
        return value, pos+ln

    def write_to(self, buf, value):
        buf += value


class String(Bytes):

    def rich_read_from(self, buf, pos, data):
        value, pos = super().rich_read_from(buf, pos, data)
        return value.decode('utf-8'), pos

    def write_to(self, buf, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        super().write_to(buf, value)


class Params(object):

    def __init__(self, list_name, mask_name):
        self.mask_name = mask_name
        self.list_name = list_name

    def add_data(self, items):
        dic = items['params']
        mask = 0
        for k in sorted(dic):
            mask |= k
        items[self.mask_name] = mask

    def write_to(self, buf, dic):
        lst = []
        for k in sorted(dic):
            lst.append(dic[k])
        buf += struct.pack('<{0}L'.format(len(lst)), *lst)


class Proto(object):

    def __init__(self, path=None):
        if path is None:
            path = self.resolve_path()
        self.path = path
        self.subprotos = {}

    def resolve_path(self):
        try:
            import sysconfig
        except ImportError:  # python3.1 has no sysconfig
            from distutils import sysconfig
        path = sysconfig.get_config_var('datarootdir')
        return os.path.join(path, 'xcb')

    def load_xml(self, name):
        with open(os.path.join(self.path, name + '.xml'), 'rb') as f:
            xml = parse(f)
        self.subprotos[name] = Subprotocol(self, xml)


class Subprotocol(object):

    def __init__(self, parent, xml):
        self.parent = parent
        self.types = {}
        self.type_lookup = [self.types]
        self.enums = {}
        self.events = {}
        self.events_by_num = {}
        self.errors = {}
        self.error_lookup = [self.errors]
        self.errors_by_num = {}
        self.requests = {}
        root = xml.getroot()
        self.extension = bool(root.attrib.get('extension-name'))
        if self.extension:
            self.xname = root.attrib['extension-xname']
            self.major_version = root.attrib['major-version']
            self.minor_version = root.attrib['minor-version']
        self.simple_types()
        for el in xml.iterfind('*'):
            getattr(self, '_parse_' + el.tag)(el)

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

    def get_type(self, name):
        for i in self.type_lookup:
            if name in i:
                return i[name]

    def _parse_import(self, el):
        if el.text not in self.parent.subprotos:
            self.parent.load_xml(el.text)
        pro = self.parent.subprotos[el.text]
        self.type_lookup.append(pro.types)
        self.error_lookup.append(pro.errors)

    def _parse_items(self, el):
        items = OrderedDict()
        for field in el.iterfind('*'):
            if field.tag == 'field':
                items[field.attrib['name']] = self.get_type(
                    field.attrib['type'])
            elif field.tag == 'pad':
                items[len(items)] = Simple(len(items),
                    '{}x'.format(field.attrib['bytes']))
            elif field.tag == 'list':
                if field.find('*') is not None:
                    expr = self._parse_expr(field.find('*'))
                    code = compile(expr, "XPROTO", "eval")
                else:
                    code = None
                if field.attrib['type'] == 'char':
                    typ = String(code)
                elif field.attrib['type'] == 'void':
                    typ = Bytes(code)
                else:
                    typ = List(code, self.get_type(field.attrib['type']))
                items[field.attrib['name']] = typ
            elif field.tag == 'valueparam':
                name = field.attrib['value-mask-name']
                if name not in items:
                    items[name] = self.get_type(
                        field.attrib['value-mask-type'])
                items['params'] = Params(field.attrib['value-list-name'], name)
            elif field.tag == 'exprfield':
                pass  # TODO(tailhook) implement exprfield
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
        ev = Event(el.attrib['name'], int(el.attrib['number']), items,
                   no_seq=el.attrib.get('no-sequence-number') == 'true')
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
        ref = el.attrib['ref']
        for i in self.error_lookup:
            if ref in i:
                er = i[ref]
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
            op = xml.attrib['op']
            assert op in '+-*/'
            if op == '/':
                op = '//'
            return '('+ op.join(map(self._parse_expr, xml.iterfind('*'))) +')'
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
        self.add_type(self.get_type(el.attrib['oldname'])
                      .clone(el.attrib['newname']))

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
