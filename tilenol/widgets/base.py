from abc import abstractmethod, ABCMeta
from collections import namedtuple


Padding = namedtuple('Padding', 'top right bottom left')


class Widget(metaclass=ABCMeta):

    @abstractmethod
    def draw(self, canvas):
        pass

    @abstractmethod
    def size(self, canvas):
        return 0
