import asyncio
import json
import re
import unittest
from decimal import Decimal
from typing import Awaitable
from unittest.mock import patch

from aioresponses import aioresponses
from bidict import bidict

from hummingbot.client.config.client_config_map import ClientConfigMap
from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.connector.exchange.coinex import (
    coinex_constants as CONSTANTS,
    coinex_web_utils as web_utils,
)
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange
from hummingbot.core.event.event_logger import EventLogger
from hummingbot.core.event.events import MarketEvent

TEST_TS_SEC = 1640000003
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"

class CoinexExchangeTests(unittest.TestCase):
    # the level is required to receive logs from the data source logger
    level = 0

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ev_loop = asyncio.get_event_loop()
        # ag
        cls.api_key = TEST_KEY
        cls.api_secret_key = TEST_SECRET
        cls.base_asset = "CET"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()
        
        self.log_records = []
        self.client_config_map = ClientConfigAdapter(ClientConfigMap())
        
        self.exchange = CoinexExchange(
            client_config_map=self.client_config_map,
            coinex_api_key=self.api_key,
            coinex_api_secret=self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )
        
        self.exchange.logger().setLevel(1)
        self.exchange.logger().addHandler(self)
        self.exchange._time_synchronizer.add_time_offset_ms_sample(0)
        self.exchange._time_synchronizer.logger().setLevel(1)
        self.exchange._time_synchronizer.logger().addHandler(self)
        self.exchange._order_tracker.logger().setLevel(1)
        self.exchange._order_tracker.logger().addHandler(self)

        self._initialize_event_loggers()

        self.exchange._set_trading_pair_symbol_map(bidict({self.trading_pair: self.trading_pair}))

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

    @aioresponses()
    def test_update_time_synchronizer_failure_is_logged(self, mock_api):
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = { "code": -1, "message": "error" }

        mock_api.get(regex_url, body=json.dumps(response))

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertTrue(self._is_logged("NETWORK", "Error getting server time."))

    @aioresponses()
    @patch("hummingbot.connector.time_synchronizer.TimeSynchronizer._current_seconds_counter")
    def test_update_time_synchronizer_successfully(self, mock_api, seconds_counter_mock):
        request_sent_event = asyncio.Event()
        seconds_counter_mock.side_effect = [TEST_TS_SEC, TEST_TS_SEC, TEST_TS_SEC]

        self.exchange._time_synchronizer.clear_time_offset_ms_samples()
        url = web_utils.public_rest_url(CONSTANTS.SERVER_TIME_EP)
        regex_url = re.compile(f"^{url}".replace(".", r"\.").replace("?", r"\?"))

        response = { "code": 0, "message": "OK", "data": {"timestamp": TEST_TS_SEC * 1e3} }

        mock_api.get(regex_url,
                     body=json.dumps(response),
                     callback=lambda *args, **kwargs: request_sent_event.set())

        self.async_run_with_timeout(self.exchange._update_time_synchronizer())

        self.assertEqual(TEST_TS_SEC, self.exchange._time_synchronizer.time())

    @aioresponses()
    def test_create_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
