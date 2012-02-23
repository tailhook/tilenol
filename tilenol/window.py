from collections import namedtuple

from zorro.di import has_dependencies, dependency

from .xcb import Core


SizeRequest = namedtuple('SizeRequest', 'x y width height border')

class SizeRequest(object):
    def __init__(self, x, y, width, height, border):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.border = border

    @classmethod
    def from_notify(cls, notify):
        return cls(
            x=notify.x,
            y=notify.y,
            width=notify.width,
            height=notify.height,
            border=notify.border_width,
            )


@has_dependencies
class Window(object):

    xcore = dependency(Core, 'xcore')

    def __init__(self, wid):
        self.wid = wid

    @classmethod
    def from_notify(cls, notify):
        win = cls(notify.window)
        win.parent = notify.parent
        win.override = notify.override_redirect
        win.size_request = SizeRequest.from_notify(notify)
        return win

    def update_size_request(self, req):
        msk = self.xcore.ConfigWindow
        sr = self.size_request
        if req.value_mask & msk.X:
            sr.x = req.x
        if req.value_mask & msk.Y:
            sr.y = req.y
        if req.value_mask & msk.Width:
            sr.width = req.width
        if req.value_mask & msk.Height:
            sr.height = req.height

    def __index__(self):
        return self.wid

    def show(self):
        self.xcore.raw.MapWindow(window=self)

