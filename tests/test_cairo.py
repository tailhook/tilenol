import unittest
import cairo
from .test_basic import xcbtest


class TestConn(unittest.TestCase):

    @xcbtest('xproto')
    def testPicture(self, conn):
        from zxcb.core import Core, Rectangle
        core = Core(conn)
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, 128, 128)
        ctx = cairo.Context(img)
        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.move_to(64, 0)
        ctx.line_to(128, 128)
        ctx.line_to(0, 128)
        ctx.fill()
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
        core.raw.MapWindow(window=win.wid)
        for ev in conn.get_events():
            print(ev)
            if ev.__class__.__name__ == 'ExposeEvent' and ev.window == win.wid:
                break
        gc = conn.new_xid()
        core.raw.CreateGC(
            cid=gc,
            drawable=conn.init_data['roots'][0]['root'],
            params={},
            )
        core.raw.PutImage(
            format=core.ImageFormat.XYPixmap,
            drawable=win.wid,
            gc=gc,
            width=128,
            height=128,
            dst_x=0,
            dst_y=0,
            left_pad=0,
            depth=32,
            data=img,
            )
        for ev in conn.get_events():
            print(ev)

