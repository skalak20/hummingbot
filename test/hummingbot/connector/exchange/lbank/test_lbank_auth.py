import asyncio
import json
import hashlib
import hmac
from copy import copy
from unittest import TestCase
from unittest.mock import MagicMock, patch

from typing_extensions import Awaitable

from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange.lbank.lbank_constants import API_HMACSHA
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

class LbankAuthTests(TestCase):
    _last_tracking_nonce: int = 0

    def setUp(self) -> None:
        self._api_key = "44afd74f-6fc0-443e-be72-18b2374086ad"
        self._api_secret = "33559D17E95D1734CEA52AA38B7BA375"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1753095319.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now
        test_url = "/test"
        params = {
            "symbol": "LTCBTC",
            "side": "BUY",
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": 1,
            "price": "0.1",
        }
        full_params = copy(params)

        auth = LbankAuth(api_key=self._api_key, api_secret=self._api_secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, url=test_url, data=json.dumps(params), is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

        full_params.update({"timestamp": 1234567890000})
        encoded_params = "&".join([f"{key}={value}" for key, value in full_params.items()])
        expected_signature = hmac.new(
            self._api_secret.encode("utf-8"),
            encoded_params.encode("utf-8"),
            hashlib.sha256).hexdigest()

        self.assertEqual(now * 1e3, configured_request.headers["timestamp"])
        self.assertEqual(API_HMACSHA, configured_request.headers["signature_method"])
        self.assertEqual(self._api_key, configured_request.params["api_key"])
        # self.assertEqual(expected_signature, configured_request.params["sign"])
