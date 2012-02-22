import sys

from .xcb import Connection, Proto, Core


class TilenolConn(Connection):

    def event_dispatcher(self, ev):
        print("EVENT", ev)


def run(options):
    proto = Proto()
    proto.load_xml('xproto')
    conn = Connection(proto)
    conn.connection()
    core = Core(conn)
    core.raw.ChangeWindowAttributes(
        window=conn.init_data['roots'][0]['root'],
        params={
            core.CW.EventMask: core.EventMask.StructureNotify
                             | core.EventMask.SubstructureNotify
                             | core.EventMask.SubstructureRedirect
                             | core.EventMask.EnterWindow
                             | core.EventMask.LeaveWindow
        })
    attr = core.raw.GetWindowAttributes(
        window=conn.init_data['roots'][0]['root'])
    if not (attr['your_event_mask'] & core.EventMask.SubstructureRedirect):
        print("Probably another window manager is running", file=sys.stderr)
        return

    from zorro import sleep
    sleep(1000)
