import unittest
from decimal import Decimal

from aioresponses import aioresponses

from hummingbot.connector.trading_rule import TradingRule
from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange

class CoinexExchangeTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # ag
        cls.api_key = "560CE33AA5E845929981B163ABD2B25F"
        cls.api_secret_key = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"
        cls.base_asset = "CET"
        cls.quote_asset = "USDT"
        cls.trading_pair = f"{cls.base_asset}{cls.quote_asset}"

    def setUp(self) -> None:
        super().setUp()

        self.exchange = CoinexExchange(
            coinex_api_key=self.api_key,
            coinex_api_secret=self.api_secret_key,
            trading_pairs=[self.trading_pair]
        )

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
    def test_create_limit_order_successfully(self, mock_api):
        self._simulate_trading_rules_initialized()
