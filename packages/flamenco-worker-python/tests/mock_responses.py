import attr
import requests


@attr.s
class JsonResponse:
    """Mocked HTTP response returning JSON.

    Maybe we want to switch to using unittest.mock.Mock for this,
    or to using the responses package.
    """

    _json = attr.ib()
    status_code = attr.ib(default=200, validator=attr.validators.instance_of(int))

    def json(self):
        return self._json

    def raise_for_status(self):
        if 200 <= self.status_code < 300:
            return

        raise requests.HTTPError(self.status_code)


@attr.s
class EmptyResponse:
    """Mocked HTTP response returning an empty 204.

    Maybe we want to switch to using unittest.mock.Mock for this,
    or to using the responses package.
    """

    status_code = attr.ib(default=204, validator=attr.validators.instance_of(int))

    def raise_for_status(self):
        pass


def CoroMock(return_value=...):
    """Corountine mocking object.

    For an example, see test_coro_mock.py.

    Source: http://stackoverflow.com/a/32505333/875379
    """

    import asyncio
    from unittest.mock import Mock

    coro = Mock(name="CoroutineResult")
    corofunc = Mock(name="CoroutineFunction", side_effect=asyncio.coroutine(coro))
    corofunc.coro = coro

    if return_value is not ...:
        corofunc.coro.return_value = return_value

    return corofunc
