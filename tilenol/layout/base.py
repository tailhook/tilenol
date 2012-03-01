from collections import OrderedDict

from zorro.di import di, has_dependencies, dependency

from tilenol.event import Event


class LayoutMeta(type):

    @classmethod
    def __prepare__(cls, name, bases):
        return OrderedDict()

    def __init__(cls, name, bases, dic):
        cls.fields = list(dic.keys())


@has_dependencies
class Layout(metaclass=LayoutMeta):

    def __init__(self):
        self.relayout = Event('layout.relayout')
        self.relayout.listen(self.layout)

    @classmethod
    def get_defined_classes(cls, base):
        res = OrderedDict()
        for k in cls.fields:
            v = getattr(cls, k)
            if isinstance(v, type) and issubclass(v, base):
                res[k] = v
        return res

    def dirty(self):
        self.relayout.emit()

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
