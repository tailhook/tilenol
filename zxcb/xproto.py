import os.path
import struct
import re
from xml.etree.ElementTree import parse, tostring
from collections import namedtuple, OrderedDict


re_ident = re.compile('^[a-zA-Z]\w+$')


class SimpleStruct(struct.Struct):

    def __init__(self, name, pattern, names):
        super().__init__(pattern)
        self.names = names
        self.insttype = namedtuple(name, names, rename=True)


class ComplexStruct(object):

    def __init__(self, name, items):
        self.name = name
        self.items = items

    def unpack_from(self, buf, pos=0):
        res = {}
        for i in self.items:
            if isinstance(i, SimpleStruct):
                res.update(i.insttype(*i.unpack_from(buf, pos))._asdict())
                pos += i.size
            elif isinstance(i, List):
                count = eval(i.code, res)
                for j in range(count):
                    res[i.name] = i.type.unpack_from(buf, pos)
                    if hasattr(i.type, 'name'):
                        print(i.type, i.type.name)
                    pos += i.type.size
            elif isinstance(i, String):
                count = eval(i.code, res)
                res[i.name]  = buf[pos:pos + count]
                pos += count
            else:
                raise NotImplementedError(i)
        return res

class List(object):

    def __init__(self, name, code, type):
        self.name = name
        self.code = code
        self.type = type


class String(object):

    def __init__(self, name, code):
        self.name = name
        self.code = code


class Proto(object):
    path = '/usr/share/xcb'

    def __init__(self, path=path):
        self.path = path
        self.simpletypes = {
            'BYTE': 'B',
            'BOOL': 'B',
            'CARD8': 'B',
            'CARD16': 'H',
            'CARD32': 'L',
            'INT8': 'b',
            'INT16': 'h',
            'INT32': 'l',
            }
        self.types = {}
        self.xidtypes = set()
        self.enums = {}
        self.events = {}
        self.errors = {}
        self.unions = {}
        self.requests = {}
        self.replies = {}

    def load_xml(self, name):
        with open(os.path.join(self.path, name + '.xml'), 'rb') as f:
            xml = parse(f)
        for el in xml.iterfind('*'):
            getattr(self, '_parse_' + el.tag)(el)

    def _parse_struct(self, el):
        strstack = []
        structdef = '<'
        structnames = []
        for field in el.iterfind('*'):
            if field.tag == 'field':
                try:
                    structdef += self.simpletypes[field.attrib['type']]
                except KeyError:
                    if field.attrib['type'] in self.xidtypes:
                        structdef += 'L'
                    else:
                        # TODO(tailhook) union types
                        print(field.attrib['type'])
                        continue
                structnames.append(field.attrib['name'])
            elif field.tag == 'pad':
                structdef += '{}x'.format(field.attrib['bytes'])
            elif field.tag == 'list':
                if structdef:
                    strstack.append(SimpleStruct(el.attrib['name']+'partial',
                        structdef, structnames))
                    structdef = '<'
                    structnames = []
                if field.find('*') is not None:
                    expr = self._parse_expr(field.find('*'))
                    code = compile(expr, "XPROTO:" + el.attrib['name'], "eval")
                else:
                    code = None
                if field.attrib['type'] == 'char':
                    strstack.append(String(field.attrib['name'], code))
                else:
                    typ = self.types.get(field.attrib['type'])
                    if typ is None:
                        typ = self.simpletypes.get(field.attrib['type'])
                    strstack.append(List(field.attrib['name'], code, typ))
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
        if strstack:
            strstack.append(SimpleStruct(el.attrib['name']+'partial',
                structdef, structnames))
            type = ComplexStruct(el.attrib['name'], strstack)
            self.types[el.attrib['name']] = type
        else:
            type = SimpleStruct(el.attrib['name'], structdef, structnames)
            self.types[el.attrib['name']] = type

    def _parse_event(self, el):
        struct = self._parse_struct(el)
        self.events[el.attrib['name']] = struct

    def _parse_error(self, el):
        struct = self._parse_struct(el)
        self.errors[el.attrib['name']] = struct

    def _parse_eventcopy(self, el):
        self.events[el.attrib['name']] = self.events[el.attrib['ref']]

    def _parse_errorcopy(self, el):
        self.errors[el.attrib['name']] = self.errors[el.attrib['ref']]

    def _parse_request(self, el):
        struct = self._parse_struct(el)
        self.requests[el.attrib['name']] = struct

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
        self.xidtypes.add(el.attrib['name'])

    def _parse_xidunion(self, el):
        self.xidtypes.add(el.attrib['name'])

    def _parse_typedef(self, el):
        self.simpletypes[el.attrib['newname']] = \
            self.simpletypes[el.attrib['oldname']]

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
        un = []
        # TODO(tailhook) implement unions
        self.unions[el.attrib['name']] = un

