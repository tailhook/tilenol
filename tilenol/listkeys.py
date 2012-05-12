import sys

from zorro import Hub
from tilenol.xcb import Connection, Proto
from tilenol.xcb.core import Core
from tilenol.xcb.keysymparse import Keysyms


def list_keysyms(options, xcore, keysyms, **kw):
    syms = []
    for ksym, kcode in xcore.keysym_to_keycode.items():
        try:
            kname = keysyms.code_to_name[ksym]
        except KeyError:
            print("Can't find name for", ksym, file=sys.stderr)
        else:
            syms.append(kname)
    for sym in sorted(syms):
        if options.debug:
            num = keysyms.name_to_code[sym]
            print(sym, 'ksym:', num, 'codes:',
                ','.join(map(str, xcore.keysym_to_keycode[num])))
        else:
            print(sym)


def get_options():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--keysyms', dest='action',
        help="Show all keysyms available for binding (without modifiers)",
        action='store_const', const='keysyms', default='keysyms')
    ap.add_argument('-d', '--debug',
        help="Print more debugging info",
        dest='debug', action='store_true', default=False)
    return ap


def main():
    ap = get_options()
    options = ap.parse_args()

    hub = Hub()
    @hub.run
    def main():
        proto = Proto()
        proto.load_xml('xproto')
        core = Core(Connection(proto))
        core.init_keymap()
        ksyms = Keysyms()
        ksyms.load_default()

        if options.action == 'keysyms':
            list_keysyms(options, xcore=core, keysyms=ksyms)

if __name__ == '__main__':
    main()
