# -*- coding: utf-8 -*-


from urllib.parse import urlencode
from xml.dom import minidom

from zorro import gethub, sleep
from zorro.http import HTTPClient
from zorro.di import has_dependencies, dependency

from .base import Widget
from tilenol.theme import Theme


QUERY_URL = 'query.yahooapis.com'
QUERY_URI = '/v1/public/yql'
WEATHER_URL = 'weather.yahooapis.com'
WEATHER_URI = '/forecastrss?'
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
        gethub().do_spawnhelper(self._update_handler)

    def _update_handler(self):
        try:
            woeid = int(self.location)
        except ValueError:
            woeid = self.fetch_woeid()
        self.uri = "{0}{1}".format(
            WEATHER_URI,
            urlencode({'w': woeid, 'u': self.metric and 'c' or 'f'})
        )
        while True:
            result = self.fetch()
            if result is not None:
                self.text = self.format.format(**result)
            sleep(600)

    def fetch_woeid(self):
        woeid = None
        while woeid is None:
            try:
                response = HTTPClient(QUERY_URL).request(QUERY_URI, query={
                    'q': "select woeid from geo.places "
                    "where text='{0}'".format(self.location),
                    'format': 'xml'
                }, headers={'Host': QUERY_URL})
                data = minidom.parseString(response.body.decode('ascii'))
                elem = data.getElementsByTagName("woeid")[0]
                woeid = elem.firstChild.nodeValue
            except:
                sleep(60)
            else:
                if woeid is None:
                    sleep(60)
        return woeid

    def fetch(self):
        try:
            response = HTTPClient(WEATHER_URL).request(
                self.uri, headers={'Host': WEATHER_URL}
            )
            dom = minidom.parseString(response.body.decode('ascii'))
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
