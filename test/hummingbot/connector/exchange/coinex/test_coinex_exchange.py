import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable, Dict, NamedTuple, Optional, List
from unittest.mock import MagicMock, patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import BuyOrderCreatedEvent, MarketEvent, MarketOrderFailureEvent, OrderCancelledEvent
from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.core.web_assistant.connections.data_types import RESTMethod


TEST_TIMESTAMP_SEC = 1640000003.356
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
        cls.ex_trading_pair = f"{TEST_BASE}{TEST_QUOTE}"

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

    def _simulate_trading_fees_initialized(self):
        fee_rates = {
            "market": self.ex_trading_pair,
            "taker_rate": str(0.0002),
            "maker_rate": str(0.0001),
        }
        self.exchange._trading_fees[self.trading_pair] = fee_rates

    def _validate_auth_credentials_present(self, request_call_tuple: NamedTuple):
        request_headers = request_call_tuple.kwargs["headers"]
        self.assertIn("Content-Type", request_headers)
        self.assertIn("X-COINEX-KEY", request_headers)
        self.assertIn("X-COINEX-SIGN", request_headers)
        self.assertIn("X-COINEX-TIMESTAMP", request_headers)

    def _setup_call(self, mock_api, url, method = RESTMethod.GET, status = None, response = None, exception = None, callback = None):
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))
        if method == RESTMethod.GET:
            if status:
                mock_api.get(regex_url, status=status, callback=callback)
            elif response:
                mock_api.get(regex_url, body=json.dumps(response), callback=callback)
            elif exception:
                mock_api.get(regex_url, exception=exception, callback=callback)

        if method == RESTMethod.POST:
            if status:
                mock_api.post(regex_url, status=status, callback=callback)
            elif response:
                mock_api.post(regex_url, body=json.dumps(response), callback=callback)
            elif exception:
                mock_api.post(regex_url, exception=exception, callback=callback)

    def _setup_get(self, mock_api, url, status = None, response = None, exception = None, callback = None):
        self._setup_call(mock_api, url, RESTMethod.GET, status, response, exception, callback)

    def _setup_post(self, mock_api, url, status = None, response = None, exception = None, callback = None):
        self._setup_call(mock_api, url, RESTMethod.POST, status, response, exception, callback)

    #endregion MANAGING

    #region TST_CHECK_NETWORK

    @aioresponses()
    def test_check_network_success(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_PING_EP)
        resp = { "code": 0, "data": { "result":"pong" }, "message": "OK" }
        self._setup_get(mock_api, url, response=resp)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(NetworkStatus.CONNECTED, ret)

    @aioresponses()
    def test_check_network_failure(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_PING_EP)
        self._setup_get(mock_api, url, status=500)

        ret = self.async_run_with_timeout(coroutine=self.exchange.check_network())

        self.assertEqual(ret, NetworkStatus.NOT_CONNECTED)

    @aioresponses()
    def test_check_network_raises_cancel_exception(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_PING_EP)
        self._setup_get(mock_api, url, exception=asyncio.CancelledError)

        self.assertRaises(asyncio.CancelledError, self.async_run_with_timeout, self.exchange.check_network())

    #endregion TESTS_CHECK_NETWORK
    
    #region TST_SERVER_TIME

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_EP)
        response = {"code": -1, "message": "error"}
        self._setup_get(mock_api, url=url, response=response)

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [TEST_TIMESTAMP_SEC, TEST_TIMESTAMP_SEC, TEST_TIMESTAMP_SEC]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()

        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_EP)
        response = {
            "code": 0,
            "message": "OK",
            "data": { "timestamp": TEST_TIMESTAMP_SEC * 1e3 },
        }

        self._setup_get(mock_api, url, response=response, callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(TEST_TIMESTAMP_SEC, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_update_time_synchronizer_raises_cancelled_error(self, mock_api):
        url = web_utils.rest_url(CONSTANTS.SERVER_TIME_EP)
        self._setup_get(mock_api, url, exception=asyncio.CancelledError)

        self.assertRaises(
            asyncio.CancelledError,
            self.async_run_with_timeout, self.exchange._update_time_synchronizer())

    #endregion TESTS_SERVER_TIME

    #region TST_TRADING_PAIRS

    @aioresponses()
    def test_update_trading_rules(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        url = web_utils.rest_url(CONSTANTS.TRADING_PAIRS_EP)
        resp = self.get_exchange_rules_mock()
        self._setup_get(mock_api, url, response=resp)

        self.async_run_with_timeout(coroutine=self.exchange._update_trading_rules())

        self.assertTrue(self.trading_pair in self.exchange._trading_rules)

    @aioresponses()
    def test_update_trading_rules_ignores_rule_with_error(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        url = web_utils.rest_url(CONSTANTS.TRADING_PAIRS_EP)
        trading_pair = f"{TEST_BASE}{TEST_QUOTE}"
        resp = {
            "code": 0,
            "message": "OK",
            "data": {
                f"{trading_pair}":
                {
                    "name": trading_pair,
                    "trading_name": TEST_BASE,
                    "pricing_name": TEST_QUOTE,
                },
            },
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
        url = web_utils.rest_url(path_url=CONSTANTS.TRADING_PAIRS_EP)
        resp = {
            "code": 0,
            "message": "OK",
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
        }
        
        self._setup_get(mock_api, url, response=resp)

        ret = self.async_run_with_timeout(coroutine=self.exchange.all_trading_pairs())

        self.assertEqual(1, len(ret))
        self.assertIn(f"{TEST_BASE}-{TEST_QUOTE}", ret)
        self.assertNotIn("SOME-PAIR", ret)

    @aioresponses()
    def test_all_trading_pairs_does_not_raise_exception(self, mock_api):
        self.exchange._set_trading_pair_symbol_map(None)

        url = web_utils.rest_url(path_url=CONSTANTS.TRADING_PAIRS_EP)

        self._setup_get(mock_api, url, exception=Exception)

        result: List[str] = self.async_run_with_timeout(self.exchange.all_trading_pairs())

        self.assertEqual(0, len(result))

    #endregion TST_TRADING_PAIRS

    #region TST_TRADING_FEE

    @aioresponses()
    def test_get_fee_returns_fee_from_exchange_if_available_and_default_if_not(self, mocked_api):
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        url = web_utils.rest_url(CONSTANTS.ACCOUNT_TRADE_FEE_EP)
        resp = {
            "code": 0,
            "message": "OK",
            "data": {
                "market": self.ex_trading_pair,
                "maker_rate": "0.003",
                "taker_rate": "0.002"
            },
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

    @aioresponses()
    def test_update_trading_fees_with_valid_pairs(self, mock_api):
        """
        Test that trading fees are updated correctly for valid pair,
        and invalid pairs are ignored in the trading pair map.
        """
        self._simulate_trading_rules_initialized()
        self._simulate_trading_fees_initialized()

        # Validate initial state
        initial_taker_fee = Decimal("0.0002")
        initial_maker_fee = Decimal("0.0001")
        self.assertEqual(initial_maker_fee, Decimal(self.exchange._trading_fees[self.trading_pair]["maker_rate"]))
        self.assertEqual(initial_taker_fee, Decimal(self.exchange._trading_fees[self.trading_pair]["taker_rate"]))

        # Mock API response
        url = web_utils.rest_url(CONSTANTS.ACCOUNT_TRADE_FEE_EP)
        response = {
            "retCode": 0,
            "message": "OK",
            "data": {
                "market": self.ex_trading_pair,
                "taker_rate": "0.0006",
                "maker_rate": "0.0005",
            },
        }
        self._setup_get(mock_api, url, response=response)

        # Execute method under test
        self.async_run_with_timeout(self.exchange._update_trading_fees())

        # Validate updated state
        updated_maker_fee = Decimal("0.0005")
        updated_taker_fee = Decimal("0.0006")
        self.assertEqual(updated_maker_fee, Decimal(self.exchange._trading_fees[self.trading_pair]["maker_rate"]))
        self.assertEqual(updated_taker_fee, Decimal(self.exchange._trading_fees[self.trading_pair]["taker_rate"]))
        self.assertNotIn("INVALIDPAIR", self.exchange._trading_pairs)

    #endregion TST_TRADING_FEE

    #region TST_BALANCE

    @aioresponses()
    def test_update_balances(self, mock_api):
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        url = web_utils.rest_url(CONSTANTS.GET_BALANCE_PATH_URL)

        response = {
            "code": 0,
            "message": "OK",
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
        }

        self._setup_get(mock_api, url, response=response)
        
        self.async_run_with_timeout(self.exchange._update_balances())

        available_balances = self.exchange.available_balances
        total_balances = self.exchange.get_all_balances()

        self.assertEqual(Decimal("10"), available_balances["BTC"])
        self.assertEqual(Decimal("2000"), available_balances["LTC"])
        self.assertEqual(Decimal("20"), total_balances["BTC"])
        self.assertEqual(Decimal("2000"), total_balances["LTC"])

        response = {
            "code": 0,
            "message": "OK",
            "data": [
                {
                    "ccy": "BTC",
                    "available": "10.0",
                    "frozen": "5.0"
                }
            ]
        }

        self._setup_get(mock_api, url, response=response)
        
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
    def test_cancel_order_raises_failure_event_when_request_fails(self, mock_api):
        test_order_id=40233
        test_client_id="OID1"

        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        self.exchange.start_tracking_order(
            order_id=test_client_id,
            exchange_order_id=test_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[test_client_id]

        url = web_utils.rest_url(CONSTANTS.ORDERS_PENDING_EP)

        self._setup_post(mock_api, url, status=400, callback=lambda *args, **kwargs: request_sent_event.set())

        request_sent_event.set()

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=test_client_id)
        self.async_run_with_timeout(request_sent_event.wait())

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged("ERROR", f"Failed to cancel order {order.client_order_id}")
        )

    @aioresponses()
    def test_cancel_order_successfully(self, mock_api):
        test_order_id=40234
        test_client_id="OID2"

        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        self.exchange.start_tracking_order(
            order_id=test_client_id,
            exchange_order_id=test_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[test_client_id]

        url = web_utils.rest_url(CONSTANTS.ORDERS_CANCEL_EP)
        response = {
            "code": 0,
            "message": "OK",
            "data": {
                "market": f"{self.ex_trading_pair}",
                "market_type": "SPOT",
                "order_id": test_order_id,
                "client_id": f"{test_client_id}",
            },
        }
        self._setup_post(mock_api, url, response=response, callback=lambda *args, **kwargs: request_sent_event.set())

        self.exchange.cancel(trading_pair=self.trading_pair, client_order_id=test_client_id)
        self.async_run_with_timeout(request_sent_event.wait())

        cancel_request = next(((key, value) for key, value in mock_api.requests.items()
                               if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(cancel_request[1][0])
        request_params = cancel_request[1][0].kwargs["params"]
        self.assertIsNone(request_params)

        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    def test_cancel_order_fail_on_retries_exchange_order_id(self):
        test_client_id="OID3"
        update_event = MagicMock()
        update_event.wait.side_effect = asyncio.TimeoutError

        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        self.exchange.start_tracking_order(
            order_id=test_client_id,
            exchange_order_id=None,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[test_client_id]
        order.exchange_order_id_update_event = update_event

        self.async_run_with_timeout(self.exchange._execute_cancel(
            trading_pair=order.trading_pair,
            order_id=order.client_order_id,
        ))

        self.assertEqual(0, len(self.order_cancelled_logger.event_log))

        self.assertTrue(
            self._is_logged("WARNING", f"Failed to cancel the order {order.client_order_id} because it does not have an exchange order id yet")
        )

        # After the fourth time not finding the exchange order id the order should be marked as failed
        for i in range(self.exchange._order_tracker._lost_order_count_limit + 1):
            self.async_run_with_timeout(self.exchange._execute_cancel(
                trading_pair=order.trading_pair,
                order_id=order.client_order_id,
            ))

        self.assertTrue(order.is_failure)

        failure_event: MarketOrderFailureEvent = self.order_failure_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, failure_event.timestamp)
        self.assertEqual(order.client_order_id, failure_event.order_id)
        self.assertEqual(order.order_type, failure_event.order_type)

    @aioresponses()
    def test_cancel_orders_with_cancel_all(self, mock_api):
        test_order_id=40236
        test_client_id="OID4"
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        self.exchange.start_tracking_order(
            order_id=test_client_id,
            exchange_order_id=test_order_id,
            trading_pair=self.trading_pair,
            trade_type=TradeType.BUY,
            price=Decimal("10000"),
            amount=Decimal("100"),
            order_type=OrderType.LIMIT,
        )

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        order = self.exchange.in_flight_orders[test_client_id]

        url = web_utils.rest_url(CONSTANTS.ORDERS_CANCEL_EP)
        response = {
            "code": 0,
            "message": "OK",
            "data": {
                "order_id": test_client_id,
                "client_id": f"{test_client_id}"
            },
        }
        self._setup_post(mock_api, url, response=response)

        cancellation_results = self.async_run_with_timeout(self.exchange.cancel_all(10))

        self.assertEqual(1, len(cancellation_results))

        self.assertEqual(1, len(self.order_cancelled_logger.event_log))
        cancel_event: OrderCancelledEvent = self.order_cancelled_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, cancel_event.timestamp)
        self.assertEqual(order.client_order_id, cancel_event.order_id)

        self.assertTrue(
            self._is_logged("INFO", f"Successfully canceled order {order.client_order_id}.")
        )

    @aioresponses()
    def test_create_limit_order_successfully(self, mock_api):
        test_order_id=40323
        test_client_id="OID6"

        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CREATE_EP)
        creation_response = {
            "code": 0,
            "message": "OK",
            "data": {
                "order_id": test_order_id,
                "client_id": f"{test_client_id}",
            }}
        self._setup_post(mock_api, url,
                         response=creation_response,
                         callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id=f"{test_client_id}",
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["market"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("limit", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(test_client_id, request_data["client_id"])

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(test_client_id, create_event.order_id)
        self.assertEqual(str(creation_response["data"]["order_id"]), create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT BUY order {test_client_id} "
                f"for {Decimal('100.000000')} {self.trading_pair} "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    def test_create_post_only_order_successfully(self, mock_api):
        test_order_id=40324
        test_client_id="OID7"

        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)
        
        url = web_utils.private_rest_url(CONSTANTS.ORDER_CREATE_EP)
        creation_response = {
            "code": 0,
            "message": "OK",
            "data": {
                "order_id": test_order_id,
                "client_id": f"{test_client_id}",
            }}
        self._setup_post(mock_api, url,
                         response=creation_response,
                         callback=lambda *args, **kwargs: request_sent_event.set())

        self.test_task = asyncio.get_event_loop().create_task(
            self.exchange._create_order(trade_type=TradeType.BUY,
                                        order_id=test_client_id,
                                        trading_pair=self.trading_pair,
                                        amount=Decimal("100"),
                                        order_type=OrderType.LIMIT_MAKER,
                                        price=Decimal("10000")))
        self.async_run_with_timeout(request_sent_event.wait())

        order_request = next(((key, value) for key, value in mock_api.requests.items()
                              if key[1].human_repr().startswith(url)))
        self._validate_auth_credentials_present(order_request[1][0])
        request_data = json.loads(order_request[1][0].kwargs["data"])
        self.assertEqual(self.ex_trading_pair, request_data["market"])
        self.assertEqual(TradeType.BUY.name.lower(), request_data["side"])
        self.assertEqual("maker_only", request_data["type"])
        self.assertEqual(Decimal("100"), Decimal(request_data["amount"]))
        self.assertEqual(Decimal("10000"), Decimal(request_data["price"]))
        self.assertEqual(test_client_id, request_data["client_id"])

        self.assertIn(test_client_id, self.exchange.in_flight_orders)
        create_event: BuyOrderCreatedEvent = self.buy_order_created_logger.event_log[0]
        self.assertEqual(self.exchange.current_timestamp, create_event.timestamp)
        self.assertEqual(self.trading_pair, create_event.trading_pair)
        self.assertEqual(OrderType.LIMIT_MAKER, create_event.type)
        self.assertEqual(Decimal("100"), create_event.amount)
        self.assertEqual(Decimal("10000"), create_event.price)
        self.assertEqual(test_client_id, create_event.order_id)
        self.assertEqual(str(creation_response["data"]["order_id"]), create_event.exchange_order_id)

        self.assertTrue(
            self._is_logged(
                "INFO",
                f"Created LIMIT_MAKER BUY order {test_client_id} "
                f"for {Decimal('100.000000')} {self.trading_pair} "
                f"at {Decimal('10000.0000')}."
            )
        )

    @aioresponses()
    @patch("hummingbot.connector.exchange.coinex.coinex_exchange.CoinexExchange.get_price")
    def test_create_order_with_wrong_params_raises_io_error(self, mock_api, get_price_mock):
        test_order_id = "C1"
        self.exchange._set_current_timestamp(TEST_TIMESTAMP_SEC)

        get_price_mock.return_value = Decimal(1000)
        self._simulate_trading_rules_initialized()
        request_sent_event = asyncio.Event()

        url = web_utils.private_rest_url(CONSTANTS.ORDER_CREATE_EP)
        creation_response = {
            "code": 3127,
            "message": "The quantity is invalid.",
        }

        self._setup_post(mock_api, url,
                         response=creation_response,
                         callback=lambda *args, **kwargs: request_sent_event.set())

        self._simulate_trading_rules_initialized()

        with self.assertRaises(IOError):
            asyncio.get_event_loop().run_until_complete(
                self.exchange._place_order(
                    trade_type=TradeType.BUY,
                    order_id=test_order_id,
                    trading_pair=self.trading_pair,
                    amount=Decimal("0"),
                    order_type=OrderType.LIMIT,
                    price=Decimal("46000"),
                ),
            )

    #endregion TST_ORDERS
