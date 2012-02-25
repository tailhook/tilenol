import os.path
import shlex


class PathGen(object):

    def __init__(self, dir_env, dir_default, *,
            dirs_env=None,
            dirs_default=None,
            extensions=('.json', '.yaml')):
        dir = os.environ.get(dir_env, dir_default)
        lst = [os.path.expanduser(dir)]
        if dirs_env is not None or dirs_default is not None:
            dirs = os.environ.get(dirs_env, dirs_default).split(':')
            lst.extend(filter(bool, dirs))
        self.dirs = lst
        self.extensions = extensions

    def __getitem__(self, name):
        for dir in self.dirs:
            for ext in self.extensions:
                fname = os.path.join(dir, name + ext)
                if os.path.exists(fname):
                    return fname
        raise RuntimeError("File {!r} not found".format(
            os.path.join(self.dirs[0], name + '.yaml')))

    def get_config(self, name):
        fname = self['tilenol/'+name]
        if fname.endswith('.json'):
            with open(fname, 'rt') as f:
                import json
                return json.load(f)
        elif fname.endswith('.yaml'):
            with open(fname, 'rb') as f:
                import yaml
                return yaml.load(f)


class Config(object):

    def __init__(self):
        self.config = PathGen(
            dir_env='XDG_CONFIG_HOME',
            dir_default='~/.config',
            dirs_env='XDG_CONFIG_DIRS',
            dirs_default='/etc/xdg',
            )
        self.data = PathGen(
            dir_env="XDG_DATA_HOME",
            dir_default="~/.local/share",
            dirs_env="XDG_DATA_DIRS",
            dirs_default="/usr/local/share:/usr/share")
        self.cache = PathGen("XDG_CACHE_HOME", "~/.cache")
        self.runtime = PathGen("XDG_RUNTIME_DIR", "~/.cache/tilenol")

    def keys(self):
        for k, v in self.config.get_config('hotkeys').items():
            if isinstance(v, str):
                yield k, shlex.split(v)
            else:
                yield k, v

