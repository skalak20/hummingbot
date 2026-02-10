import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from aioresponses import aioresponses

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source import CoinexAPIUserStreamDataSource
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant

TEST_TS = 1661927587825
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"
TEST_BASE = "BTC"
TEST_QUOTE = "USDT"


class TestCoinexAPIUserStreamDataSource(IsolatedAsyncioWrapperTestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    # region TESTS MANAGE

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.base_asset = TEST_BASE
        cls.quote_asset = TEST_QUOTE
        cls.trading_pair = f"{TEST_BASE}-{TEST_QUOTE}"
        cls.ex_trading_pair = f"{TEST_BASE}{TEST_QUOTE}"
        cls.api_key = TEST_KEY
        cls.api_secret_key = TEST_SECRET

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.log_records = []
        self.listening_task: Optional[asyncio.Task] = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        self.mock_time_provider = MagicMock()
        self.mock_time_provider.time.return_value = TEST_TS
        self.auth = CoinexAuth(
            self.api_key,
            self.api_secret_key,
            time_provider=self.mock_time_provider)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CoinexExchange(
            client_config_map=client_config_map,
            coinex_api_key=TEST_KEY,
            coinex_api_secret=TEST_SECRET,
            trading_pairs=[],
            trading_required=False)

        self.data_source = CoinexAPIUserStreamDataSource(
            auth=self.auth,
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @staticmethod
    def _setup_post(mock_api, url, status = None, response = None, exception = None, callback = None):
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        if status:
            mock_api.post(regex_url, status=status, callback=callback)
        elif response:
            mock_api.post(regex_url, body=json.dumps(response), callback=callback)
        elif exception:
            mock_api.post(regex_url, exception=exception, callback=callback)

    @staticmethod
    def get_listen_key_mock():
        listen_key = {
            "code": 0,
            "message": "OK",
            "data": {
                "token": "someToken",
                "instanceServers": [
                    {
                        "endpoint": "wss://someEndpoint",
                        "encrypt": True,
                        "protocol": "websocket",
                        "pingInterval": 18000,
                        "pingTimeout": 10000,
                    }
                ]
            }
        }
        return listen_key

    # endregion TESTS MANAGE

    async def test_last_recv_time(self):
        # Initial last_recv_time
        self.assertEqual(0, self.data_source.last_recv_time)

        ws_assistant = await self.data_source._get_ws_assistant()
        ws_assistant._connection._last_recv_time = 1000
        self.assertEqual(1000, self.data_source.last_recv_time)

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("hummingbot.connector.exchange.coinex.coinex_auth.CoinexAuth._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_auth(self, ws_connect_mock, auth_time_mock, sleep_mock):
        auth_time_mock.return_value = TEST_TS
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        sleep_mock.side_effect = asyncio.CancelledError()

        result_auth = {
            "id": CONSTANTS.WS_AUTH_ID,
            "code": 0,
            "message": "OK",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_auth))

        output_queue = asyncio.Queue()
        try:
            self.data_source._sleep = AsyncMock()
            self.data_source._sleep.side_effect = asyncio.CancelledError()
            self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
            await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        except asyncio.CancelledError:
            pass

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        self.assertEqual(5, len(sent_subscription_messages))  # 5 messages: [ auth, subscribe_balanse, subscribe_orders, subscribe_trades, ping ]

        expires = int(TEST_TS * 1e3)
        signature = self.auth.gen_sign(expires)
        auth_subscription = {
            "id": CONSTANTS.WS_AUTH_ID,
            "method": CONSTANTS.WS_METHOD_SERVER_SIGN,
            "params": {
                "access_id": TEST_KEY,
                "signed_str": signature,
                "timestamp": expires,
            }
        }

        self.assertEqual(auth_subscription, sent_subscription_messages[0])

    @aioresponses()
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, mock_api, sleep_mock, mock_ws):
        url = web_utils.private_rest_url(path_url=CONSTANTS.WSS_SPOT_URL)
        mock_response = self.get_listen_key_mock()

        self._setup_post(mock_api, url, response=mock_response)

        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

        # auth_fail = { "id": CONSTANTS.WS_AUTH_ID, "code": 21002, "message": "Authentication failed" }
