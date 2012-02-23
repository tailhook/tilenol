from zorro import Hub

from .options import get_options
from .main import Tilenol


def main():
    ap = get_options()
    options = ap.parse_args()
    hub = Hub()
    hub.run(Tilenol(options).run)

if __name__ == '__main__':
    main()
