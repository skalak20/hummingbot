import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS, lbank_utils, lbank_web_utils as web_utils
from hummingbot.connector.exchange.lbank.error import CommonError
from hummingbot.connector.exchange.lbank.lbank_api_order_book_data_source import LbankAPIOrderBookDataSource
from hummingbot.connector.exchange.lbank.lbank_api_user_stream_data_source import LbankAPIUserStreamDataSource
from hummingbot.connector.exchange.lbank.lbank_auth import LbankAuth
from hummingbot.connector.exchange.lbank.lbank_utils import convert_from_exchange_trading_pair
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
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
        self.logger().setLevel(level=logging.DEBUG)
        super().__init__(client_config_map)

    @staticmethod
    def lbank_order_type(trade_type: TradeType, order_type: OrderType) -> str:
        if order_type == OrderType.LIMIT:
            if trade_type == TradeType.BUY:
                return CONSTANTS.ORDER_LIMIT_BUY
            elif trade_type == TradeType.SELL:
                return CONSTANTS.ORDER_LIMIT_SELL
        elif order_type == OrderType.MARKET:
            if trade_type == TradeType.BUY:
                return CONSTANTS.ORDER_MARKET_BUY
            elif trade_type == TradeType.SELL:
                return CONSTANTS.ORDER_MARKET_SELL
        elif False: # order_type == OrderType.ioc: # Condition to create IOC order (Immediate or Cancel)
            if trade_type == TradeType.BUY:
                return CONSTANTS.ORDER_IOC_BUY
            elif trade_type == TradeType.SELL:
                return CONSTANTS.ORDER_IOC_SELL
        elif False: # order_type == OrderType.fok: # Condition to create FOK order (Fill or Kill)
            if trade_type == TradeType.BUY:
                return CONSTANTS.ORDER_FOK_BUY
            elif trade_type == TradeType.SELL:
                return CONSTANTS.ORDER_FOK_SELL

        raise CommonError(f"invalid order types: {trade_type} and/or {order_type}")

    @property
    def authenticator(self) -> AuthBase:
        return LbankAuth(
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
    def name(self) -> str:
        return "lbank"

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

    def supported_order_types(self) -> List[OrderType]:
        raise NotImplementedError

    async def _all_trade_updates_for_order(self, order: InFlightOrder) -> List[TradeUpdate]:
        raise NotImplementedError

    def _create_order_book_data_source(self) -> OrderBookTrackerDataSource:
        return LbankAPIOrderBookDataSource(
            trading_pairs=self.trading_pairs,
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
        for symbol_data in filter(lbank_utils.is_exchange_information_valid, exchange_info["data"]):
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
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        api_params = {
            "symbol": symbol,
            "orderId": order_id,
            "origClientOrderId": tracked_order,
        }
        cancel_result = await self._api_post(path_url=CONSTANTS.ORDER_CANCEL_EP,
                                             params=api_params,
                                             is_auth_required=True)

        """
        Order status 
            -1: Cancelled
             0: Unfilled
             1: Partially filled
             2: Completely filled
             3: Partially filled has been cancelled
             4: Cancellation is being processed
        """
        if cancel_result["status"] == 3:
            pass
        
        raise NotImplementedError

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        
        symbol = await self.exchange_symbol_associated_to_pair(trading_pair)
        type_str = LbankExchange.lbank_order_type(trade_type, order_type)
        api_params = {
            "symbol": symbol,
            "type": type_str,
            "custom_id": order_id,
        }
        
        if type_str == "buy_market":
            api_params["price"] = price     # price must be passed, quoted asset quantity;
        elif type_str == "sell_market":
            api_params["price"] = amount    # amount must be passed, basic asset quantity;
        else:
            api_params["price"] = price
            api_params["price"] = amount

        created_result = await self._api_post(path_url=CONSTANTS.ORDER_CREATE_EP,
                                              params=api_params,
                                              is_auth_required=True)
        if created_result["order_id"]:
            pass
        
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
        try:
            local_asset_names = set(self._account_balances.keys())
            remote_asset_names = set()
            
            response = await self._api_post(
                path_url=CONSTANTS.ACCOUNTS_EP,
                is_auth_required=True)

            if response["result"] != "true":
                self.logger().exception(f"{response}")
                raise CommonError(f"{response}")

            for balance_entry in response["data"]:
                asset_name = balance_entry["coin"].upper()
                self._account_available_balances[asset_name] = Decimal(balance_entry["usableAmt"])
                self._account_balances[asset_name] = Decimal(balance_entry["assetAmt"])
                remote_asset_names.add(asset_name)
                
            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

        except asyncio.CancelledError:
            raise

        except Exception as e:
            error_description = str(e)
            self.logger().exception(f"{error_description}")
            raise

    def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        raise NotImplementedError

    def _user_stream_event_listener(self):
        raise NotImplementedError
