import asyncio
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock

from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest


class CoinexAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.api_key = "560CE33AA5E845929981B163ABD2B25F"
        self.secret_key = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = 1000

        self.auth = CoinexAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self.mock_time_provider,
        )

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def test_rest_authenticate(self):
        now = 1753095319.000
        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now
        test_url = "/test"
        params = {}

        auth = CoinexAuth(api_key=self._api_key, secret_key=self._secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.GET, params=params, is_auth_required=True)
        configured_request = self.async_run_with_timeout(auth.rest_authenticate(request))
