import asyncio
import base64
import hashlib
import hmac

from typing import Awaitable
from aioresponses import aioresponses
from unittest import TestCase
from unittest.mock import MagicMock, patch

from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

TEST_TS_SEC = 1700490703.564
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"

class CoinexAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._api_key = TEST_KEY
        self._secret_key = TEST_SECRET

        self._mock_time_provider = MagicMock()
        self._mock_time_provider.time.return_value = TEST_TS_SEC

        self._auth = CoinexAuth(
            api_key=self._api_key,
            secret_key=self._secret_key,
            time_provider=self._mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1753095319.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

		# Place a limit order
        test_method = RESTMethod.POST
        test_url = "/spot/order"
        test_params = {
            "market": "CETUSDT",
            "market_type": "SPOT",
            "side": "buy",
            "type": "limit",
            "amount":"10000",
            "price": "1",   
            "client_id": "order1",
            "is_hide": True,
        }

        request = RESTRequest(method=test_method, url=test_url, params=test_params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(self._auth.rest_authenticate(request))

        test_params.update({"timestamp": TEST_TS_SEC * 1e3})
        for key, value in test_params.items():
            api_post += f"&{key}={value}"

        api_sha256: bytes = hashlib.sha256(bytes(api_post, 'utf-8')).digest()
        api_secret = base64.b64decode(self._secret_key)
        api_path: bytes = bytes(request.url, 'utf-8')

        api_hmac: hmac.HMAC = hmac.new(api_secret, api_path + "?" + api_sha256, hashlib.sha512)
        expected_signature: bytes = base64.b64encode(api_hmac.digest())
        # auth = CoinexAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        
        self.assertEqual(configured_request.headers["X-COINEX-SIGN"], str(expected_signature, 'utf-8'))
        self.assertEqual(configured_request.headers["X-COINEX-KEY"], self._api_key, )
        self.assertEqual(configured_request.headers["X-COINEX-TIMESTAMP"], TEST_TS_SEC * 1e3)

    @aioresponses()
    def test_add_auth_headers_to_get_request_with_params(self, mock_api):
        request = RESTRequest(
            method=RESTMethod.GET,
            url="https://test.url/api/ping",
            params={"param_z": "value_param_z", "param_a": "value_param_a"},
            is_auth_required=True,
            throttler_limit_id="/api/ping"
        )

        self.async_run_with_timeout(self._auth.rest_authenticate(request))

        self.assertEqual(self.api_key, request.headers["X-COINEX-KEY"])
        self.assertEqual(TEST_TS_SEC * 1e3, request.headers["X-COINEX-TIMESTAMP"])
