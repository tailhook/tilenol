import unittest
try:
    from unittest import mock  # builtin mock in 3.3
except ImportError:
    import mock
from tilenol.xcb import Rectangle


class Window(object):

    def set_bounds(self, rect):
        assert isinstance(rect, Rectangle)
        self.rect = rect


class TestTile(unittest.TestCase):

    def wmock(self):
        w = mock.Mock()
        w.lprops.stack = None
        return w

    @mock.patch('tilenol.event.Event')
    def testTile(self, event):
        from tilenol.layout.examples import Tile
        lay = Tile()
        lay.set_bounds(Rectangle(0, 0, 800, 600))
        w1 = self.wmock()
        lay.add(w1)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 800, 600))
        w1.reset_mock()
        w2 = self.wmock()
        lay.add(w2)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 600))
        w1.reset_mock()
        w2.reset_mock()
        w3 = self.wmock()
        lay.add(w3)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 300))
        w3.set_bounds.assert_called_with(Rectangle(600, 300, 200, 300))

    @mock.patch('tilenol.event.Event')
    def testPixels(self, event):
        from tilenol.layout import Split, Stack, TileStack
        class Tile(Split):
            class left(TileStack):
                size = 128
                limit = 1
            class right(TileStack):
                weight = 2
                min_size = 300
        lay = Tile()
        lay.set_bounds(Rectangle(0, 0, 800, 600))
        w1 = self.wmock()
        lay.add(w1)
        w2 = self.wmock()
        lay.add(w2)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 128, 600))
        w2.set_bounds.assert_called_with(Rectangle(128, 0, 672, 600))
        lay.set_bounds(Rectangle(0, 0, 400, 300))
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 133, 300))
        w2.set_bounds.assert_called_with(Rectangle(133, 0, 267, 300))

    @mock.patch('tilenol.event.Event')
    def testOnlyPixels(self, event):
        from tilenol.layout import Split, Stack, TileStack
        class Tile(Split):
            class left(TileStack):
                size = 2
                limit = 1
            class right(TileStack):
                size = 3
        lay = Tile()
        lay.set_bounds(Rectangle(0, 0, 800, 600))
        w1 = self.wmock()
        lay.add(w1)
        w2 = self.wmock()
        lay.add(w2)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 400, 600))
        w2.set_bounds.assert_called_with(Rectangle(400, 0, 400, 600))


