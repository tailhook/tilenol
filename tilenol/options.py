import argparse

def get_options():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log-stdout', default=False, action='store_true',
        help="Enable logging to stdout (default ~/.cache/tilenol/tilenol.log)")
    return ap
