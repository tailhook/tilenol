from zorro.http import HTTPClient
from zorro import gethub

from urllib.parse import splittype, splithost, urlencode


class RequestError(Exception):
    """URL cannot be fetched"""


def fetchurl(url, query=None):
    if query is not None:
        assert '?' not in url, ("Either include query in url"
                                "or pass as parameter, but not both")
        url += '?' + urlencode(query)
    proto, tail = splittype(url)
    if proto != 'http':
        raise RuntimeError("Unsupported protocol HTTP")
    host, tail = splithost(tail)
    ip = gethub().dns_resolver.gethostbyname(host)
    cli = HTTPClient(ip)
    resp = cli.request(tail, headers={'Host': host})
    if resp.status.endswith('200 OK'):
        return resp.body
    raise RequestError(resp.status, resp)
