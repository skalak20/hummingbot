import asyncio
import json
import re
from test.isolated_asyncio_wrapper_test_case import IsolatedAsyncioWrapperTestCase
from unittest.mock import AsyncMock, MagicMock

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.connector.exchange.coinex.coinex_api_order_book_data_source import CoinexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange
from hummingbot.connector.test_support.network_mocking_assistant import NetworkMockingAssistant
from hummingbot.core.data_type.order_book_message import OrderBookMessage

TEST_TS = 1661927587825
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"
TEST_BASE = "BTC"
TEST_QUOTE = "USDT"


class TestCoinexAPIOrderBookDataSource(IsolatedAsyncioWrapperTestCase):
    # logging.Level required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.api_key = TEST_KEY
        cls.api_secret = TEST_SECRET
        cls.base_asset = TEST_BASE
        cls.quote_asset = TEST_QUOTE
        cls.trading_pair = f"{cls.base_asset}-{cls.quote_asset}"
        cls.ex_trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    async def asyncSetUp(self) -> None:
        # await super().asyncSetUp()
        self.log_records = []
        self.async_task = None
        self.mocking_assistant = NetworkMockingAssistant(self.local_event_loop)

        client_config_map = ClientConfigAdapter(ClientConfigMap())
        self.connector = CoinexExchange(
            client_config_map=client_config_map,
            coinex_api_key=self.api_key,
            coinex_api_secret=self.api_secret,
            trading_pairs=[self.trading_pair],
            trading_required=False)

        self.data_source = CoinexAPIOrderBookDataSource(
            trading_pairs=[self.trading_pair],
            connector=self.connector,
            api_factory=self.connector._web_assistants_factory)

        self.data_source.logger().setLevel(1)
        self.data_source.logger().addHandler(self)

        self._original_full_order_book_reset_time = self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = -1

        self.resume_test_event = asyncio.Event()

        self.connector._set_trading_pair_symbol_map(bidict({f"{TEST_BASE}{TEST_QUOTE}": self.trading_pair}))

    def tearDown(self) -> None:
        self.async_task and self.async_task.cancel()
        self.data_source.FULL_ORDER_BOOK_RESET_DELTA_SECONDS = self._original_full_order_book_reset_time
        super().tearDown()

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message
                   for record in self.log_records)

    @classmethod
    def _get_snapshot_mock(cls):
        snapshot = {
            "code": 0,
            "data": {
                "market": f"{cls.ex_trading_pair}",
                "is_full": True,
                "depth": {
                    "asks": [["69417", "0.07235316"], ["69418", "0.17286582"], ["69420", "0.07346604"], ["69421", "1.48370088"], ["69427", "0.7201809"]],
                    "bids": [["69416", "0.19272954"], ["69411", "0.01008485"], ["69410", "0.00144069"], ["69405", "0.02334033"], ["69402", "0.04322641"]],
                    "checksum": 3200617993,
                    "last": "69410",
                    "updated_at": 1770295371577
                },
            },
            "message": "OK"
        }
        return snapshot

    @classmethod
    def _order_diff_event(cls):
        depth = {
            "method": "depth.update",
            "data": {
                "market": f"{cls.ex_trading_pair}",
                "is_full": False,
                "depth": {
                    "asks": [["69417", "0.07235316"], ["69418", "0.17286582"], ["69420", "0.07346604"], ["69421", "1.48370088"], ["69427", "0.7201809"]],
                    "bids": [["69416", "0.19272954"], ["69411", "0.01008485"], ["69410", "0.00144069"], ["69405", "0.02334033"], ["69402", "0.04322641"]],
                    "checksum": 3200617993,
                    "last": "69410",
                    "updated_at": 1770295371577
                },
            },
            "id": None
        }
        return depth

    @classmethod
    def _trade_update_event(cls):
        resp = {
            "method": "deals.update",
            "data": {
                "market": f"{cls.ex_trading_pair}",
                "deal_list": [{
                    "deal_id": 3514376759,
                    "created_at": TEST_TS,
                    "side": "buy",
                    "price": "30718.42",
                    "amount": "0.00000325"
                }, {
                    "deal_id": 3514376758,
                    "created_at": TEST_TS,
                    "side": "buy",
                    "price": "30718.42",
                    "amount": "0.00015729"
                }, {
                    "deal_id": 3514376757,
                    "created_at": TEST_TS,
                    "side": "sell",
                    "price": "30718.42",
                    "amount": "0.00154936"
                }],
            },
            "id": None,
        }
        return resp

    def _setup_get(self, mock_api, url, status = None, response = None, exception = None, callback = None):
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        if status:
            mock_api.get(regex_url, status=status, callback=callback)
        elif response:
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        elif exception:
            mock_api.get(regex_url, exception=exception, callback=callback)

    @aioresponses()
    async def test_get_new_order_book_successful(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_NO_AUTH_EP)
        resp = self._get_snapshot_mock()
        self._setup_get(mock_api, url, response=resp)

        ret = await self.data_source.get_new_order_book(self.trading_pair)
        bid_entries = list(ret.bid_entries())
        ask_entries = list(ret.ask_entries())
        self.assertEqual(5, len(bid_entries))
        self.assertEqual(69416.0, bid_entries[0].price)
        self.assertEqual(0.19272954, bid_entries[0].amount)
        self.assertEqual(resp["data"]["depth"]["checksum"], bid_entries[0].update_id)
        self.assertEqual(5, len(ask_entries))
        self.assertEqual(69417.0, ask_entries[0].price)
        self.assertEqual(0.07235316, ask_entries[0].amount)
        self.assertEqual(resp["data"]["depth"]["checksum"], ask_entries[0].update_id)

    @aioresponses()
    async def test_get_new_order_book_raises_exception(self, mock_api):
        url = web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_NO_AUTH_EP)
        self._setup_get(mock_api, url, status=400)

        with self.assertRaises(IOError):
            await self.data_source.get_new_order_book(self.trading_pair)

    async def test_subscribe_channels_raises_cancel_exception(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source._subscribe_channels(mock_ws)

    async def test_subscribe_channels_raises_exception_and_logs_error(self):
        mock_ws = MagicMock()
        mock_ws.send.side_effect = Exception("Test Error")

        with self.assertRaises(Exception):
            await self.data_source._subscribe_channels(mock_ws)

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error occurred subscribing to Coinex order book trading and delta streams...")
        )

    async def test_listen_for_trades_cancelled_when_listening(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)

    async def test_listen_for_trades_logs_exception(self):
        mock_queue = MagicMock()

        incomplete_resp = {"m": 1, "i": 2}
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_trades(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public trade updates from exchange")
        )

    async def test_listen_for_trades_successful(self):
        mock_queue = AsyncMock()
        trade_event = self._trade_update_event()
        mock_queue.get.side_effect = [trade_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._trade_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_trades(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(3514376759, msg.trade_id)

    async def test_listen_for_order_book_diffs_cancelled(self):
        mock_queue = MagicMock()
        mock_queue.get.side_effect = asyncio.CancelledError()
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        with self.assertRaises(asyncio.CancelledError):
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)

    async def test_listen_for_order_book_diffs_logs_exception(self):
        mock_queue = AsyncMock()

        incomplete_resp = {"m": 1, "i": 2}
        mock_queue.get.side_effect = [incomplete_resp, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        try:
            await self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue)
        except asyncio.CancelledError:
            pass

        self.assertTrue(
            self._is_logged("ERROR", "Unexpected error when processing public order book updates from exchange")
        )

    async def test_listen_for_order_book_diffs_successful(self):
        mock_queue = AsyncMock()
        diff_event = self._order_diff_event()
        mock_queue.get.side_effect = [diff_event, asyncio.CancelledError()]
        self.data_source._message_queue[self.data_source._diff_messages_queue_key] = mock_queue

        msg_queue: asyncio.Queue = asyncio.Queue()

        self.listening_task = self.local_event_loop.create_task(
            self.data_source.listen_for_order_book_diffs(self.local_event_loop, msg_queue))

        msg: OrderBookMessage = await msg_queue.get()

        self.assertEqual(int(diff_event["d"]["r"]), msg.update_id)
