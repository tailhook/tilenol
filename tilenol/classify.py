from zorro.di import di

from .ewmh import match_type


class Classifier(object):

    def __init__(self):
        self.global_rules = []
        self.class_rules = {}

    def add_rule(self, conditions, actions, klass=None):
        if klass is None:
            self.global_rules.append((conditions, actions))
        else:
            if klass not in self.class_rules:
                self.class_rules[klass] = []
            self.class_rules[klass].append((conditions, actions))


    def apply(self, win):
        for conditions, actions in self.global_rules:
            if all(cond(win) for cond in conditions):
                for act in actions:
                    act(win)
        for klass in self._split_class(win.props.get('WM_CLASS', '')):
            for conditions, actions in self.class_rules.get(klass, ''):
                if all(cond(win) for cond in conditions):
                    for act in actions:
                        act(win)

    @staticmethod
    def _split_class(cls):
        for name in cls.split('\0'):
            if not name:
                continue
            yield name
            while '-' in name:
                name, _ = name.rsplit('-', 1)
                yield name


def match_role(*roles):
    def checker(win):
        for typ in roles:
            if typ == win.props.get('WM_WINDOW_ROLE'):
                return True
    return checker


def has_property(*properties):
    def checker(win):
        for prop in properties:
            if prop in win.props:
                return True
    return checker


def layout_properties(**kw):
    def setter(win):
        for k, v in kw.items():
            setattr(win.lprops, k, v)
    return setter


def ignore_hints(ignore):
    def setter(win):
        win.ignore_hints = True
    return setter


def move_to_group_of(prop):
    def setter(win):
        wid = win.props[prop][0]
        other = di(win)['event-dispatcher'].all_windows[wid]
        win.lprops.group = other.lprops.group
    return setter


def move_to_group(group):
    def setter(win):
        gman = di(win)['group-manager']
        if group in gman.by_name:
            win.lprops.group = gman.groups.index(gman.by_name[group])
    return setter


all_conditions = {
    'match-role': match_role,
    'match-type': match_type,
    'has-property': has_property,
    }
all_actions = {
    'layout-properties': layout_properties,
    'ignore-hints': ignore_hints,
    'move-to-group-of': move_to_group_of,
    'move-to-group': move_to_group,
    }
