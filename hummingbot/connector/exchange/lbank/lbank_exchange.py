from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_utils, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source import LbankAPIOrderBookDataSource
from hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source import LbankAPIUserStreamDataSource
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange.lbank.lbank_utils import convert_from_exchange_trading_pair
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class LbankExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 lbank_api_key: str,
                 lbank_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True):
        self._domain = CONSTANTS.DEF_DOMAIN
        self._api_key = lbank_api_key
        self._secret_key = lbank_api_secret
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        super().__init__(client_config_map)

    @property
    def authenticator(self) -> AuthBase:
        return LbankAuth(
            api_key=self._api_key,
            secret_key=self._secret_key)

    @property
    def check_network_request_path(self) -> str:
        raise NotImplementedError

    @property
    def client_order_id_max_length(self) -> int:
        raise NotImplementedError

    @property
    def client_order_id_prefix(self) -> str:
        raise NotImplementedError

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        raise NotImplementedError

    @property
    def is_trading_required(self) -> bool:
        raise NotImplementedError

    @property
    def name(self) -> str:
        return "lbank"

    @property
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_fees

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.TRADING_PAIRS_ENDPOINT

    @property
    def trading_rules_request_path(self) -> str:
        raise NotImplementedError

    def supported_order_types(self) -> List[OrderType]:
        raise NotImplementedError

    def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LbankAPIOrderBookDataSource(
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return LbankAPIUserStreamDataSource()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        raise NotImplementedError

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(lbank_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data["symbol"]] = convert_from_exchange_trading_pair(symbol_data["symbol"])
        self._set_trading_pair_symbol_map(mapping)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        raise NotImplementedError

    def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise NotImplementedError

    def _place_order(self,
                     order_id: str,
                     trading_pair: str,
                     amount: Decimal,
                     trade_type: TradeType,
                     order_type: OrderType,
                     price: Decimal,
                     **kwargs) -> Tuple[str, float]:
        raise NotImplementedError

    def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise NotImplementedError

    def _update_balances(self):
        raise NotImplementedError

    def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        raise NotImplementedError

    def _user_stream_event_listener(self):
        raise NotImplementedError
