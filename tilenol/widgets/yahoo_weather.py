# -*- coding: utf-8 -*-


import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.dom import minidom

from zorro.di import has_dependencies, dependency

from .base import Widget
from tilenol.theme import Theme


QUERY_URL = 'http://query.yahooapis.com/v1/public/yql?'
WEATHER_URL = 'http://weather.yahooapis.com/forecastrss?'
WEATHER_NS = 'http://xml.weather.yahoo.com/ns/rss/1.0'


@has_dependencies
class YahooWeather(Widget):

    structure = (
        ('location', ('city', 'region', 'country')),
        ('units', ('temperature', 'distance', 'pressure', 'speed')),
        ('wind', ('chill', 'direction', 'speed')),
        ('atmosphere', ('humidity', 'visibility', 'pressure', 'rising')),
        ('astronomy', ('sunrise', 'sunset')),
        ('condition', ('text', 'code', 'temp', 'date'))
    )

    theme = dependency(Theme, 'theme')

    def __init__(
            self, location, *,
            format='{condition_temp}°{units_temperature}',
            metric=True, right=False):
        """
        Location should be either a woeid or a name string.

        Change metric to False for imperial units.

        Available format variables:
            astronomy_sunrise, astronomy_sunset
            atmosphere_humidity, atmosphere_visibility,
            atmosphere_pressure, atmosphere_rising
            condition_text, condition_code, condition_temp, condition_date
            location_city. location_region, location_country
            units_temperature, units_distance, units_pressure, units_speed
            wind_chill, wind_direction, wind_speed
        """
        super().__init__(right=right)
        self.location = location
        self.format = format
        self.metric = metric
        self.text = '--'

    def __zorro_di_done__(self):
        bar = self.theme.bar
        self.font = bar.font
        self.color = bar.text_color_pat
        self.padding = bar.text_padding
        try:
            woeid = int(self.location)
            self.callback(woeid)
        except ValueError:
            self.thread = threading.Thread(
                target=self.fetch_woeid, args=(self.location, self.callback)
            )
            self.thread.daemon = True
            self.thread.start()

    def fetch_woeid(self, location, callback):
        url = "{0}{1}".format(
            QUERY_URL,
            urlencode({
                'q': 'select woeid from geo.places where text="{0}"'.format(
                    location
                ),
                'format': 'xml'
            })
        )
        woeid = None
        while woeid is None:
            try:
                response = urlopen(url).read()
                data = minidom.parseString(response)
                elem = data.getElementsByTagName("woeid")[0]
                woeid = elem.firstChild.nodeValue
            except:
                time.sleep(60)
            else:
                if woeid is None:
                    time.sleep(60)
        callback(woeid)

    def read_loop(self):
        while True:
            result = self.fetch()
            if result is None:
                self.text = '--'
            else:
                self.text = self.format.format(**result)
            time.sleep(600)

    def callback(self, woeid):
        self.url = "{0}{1}".format(
            WEATHER_URL,
            urlencode({'w': woeid, 'u': self.metric and 'c' or 'f'})
        )
        self.thread = threading.Thread(target=self.read_loop)
        self.thread.daemon = True
        self.thread.start()

    def fetch(self):
        try:
            response = urlopen(self.url).read()
            dom = minidom.parseString(response)
        except:
            return None
        data = dict()
        for tag, attrs in YahooWeather.structure:
            elem = dom.getElementsByTagNameNS(WEATHER_NS, tag)[0]
            for attr in attrs:
                data['{0}_{1}'.format(tag, attr)] = elem.getAttribute(attr)
        return data

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
