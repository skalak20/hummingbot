import hashlib
import hmac
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

    def __init__(self, api_key: str, secret_key: str, time_provider: TimeSynchronizer):
        self.access_id = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider
        self.headers = self.HEADERS.copy()

    async def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """

        timestamp = str(int(self.time_provider.time() * 1e3) if self.time_provider else get_timestamp())
        signed_str = self.gen_sign("GET", "", "", timestamp)
        headers = self.get_common_headers(signed_str, timestamp)
        request.headers = headers

        return request

    def request(self, method, url, params={}, data=""):
        req = urlparse(url)

        timestamp = str(int(self.time_provider.time() * 1e3))

        signed_str = self.gen_sign(method, req.path, params, data, timestamp)

        if method.upper() == "GET":
            response = requests.get(
                url,
                params=params,
                headers=self.get_common_headers(signed_str, timestamp),
            )
        else:
            response = requests.post(
                url,
                params=data,
                headers=self.get_common_headers(signed_str, timestamp)
            )

        if response.status_code != 200:
            raise ValueError(response.text)
        return response

    def get_common_headers(self, signed_str, timestamp):
        headers = self.HEADERS.copy()
        headers["X-COINEX-KEY"] = self.access_id
        headers["X-COINEX-SIGN"] = signed_str
        headers["X-COINEX-TIMESTAMP"] = timestamp
        return headers

    def gen_sign(self, method: RESTMethod, path, params: Dict[str, Any], body, timestamp):
        request_path = path

        if method.upper() == "GET" and params:
            for item in params:
                if params[item] is None:
                    del params[item]
            request_path = path + "?" + urlencode(params)

        prepared_str = f"{method}{request_path}{body}{timestamp}"

        signature = hmac.new(
            bytes(self.secret_key, 'latin-1'),
            msg=bytes(prepared_str, 'latin-1'),
            digestmod=hashlib.sha256
        ).hexdigest().lower()

        return signature
