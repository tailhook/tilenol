from abc import abstractmethod, ABCMeta
from collections import namedtuple

from cairo import SolidPattern


Padding = namedtuple('Padding', 'top right bottom left')


class Widget(metaclass=ABCMeta):

    def __init__(self, right=False):
        self.right = right

    @abstractmethod
    def draw(self, canvas):
        return 0


class Sep(Widget):

    def __init__(self,
        padding=Padding(2, 2, 2, 2),
        color=SolidPattern(0.5, 0.5, 0.5),
        right=False):
        super().__init__(right=right)
        self.padding = padding
        self.color = color

    def draw(self, canvas):
        if self.right:
            l, t, r, b = canvas.clip_extents()
            x = r - self.padding.right
        else:
            x = self.padding.left
        canvas.set_source(self.color)
        canvas.move_to(x, self.padding.top)
        canvas.line_to(x, self.height - self.padding.bottom)
        canvas.stroke()
        return self.padding.left + self.padding.right
