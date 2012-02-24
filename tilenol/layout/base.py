from collections import OrderedDict


class LayoutMeta(type):

    @classmethod
    def __prepare__(cls, name, bases):
        return OrderedDict()


class Layout(object):
    pass

    @classmethod
    def get_defined_classes(cls, base):
        res = OrderedDict()
        for k in dir(cls):
            v = getattr(cls, k)
            if isinstance(v, type) and issubclass(v, base):
                res[k] = v
        return res
