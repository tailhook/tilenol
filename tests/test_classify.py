import unittest
import mock

class TestClassify(unittest.TestCase):

    def setUp(self):
        from tilenol.classify import Classifier
        cl = Classifier()
        cl.default_rules()
        self.cl = cl

    def testFloat(self):
        win = mock.Mock()
        win.lprops.floating = None
        win.xcore.atom._NET_WM_WINDOW_TYPE_UTILITY = 123456
        win.props = {
            '_NET_WM_WINDOW_TYPE': (123, 123456),
            }
        self.cl.apply(win)
        self.assertEqual(win.lprops.floating, True)

    def testNoFloat(self):
        win = mock.Mock()
        win.lprops.floating = None
        win.xcore.atom._NET_WM_WINDOW_TYPE_UTILITY = 123456
        win.props = {
            '_NET_WM_WINDOW_TYPE': (456,),
            }
        self.cl.apply(win)
        self.assertEqual(win.lprops.floating, None)

    def testGimp(self):
        win = mock.Mock()
        win.lprops.floating = None
        win.xcore.atom._NET_WM_WINDOW_TYPE_UTILITY = 123456
        win.props = {
            '_NET_WM_WINDOW_TYPE': (123, 123456),
            'WM_CLASS': 'gimp\0Gimp\0',
            }
        self.cl.apply(win)
        self.assertEqual(win.lprops.floating, False)

    def testGimp26(self):
        win = mock.Mock()
        win.lprops.floating = None
        win.xcore.atom._NET_WM_WINDOW_TYPE_UTILITY = 123456
        win.props = {
            '_NET_WM_WINDOW_TYPE': (123, 123456),
            'WM_CLASS': 'gimp-2.6\0Gimp-2.6\0',
            }
        self.cl.apply(win)
        self.assertEqual(win.lprops.floating, False)
