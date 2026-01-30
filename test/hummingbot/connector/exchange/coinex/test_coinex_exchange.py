import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, Optional, List
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent
from hummingbot.core.network_iterator import NetworkStatus


TEST_TS_SEC = 1640000003.356
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"
TEST_BASE = "CET"
TEST_QUOTE = "USDT"


class CoinexExchangeTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    #region MANAGING

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        # ag
        cls.api_key = TEST_KEY
        cls.api_secret_key = TEST_SECRET
        cls.base_asset = TEST_BASE
        cls.quote_asset = TEST_QUOTE
        cls.trading_pair = f"{TEST_BASE}-{TEST_QUOTE}"

    def setUp(self) -> None:
        super().setUp()

        self.log_records = []
        self.test_task: Optional[asyncio.Task] = None

        self.exchange = self.create_exchange_instance()

        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(bidict({f"{TEST_BASE}{TEST_QUOTE}": self.trading_pair}))

    def tearDown(self) -> None:
        self.test_task and self.test_task.cancel()
        super().tearDown()

    def create_exchange_instance(self):
        client_config_map = ClientConfigAdapter(ClientConfigMap())
        return CoinexExchange(
            client_config_map=client_config_map,
            coinex_api_key=self.api_key,
            coinex_api_secret=self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )

    def get_exchange_rules_mock(self) -> Dict:
        exchange_rules = {
            "code": 0,
            "data": {
                f"{TEST_BASE}{TEST_QUOTE}": {
                    "name": f"{TEST_BASE}{TEST_QUOTE}",
                    "min_amount": "50000000",
                    "maker_fee_rate": "0.003",
                    "taker_fee_rate": "0.003",
                    "pricing_name": TEST_QUOTE,
                    "pricing_decimal": 12,
                    "trading_name": TEST_BASE,
                    "trading_decimal": 2,
                },
            },
            "message": "OK",
        }
        return exchange_rules

    def _initialize_event_loggers(self):
        self.buy_order_completed_logger = EventLogger()
        self.buy_order_created_logger = EventLogger()
        self.order_cancelled_logger = EventLogger()
        self.order_failure_logger = EventLogger()
        self.order_filled_logger = EventLogger()
        self.sell_order_completed_logger = EventLogger()
        self.sell_order_created_logger = EventLogger()

        events_and_loggers = [
            (MarketEvent.BuyOrderCompleted, self.buy_order_completed_logger),
            (MarketEvent.BuyOrderCreated, self.buy_order_created_logger),
            (MarketEvent.OrderCancelled, self.order_cancelled_logger),
            (MarketEvent.OrderFailure, self.order_failure_logger),
            (MarketEvent.OrderFilled, self.order_filled_logger),
            (MarketEvent.SellOrderCompleted, self.sell_order_completed_logger),
            (MarketEvent.SellOrderCreated, self.sell_order_created_logger)]

        for event, logger in events_and_loggers:
            self.exchange.add_listener(event, logger)

    def handle(self, record):
        self.log_records.append(record)

    def _is_logged(self, log_level: str, message: str) -> bool:
        return any(record.levelname == log_level and record.getMessage() == message for record in self.log_records)

    def async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = self.ev_loop.run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _simulate_trading_rules_initialized(self):
        self.exchange._trading_rules = {
            self.trading_pair: TradingRule(
                trading_pair=self.trading_pair,
                min_order_size=Decimal(str(0.01)),
                min_price_increment=Decimal(str(0.0001)),
                min_base_amount_increment=Decimal(str(0.000001)),
            )
        }

    def _setup_get(self, mock_api, url, response = None, status = None, exception = None, callback = None):
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        
        if response:
            mock_api.get(regex_url, body=json.dumps(response), callback=callback)
        elif status:
            mock_api.get(regex_url, status=status, callback=callback)
        elif exception:
            mock_api.get(regex_url, exception=exception, callback=callback)

    #endregion MANAGING

    #region TST_CHECK_NETWORK

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_PING_EP)
        resp = { "code": 0, "data": { "result":"pong" }, "message": "OK" }
        self._setup_get(mock_api, url, resp)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, ret)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_PING_EP)
        self._setup_get(mock_api, url, status=500)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_PING_EP)
        self._setup_get(mock_api, url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    #endregion TESTS_CHECK_NETWORK
    
    #region TST_SERVER_TIME

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        response = {"code": -1, "message": "error"}
        self._setup_get(mock_api, url, response)

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [TEST_TS_SEC, TEST_TS_SEC, TEST_TS_SEC]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()

        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        response = {
            "code": 0,
            "data": { "timestamp": TEST_TS_SEC * 1e3 },
            "message": "OK",
        }

        self._setup_get(mock_api, url, response, callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(TEST_TS_SEC, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        self._setup_get(mock_api, url, exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    #endregion TESTS_SERVER_TIME

    #region TST_TRADING_PAIRS

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TS_SEC)

        url = web_utils.public_rest_url(CONSTANTS.TRADING_PAIRS_EP)
        resp = self.get_exchange_rules_mock()
        self._setup_get(mock_api, url, response=resp)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange._trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TS_SEC)

        url = web_utils.public_rest_url(CONSTANTS.TRADING_PAIRS_EP)
        trading_pair = f"{TEST_BASE}{TEST_QUOTE}"
        resp = {
            "code": 0,
            "data": {
                f"{trading_pair}":
                {
                    "name": trading_pair,
                    "trading_name": TEST_BASE,
                    "pricing_name": TEST_QUOTE,
                },
            },
            "message": "OK",
        }

        self._setup_get(mock_api, url, response=resp)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertEqual(0, len(self.exchange._trading_rules))
        self.assertTrue(
            self._is_logged("ERROR", f"Error parsing the trading pair rule {resp['data'][f"{trading_pair}"]}. Skipping.")
        )

    @aioresponses()
    def test_all_trading_pairs(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)
        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADING_PAIRS_EP)
        resp = {
            "code": 0,
            "data": {
                f"{TEST_BASE}{TEST_QUOTE}": {
                    "name": f"{TEST_BASE}{TEST_QUOTE}",
                    "min_amount": "50000000",
                    "maker_fee_rate": "0.003",
                    "taker_fee_rate": "0.003",
                    "pricing_name": TEST_QUOTE,
                    "pricing_decimal": 12,
                    "trading_name": TEST_BASE,
                    "trading_decimal": 2,
                },
                "SOME-PAIR":{
                    "name": "SOME-PAIR",
                    "min_amount": "50",
                    "maker_fee_rate": "0.003",
                    "taker_fee_rate": "0.003",
                    "pricing_name": "PAIR",
                    "pricing_decimal": 6,
                    "trading_name": "SOME",
                    "trading_decimal": 8,
                }
            },
            "message": "OK"
        }
        
        self._setup_get(mock_api, url, response=resp)

        ret = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(ret))
        self.assertIn(f"{TEST_BASE}-{TEST_QUOTE}", ret)
        self.assertNotIn("SOME-PAIR", ret)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = web_utils.public_rest_url(path_url=CONSTANTS.TRADING_PAIRS_EP)

        self._setup_get(mock_api, url, exception=Exception)

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    #endregion TST_TRADING_PAIRS
    
    #region TST_TRADING_FEE

    @aioresponses()
    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self, mocked_api):
        self.exchange._set_current_timestamp(TEST_TS_SEC)
        
        url = web_utils.public_rest_url(CONSTANTS.ACCOUNT_TRADE_FEE_EP)
        resp = {
            "code": 0,
            "data": {
                "market": f"{TEST_BASE}{TEST_QUOTE}",
                "maker_rate": "0.003",
                "taker_rate": "0.002"
            },
            "message": "OK"
        }

        self._setup_get(mocked_api, url, response=resp)

        self.async_run_with_timeout(self.exchange._update_trading_fees())

        fee = self.exchange.get_fee(
            base_currency=self.base_asset,
            quote_currency=self.quote_asset,
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.002"), fee.percent)

        fee = self.exchange.get_fee(
            base_currency="SOME",
            quote_currency="OTHER",
            order_type=OrderType.LIMIT,
            order_side=TradeType.BUY,
            amount=Decimal("10"),
            price=Decimal("20"),
        )

        self.assertEqual(Decimal("0.2"), fee.percent)  # default fee

    #endregion TST_TRADING_FEE
    
    #region TST_BALANCE

    @aioresponses()
    def test_update_balances(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TS_SEC)

        url = web_utils.private_rest_url(CONSTANTS.GET_BALANCE_PATH_URL)
        
        response = {
            "code": 0,
            "data": [
                {
                    "ccy": "BTC",
                    "available": "10.0",
                    "frozen": "10.0"
                },
                {
                    "ccy": "LTC",
                    "available": "2000",
                    "frozen": "0"
                }
            ],
            "message": "OK",
        }

        self._setup_get(mock_api, url, response)
        
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("20"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        response = {
            "code": 0,
            "data": [
                {
                    "ccy": "BTC",
                    "available": "10.0",
                    "frozen": "5.0"
                }]
        }

        self._setup_get(mock_api, url, response)
        
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertNotIn("LTC", available_balances)
        self.assertNotIn("LTC", total_balances)
        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("15"), total_balances["BTC"])

    #endregion TST_BALANCE

    #region TST_ORDERS
    def test_supported_order_types(self):
        supported_types = self.exchange.supported_order_types()
        self.assertIn(OrderType.MARKET, supported_types)
        self.assertIn(OrderType.LIMIT, supported_types)
        self.assertIn(OrderType.LIMIT_MAKER, supported_types)

    @aioresponses()
    def test_create_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()

    #endregion TST_ORDERS
