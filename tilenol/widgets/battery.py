import os.path
import threading
import time
import errno


from cairo import SolidPattern
from zorro.di import has_dependencies, dependency

from .base import Widget
from tilenol.theme import Theme


BATTERY_PATH = '/sys/class/power_supply'

MIN_IN_HOUR = 60

ENERGY_NOW = 0
ENERGY_FULL = 1
POWER_NOW = 2
ENERGY_FILES = [ 'energy_now', 'energy_full', 'power_now' ]
CHARGE_FILES = [ 'charge_now', 'charge_full', 'current_now' ]


class BatteryStatus:
    def __init__( self, path ):
        # set up the initial battery charge files - these will change as required
        self.files = ENERGY_FILES
        self.path = path

    def read_battery( self ):
        try: # pick the battery charge files which is appropriate to your machine
            self._now = float( self.get_file( self.files[ ENERGY_NOW ] ) )
        except IOError as e: # FileNotFoundError: in python 3.3
            if e.errno == errno.ENOENT: # file not found
                self.files = ENERGY_FILES if self.files == CHARGE_FILES else CHARGE_FILES
                self._now = float( self.get_file( self.files[ ENERGY_NOW ] ) )
            else:
                raise
        except OSError: # device not found? - make up a value
            self._now = 1000

        try: # ...but sometimes, plugging in/out the power causes something to fail, if so make it up,
            self._full = float( self.get_file( self.files[ ENERGY_FULL ] ) )
            self._power = float( self.get_file( self.files[ POWER_NOW ] ) )
            self._status = self.get_file( 'status' ).lower()
        except OSError:
            self._full = self._now
            self._power = self._now*MIN_IN_HOUR
            self._status = 'unknown'

    def get_file( self, name ):
        with open( os.path.join( self.path, name ), 'rt' ) as f:
            return f.read().strip()

    @property
    def charge( self ):
        return self._now/self._full

    @property
    def time_to_full( self ):
        return int( ( self._full - self._now )/self._power*MIN_IN_HOUR )

    @property
    def time_to_empty( self ):
        return int( self._now/self._power*MIN_IN_HOUR )

    @property
    def is_charging( self ):
        return self._status == 'charging'

    @property
    def is_unknown_status( self ):
        return self._status == 'unknown'

    @property
    def has_full_charge( self ):
        return self.charge > 0.99 or self._power == 0


@has_dependencies
class Battery(Widget):

    theme = dependency(Theme, 'theme')

    def __init__(self, *, which="BAT0", right=False):
        super().__init__(right=right)
        self.text = '--'
        path = os.path.join(BATTERY_PATH, which )
        self.data = BatteryStatus( path )

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.color = bar.text_color_pat
        self.padding = bar.text_padding
        # Reading battery can be immensely slow (more than 3 seconds)
        # so we update it in thread
        self.thread = threading.Thread(target=self.read_loop)
        self.thread.daemon = True
        self.thread.start()

    def read_loop(self):
        while True:
            self.format_battery_msg()
            time.sleep(10)

    def format_battery_msg(self):
        self.data.read_battery()
        if not self.data.is_unknown_status:
            txt = '{:.0%}'.format( self.data.charge )
            if not self.data.has_full_charge:
                tm, sign = ( self.data.time_to_full, '+' ) if self.data.is_charging else ( self.data.time_to_empty, '-' )
                hour = tm // MIN_IN_HOUR
                min = tm % MIN_IN_HOUR
                txt += ' {} {:02d}:{:02d}'.format( sign, hour, min )
            self.text = txt
        else:
            self.text = '--'

    def draw(self, canvas, l, r):
        self.font.apply(canvas)
        canvas.set_source(self.color)
        _, _, w, h, _, _ = canvas.text_extents(self.text)
        if self.right:
            x = r - self.padding.right - w
            r -= self.padding.left + self.padding.right + w
        else:
            x = l + self.padding.left
            l += self.padding.left + self.padding.right + w
        canvas.move_to(x, self.height - self.padding.bottom)
        canvas.show_text(self.text)
        return l, r
