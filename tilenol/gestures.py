import ctypes
from math import atan2, pi, sqrt
from collections import defaultdict

from zorro import gethub, sleep
from zorro.util import marker_object
from zorro.di import has_dependencies, dependency

from tilenol.xcb import shm
from .event import Event
from .commands import CommandDispatcher

GRAD = pi/180
directions = {
    'up': lambda a, min=-160*GRAD, max=160*GRAD: a < min or a > max,
    'upright': lambda a, max=160*GRAD, min=110*GRAD: min <= a <= max,
    'right': lambda a, max=110*GRAD, min=70*GRAD: min < a < max,
    'downright': lambda a, max=70*GRAD, min=20*GRAD: min <= a <= max,
    'down': lambda a, max=20*GRAD, min=-20*GRAD: min < a < max,
    'downleft': lambda a, max=-20*GRAD, min=-70*GRAD: min <= a <= max,
    'left': lambda a, max=-70*GRAD, min=-110*GRAD: min < a < max,
    'upleft': lambda a, max=-110*GRAD, min=-160*GRAD: min <= a <= max,
    }
from .config import Config


SYNAPTICS_SHM = 23947
START = marker_object('gestures.START')
PARTIAL = marker_object('gestures.PARTIAL')
FULL = marker_object('gestures.FULL')
COMMIT = marker_object('gestures.COMMIT')
UNDO = marker_object('gestures.UNDO')
CANCEL = marker_object('gestures.CANCEL')


class SynapticsSHM(ctypes.Structure):
    _fields_ = [
        ('version', ctypes.c_int),
        # Current device state
        ('x', ctypes.c_int),
        ('y', ctypes.c_int),
        ('z', ctypes.c_int),  # pressure
        ('numFingers', ctypes.c_int),
        ('fingerWidth', ctypes.c_int),
        ('left', ctypes.c_int),  # buttons
        ('right', ctypes.c_int),
        ('up', ctypes.c_int),
        ('down', ctypes.c_int),
        ('multi', ctypes.c_bool * 8),
        ('middle', ctypes.c_bool),
        ]


@has_dependencies
class Gestures(object):

    config = dependency(Config, 'config')
    commander = dependency(CommandDispatcher, 'commander')

    def __init__(self):
        self.callbacks = defaultdict(list)

    def __zorro_di_done__(self):
        self.cfg = self.config.gestures()
        gethub().do_spawnhelper(self._shm_checker)

    def add_callback(self, name, fun):
        self.callbacks[name].append(fun)

    @property
    def active_gestures(self):
        return self.cfg.keys()

    def _shm_checker(self):
        shmid = shm.shmget(SYNAPTICS_SHM, ctypes.sizeof(SynapticsSHM), 0)
        if shmid < 0:
            raise RuntimeError("No synaptics driver loaded")
        addr = shm.shmat(shmid, None, 0)
        if addr < 0:
            raise RuntimeError("Can't attach SHM")
        try:
            struct = ctypes.cast(addr, ctypes.POINTER(SynapticsSHM))
            self._shm_loop(struct)
        finally:
            shm.shmdt(addr)

    def _shm_loop(self, ptr):
        while True:
            sleep(0.2)
            struct = ptr[0]
            if struct.numFingers >= 2:
                initialx = struct.x
                initialy = struct.y
                initialf = struct.numFingers
                gesture_prefix = '{}f-'.format(initialf)
                full = False
                name = None
                while initialf == struct.numFingers:
                    sleep(0.1)
                    dx = struct.x - initialx
                    dy = struct.y - initialy
                    angle = atan2(dx, dy)
                    dist = sqrt(dx*dx + dy*dy)
                    for name, cfg in self.cfg.items():
                        if not name.startswith(gesture_prefix):
                            continue
                        cond = cfg['condition']
                        if cond(angle) and dist > cfg['detect-distance']:
                            callbacks = self.callbacks[name]
                            break
                    else:
                        continue
                    break
                else:
                    continue
                for f in callbacks:
                    f(name, 0, START, cfg)

                while initialf == struct.numFingers:
                    sleep(0.1)
                    dx = struct.x - initialx
                    dy = struct.y - initialy
                    angle = atan2(dx, dy)
                    dist = sqrt(dx*dx + dy*dy)
                    percent = dist / cfg['commit-distance']
                    full = percent >= 1
                    if not cond(angle) or dist < cfg['detect-distance']:
                        for f in callbacks:
                            f(name, percent, UNDO, cfg)
                    else:
                        state = FULL if full else PARTIAL
                        for f in callbacks:
                            f(name, percent, state, cfg)

                if full:
                    for f in callbacks:
                        f(name, 1, COMMIT, cfg)
                    self.commander.callback(*cfg['action'])()
                else:
                    for f in callbacks:
                        f(name, 0, CANCEL, cfg)



