import logging

from zorro import Condition, gethub


log = logging.getLogger(__name__)


class Event(object):

    def __init__(self, name=None):
        self.name = name
        self._listeners = []
        self._worker = None
        self._condition = Condition()

    def listen(self, fun):
        self._listeners.append(fun)

    def emit(self):
        log.debug("Emitting event %r", self.name)
        if self._worker is None:
            self._worker = gethub().do_spawnhelper(self._do_work)
        else:
            self._condition.notify()

    def _do_work(self):
        while True:
            log.debug("Processing event %r", self.name)
            for l in self._listeners:
                l()
            self._condition.wait()


