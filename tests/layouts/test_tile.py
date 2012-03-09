import mock
import unittest
from tilenol.xcb import Rectangle


class Window(object):

    def set_bounds(self, rect):
        assert isinstance(rect, Rectangle)
        self.rect = rect


class TestTile(unittest.TestCase):

    @mock.patch('tilenol.event.Event')
    def testTile(self, event):
        from tilenol.layout.examples import Tile
        lay = Tile()
        lay.set_bounds(Rectangle(0, 0, 800, 600))
        w1 = mock.Mock()
        w1.lprops.stack = None
        lay.add(w1)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 800, 600))
        w1.reset_mock()
        w2 = mock.Mock()
        w2.lprops.stack = None
        lay.add(w2)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 600))
        w1.reset_mock()
        w2.reset_mock()
        w3 = mock.Mock()
        w3.lprops.stack = None
        lay.add(w3)
        lay.layout()
        w1.set_bounds.assert_called_with(Rectangle(0, 0, 600, 600))
        w2.set_bounds.assert_called_with(Rectangle(600, 0, 200, 300))
        w3.set_bounds.assert_called_with(Rectangle(600, 300, 200, 300))
