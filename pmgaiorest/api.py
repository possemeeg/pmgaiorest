from aiohttp.web_exceptions import HTTPUnauthorized
from aiohttp import hdrs
from logging import getLogger
from urllib import parse

logger = getLogger(__name__)

class ApiBase:
    def __init__(self, aiohttp_session, base_url, header_args, *, handle_reconnect=None):
        self.aiohttp_session = aiohttp_session

        self.base_url = base_url
        self.base_headers = self.create_headers(**header_args)

        self.get = self._resp_wrap(self.aiohttp_session.get, handle_reconnect)
        self.get_with_headers = self._resp_wrap(
                self.aiohttp_session.get, handle_reconnect, with_headers=True)
        self.post = self._resp_wrap(self.aiohttp_session.post, handle_reconnect)

    def update_header_args(self, header_args):
        self.base_headers = self.create_headers(**header_args)

    def _resp_wrap(self, rem_call, handle_reconnect, *, with_headers=False):
        async def wrapper(*args, **kwargs):
            headers = kwargs.pop('headers',{})
            headers.update(self.base_headers)
            path = args[0]
            if path is not None:
                uri = f'{self.base_url}/{args[0]}'
            else:
                full_path = kwargs.pop('full_path', 0)
                assert full_path is not None
                parsed = parse.urlparse(self.base_url)
                uri = parse.urlunparse(parsed._replace(path=full_path))

            connect_retries = 1
            while True:
                resp = await rem_call(uri, *args[1:], headers=headers, **kwargs)

                if 200 <= resp.status <= 299:
                    json = await resp.json() 
                    return (json if not with_headers
                            else (json, resp.headers))

                if handle_reconnect is None or connect_retries <= 0:
                    resp.raise_for_status()

                connect_retries -= 1

                if resp.status != HTTPUnauthorized.status_code:
                    resp.raise_for_status()

                logger.warning(f'Request unauthorised {resp.status} - attempting to reconnect')

                reconnect_args = handle_reconnect()
    
                if reconnect_args is None:
                    # original error
                    resp.raise_for_status()

                self.base_headers = self.create_headers(**reconnect_args)
                headers.update(self.base_headers)
    
        return wrapper

    def create_headers(self, **kwargs):
        headers = {
                hdrs.CONTENT_TYPE: 'application/json',
                hdrs.ACCEPT: 'application/json',
                }
        access_token = kwargs.get('access_token')
        if access_token is not None:
            token_type = kwargs.get('token_type', 'Bearer')
            headers[hdrs.AUTHORIZATION] = f'{token_type} {access_token}'
        return headers

                

