from collections import namedtuple

from cairo import SolidPattern


Padding = namedtuple('Padding', 'top right bottom left')


class SubTheme(object):

    def __init__(self, name):
        self.name = name

    def set_color(self, name, num):
        setattr(self, name, num)
        setattr(self, name+'_pat', SolidPattern(
            (num >> 16) / 255.0,
            ((num >> 8) & 0xff) / 255.0,
            (num & 0xff) / 255.0,
            ))

    def update_from(self, dic):
        for k, v in dic.items():
            k = k.replace('-', '_')
            old = getattr(self, k, None)
            if old is None:
                return
            if isinstance(old, int):
                if hasattr(self, k+'_pat'):
                    self.set_color(k, int(v))
                else:
                    setattr(self, k, int(v))
            elif isinstance(old, Padding):
                setattr(self, k, Padding(*v))
            elif isinstance(old, Font):
                if isinstance(v, (list, tuple)):
                    f = Font(*v)
                elif isinstance(v, str):
                    f = Font(v, old.size)
                elif isinstance(v, int):
                    f = Font(old.face, v)
                elif isinstance(v, dict):
                    f = Font(**v)
                else:
                    raise NotImplemented("Invalid font {!r}".format(v))
                setattr(self, k, f)
            else:
                setattr(self, k, v)


class Font(object):

    def __init__(self, face, size):
        self.face = face
        self.size = size

    def apply(self, ctx):
        ctx.select_font_face(self.face)
        ctx.set_font_size(self.size)


class Theme(SubTheme):

    def __init__(self):

        blue = 0x4c4c99
        dark_blue = 0x191933
        orange = 0x99994c
        gray = 0x808080
        red = 0x994c4c
        black = 0x000000
        white = 0xffffff

        self.window = SubTheme('window')
        self.window.border_width = 2
        self.window.set_color('active_border', blue)
        self.window.set_color('inactive_border', gray)
        self.window.set_color('background', black)

        self.bar = SubTheme('bar')
        self.bar.set_color('background', black)
        self.bar.font = Font('Consolas', 18)
        self.bar.box_padding = Padding(2, 2, 2, 2)
        self.bar.text_padding = Padding(2, 4, 7, 4)
        self.bar.icon_spacing = 2
        self.bar.set_color('text_color', white)
        self.bar.set_color('dim_color', gray)
        self.bar.set_color('bright_color', orange)
        self.bar.set_color('active_border', blue)
        self.bar.set_color('subactive_border', gray)
        self.bar.set_color('urgent_border', red)
        self.bar.border_width = 2
        self.bar.height = 24
        self.bar.set_color('graph_color', blue)
        self.bar.set_color('graph_fill_color', dark_blue)
        self.bar.graph_line_width = 2
        self.bar.separator_width = 1
        self.bar.set_color('separator_color', gray)

        self.menu = SubTheme('bar')
        self.menu.set_color('background', gray)
        self.menu.set_color('text', white)
        self.menu.set_color('highlight', blue)
        self.menu.set_color('selection', blue)
        self.menu.set_color('selection_text', white)
        self.menu.set_color('cursor', black)
        self.menu.font = Font('Consolas', 18)
        self.menu.padding = Padding(2, 4, 7, 4)
        self.menu.line_height = 24

        self.hint = SubTheme('hint')
        self.hint.font = Font('Consolas', 18)
        self.hint.set_color('background', black)
        self.hint.set_color('border_color', gray)
        self.hint.set_color('text_color', white)
        self.hint.border_width = 2
        self.hint.padding = Padding(5, 6, 9, 6)

        self.tabs = SubTheme('tabs')
        self.tabs.font = Font('Monofur', 12)
        self.tabs.set_color('background', black)
        self.tabs.set_color('inactive_title', gray)
        self.tabs.set_color('inactive_bg', black)
        self.tabs.set_color('active_title', white)
        self.tabs.set_color('active_bg', blue)
        self.tabs.set_color('urgent_title', white)
        self.tabs.set_color('urgent_bg', orange)
        self.tabs.section_font = Font('Monofur', 12)
        self.tabs.set_color('section_color', gray)
        self.tabs.padding = Padding(5, 6, 6, 4)
        self.tabs.margin = Padding(4, 4, 4, 4)
        self.tabs.border_radius = 5
        self.tabs.spacing = 2
        self.tabs.icon_size = 14
        self.tabs.icon_spacing = 6
        self.tabs.section_padding = Padding(6, 2, 2, 2)

    def update_from(self, dic):
        for key, sub in self.__dict__.items():
            if isinstance(sub, SubTheme) and key in dic:
                sub.update_from(dic[key])

