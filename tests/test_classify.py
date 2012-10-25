import unittest
try:
    from unittest import mock  # builtin mock in 3.3
except ImportError:
    import mock


class TestClassify(unittest.TestCase):


    def setUp(self):
        from tilenol.classify import Classifier, all_actions, all_conditions
        cl = Classifier()
        cl.add_rule([all_conditions['match-type']('utility')],
                    [all_actions['layout-properties'](floating=True)])
        cl.add_rule([],
                    [all_actions['layout-properties'](floating=False)],
                    klass="Gimp")
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
