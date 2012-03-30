import string
from functools import partial

from zorro.di import di, has_dependencies, dependency

from tilenol.xcb import Core as XCore, Keysyms
from tilenol.events import EventDispatcher


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

    def __init__(self, draw_event, theme):
        self.value = ""
        self.sel_start = 0
        self.sel_width = 0
        self.draw_event = draw_event
        self.theme = theme

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
        ch = chr(sym)
        mod = self.xcore.modifiers_mask & event.state
        meth = self.key_table.get((mod, sym))
        if meth is not None:
            meth()
            self.draw_event.emit()
            return
        if mod:
            # TODO(tailhook) capitals?
            return
        if ch in string.printable:
            self._clearsel(ch)
            self.sel_start += 1
        self.draw_event.emit()

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

    def draw(self, canvas):
        th = self.theme
        canvas.set_source(th.text_pat)
        th.font.apply(canvas)
        canvas.move_to(th.padding.left, th.padding.top+10)
        canvas.show_text(self.value)
