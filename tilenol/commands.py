from functools import partial
import subprocess


class CommandDispatcher(dict):

    def call(self, obj, meth, *args):
        getattr(self[obj], 'cmd_' + meth)(*args)

    def callback(self, *args):
        return partial(self.call, *args)


class EnvCommands(object):

    def cmd_exec(self, *args):
        subprocess.Popen(args)

    def cmd_shell(self, *args):
        subprocess.Popen(args, shell=True)
