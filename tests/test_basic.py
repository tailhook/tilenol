import unittest
import os
from functools import wraps


def xcbtest(*protos):
    def wrapper(fun):
        @wraps(fun)
        def wrapper(self):
            from zxcb.xproto import read_auth, Proto, Connection
            from zorro import Hub
            err = []
            hub = Hub()
            def real_test():
                pr = Proto()
                for i in protos:
                    pr.load_xml(i)
                conn = Connection(pr, os.environ['DISPLAY'])
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


class Test(unittest.TestCase):

    @xcbtest('xproto')
    def testAtom(self, conn):
        a1 = conn.InternAtom(only_if_exists=False, name="ZXCB")['atom']
        self.assertTrue(a1 > 200)
        self.assertTrue(isinstance(a1, int))
        a2 = conn.InternAtom(only_if_exists=True, name="WM_CLASS")['atom']
        self.assertEqual(a2, 67)
        self.assertNotEqual(a1, a2)

    @xcbtest('xproto')
    def testMoreAtoms(self, conn):
        totalatom = "TESTTESTTESTTESTTEST"
        for i in range(1, len(totalatom)):
            n = conn.InternAtom(only_if_exists=False,
                                name=totalatom[:i])['atom']
            self.assertTrue(n > 200)
            self.assertTrue(isinstance(n, int))


    @xcbtest('xproto')
    def testXid(self, conn):
        conn.connection()
        xid1 = conn.new_xid()
        xid2 = conn.new_xid()
        self.assertTrue(xid2 > xid1)
        self.assertTrue(isinstance(xid1, int))

    @xcbtest('xproto')
    def testWin(self, conn):
        win = conn.create_toplevel(
            bounds=Rectangle(10, 10, 100, 100),
            border=1,
            klass=conn.atom.XCB_WINDOW_CLASS_INPUT_OUTPUT,
            params={
                conn.CW.BackPixel: conn.init_data['black_pixel'],
                conn.CW.EventMask: conn.EventMask.Exposure | conn.EventMask.KeyPress,
                })

