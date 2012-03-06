from functools import partial
import subprocess

from .event import Event


class Events(dict):

    def __missing__(self, key):
        res = self[key] = Event('changed.'+key)
        return res


class CommandDispatcher(dict):

    def __init__(self):
        self.events = Events()

    def __setitem__(self, name, value):
        super().__setitem__(name, value)
        ev = self.events.get(name)
        if ev is not None:
            ev.emit()

    def call(self, obj, meth, *args):
        getattr(self[obj], 'cmd_' + meth)(*args)

    def callback(self, *args):
        return partial(self.call, *args)


class EnvCommands(object):

    def cmd_exec(self, *args):
        subprocess.Popen(args)

    def cmd_shell(self, *args):
        subprocess.Popen(args, shell=True)
