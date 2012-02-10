import xcb.xproto

conn = xcb.Connection()

def mkatom(name):
    return conn.core.InternAtom(False, len(name), name).reply().atom

prop = mkatom('XFree86_VT')

while True:
    conn.core.GetProperty(
            False, 0x15d,
            prop,
            xcb.xproto.GetPropertyType.Any,
            0, (2**32)-1
        ).reply()
    break
