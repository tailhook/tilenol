from math import pi

from zorro.di import dependency, has_dependencies

from  .base import Widget
from tilenol.theme import Theme
from tilenol import gestures as G


GRAD = pi/180
rotations = {
    'up': 0*GRAD,
    'upright': 45*GRAD,
    'right': 90*GRAD,
    'downright': 135*GRAD,
    'down': 180*GRAD,
    'downleft': -135*GRAD,
    'left': -90*GRAD,
    'upleft': -45*GRAD,
    }


@has_dependencies
class Gesture(Widget):

    theme = dependency(Theme, 'theme')
    gestures = dependency(G.Gestures, 'gestures')

    def __init__(self, *, gestures=None, right=False):
        super().__init__(right=right)
        self.format = format
        self.gesture_names = gestures
        self.state = (None, None, None, None)

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.color = bar.text_color_pat
        self.background = bar.background_pat
        self.dig = bar.bright_color_pat
        self.inactive_color = bar.dim_color_pat
        self.padding = bar.text_padding
        self.gwidth = self.height - self.padding.top - self.padding.bottom
        if self.gesture_names is None:
            for name in self.gestures.active_gestures:
                self.gestures.add_callback(name, self._update_gesture)
        else:
            for name in self.gesture_names:
                self.gestures.add_callback(name, self._update_gesture)

    def _update_gesture(self, name, percent, state, cfg):
        px = min(int(percent*self.gwidth), self.gwidth)
        st = (name, px, state, cfg)
        if self.state != st:
            if state in {G.CANCEL, G.COMMIT}:
                self.state = (None, None, None, None)
            else:
                self.state = st
            self.bar.redraw.emit()

    def draw(self, canvas, l, r):
        name, offset, state, cfg = self.state
        if not name:
            return l, r
        fin, dir = name.split('-')
        nfin = int(fin[:-1])
        char = cfg['char']
        self.font.apply(canvas)
        if state == G.FULL:
            canvas.set_source(self.color)
        else:
            canvas.set_source(self.inactive_color)
        _, _, w, h, _, _ = canvas.text_extents(char)
        if self.right:
            x = r - self.padding.right - w
            r -= self.padding.left + self.padding.right + w
        else:
            x = l + self.padding.left
            l += self.padding.left + self.padding.right + w
        cx = x + w/2
        cy = self.padding.top + self.gwidth/2
        canvas.translate(cx+1, cy)
        canvas.rotate(rotations[dir])
        canvas.translate(-cx, -cy)
        canvas.translate(0, self.gwidth/2 - offset)
        canvas.move_to(x, self.height - self.padding.bottom)
        canvas.show_text(char)
        return l, r
