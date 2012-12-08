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
        except ValueError:
            woeid = self.get_woeid(self.location)  # loopy-loop
        self.url = "{0}{1}".format(
            WEATHER_URL,
            urlencode({'w': woeid, 'u': self.metric and 'c' or 'f'})
        )
        self.thread = threading.Thread(target=self.read_loop)
        self.thread.daemon = True
        self.thread.start()

    def get_woeid(self, location):
        url = "{0}{1}".format(
            QUERY_URL,
            urlencode({
                'q': 'select woeid from geo.places where text="{0}"'.format(
                    location
                ),
                'format': 'xml'
            })
        )
        try:
            response = urlopen(url).read()
            data = minidom.parseString(response)
            return data.getElementsByTagName("woeid")[0].firstChild.nodeValue
        except:
            return None

    def read_loop(self):
        while True:
            self.text = self.format.format(**self.fetch())
            time.sleep(600)

    def fetch(self):
        try:
            response = urlopen(self.url).read()
            dom = minidom.parseString(response)
        except:
            return '--'
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
