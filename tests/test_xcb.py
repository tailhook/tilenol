import unittest
import os
from functools import wraps


def xcbtest(*protos):
    def wrapper(fun):
        @wraps(fun)
        def wrapper(self):
            from tilenol.xcb import Proto, Connection
            from zorro import Hub
            err = []
            hub = Hub()
            def real_test():
                pr = Proto()
                for i in protos:
                    pr.load_xml(i)
                conn = Connection(pr)
                fun(self, conn)
            @hub.run
            def test():
                try:
                    real_test()
                except Exception as e:
                    err.append(e)
            if err:
                raise err[0]
        return wrapper
    return wrapper


class TestConn(unittest.TestCase):

    @xcbtest('xproto')
    def testAtom(self, conn):
        xproto = conn.proto.subprotos['xproto']
        a1 = conn.do_request(xproto.requests['InternAtom'],
            only_if_exists=False, name="_ZXCB")['atom']
        self.assertTrue(a1 > 100)
        self.assertTrue(isinstance(a1, int))
        a2 = conn.do_request(xproto.requests['InternAtom'],
            only_if_exists=True, name="WM_CLASS")['atom']
        self.assertEqual(a2, 67)
        self.assertNotEqual(a1, a2)

    @xcbtest('xproto')
    def testMoreAtoms(self, conn):
        xproto = conn.proto.subprotos['xproto']
        totalatom = "TESTTESTTESTTESTTEST"
        for i in range(1, len(totalatom)):
            n = conn.do_request(xproto.requests['InternAtom'],
                only_if_exists=False, name=totalatom[:i])['atom']
            self.assertTrue(n > 200)
            self.assertTrue(isinstance(n, int))


    @xcbtest('xproto')
    def testXid(self, conn):
        conn.connection()
        xid1 = conn.new_xid()
        xid2 = conn.new_xid()
        self.assertTrue(xid2 > xid1)
        self.assertTrue(isinstance(xid1, int))


class TestWrapper(unittest.TestCase):

    @xcbtest('xproto')
    def testAtoms(self, conn):
        from tilenol.xcb.core import Core
        core = Core(conn)
        self.assertEqual(core.atom.WM_CLASS, 67)
        self.assertEqual(core.atom.WM_CLASS.name, 'WM_CLASS')
        self.assertEqual(repr(core.atom.WM_CLASS), '<Atom WM_CLASS:67>')
        a1 = conn.do_request(conn.proto.requests['InternAtom'],
            only_if_exists=False, name="_ZXCB")['atom']
        self.assertTrue(a1 > 200)
        self.assertEquals(core.atom._ZXCB, a1)

    @xcbtest('xproto')
    def testAtoms(self, conn):
        from tilenol.xcb.core import Core
        core = Core(conn)
        self.assertEqual(core.EventMask.Exposure, 32768)
        self.assertEqual(core.CW.BackPixel, 2)
        self.assertEqual(repr(core.CW.BackPixel), '<Const BackPixel:2>')

    @xcbtest('xproto')
    def testRaw(self, conn):
        from tilenol.xcb.core import Core
        core = Core(conn)
        a2 = core.raw.InternAtom(only_if_exists=True, name="WM_CLASS")['atom']
        self.assertEqual(a2, 67)

    @xcbtest('xproto')
    def testWin(self, conn):
        from tilenol.xcb.core import Core, Rectangle
        core = Core(conn)
        conn.connection()
        win = core.create_toplevel(
            bounds=Rectangle(10, 10, 100, 100),
            border=1,
            klass=core.WindowClass.InputOutput,
            params={
                core.CW.BackPixel: conn.init_data['roots'][0]['white_pixel'],
                core.CW.EventMask:
                    core.EventMask.Exposure | core.EventMask.KeyPress,
                })
        core.raw.MapWindow(window=win)
        for ev in conn.get_events():
            if ev.__class__.__name__ == 'ExposeEvent' and ev.window == win:
                break
        attr = core.raw.GetWindowAttributes(window=win)
        self.assertTrue(attr['map_state'])


