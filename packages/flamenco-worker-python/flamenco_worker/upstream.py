import attr
import concurrent.futures
import requests

from . import attrs_extra

HTTP_RETRY_COUNT = 5
HTTP_TIMEOUT = 3  # in seconds


@attr.s
class FlamencoManager:
    manager_url = attr.ib(validator=attr.validators.instance_of(str))
    session = attr.ib(default=None, init=False)
    auth = attr.ib(default=None, init=False)  # tuple (worker_id, worker_secret)

    # Executor for HTTP requests, so that they can run in separate threads.
    _executor = attr.ib(default=attr.Factory(concurrent.futures.ThreadPoolExecutor),
                        init=False)
    _log = attrs_extra.log('%s.FlamencoManager' % __name__)

    async def get(self, *args, loop, **kwargs) -> requests.Response:
        return await self.client_request('GET', *args, loop=loop, **kwargs)

    async def post(self, *args, loop, **kwargs) -> requests.Response:
        return await self.client_request('POST', *args, loop=loop, **kwargs)

    async def put(self, *args, loop, **kwargs) -> requests.Response:
        return await self.client_request('PUT', *args, loop=loop, **kwargs)

    async def delete(self, *args, loop, **kwargs) -> requests.Response:
        return await self.client_request('DELETE', *args, loop=loop, **kwargs)

    async def patch(self, *args, loop, **kwargs) -> requests.Response:
        return await self.client_request('PATCH', *args, loop=loop, **kwargs)

    async def client_request(self, method, url, *,
                             params=None,
                             data=None,
                             headers=None,
                             cookies=None,
                             files=None,
                             auth=...,
                             timeout=HTTP_TIMEOUT,
                             allow_redirects=True,
                             proxies=None,
                             hooks=None,
                             stream=None,
                             verify=None,
                             cert=None,
                             json=None,
                             loop) -> requests.Response:
        """Performs a HTTP request to the server.

        Creates and re-uses the HTTP session, to have efficient communication.

        if 'auth=...' (the async default), self.auth is used. If 'auth=None', no authentication is used.
        """

        import logging
        import urllib.parse
        from functools import partial

        if not self.session:
            from requests.adapters import HTTPAdapter

            self._log.debug('Creating new HTTP session')
            self.session = requests.session()
            self.session.mount(self.manager_url, HTTPAdapter(max_retries=HTTP_RETRY_COUNT))

        abs_url = urllib.parse.urljoin(self.manager_url, url)
        if self._log.isEnabledFor(logging.DEBUG):
            if json is None:
                self._log.debug('%s %s', method, abs_url)
            else:
                self._log.debug('%s %s with JSON: %s', method, abs_url, json)

        http_req = partial(self.session.request,
                           method, abs_url,
                           params=params,
                           data=data,
                           headers=headers,
                           cookies=cookies,
                           files=files,
                           auth=self.auth if auth is ... else auth,
                           timeout=timeout,
                           allow_redirects=allow_redirects,
                           proxies=proxies,
                           hooks=hooks,
                           stream=stream,
                           verify=verify,
                           cert=cert,
                           json=json)

        resp = await loop.run_in_executor(self._executor, http_req)

        return resp
