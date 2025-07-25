import asyncio
import json
from unittest import TestCase
from unittest.mock import MagicMock, patch

from typing_extensions import Awaitable

from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest

class LbankAuthTests(TestCase):

    def setUp(self) -> None:
        self._api_key = "44afd74f-6fc0-443e-be72-18b2374086ad"
        self._api_secret = "33559D17E95D1734CEA52AA38B7BA375"

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    @patch("hummingbot.connector.exchange.lbank.lbank_auth.LbankAuth.get_tracking_nonce")
    def test_rest_authenticate(self, mocked_nonce):
        mocked_nonce.return_value = "1"
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
        
        auth = LbankAuth(api_key=self._api_key, api_secret=self._api_secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, url=test_url, data=json.dumps(params), is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))

