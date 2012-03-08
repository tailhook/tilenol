import os.path

from cairo import SolidPattern
from zorro.di import has_dependencies, dependency

from  .base import Widget
from tilenol.theme import Theme


BATTERY_PATH = '/sys/class/power_supply'


@has_dependencies
class Battery(Widget):

    theme = dependency(Theme, 'theme')

    def __init__(self, *, which="BAT0", right=False):
        super().__init__(right=right)
        self.which = which

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.color = bar.text_color_pat
        self.padding = bar.text_padding
        self.path = os.path.join(BATTERY_PATH, self.which)

    def get_file(self, name):
        with open(os.path.join(self.path, name), 'rt') as f:
            return f.read().strip()

    def draw(self, canvas, l, r):
        stat = self.get_file('status')
        now = float(self.get_file('energy_now'))
        full = float(self.get_file('energy_full'))
        power = float(self.get_file('power_now'))

        perc = now/full
        if perc > 0.99:
            txt = '100%'
        elif stat.lower() == 'charging':
            hour = int((full - now)/power)
            min = int((full - now)/power) % 60
            txt = '{:.0%} + {:02d}:{:02d}'.format(perc, hour, min)
        else:
            hour = int(now/power)
            min = int(now/power*60) % 60
            txt = '{:.0%} - {:02d}:{:02d}'.format(perc, hour, min)

        self.font.apply(canvas)
        canvas.set_source(self.color)
        _, _, w, h, _, _ = canvas.text_extents(txt)
        if self.right:
            x = r - self.padding.right - w
            r -= self.padding.left + self.padding.right + w
        else:
            x = l + self.padding.left
            l += self.padding.left + self.padding.right + w
        canvas.move_to(x, self.height - self.padding.bottom)
        canvas.show_text(txt)
        return l, r
