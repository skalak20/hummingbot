import hashlib
import hmac
import time
from typing import Any, Dict
from urllib.parse import urlencode, urlparse

from hummingbot.connector.exchange.coinex.coinex_utils import get_timestamp
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class CoinexAuth(AuthBase):

    HEADERS = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
        "X-COINEX-KEY": "",
        "X-COINEX-SIGN": "",
        "X-COINEX-TIMESTAMP": "",
    }

    def __init__(self, api_key: str, api_secret: str, time_provider: TimeSynchronizer):
        self.access_id = api_key
        self.secret_key = api_secret
        self.time_provider = time_provider
        self.headers = self.HEADERS.copy()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """
        headers = {}
        if request.headers is not None:
            headers.update(request.headers)
        headers.update(self.authentication_headers(request=request))
        request.headers = headers
        return request

    async def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Mexc does not use this
        functionality
        """
        return request  # pass-through

    def authentication_headers(self, request: RESTRequest) -> Dict[str, Any]:
        timestamp = str(int(self.time_provider.time() * 1e3) if self.time_provider else get_timestamp())
        request_path = request.throttler_limit_id

        method = str(request.method).upper()
        if method == "GET":
            params = request.params
            # If params exist, query string needs to be added to the request path
            if params:
                for item in params:
                    if params[item] is None:
                        del params[item]
                        continue
                request_path = request_path + "?" + urlencode(params)

            signed_str = self.gen_sign(method, request_path, "", timestamp)

        else:
            data = ""  # TODO: request.body
            signed_str = self.gen_sign(method, request_path, data, timestamp)

        header = self.get_common_headers(signed_str, timestamp)
        return header

    def gen_sign(self, method, request_path, body, timestamp):
        prepared_str = f"{method}{request_path}{body}{timestamp}"
        signature = hmac.new(
            bytes(self.secret_key, 'latin-1'),
            msg=bytes(prepared_str, 'latin-1'),
            digestmod=hashlib.sha256
        ).hexdigest().lower()
        return signature

    def get_common_headers(self, signature, timestamp):
        headers = self.HEADERS.copy()
        headers["X-COINEX-KEY"] = self.access_id
        headers["X-COINEX-SIGN"] = str(signature)
        headers["X-COINEX-TIMESTAMP"] = str(timestamp)
        return headers
