import os, os.path
import logging, logging.handlers

from zorro import Hub

from .options import get_options
from .main import Tilenol


def main():
    ap = get_options()
    options = ap.parse_args()
    if options.log_stdout:
        logging.basicConfig(level=logging.WARNING)
    else:
        os.environ.setdefault('XDG_CACHE_HOME', os.path.expanduser('~/.cache'))
        dir = os.path.expandvars('$XDG_CACHE_HOME/tilenol')
        if not os.path.exists(dir):
            os.makedirs(dir)
        root = logging.getLogger()
        filename = os.path.expandvars('$XDG_CACHE_HOME/tilenol/tilenol.log')
        root.addHandler(logging.handlers.RotatingFileHandler(
            filename,
            maxBytes=1 << 20, # 1Mb
            backupCount=1,
            ))
        try:
            print("Logging is redirected to", filename)
        except IOError:
            pass  # no console to write to, that's ok
    hub = Hub()
    hub.run(Tilenol(options).run)

if __name__ == '__main__':
    main()
