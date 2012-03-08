import datetime
import time

from zorro.di import dependency, has_dependencies
from zorro import gethub, sleep
from cairo import SolidPattern

from  .base import Widget
from tilenol.theme import Theme


@has_dependencies
class Clock(Widget):

    theme = dependency(Theme, 'theme')

    def __init__(self, *, format="%H:%M:%S %d.%m.%Y", right=False):
        super().__init__(right=right)
        self.format = format

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.color = bar.text_color_pat
        self.padding = bar.text_padding
        gethub().do_spawnhelper(self._update_time)

    def _update_time(self):
        while True:
            tts = 1.0 - (time.time() % 1.0)
            if tts < 0.001:
                tts = 1
            sleep(tts)
            self.bar.redraw.emit()

    def _time(self):
        return datetime.datetime.now().strftime(self.format)

    def draw(self, canvas, l, r):
        self.font.apply(canvas)
        canvas.set_source(self.color)
        tm = self._time()
        _, _, w, h, _, _ = canvas.text_extents(tm)
        if self.right:
            x = r - self.padding.right - w
            r -= self.padding.left + self.padding.right + w
        else:
            x = l + self.padding.left
            l += self.padding.left + self.padding.right + w
        canvas.move_to(x, self.height - self.padding.bottom)
        canvas.show_text(tm)
        return l, r
