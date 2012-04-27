from collections import namedtuple
from fractions import Fraction


USPosition	= (1 << 0)	# user specified x, y */
USSize		= (1 << 1)	# user specified width, height */
PPosition	= (1 << 2)	# program specified position */
PSize		= (1 << 3)	# program specified size */
PMinSize	= (1 << 4)	# program specified minimum size */
PMaxSize	= (1 << 5)	# program specified maximum size */
PResizeInc	= (1 << 6)	# program specified resize increments */
PAspect		= (1 << 7)	# program specified min and max aspect ratios */
PBaseSize	= (1 << 8)
PWinGravity	= (1 << 9)

InputHint   = 1
StateHint   = 2
IconPixmapHint = 4
IconWindowHint = 8
IconPositionHint = 16
IconMaskHint = 32
WindowGroupHint = 64
MessageHint = 128
UrgencyHint = 256


class SizeHints(namedtuple('_SizeHints', ('flags', 'p1', 'p2', 'p3', 'p4',
    'min_width', 'min_height',
    'max_width', 'max_height',
    'width_inc', 'height_inc', 'max_aspect_num',
    'max_aspect_denom', 'base_width', 'base_height', 'win_gravity'))):
    __slots__ = ()


class SizeHints(object):

    @classmethod
    def from_property(self, type, arr):
        assert type.name == 'WM_SIZE_HINTS'
        flags = arr[0]
        hints = SizeHints()
        if flags & PMinSize:
            hints.min_width = arr[5]
            hints.min_height = arr[6]
        if flags & PMaxSize:
            hints.max_width = arr[7]
            hints.max_height = arr[8]
        if flags & PResizeInc:
            hints.width_inc = arr[9]
            hints.height_inc = arr[10]
        if flags & PAspect:
            hints.min_aspect = Fraction(arr[11], arr[12])
            hints.max_aspect = Fraction(arr[13], arr[14])
        if flags & PBaseSize:
            hints.base_width = arr[15]
            hints.base_height = arr[16]
        if flags & PWinGravity:
            hints.win_gravity = arr[17]
        return hints


def is_window_urgent(win):
    hints = win.props.get('WM_HINTS')
    if hints is None:
        return False
    return bool(hints[0] & UrgencyHint)

