import os.path
from cairo import SolidPattern

from  .base import Widget, Padding


BATTERY_PATH = '/sys/class/power_supply'


class Battery(Widget):

    def __init__(self, *,
            which="BAT0",
            font_face="Consolas",
            font_size=18,
            color=SolidPattern(1, 1, 1),
            padding=Padding(2, 4, 8, 4),
            right=False):
        super().__init__(right=right)
        self.font_face = font_face
        self.font_size = font_size
        self.color = color
        self.padding = padding
        self.path = os.path.join(BATTERY_PATH, which)

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

        canvas.select_font_face(self.font_face)
        canvas.set_font_size(self.font_size)
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
