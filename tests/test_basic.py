import unittest
import os

def xcbtest(*protos):
    def wrapper(fun):
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
