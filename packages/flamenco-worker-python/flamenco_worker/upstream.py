import attr
import requests

from . import attrs_extra

HTTP_RETRY_COUNT = 5
HTTP_TIMEOUT = 3  # in seconds


@attr.s
class FlamencoManager:
    manager_url = attr.ib(validator=attr.validators.instance_of(str))
    session = attr.ib(default=None, init=False)
    _log = attrs_extra.log('%s.FlamencoManager' % __name__)

    def get(self, *args, **kwargs) -> requests.Response:
        return self.client_request('GET', *args, **kwargs)

    def post(self, *args, **kwargs) -> requests.Response:
        return self.client_request('POST', *args, **kwargs)

    def put(self, *args, **kwargs) -> requests.Response:
        return self.client_request('PUT', *args, **kwargs)

    def delete(self, *args, **kwargs) -> requests.Response:
        return self.client_request('DELETE', *args, **kwargs)

    def patch(self, *args, **kwargs) -> requests.Response:
        return self.client_request('PATCH', *args, **kwargs)

    def client_request(self, method, url,
                       params=None,
                       data=None,
                       headers=None,
                       cookies=None,
                       files=None,
                       auth=None,
                       timeout=HTTP_TIMEOUT,
                       allow_redirects=True,
                       proxies=None,
                       hooks=None,
                       stream=None,
                       verify=None,
                       cert=None,
                       json=None) -> requests.Response:
        """Performs a HTTP request to the server.

        Creates and re-uses the HTTP session, to have efficient communication.
        """

        import urllib.parse

        if not self.session:
            from requests.adapters import HTTPAdapter

            self._log.debug('Creating new HTTP session')
            self.session = requests.session()
            self.session.mount(self.manager_url, HTTPAdapter(max_retries=HTTP_RETRY_COUNT))

        abs_url = urllib.parse.urljoin(self.manager_url, url)
        self._log.debug('%s %s', method, abs_url)

        resp = self.session.request(
            method, abs_url,
            params=params,
            data=data,
            headers=headers,
            cookies=cookies,
            files=files,
            auth=auth,
            timeout=timeout,
            allow_redirects=allow_redirects,
            proxies=proxies,
            hooks=hooks,
            stream=stream,
            verify=verify,
            cert=cert,
            json=json)

        return resp
