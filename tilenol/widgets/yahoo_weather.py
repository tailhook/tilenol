# -*- coding: utf-8 -*-


from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET
import json
import logging
from io import BytesIO

from zorro import gethub, sleep
from zorro.http import HTTPClient
from zorro.di import has_dependencies, dependency
import cairo

from .base import Widget
from tilenol.theme import Theme


log = logging.getLogger(__name__)
QUERY_URL = 'query.yahooapis.com'
QUERY_URI = '/v1/public/yql'
WEATHER_URL = 'weather.yahooapis.com'
WEATHER_URI = '/forecastrss?'
WEATHER_NS = 'http://xml.weather.yahoo.com/ns/rss/1.0'
DEFAULT_PIC = 'http://l.yimg.com/a/i/us/nws/weather/gr/{condition_code}d.png'


@has_dependencies
class YahooWeather(Widget):

    tags_to_fetch = (
        'location',
        'units',
        'wind',
        'atmosphere',
        'astronomy',
        'condition',
    )

    theme = dependency(Theme, 'theme')

    def __init__(
            self, location, *,
            picture_url=DEFAULT_PIC,
            format='{condition_temp}°{units_temperature}',
            metric=True, right=False):
        """
        Location should be either a woeid or a name string.

        Change metric to False for imperial units.

        Set `picture_url` to None to hide picture.

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
        self.picture_url = picture_url

        self.text = '--'
        self.image = None
        self.oldimg_url = None

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
                self.text = self.format.format_map(result)
                if self.picture_url is not None:
                    self.fetch_image(result)
            sleep(600)

    def fetch_image(self, data):
        img_url = None
        try:
            img_url = self.picture_url.format_map(data)
            if img_url == self.oldimg_url and self.image:
                return
            parsed_url = urlparse(img_url)
            resp = HTTPClient(parsed_url.hostname).request(parsed_url.path,
                headers={
                'Host': parsed_url.hostname,
                })
            self.image = cairo.ImageSurface.create_from_png(BytesIO(resp.body))
            self.oldimg_url = img_url
        except Exception as e:
            log.exception("Error fetching picture %r", img_url, exc_info=e)
            self.image = None

    def fetch_woeid(self):
        woeid = None
        while woeid is None:
            try:
                response = HTTPClient(QUERY_URL).request(QUERY_URI, query={
                    'q': "select woeid from geo.places "
                    "where text='{0}'".format(self.location),
                    'format': 'json'
                }, headers={'Host': QUERY_URL})
                data = json.loads(response.body.decode('ascii'))['query']
                if data['count'] > 1:
                    woeid = data['results']['place'][0]['woeid']
                else:
                    woeid = data['results']['place']['woeid']
            except Exception as e:
                log.exception("Error fetching woeid", exc_info=e)
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
            xml = ET.fromstring(response.body.decode('ascii'))
        except Exception as e:
            log.exception("Error fetching weather info", exc_info=e)
            return None
        data = dict()
        for tag in self.tags_to_fetch:
            elem = xml.find('.//{%s}%s' % (WEATHER_NS, tag))
            for attr, val in elem.attrib.items():
                data['{0}_{1}'.format(tag, attr)] = val
        return data

    def draw(self, canvas, l, r):
        self.font.apply(canvas)
        _, _, w, h, _, _ = canvas.text_extents(self.text)
        if self.image:
            iw = self.image.get_width()
            ih = self.image.get_height()
            imh = self.height
            imw = int(iw/ih*imh + 0.5)
            scale = ih/imh
            if self.right:
                x = r - w - self.padding.right - imw
            else:
                x = l
            y = 0
            pat = cairo.SurfacePattern(self.image)
            pat.set_matrix(cairo.Matrix(
                xx=scale, yy=scale,
                x0=-x*scale, y0=-y*scale))
            pat.set_filter(cairo.FILTER_BEST)
            canvas.set_source(pat)
            canvas.rectangle(x, 0, imw, imh)
            canvas.fill()
        else:
            imw = 0
        canvas.set_source(self.color)
        if self.right:
            x = r - self.padding.right - w
            r -= self.padding.left + self.padding.right + w + imw
        else:
            x = l + self.padding.left
            l += self.padding.left + self.padding.right + w + imw
        canvas.move_to(x, self.height - self.padding.bottom)
        canvas.show_text(self.text)
        return l, r
