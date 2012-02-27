from abc import abstractmethod, ABCMeta
from collections import namedtuple

from cairo import SolidPattern
from zorro.di import has_dependencies, dependency

from .bar import Bar


Padding = namedtuple('Padding', 'top right bottom left')


@has_dependencies
class Widget(metaclass=ABCMeta):

    bar = dependency(Bar, 'bar')

    def __init__(self, right=False):
        self.right = right

    @abstractmethod
    def draw(self, canvas, left, right):
        return left, right


class Sep(Widget):

    def __init__(self,
            padding=Padding(2, 2, 2, 2),
            color=SolidPattern(0.5, 0.5, 0.5),
            line_width=1,
            right=False):
        super().__init__(right=right)
        self.padding = padding
        self.color = color
        self.line_width = line_width

    def draw(self, canvas, l, r):
        if self.right:
            x = r - self.padding.right - 0.5
            r -= self.padding.left + self.padding.right
        else:
            x = l + self.padding.left + 0.5
            l += self.padding.left + self.padding.right
        canvas.set_source(self.color)
        canvas.set_line_width(self.line_width)
        canvas.move_to(x, self.padding.top)
        canvas.line_to(x, self.height - self.padding.bottom)
        canvas.stroke()
        return l, r
