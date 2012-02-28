from zorro.di import di, has_dependencies, dependency

from collections import OrderedDict


class LayoutMeta(type):

    @classmethod
    def __prepare__(cls, name, bases):
        return OrderedDict()


@has_dependencies
class Layout(object):

    @classmethod
    def get_defined_classes(cls, base):
        res = OrderedDict()
        for k in dir(cls):
            v = getattr(cls, k)
            if isinstance(v, type) and issubclass(v, base):
                res[k] = v
        return res

    def all_visible_windows(self):
        for i in getattr(self, 'visible_windows', ()):
            yield i
        sub = getattr(self, 'sublayouts', None)
        if sub:
            for s in sub():
                for i in s.visible_windows:
                    yield i


    def hide_all(self):
        for i in self.all_visible_windows():
            i.hide()


    def show_all(self):
        for i in self.all_visible_windows():
            i.show()
