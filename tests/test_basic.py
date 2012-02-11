import unittest
import os


class Test(unittest.TestCase):

    def testAtom(self):
        from zxcb.xproto import read_auth, Proto, Connection
        from zorro import Hub
        err = []
        hub = Hub()
        def real_test():
            pr = Proto()
            pr.load_xml('xproto')
            pr.load_xml('xc_misc')
            conn = Connection(pr, os.environ['DISPLAY'])
            a1 = conn.InternAtom(only_if_exists=False, name="ZXCB")['atom']
            self.assertTrue(a1 > 200)
            self.assertTrue(isinstance(a1, int))
            a2 = conn.InternAtom(only_if_exists=True, name="WM_CLASS")['atom']
            self.assertEqual(a2, 67)
            self.assertNotEqual(a1, a2)
        @hub.run
        def test():
            try:
                real_test()
            except Exception as e:
                err.append(e)
        if err:
            raise err[0]
