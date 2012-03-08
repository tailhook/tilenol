import time

import cairo
from zorro import gethub, sleep
from zorro.di import has_dependencies, dependency

from .base import Widget
from tilenol.theme import Theme


@has_dependencies
class _Graph(Widget):
    fixed_upper_bound = False

    theme = dependency(Theme, 'theme')

    def __init__(self, samples=60, right=False):
        super().__init__(right=right)
        self.samples = samples
        self.values = [0]*self.samples
        self.maxvalue = 0

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.padding = bar.box_padding
        self.graph_color = bar.graph_color_pat
        self.fill_color = bar.graph_fill_color_pat
        self.line_width = bar.graph_line_width
        gethub().do_spawnhelper(self._update_handler)

    def _update_handler(self):
        while True:
            tts = 1.0 - (time.time() % 1.0)
            if tts < 0.001:
                tts = 1
            sleep(tts)
            self.update()
            self.bar.redraw.emit()

    def draw(self, canvas, l, r):
        canvas.set_line_join(cairo.LINE_JOIN_ROUND)
        canvas.set_source(self.graph_color)
        canvas.set_line_width(self.line_width)
        h = self.height - self.padding.top - self.padding.bottom
        k = h/(self.maxvalue or 1)
        y = self.height - self.padding.bottom
        if self.right:
            start = current = r - self.padding.right - self.samples
        else:
            start = current = l + self.padding.left
        canvas.move_to(current, y - self.values[-1]*k)
        for val in reversed(self.values):
            canvas.line_to(current, y-val*k)
            current += 1
        canvas.stroke_preserve()
        canvas.line_to(current, y + self.line_width/2.0)
        canvas.line_to(start, y + self.line_width/2.0)
        canvas.set_source(self.fill_color)
        canvas.fill()
        if self.right:
            return l, r - self.padding.left - self.padding.right - self.samples
        else:
            return l + self.padding.left + self.padding.right + self.samples, r

    def push(self, value):
        self.values.insert(0, value)
        self.values.pop()
        if not self.fixed_upper_bound:
            self.maxvalue = max(self.values)
        self.bar.redraw.emit()


class CPUGraph(_Graph):
    fixed_upper_bound = True

    def __init__(self, samples=60, right=False):
        super().__init__(samples=samples, right=right)
        self.maxvalue = 100
        self.oldvalues = self._getvalues()

    def _getvalues(self):
        with open('/proc/stat') as file:
            all_cpus = next(file)
            name, user, nice, sys, idle, iowait, tail = all_cpus.split(None, 6)
            return int(user), int(nice), int(sys), int(idle)

    def update(self):
        nval = self._getvalues()
        oval = self.oldvalues
        busy = (nval[0]+nval[1]+nval[2] - oval[0]-oval[1]-oval[2])
        total = busy+nval[3]-oval[3]
        if total:
            # sometimes this value is zero for unknown reason (time shift?)
            # we just skip the value, because it gives us no info about
            # cpu load, if it's zero
            self.push(busy*100.0/total)
        self.oldvalues = nval


def get_meminfo():
    with open('/proc/meminfo') as file:
        val = {}
        for line in file:
            key, tail = line.split(':')
            uv = tail.split()
            val[key] = int(uv[0])
    return val


class MemoryGraph(_Graph):
    fixed_upper_bound = True

    def __init__(self, samples=60, right=False):
        super().__init__(samples=samples, right=right)
        self.oldvalues = self._getvalues()
        self.maxvalue = self.oldvalues['MemTotal']

    def _getvalues(self):
        return get_meminfo()

    def update(self):
        val = self._getvalues()
        self.push(val['MemTotal'] - val['MemFree'] - val['Inactive'])


class SwapGraph(_Graph):
    fixed_upper_bound = True

    def __init__(self, samples=60, right=False):
        super().__init__(samples=samples, right=right)
        self.oldvalues = self._getvalues()
        self.maxvalue = self.oldvalues['SwapTotal']

    def _getvalues(self):
        return get_meminfo()

    def update(self):
        val = self._getvalues()
        swap = val['SwapTotal'] - val['SwapFree'] - val['SwapCached']
        self.push(swap)
