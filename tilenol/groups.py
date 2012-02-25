

class Group(object):

    def __init__(self, name, layout_class):
        self.name = name
        self.default_layout = layout_class
        self.current_layout = layout_class()

    def __repr__(self):
        return '<{} {}>'.format(self.__class__.__name__, self.name)
