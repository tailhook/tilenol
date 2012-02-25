from .xcb import Rectangle


class ScreenManager(object):

    def __init__(self, rectangles):
        self.screens = []
        for rect in rectangles:
            scr = Screen()
            scr.set_bounds(rect)
            self.screens.append(scr)


class Screen(object):

    def __init__(self):
        self.topbars = []
        self.listeners = []

    def set_bounds(self, rect):
        self.bounds = rect
        x, y, w, h = rect
        for bar in self.topbars:
            y += bar.height
            h -= bar.height
        # TODO(tailhook) impement other bars
        self.inner_bounds = Rectangle(x, y, w, h)
        print("INNER", self.inner_bounds)
        for l in self.listeners:
            l(self)

    def add_listener(self, callable):
        self.listeners.append(callable)

    def add_top_bar(self, bar):
        self.topbars.append(bar)
        self.set_bounds(self.bounds)

