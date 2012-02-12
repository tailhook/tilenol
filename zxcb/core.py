class Atom(int):

    def __new__(self, val, name):
        return super().__new__(Atom, val)

    def __init__(self, val, name):
        self.name = name
        super().__init__(val)

    def __repr__(self):
        return '<{} {}:{}>'.format(self.__class__.__name__, self.name, self)


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


class Core(object):

    def __init__(self, connection):
        self._conn = connection
        self.proto = connection.proto
        self.atom = AtomWrapper(connection, self.proto)

