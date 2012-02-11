import xcb.xproto

conn = xcb.Connection()

def mkatom(name):
    return conn.core.InternAtom(False, len(name), name).reply().atom

prop = mkatom('hello')
print("HELLO", prop)
prop = mkatom('world')
print("WORLD", prop)


while False:
    conn.core.GetProperty(
            False, 0x15d,
            prop,
            xcb.xproto.GetPropertyType.Any,
            0, (2**32)-1
        ).reply()
    break
