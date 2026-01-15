from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.backtest import backtest_utils, constants as CONSTANTS, web_utils as web_utils
from hummingbot.connector.exchange.backtest.auth import BacktestAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import DeductedFromReturnsTradeFee, TokenAmount, TradeFeeBase
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class BacktestExchange(ExchangePyBase):
    web_utils = web_utils

    def __init__(self,
                 backtest_api_key: str,
                 backtest_api_secret: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEF_DOMAIN):
        self.api_key = backtest_api_key
        self.secret_key = backtest_api_secret
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self._domain = domain
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @property
    def authenticator(self) -> AuthBase:
        return BacktestAuth(
            api_key=self.api_key,
            secret_key=self.secret_key,
            time_provider=self._time_synchronizer)

    @property
    def name(self) -> str:
        return CONSTANTS.DEF_NAME

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError("_all_trade_updates_for_order")

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        raise NotImplementedError("_create_order_book_data_source")

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        raise NotImplementedError("_create_user_stream_data_source")

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        raise NotImplementedError("_create_web_assistants_factory")

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        raise NotImplementedError("_format_trading_rules")

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> TradeFeeBase:
        raise NotImplementedError("_get_fee")

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        raise NotImplementedError("_initialize_trading_pair_symbols_from_exchange_info")

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        raise NotImplementedError("_is_order_not_found_during_cancelation_error")

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError("_is_order_not_found_during_status_update_error")

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception):
        raise NotImplementedError("_is_request_exception_related_to_time_synchronizer")

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise NotImplementedError("_place_cancel")

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        raise NotImplementedError("_place_order")

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        raise NotImplementedError("_request_order_status")

    async def _update_balances(self):
        raise NotImplementedError("_update_balances")

    async def _update_trading_fees(self):
        raise NotImplementedError("_update_trading_fees")

    async def _user_stream_event_listener(self):
        raise NotImplementedError("_user_stream_event_listener")

    @property
    def check_network_request_path(self):
        raise NotImplementedError("check_network_request_path")

    @property
    def client_order_id_max_length(self):
        raise NotImplementedError("client_order_id_max_length")

    @property
    def client_order_id_prefix(self):
        raise NotImplementedError("client_order_id_prefix")

    @property
    def domain(self):
        return self._domain

    @property
    def is_cancel_request_in_exchange_synchronous(self) -> bool:
        raise NotImplementedError("is_cancel_request_in_exchange_synchronous")

    @property
    def is_trading_required(self) -> bool:
        raise NotImplementedError("is_trading_required")

    @property
    def rate_limits_rules(self):
        raise NotImplementedError("rate_limits_rules")

    def supported_order_types(self):
        raise NotImplementedError("supported_order_types")

    @property
    def trading_pairs(self):
        raise NotImplementedError("trading_pairs")

    @property
    def trading_pairs_request_path(self):
        raise NotImplementedError("trading_pairs_request_path")

    @property
    def trading_rules_request_path(self):
        raise NotImplementedError("trading_rules_request_path")
