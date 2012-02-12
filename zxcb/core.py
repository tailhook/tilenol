from functools import partial


class Const(int):

    def __new__(cls, val, name):
        return super().__new__(cls, val)

    def __init__(self, val, name):
        self.name = name
        super().__init__(val)

    def __repr__(self):
        return '<{} {}:{}>'.format(self.__class__.__name__, self.name, self)

class Atom(Const):
    pass


class AtomWrapper(object):

    def __init__(self, connection, proto):
        self._conn = connection
        self.proto = proto
        for k, v in self.proto.enums['Atom'].items():
            setattr(self, k, Atom(v, k))

    def __getattr__(self, name):
        assert name.isidentifier()
        props = self._conn.do_request(self.proto.requests['InternAtom'],
            only_if_exists=True,
            name=name,
            )
        atom = Atom(props['atom'], name)
        setattr(self, name, atom)
        return atom


class EnumWrapper(object):

    def __init__(self, enums):
        for k, v in enums.items():
            setattr(self, k, Const(v, k))


class RawWrapper(object):

    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return partial(self._conn.do_request, self._conn.proto.requests[name])


class Core(object):

    def __init__(self, connection):
        self._conn = connection
        self.proto = connection.proto
        self.atom = AtomWrapper(connection, self.proto)
        self.raw = RawWrapper(connection)
        for k, lst in self.proto.enums.items():
            setattr(self, k, EnumWrapper(lst))

