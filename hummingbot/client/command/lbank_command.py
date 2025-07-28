import asyncio
import json
import threading

from typing import TYPE_CHECKING, Optional
from unittest.mock import MagicMock
from typing_extensions import Awaitable

from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest
from hummingbot.core.utils.async_utils import safe_ensure_future

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class LbankCommand:
    def lbank(self, # type: HummingbotApplication
              command: Optional[str] = None):
        
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.lbank, command)
            return
        
        self.app.clear_input()
        self.notify(f"\nLbank command: {command}")

        if command == "info":
            safe_ensure_future(self.call_user_info())
        elif command is None:
            pass
        else:
            pass

    async def call_user_info(self, # type: HummingbotApplication
                             ):

        now = 1234567890.000
        api_key = "44afd74f-6fc0-443e-be72-18b2374086ad"
        api_secret = "33559D17E95D1734CEA52AA38B7BA375"
        test_url = "/supplement/user_info.do"
        params = {}

        mock_time_provider = MagicMock()
        mock_time_provider.time.return_value = now

        market_connector = self.trading_core.markets["lbank"]
            
        auth = LbankAuth(sign_method="HMACSHA256", api_key=api_key, api_secret=api_secret, time_provider=mock_time_provider)
        request = RESTRequest(method=RESTMethod.POST, url=test_url, data=json.dumps(params), is_auth_required=True)
        request = await auth.rest_authenticate(request)

        # throttler = create_throttler()
        # api_factory = build_api_factory_without_time_synchronizer_pre_processor(throttler=throttler)
        # rest_assistant = await api_factory.get_rest_assistant()
        rest_assistant = await self._web_assistants_factory.get_rest_assistant()
        result = await rest_assistant.execute_request()

        resp = await self._post_process_response(result)
        if resp:
            pass
        pass

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: float = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret
