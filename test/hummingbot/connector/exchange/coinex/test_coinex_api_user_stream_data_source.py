import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from bidict import bidict

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

        self.connector._set_trading_pair_symbol_map(bidict({self.ex_trading_pair: self.trading_pair}))

    def tearDown(self) -> None:
        self.listening_task and self.listening_task.cancel()
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    def mock_auth_reqeust(self):
        timestamp = int(TEST_TS * 1e3)
        signature = self.auth.gen_sign(timestamp)
        auth_request = {
            "id": CONSTANTS.WS_AUTH_ID,
            "method": CONSTANTS.WS_METHOD_SERVER_SIGN,
            "params": {
                "access_id": TEST_KEY,
                "signed_str": signature,
                "timestamp": timestamp,
            }
        }
        return auth_request

    def mock_auth_success(self):
        auth_success = {
            "id": CONSTANTS.WS_AUTH_ID,
            "code": 0,
            "message": "OK",
        }
        return auth_success

    def mock_auth_failed(self):
        auth_failed = {
            "id": CONSTANTS.WS_AUTH_ID,
            "code": 21002,
            "message": "Authentication failed",
        }
        return auth_failed

    def mock_ping_request(self):
        ping_request = {
            "id": CONSTANTS.WS_PING_ID,
            "method": CONSTANTS.WS_METHOD_SERVER_PING,
            "params": {},
        }
        return ping_request

    def mock_pong_response(self):
        pong_response = {
            "id": CONSTANTS.WS_PING_ID,
            "code": 0,
            "message": "OK",
            "data": {"result": "pong"},
        }
        return pong_response

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
        ws_assistant._connection._last_recv_time = TEST_TS
        self.assertEqual(TEST_TS, self.data_source.last_recv_time)

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError

        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("hummingbot.connector.exchange.coinex.coinex_auth.CoinexAuth._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_auth_failed_throws_exception(self, ws_connect_mock, auth_time_mock, sleep_mock):
        # Mock sleep to raise CancelledError to exit the loop
        sleep_mock.side_effect = asyncio.CancelledError()
        auth_time_mock.side_effect = [100]
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_auth_failed = self.mock_auth_failed()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_auth_failed))

        output_queue = asyncio.Queue()
        try:
            self.listening_task = self.local_event_loop.create_task(
                self.data_source.listen_for_user_stream(output=output_queue))
            await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
            await self.listening_task
        except asyncio.CancelledError:
            pass

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        # 4 channels: auth, orderbook, trades, wallet and ping
        self.assertEqual(5, len(sent_subscription_messages))
        self.assertTrue(
            self._is_logged("ERROR",
                            "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    @patch("hummingbot.connector.exchange.coinex.coinex_auth.CoinexAuth._time")
    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_auth(self, ws_connect_mock, auth_time_mock, sleep_mock):
        auth_time_mock.return_value = TEST_TS
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()
        sleep_mock.side_effect = asyncio.CancelledError()

        auth_request = self.mock_auth_reqeust()
        result_auth_success = self.mock_auth_success()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_auth_success))

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

        # 5 messages: [ auth, subscribe_balanse, subscribe_orders, subscribe_trades, ping ]
        self.assertEqual(5, len(sent_subscription_messages))
        self.assertEqual(auth_request, sent_subscription_messages[0])

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source.CoinexAPIUserStreamDataSource._time")
    async def test_listen_for_user_stream_subscribes_to_orders_and_balances_events(self, time_mock, ws_connect_mock):
        time_mock.return_value = TEST_TS
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_balance = {
            "id": CONSTANTS.WS_BALANCE_ID,
            "code": 0,
            "message": "OK",
        }
        result_subscribe_orders = {
            "id": CONSTANTS.WS_ORDERS_ID,
            "code": 0,
            "message": "OK",
        }
        result_subscribe_trades = {
            "id": CONSTANTS.WS_TRADES_ID,
            "code": 0,
            "message": "OK",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_balance))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))

        output_queue = asyncio.Queue()
        try:
            self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
            await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)
        except asyncio.CancelledError:
            pass

        sent_subscription_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        # 5 messages: [ auth, subscribe_balanse, subscribe_orders, subscribe_trades, ping ]
        expected_balances_subscription = {
            "id": CONSTANTS.WS_BALANCE_ID,
            "method": CONSTANTS.WS_METHOD_BALANCE_SUBSCRIBE,
            "params": {"ccy_list": [self.base_asset, self.quote_asset]},
        }
        expected_orders_subscription = {
            "id": CONSTANTS.WS_ORDERS_ID,
            "method": CONSTANTS.WS_METHOD_ORDER_SUBSCRIBE,
            "params": {"market_list": [self.ex_trading_pair]},
        }
        expected_trades_subscription = {
            "id": CONSTANTS.WS_TRADES_ID,
            "method": CONSTANTS.WS_METHOD_USERDEALS_SUBSCRIBE,
            "params": {"market_list": [self.ex_trading_pair]},
        }

        self.assertEqual(5, len(sent_subscription_messages))
        self.assertEqual(expected_balances_subscription, sent_subscription_messages[1])
        self.assertEqual(expected_orders_subscription, sent_subscription_messages[2])
        self.assertEqual(expected_trades_subscription, sent_subscription_messages[3])
        self.assertTrue(self._is_logged("INFO", "Subscribed to private channels successful"))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source.CoinexAPIUserStreamDataSource._time")
    async def test_listen_for_user_stream_skips_subscribe_unsubscribe_messages(self, time_mock, ws_connect_mock):
        time_mock.return_value = TEST_TS
        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_subscribe_balance = {
            "id": CONSTANTS.WS_BALANCE_ID,
            "code": 0,
            "message": "OK",
        }
        result_subscribe_orders = {
            "id": CONSTANTS.WS_ORDERS_ID,
            "code": 0,
            "message": "OK",
        }
        result_subscribe_trades = {
            "code": 0,
            "id": CONSTANTS.WS_TRADES_ID,
            "message": "OK",
        }

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_balance))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_orders))
        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_subscribe_trades))

        output_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        self.assertTrue(output_queue.empty())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    async def test_listen_for_user_stream_does_not_queue_pong_payload(self, mock_ws):
        result_pong = self.mock_pong_response()
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        self.mocking_assistant.add_websocket_aiohttp_message(mock_ws.return_value, json.dumps(result_pong))

        msg_queue = asyncio.Queue()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(msg_queue))
        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(mock_ws.return_value)

        self.assertEqual(0, msg_queue.qsize())

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_connection_failed(self, sleep_mock, mock_ws):
        mock_ws.side_effect = Exception("TEST ERROR.")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.core.data_type.user_stream_tracker_data_source.UserStreamTrackerDataSource._sleep")
    async def test_listen_for_user_stream_iter_message_throws_exception(self, sleep_mock, mock_ws):
        mock_ws.return_value = self.mocking_assistant.create_websocket_mock()
        mock_ws.return_value.receive.side_effect = Exception("TEST ERROR")
        sleep_mock.side_effect = asyncio.CancelledError  # to finish the task execution

        msg_queue = asyncio.Queue()
        try:
            await self.data_source.listen_for_user_stream(msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error while listening to user stream. Retrying after 5 seconds..."))

    @patch("aiohttp.ClientSession.ws_connect", new_callable=AsyncMock)
    @patch("hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source.CoinexAPIUserStreamDataSource._time")
    async def test_listen_for_user_stream_sends_ping_message_before_ping_interval_finishes(self, time_mock, ws_connect_mock):
        time_mock.side_effect = [1000, 1100, 1101, 1102]  # Simulate first ping interval is already due

        ws_connect_mock.return_value = self.mocking_assistant.create_websocket_mock()

        result_auth = self.mock_auth_success()

        self.mocking_assistant.add_websocket_aiohttp_message(
            websocket_mock=ws_connect_mock.return_value,
            message=json.dumps(result_auth))

        output_queue = asyncio.Queue()
        self.data_source._sleep = AsyncMock()
        self.data_source._sleep.side_effect = asyncio.CancelledError()
        self.listening_task = self.local_event_loop.create_task(self.data_source.listen_for_user_stream(output=output_queue))

        await self.mocking_assistant.run_until_all_aiohttp_messages_delivered(ws_connect_mock.return_value)

        sent_messages = self.mocking_assistant.json_messages_sent_through_websocket(
            websocket_mock=ws_connect_mock.return_value)

        expected_ping_message = self.mock_ping_request()
        self.assertEqual(expected_ping_message, sent_messages[-1])
