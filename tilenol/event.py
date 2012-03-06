import logging

from zorro import Condition, gethub


log = logging.getLogger(__name__)


class Event(object):

    def __init__(self, name=None):
        self.name = name
        self._listeners = []
        self._worker = None

    def listen(self, fun):
        self._listeners.append(fun)

    def unlisten(self, fun):
        self._listeners.remove(fun)

    def emit(self):
        log.debug("Emitting event %r", self.name)
        if self._worker is None and self._listeners:
            self._worker = gethub().do_spawn(self._do_work)

    def _do_work(self):
        try:
            log.debug("Processing event %r", self.name)
            for l in self._listeners:
                l()
        finally:
            self._worker = None


