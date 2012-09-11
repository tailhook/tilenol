import sys
import pprint
import struct

from zorro import Hub
from tilenol.xcb import Connection, Proto
from tilenol.xcb.core import Core


def print_screen(core):
    # Strange hack because either wrong spec or wrong X server
    # We don't care about refresh rates any way
    scr = core.randr.GetScreenInfo(window=core.root_window)
    pprint.pprint(scr)
    scr = core.randr.GetScreenResources(window=core.root_window)
    pprint.pprint(scr)


def print_screen_size_range(core):
    scr = core.randr.GetScreenSizeRange(window=core.root_window)
    pprint.pprint(scr)


def print_xinerama(core):
    scr = core.xinerama.QueryScreens(window=core.root_window)
    pprint.pprint(scr)


def print_crtc(core):
    scr = core.randr.GetScreenResources(window=core.root_window)
    allinfo = {}
    for crtc in scr['crtcs']:
        cinfo = core.randr.GetCrtcInfo(
            crtc=crtc,
            config_timestamp=scr['config_timestamp'],
            )
        allinfo[crtc] = cinfo
    pprint.pprint(allinfo)

def print_crtc_extra(core):
    scr = core.randr.GetScreenResources(window=core.root_window)
    allinfo = {}
    for crtc in scr['crtcs']:
        cinfo = {
            'info': core.randr.GetCrtcInfo(
                crtc=crtc,
                config_timestamp=scr['config_timestamp'],
                ),
            'panning': core.randr.GetPanning(crtc=crtc),
            'transform': core.randr.GetCrtcTransform(crtc=crtc),
            'gamma': core.randr.GetCrtcGamma(crtc=crtc),
            }
        allinfo[crtc] = cinfo
    pprint.pprint(allinfo)


def print_output(core):
    scr = core.randr.GetScreenResources(window=core.root_window)
    allinfo = {}
    for output in scr['outputs']:
        oinfo = core.randr.GetOutputInfo(
            output=output,
            config_timestamp=scr['config_timestamp'],
            )
        oinfo['name'] = bytes(oinfo['name']).decode('utf-8')
        allinfo[output] = oinfo
    pprint.pprint(allinfo)


def print_providers(core):
    scr = core.randr.GetProviders(window=core.root_window)
    allinfo = {}
    for provider in scr['providers']:
        pinfo = core.randr.GetProviderInfo(provider=provider)
        allinfo[provider] = pinfo
    pprint.pprint(allinfo)


def disable_output(core, output):
    scr = core.randr.GetScreenResources(window=core.root_window)
    sinfo = core.randr.GetScreenInfo(window=core.root_window)
    anames = {}
    for oid in scr['outputs']:
        oinfo = core.randr.GetOutputInfo(
            output=oid,
            config_timestamp=scr['config_timestamp'],
            )
        anames[bytes(oinfo['name']).decode('utf-8')] = oid
    if output not in anames:
        print("No such output", file=sys.stderr)
    oid = anames[output]
    for crtc in scr['crtcs']:
        cinfo = core.randr.GetCrtcInfo(
            crtc=crtc,
            config_timestamp=scr['config_timestamp'],
            )
        if oid in cinfo['outputs']:
            res = core.randr.SetCrtcConfig(
                crtc=crtc,
                timestamp=0,
                config_timestamp=scr['config_timestamp'],
                x=cinfo['x'],
                y=cinfo['y'],
                mode=0,
                rotation=cinfo['rotation'],
                outputs=bytes([o for o in cinfo['outputs'] if o != oid]),
                )
    core.randr.SetOutputPrimary(
        window=core.root_window,
        output=scr['outputs'][0],
        )


def print_output_properties(core):
    scr = core.randr.GetScreenResources(window=core.root_window)
    allinfo = {}
    for output in scr['outputs']:
        lst = core.randr.ListOutputProperties(output=output)
        props = {}
        for atom in lst['atoms']:
            props[core.atom[atom].name] = core.randr.GetOutputProperty(
                output=output,
                property=atom,
                type=core.atom.Any,
                long_offset=0,
                long_length=128,
                delete=0,
                pending=0,
                )
        allinfo[output] = props
    pprint.pprint(allinfo)

def check_screens(core):
    scr = core.randr.GetScreenResources(window=core.root_window)
    allmapped = set()
    for crtc in scr['crtcs']:
        cinfo = core.randr.GetCrtcInfo(
            crtc=crtc,
            config_timestamp=scr['config_timestamp'],
            )
        allmapped.update(cinfo['outputs'])
    for oid in scr['outputs']:
        oinfo = core.randr.GetOutputInfo(
            output=oid,
            config_timestamp=scr['config_timestamp'],
            )
        oname = bytes(oinfo['name']).decode('utf-8')
        if oinfo['connection'] == 0 and oid not in allmapped:
            print("CONNECTED", oname)
            return True  # connected screen
        if oinfo['connection'] != 0 and oid in allmapped:
            print("DISCON", oname)
            return True  # disconnected screen
    return False

def configure_outputs(core):
    core.raw.GrabServer()
    try:
        sinfo = core.randr.GetScreenInfo(window=core.root_window)
        scr = core.randr.GetScreenResources(window=core.root_window)
        modes = {m['id']:m for m in scr['modes']}
        updates = []
        width = 0
        height = 0
        mm_width = 0
        mm_height = 0
        crtc_index = 0
        for idx, oid in enumerate(scr['outputs']):
            oinfo = core.randr.GetOutputInfo(
                output=oid,
                config_timestamp=scr['config_timestamp'],
                )
            oname = bytes(oinfo['name']).decode('utf-8')
            if oinfo['connection'] == 0:
                crtc = scr['crtcs'][crtc_index]
                crtc_index += 1
                cinfo = core.randr.GetCrtcInfo(
                    crtc=crtc,
                    config_timestamp=scr['config_timestamp'],
                    )
                mid = oinfo['modes'][0]
                updates.append(dict(
                    crtc=crtc,
                    timestamp=0,
                    config_timestamp=scr['config_timestamp'],
                    x=width,
                    y=0,
                    mode=oinfo['modes'][0],
                    rotation=cinfo['rotation'],
                    outputs=struct.pack('<L', oid),
                    ))
                width += modes[mid]['width']
                height = max(height, modes[mid]['height'])
                mm_width = oinfo['mm_width']
                mm_height = max(oinfo['mm_height'], mm_height)
        for crtc in scr['crtcs'][crtc_index:]:
            updates.append(dict(
                crtc=crtc,
                timestamp=0,
                config_timestamp=scr['config_timestamp'],
                x=0,
                y=0,
                mode=0,
                rotation=1,
                outputs=b'',
                ))
        core.randr.SetScreenSize(
            window=core.root_window,
            width=width,
            height=height,
            mm_width=mm_width,
            mm_height=mm_height,
            )
        for up in updates:
            core.randr.SetCrtcConfig(**up)
    finally:
        core.raw.UngrabServer()


def get_options():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--screen', dest='action',
        help="Show screen properties",
        action='store_const', const='screen', default='help')
    ap.add_argument('--check', dest='action',
        help="Returns non-zero exit status if either some mapped screens"
             " disconnected, or some unmapped screens connected",
        action='store_const', const='check', default='help')
    ap.add_argument('--crtcs', dest='action',
        help="Show CRTCs",
        action='store_const', const='crtc')
    ap.add_argument('--crtc-extra', dest='action',
        help="Show extra CRTC info",
        action='store_const', const='crtc_extra')
    ap.add_argument('--outputs', dest='action',
        help="Show outputs",
        action='store_const', const='output')
    ap.add_argument('--providers', dest='action',
        help="Show providers",
        action='store_const', const='providers')
    ap.add_argument('--output-properties', dest='action',
        help="Show output properties",
        action='store_const', const='output_properties')
    ap.add_argument('--xinerama', dest='action',
        help="Show xinerama info",
        action='store_const', const='xinerama')
    ap.add_argument('--screen-size-range', dest='action',
        help="Show screen size range",
        action='store_const', const='screen_size_range')
    ap.add_argument('--disable', dest='disable', metavar="X",
        help="Disable screen by name (like xrandr --output X --off)",
        default=None)
    ap.add_argument('--auto-config', dest='action',
        help="Disable screen by name (like xrandr --output X --off)",
        action='store_const', const='autoconfig')
    ap.add_argument('--all', dest='action',
        help="Show all available data (except output properties)",
        action='store_const', const='all')
    return ap


def print_help(ap):
    ap.print_help()


def main():
    ap = get_options()
    options = ap.parse_args()
    retcode = 0

    hub = Hub()
    @hub.run
    def main():
        nonlocal retcode
        proto = Proto()
        proto.load_xml('xproto')
        proto.load_xml('randr')
        proto.load_xml('xinerama')
        core = Core(Connection(proto))
        core.randr._proto.requests['GetScreenInfo'].reply.items['rates'].code \
            = compile('0', 'XPROTO', 'eval')

        if options.disable is not None:
            disable_output(core, options.disable)
        elif options.action == 'help':
            val = core.randr._proto.requests['SetCrtcConfig'].read_from(
                b"\226\25\10\0"
                b"@\0\0\0" #crtc
                b"\0\0\0\0" # timestamp
                b"mi&\6" #cfg timestamp
                b"\200\7" # x
                b"\0\0" # y
                b"\270\0\0\0" # mode
                b"\1\0" # rotation
                b"\0\0" # padding
                b"D\0\0\0" # output
                , 4)
            print_help(ap)
        elif options.action == 'all':
            print_screen(core)
            print_screen_size_range(core)
            print_crtc(core)
            print_output(core)
            print_xinerama(core)
        elif options.action == 'screen':
            print_screen(core)
        elif options.action == 'screen_size_range':
            print_screen_size_range(core)
        elif options.action == 'crtc':
            print_crtc(core)
        elif options.action == 'crtc_extra':
            print_crtc_extra(core)
        elif options.action == 'output':
            print_output(core)
        elif options.action == 'output_properties':
            print_output_properties(core)
        elif options.action == 'xinerama':
            print_xinerama(core)
        elif options.action == 'providers':
            print_providers(core)
        elif options.action == 'autoconfig':
            configure_outputs(core)
        elif options.action == 'check':
            retcode = check_screens(core)
    sys.exit(retcode)


if __name__ == '__main__':
    main()
