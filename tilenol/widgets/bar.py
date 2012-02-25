from zorro.di import has_dependencies, dependency

from tilenol.xcb import Core
from tilenol.screen import ScreenManager


@has_dependencies
class Bar(object):

    xcore = dependency(Core, 'xcore')
    screenman = dependency(ScreenManager, 'screen-manager')

    def __init__(self, widgets,
                 screen_no=0,
                 height=24,
                 background=0x000000,
                 ):
        self.widgets = widgets
        self.screen_no = screen_no
        self.height = height
        self.background = background

    def __zorro_di_done__(self):
        scr = self.screenman.screens[self.screen_no]
        scr.add_top_bar(self)
        scr.add_listener(self.update_screen)

    def update_screen(self, screen):
        self.width = screen.bounds.width

    def create_window(self):
        self.window = Window(self.xcore.create_toplevel(
            self.bar.bounds(),
            klass=self.xcore.WindowClass.InputOutput,
            params={
                self.xcore.CW.EventMask: EM.Expose,
                self.xcore.CW.OverrideRedirect: True,
                self.xcore.CW.BackPixel: self.background
            }))


