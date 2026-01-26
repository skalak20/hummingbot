import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinex import (
    coinex_constants as CONSTANTS,
    coinex_utils,
    coinex_web_utils as web_utils,
)
from hummingbot.connector.exchange.coinex.coinex_api_order_book_data_source import CoinexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source import CoinexAPIUserStreamDataSource
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.connector.exchange.coinex.coinex_utils import convert_from_exchange_trading_pair
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory


class CoinexExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 coinex_api_key: str,
                 coinex_api_secret: str,
                 balance_asset_limit: Optional[Dict[str, Dict[str, Decimal]]] = None,
                 rate_limits_share_pct: Decimal = Decimal("100"),
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEF_DOMAIN):
        self._api_key = coinex_api_key
        self._secret_key = coinex_api_secret
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self.logger().setLevel(level=logging.DEBUG)
        super().__init__(balance_asset_limit, rate_limits_share_pct)

    @staticmethod
    def lbank_order_type(trade_type: TradeType, order_type: OrderType) -> str:
        None

    @property
    def name(self) -> str:
        return "coinex"

    @property
    def authenticator(self) -> AuthBase:
        return CoinexAuth(
            api_key=self._api_key,
            api_secret=self._secret_key)

    @property
    def check_network_request_path(self) -> str:
        return CONSTANTS.SERVER_PING_EP

    @property
    def client_order_id_max_length(self) -> int:
        return CONSTANTS.ORDER_CLIENT_ID_MAXLEN

    @property
    def client_order_id_prefix(self) -> str:
        return CONSTANTS.ORDER_CLIENT_ID_PREFIX

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
    def rate_limits_rules(self) -> List[RateLimit]:
        return CONSTANTS.RATE_LIMITS

    @property
    def trading_pairs(self) -> List[str]:
        return self._trading_pairs if self._trading_pairs is not None else []

    @property
    def trading_pairs_request_path(self) -> str:
        return CONSTANTS.TRADING_PAIRS_EP

    @property
    def trading_rules_request_path(self) -> str:
        return CONSTANTS.ACCURACY_EP

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return CoinexAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self._domain
        )

    def _create_user_stream_data_source(self) -> UserStreamTrackerDataSource:
        return CoinexAPIUserStreamDataSource()

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]):
        trading_pair_rules = exchange_info_dict.get("symbols", [])
        raise NotImplementedError

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:
        raise NotImplementedError

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        for symbol_data in filter(coinex_utils.is_exchange_information_valid, exchange_info["data"]):
            mapping[symbol_data] = convert_from_exchange_trading_pair(symbol_data if symbol_data is not None else "")
        self._set_trading_pair_symbol_map(mapping)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        return CONSTANTS.RET_MSG_AUTH_TIMESTAMP_ERROR in error_description

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        raise NotImplementedError

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        raise NotImplementedError

    async def _request_order_status(self, tracked_order: InFlightOrder) -> OrderUpdate:
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "orderId": tracked_order.exchange_order_id,
            "origClientOrderId": tracked_order,
        }
        check_result = await self._api_post(path_url=CONSTANTS.ORDER_CHECK_EP,
                                            params=api_params,
                                            is_auth_required=True)
        if check_result["status"] == 3:
            pass

        raise NotImplementedError

    async def _update_balances(self):
        """
        Calls REST API to update total and available balances.
        """
        local_asset_names = set(self._account_balances.keys())
        remote_asset_names = set()
        account_info = await self._api_get(
            path_url=CONSTANTS.GET_BALANCE_PATH_URL,
            is_auth_required=True)
        raise NotImplementedError

    def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        raise NotImplementedError

    def _user_stream_event_listener(self):
        raise NotImplementedError

    def supported_order_types(self) -> List[OrderType]:
        raise NotImplementedError
