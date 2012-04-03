import string
from functools import partial

from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core as XCore, Keysyms
from tilenol.events import EventDispatcher
from tilenol.theme import Theme


@has_dependencies
class GadgetBase(object):

    xcore = dependency(XCore, 'xcore')
    theme = dependency(Theme, 'theme')


all_keys = {}


def key(key):
    def wrapper(fun):
        all_keys[key] = fun
        return fun
    return wrapper


@has_dependencies
class TextField(object):

    xcore = dependency(XCore, 'xcore')
    keysyms = dependency(Keysyms, 'keysyms')

    def __init__(self, theme, events):
        self.value = ""
        self.sel_start = 0
        self.sel_width = 0
        self.theme = theme
        self.events = events

    def __zorro_di_done__(self):
        self.key_table = {}
        for k, fun in all_keys.items():
            mod, key = self.parse_key(k)
            self.key_table[mod, key] = partial(fun, self)

    def parse_key(self, keystr):
        mod = 0
        if keystr[0] == '<':
            keystr = keystr[1:-1]
            if '-' in keystr:
                mstr, sym = keystr.split('-')
                if 'S' in mstr:
                    mod |= self.core.ModMask.Shift
                if 'C' in mstr:
                    mod |= self.core.ModMask.Control
                if 'W' in mstr:
                    mod |= getattr(self.core.ModMask, '4')
            else:
                sym = keystr
        else:
            if sym.lower() != sym:
                mod = self.core.ModMask.Shift
            sym = sym.lower()
        code = self.keysyms.name_to_code[sym]
        return mod, code

    def handle_keypress(self, event):
        sym = self.xcore.keycode_to_keysym[event.detail]
        mod = self.xcore.modifiers_mask & event.state
        meth = self.key_table.get((mod, sym))
        if meth is not None:
            meth()
            self.events['draw'].emit()
            return
        if mod not in (self.xcore.ModMask.Shift, 0):
            # TODO(tailhook) capitals?
            return
        ch = chr(sym)
        if mod & self.xcore.ModMask.Shift:
            ch = chr(self.xcore.shift_keycode_to_keysym[event.detail])
        if ch in string.printable and ch != '\n':
            self._clearsel(ch)
            self.sel_start += 1
        self.events['draw'].emit()

    def _clearsel(self, value=''):
        self.value = (self.value[:self.sel_start]
                      + value
                      + self.value[self.sel_start+self.sel_width:])
        self.sel_width = 0

    @key('<BackSpace>')
    def do_bs(self):
        if not self.sel_width:
            self.sel_start -= 1
            self.sel_width += 1
        self._clearsel()

    @key('<Delete>')
    def do_del(self):
        if not self.sel_width:
            self.sel_width += 1
        self._clearsel()

    @key('<Left>')
    def do_left(self):
        if not self.sel_width:
            self.sel_start -= 1
        self.sel_width = 0

    @key('<Right>')
    def do_right(self):
        if self.sel_width:
            self.sel_start += self.sel_width
            self.sel_width = 0
        else:
            self.sel_start += 1

    @key('<Return>')
    def do_submit(self):
        if 'submit' in self.events:
            self.events['submit'].emit()

    @key('<Tab>')
    def do_complete(self):
        if 'complete' in self.events:
            self.events['complete'].emit()

    @key('<Escape>')
    def do_close(self):
        if 'close' in self.events:
            self.events['close'].emit()

    def draw(self, canvas):
        sx, sy, tw, th, ax, ay = canvas.text_extents(self.value)
        one = self.value[0:self.sel_start]
        two = self.value[self.sel_start:self.sel_start+self.sel_width]
        three = self.value[self.sel_start+self.sel_width:]
        self.theme.font.apply(canvas)
        canvas.move_to(self.theme.padding.left,
            self.theme.line_height - self.theme.padding.bottom)
        canvas.set_source(self.theme.text_pat)
        canvas.show_text(one)
        x, y = canvas.get_current_point()
        canvas.fill()
        if two:
            sx, sy, tw, th, ax, ay = canvas.text_extents(two)
            canvas.set_source(self.theme.selection)
            canvas.rectangle(x, self.theme.padding.top,
                tw, self.theme.line_height - self.theme.padding.bottom)
            canvas.fill()
            canvas.move_to(x, y)
            canvas.set_source(self.theme.selection_text_pat)
            canvas.show_text(two)
            x, y = canvas.get_current_point()
            canvas.fill()
        else:
            canvas.set_source(self.theme.cursor_pat)
            canvas.rectangle(x, self.theme.padding.top,
                1, self.theme.line_height - self.theme.padding.bottom)
            canvas.fill()
        canvas.move_to(x, y)
        canvas.set_source(self.theme.text_pat)
        canvas.show_text(three)
        canvas.fill()
