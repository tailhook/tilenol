import mock
import unittest
from tilenol.layout.examples import Tile2
from tilenol.xcb import Rectangle


class Window(object):

    def set_bounds(self, rect):
        assert isinstance(rect, Rectangle)
        self.rect = rect


class TestTile(unittest.TestCase):

    def testTile2(self):
        lay = Tile2()
        lay.set_bounds(Rectangle(0, 0, 800, 600))
        w1 = mock.Mock()
        lay.add(w1)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 800, 600))
        w1.reset_mock()
        w2 = mock.Mock()
        lay.add(w2)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 600))
        w1.reset_mock()
        w2.reset_mock()
        w3 = mock.Mock()
        lay.add(w3)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 300))
        w3.set_bounds.assert_called_with(Rectangle(600, 300, 200, 300))
