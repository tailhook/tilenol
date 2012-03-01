from . import ewmh


class Classifier(object):

    def __init__(self):
        self.global_rules = []
        self.class_rules = {}

    def add_rule(self, condition, action, klass=None):
        if klass is None:
            self.global_rules.append((condition, action))
        else:
            if klass not in self.class_rules:
                self.class_rules[klass] = []
            self.class_rules[klass].append((condition, action))

    def default_rules(self):
        self.add_rule(ewmh.match_type(
            'UTILITY',
            'NOTIFICATION',
            'TOOLBAR',
            'SPLASH',
            ), set_property('floating', True))
        self.add_rule(ewmh.match_type(
            'UTILITY',
            ), set_property('floating', False),
            klass='Gimp')

    def apply(self, win):
        for condition, action in self.global_rules:
            if condition(win):
                action(win)

        for klass in self._split_class(win.props.get('WM_CLASS', '')):
            for condition, action in self.class_rules.get(klass, ''):
                if condition(win):
                    action(win)

    @staticmethod
    def _split_class(cls):
        for name in cls.split('\0'):
            if not name:
                continue
            yield name
            while '-' in name:
                name, _ = name.rsplit('-', 1)
                yield name


def set_property(name, value):
    def setter(win):
        setattr(win, name, value)
    return setter

