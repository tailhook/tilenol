from zorro import Hub

from .options import get_options
from .main import run


def main():
    ap = get_options()
    options = ap.parse_args()
    hub = Hub()
    hub.run(lambda: run(options))

if __name__ == '__main__':
    main()
