import os.path
import shlex
import re
import logging


log = logging.getLogger(__name__)
separator = re.compile('^[-_]+$')
NoDefault = object()


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

    def find_file(self, name, required=True):
        for dir in self.dirs:
            for ext in self.extensions:
                fname = os.path.join(dir, name + ext)
                if os.path.exists(fname):
                    return fname
        if required:
            raise RuntimeError("File {!r} not found".format(
                os.path.join(self.dirs[0], name + '.yaml')))

    def get_config(self, name, data=NoDefault):
        fname = self.find_file('tilenol/'+name, required=data is NoDefault)
        if fname is None:
            if data is not NoDefault:
                return data
            return
        if fname.endswith('.json'):
            with open(fname, 'rt') as f:
                import json
                return json.load(f)
        elif fname.endswith('.yaml'):
            with open(fname, 'rb') as f:
                import yaml
                return yaml.load(f)
        if data is not NoDefault:
            return data
        return


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
        config = self.config.get_config('config', {})
        self.data = config

    def keys(self):
        for k, v in self.config.get_config('hotkeys', {}).items():
            if isinstance(v, str):
                yield k, shlex.split(v)
            else:
                yield k, v

    def theme(self):
        from tilenol.theme import Theme
        theme = Theme()
        if self.data.get('theme'):
            theme.update_from(self.config.get_config('themes/'
                + self.data['theme'], {}))
        theme.update_from(self.config.get_config('theme-customize', {}))
        theme.update_from(self.data.get('theme-customize', {}))
        return theme

    def groups(self):
        from tilenol.groups import Group
        groups = []
        if 'groups' in self.data:
            from tilenol.layout import examples
            try:
                from tilenol.layout import layouts
            except ImportError:
                log.warning("Can't import layouts module,"
                            " extra layouts are not available")
            for name, lname in self.data['groups'].items():
                try:
                    lay = (getattr(examples, lname, None)
                           or getattr(layouts, lname))
                except AttributeError:
                    log.warning('Layout %r is not available', lname)
                    lay = examples.Tile2
                groups.append(Group(str(name), lay))
        else:
            from tilenol.layout import Tile
            for i in range(10):
                groups.append(Group(str(i), Tile))
        return groups

    def bars(self):
        bars = self.data.get('bars')
        if not bars:
            bars = self.config.get_config('bars', {})
        from tilenol import widgets
        for binfo in bars:
            w = []
            for winfo in binfo.pop('left', ()):
                if isinstance(winfo, dict):
                    for typ, params in winfo:
                        break
                else:
                    typ = winfo
                    params = {}
                if separator.match(typ):
                    typ = 'Sep'
                wclass = getattr(widgets, typ)
                w.append(wclass(**params))
            for winfo in reversed(binfo.pop('right', ())):
                if isinstance(winfo, dict):
                    for typ, params in winfo:
                        break
                else:
                    typ = winfo
                    params = {}
                if separator.match(typ):
                    typ = 'Sep'
                params['right'] = True
                wclass = getattr(widgets, typ)
                w.append(wclass(**params))
            sno = int(binfo.pop('screen', 0))
            bar = widgets.Bar( w, **binfo)
            yield sno, bar


