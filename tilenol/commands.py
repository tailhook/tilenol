from functools import partial
import subprocess


class CommandDispatcher(object):

    def __init__(self):
        self.objects = {}

    def __setitem__(self, name, value):
        self.objects[name] = value

    def __delitem__(self, name):
        del self.objects[name]

    def call(self, obj, meth, *args):
        getattr(self.objects[obj], 'cmd_' + meth)(*args)

    def callback(self, *args):
        return partial(self.call, *args)


class EnvCommands(object):

    def cmd_exec(self, *args):
        subprocess.Popen(args)

    def cmd_shell(self, *args):
        subprocess.Popen(args, shell=True)
