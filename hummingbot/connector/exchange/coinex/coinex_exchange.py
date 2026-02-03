import asyncio
import logging
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from bidict import bidict

from hummingbot.connector.constants import s_decimal_NaN
from hummingbot.connector.exchange.coinex import (
    coinex_constants as CONSTANTS,
    coinex_utils as utils,
    coinex_web_utils as web_utils,
)
from hummingbot.connector.utils import combine_to_hb_trading_pair
from hummingbot.connector.exchange.coinex.coinex_api_order_book_data_source import CoinexAPIOrderBookDataSource
from hummingbot.connector.exchange.coinex.coinex_api_user_stream_data_source import CoinexAPIUserStreamDataSource
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.connector.exchange_py_base import ExchangePyBase
from hummingbot.connector.trading_rule import TradingRule
from hummingbot.core.api_throttler.data_types import RateLimit
from hummingbot.core.data_type.common import OrderType, TradeType
from hummingbot.core.data_type.in_flight_order import InFlightOrder, OrderUpdate, TradeUpdate
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.data_type.trade_fee import AddedToCostTradeFee
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.utils.estimate_fee import build_trade_fee
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.client.config.config_helpers import ClientConfigAdapter


class CoinexExchange(ExchangePyBase):

    web_utils = web_utils

    def __init__(self,
                 client_config_map: "ClientConfigAdapter",
                 coinex_api_key: str,
                 coinex_api_secret: str,
                 trading_pairs: Optional[List[str]] = None,
                 trading_required: bool = True,
                 domain: str = CONSTANTS.DEF_DOMAIN):
        self._api_key = coinex_api_key
        self._secret_key = coinex_api_secret
        self._domain = domain
        self._trading_pairs = trading_pairs
        self._trading_required = trading_required
        self.logger().setLevel(level=logging.DEBUG)
        super().__init__(client_config_map)

    @property
    def name(self) -> str:
        return "coinex"

    @property
    def authenticator(self) -> AuthBase:
        return CoinexAuth(
            api_key=self._api_key,
            api_secret=self._secret_key,
            time_provider=self._time_synchronizer)

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
        return True

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
        return CONSTANTS.TRADING_PAIRS_EP

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
        return CoinexAPIUserStreamDataSource(
            auth=self._auth,
            trading_pairs=self._trading_pairs,
            connector=self,
            api_factory=self._web_assistants_factory,
            domain=self.domain,
        )

    def _create_web_assistants_factory(self) -> WebAssistantsFactory:
        return web_utils.build_api_factory(
            throttler=self._throttler,
            time_synchronizer=self._time_synchronizer,
            domain=self.domain,
            auth=self._auth)

    async def _format_trading_rules(self, exchange_info_dict: Dict[str, Any]) -> List[TradingRule]:
        trading_rules = []
        data = exchange_info_dict.get("data", {})
        trading_pair_rules = list(data.values())
        for info in trading_pair_rules:
            if utils.is_pair_information_valid(info):
                try:
                    trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=info.get("name"))
                    min_amount = Decimal(info["min_amount"])
                    base_increment = Decimal(f"1e-{info['trading_decimal']}")
                    quote_increment = Decimal(f"1e-{info['pricing_decimal']}")
                    trading_rules.append(
                        TradingRule(trading_pair,
                                    min_order_size=min_amount,
                                    min_price_increment=quote_increment,
                                    min_base_amount_increment=base_increment,
                                    min_quote_amount_increment=quote_increment,
                                    min_notional_size=quote_increment)
                    )
                except Exception:
                    self.logger().error(f"Error parsing the trading pair rule {info}. Skipping.", exc_info=True)
        return trading_rules

    def _get_fee(self,
                 base_currency: str,
                 quote_currency: str,
                 order_type: OrderType,
                 order_side: TradeType,
                 amount: Decimal,
                 price: Decimal = s_decimal_NaN,
                 is_maker: Optional[bool] = None) -> AddedToCostTradeFee:

        is_maker = is_maker or (order_type is OrderType.LIMIT_MAKER)
        trading_pair = combine_to_hb_trading_pair(base=base_currency, quote=quote_currency)
        if trading_pair in self._trading_fees:
            fees_data = self._trading_fees[trading_pair]
            fee_value = Decimal(fees_data["maker_rate"]) if is_maker else Decimal(fees_data["taker_rate"])
            fee = AddedToCostTradeFee(percent=fee_value)
        else:
            fee = build_trade_fee(
                self.name,
                is_maker,
                base_currency=base_currency,
                quote_currency=quote_currency,
                order_type=order_type,
                order_side=order_side,
                amount=amount,
                price=price,
            )
        return fee

    def _initialize_trading_pair_symbols_from_exchange_info(self, exchange_info: Dict[str, Any]):
        mapping = bidict()
        data = exchange_info.get("data", {})
        symbol_datas = list(data.values())
        for symbol_data in filter(utils.is_pair_information_valid, symbol_datas):
            mapping[symbol_data["name"]] = combine_to_hb_trading_pair(base=symbol_data["trading_name"], quote=symbol_data["pricing_name"])
        self._set_trading_pair_symbol_map(mapping)

    def _is_order_not_found_during_cancelation_error(self, cancelation_exception: Exception) -> bool:
        # TODO: implement this method correctly for the connector
        # The default implementation was added when the functionality to detect not found orders was introduced in the
        # ExchangePyBase class. Also fix the unit test test_cancel_order_not_found_in_the_exchange when replacing the
        # dummy implementation
        return False

    def _is_order_not_found_during_status_update_error(self, status_update_exception: Exception) -> bool:
        raise NotImplementedError

    def _is_request_exception_related_to_time_synchronizer(self, request_exception: Exception) -> bool:
        error_description = str(request_exception)
        return CONSTANTS.RET_MSG_AUTH_TIMESTAMP_ERROR in error_description

    async def _place_cancel(self, order_id: str, tracked_order: InFlightOrder):
        exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=tracked_order.trading_pair)
        exchange_order_id = await tracked_order.get_exchange_order_id()
        # exchange_order_id = tracked_order.exchange_order_id
        if exchange_order_id is None:
            return await self._place_cancel_by_client_id(exchange_symbol, tracked_order.client_order_id, tracked_order)
        else:
            return await self._place_cancel_by_order_id(exchange_symbol, exchange_order_id)

    async def _place_cancel_by_client_id(self, exchange_symbol, client_order_id) -> bool:
        api_params = {
            "market": exchange_symbol,
            "market_type": "SPOT",
            "client_id": client_order_id}

        response = await self._api_post(
            path_url=CONSTANTS.ORDERS_CANCEL_BY_CLIENTID_EP,
            data=api_params,
            is_auth_required=True)

        if response["code"] != 0:
            raise ValueError(f"{response['message']}")

        orders_list = response["data"]
        if isinstance(orders_list, list):
            found_order = next((x for x in orders_list if (lambda n: n["code"] == 0 and n["data"]['client_id'] == client_order_id)(x)), None)
            if found_order:
                return True

        return False

    async def _place_cancel_by_order_id(self, exchange_symbol, exchange_order_id) -> bool:
        api_params = {
            "market": exchange_symbol,
            "market_type": "SPOT",
            "order_id": exchange_order_id}

        cancel_result = await self._api_post(
            path_url=CONSTANTS.ORDERS_CANCEL_EP,
            data=api_params,
            is_auth_required=True)

        if cancel_result["code"] != 0:
            raise ValueError(f"{cancel_result['message']}")

        if cancel_result.get("data") is not None:
            return cancel_result["data"]["order_id"] == exchange_order_id

        return False

    async def _place_order(self,
                           order_id: str,
                           trading_pair: str,
                           amount: Decimal,
                           trade_type: TradeType,
                           order_type: OrderType,
                           price: Decimal,
                           **kwargs) -> Tuple[str, float]:
        side = trade_type.name.lower()
        order_type_str = "market" if order_type == OrderType.MARKET else "limit"
        data = {
            "amount": str(amount),
            "client_id": order_id,
            "side": side,
            "market": await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "type": order_type_str,
        }
        if order_type is OrderType.LIMIT:
            data["price"] = str(price)
        elif order_type is OrderType.LIMIT_MAKER:
            data["price"] = str(price)
            data["type"] = "maker_only"
        exchange_order_response = await self._api_post(
            path_url=CONSTANTS.ORDER_CREATE_EP,
            data=data,
            is_auth_required=True)
        if exchange_order_response.get("code") != 0:
            raise IOError(f"Error placing order on Coinex: {exchange_order_response.get("message")}")
        return str(exchange_order_response["data"]["order_id"]), self.current_timestamp

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

        balance_response = await self._api_get(
            path_url=CONSTANTS.GET_BALANCE_PATH_URL,
            # params={"market": "CETUSDT"},
            is_auth_required=True)

        if balance_response and balance_response["code"] == 0 and isinstance(balance_response["data"], list) and any(balance_response["data"]):
            for balance_entry in balance_response["data"]:
                asset_name = balance_entry["ccy"]
                available = Decimal(balance_entry["available"])
                frozen = Decimal(balance_entry["frozen"])
                self._account_available_balances[asset_name] = available
                self._account_balances[asset_name] = available + frozen
                remote_asset_names.add(asset_name)

            asset_names_to_remove = local_asset_names.difference(remote_asset_names)
            for asset_name in asset_names_to_remove:
                del self._account_available_balances[asset_name]
                del self._account_balances[asset_name]

    async def _update_trading_fees(self):
        """
        Update fees information from the exchange
        """
        fees_json = []
        for trading_pair in self._trading_pairs:
            exchange_symbol = await self.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
            params = {
                "market_type": "SPOT",
                "market": exchange_symbol,
            }
            resp = await self._api_get(
                path_url=CONSTANTS.ACCOUNT_TRADE_FEE_EP,
                params=params,
                is_auth_required=True,
            )
            fees_json.append(resp["data"])

        for fee_json in fees_json:
            trading_pair = await self.trading_pair_associated_to_exchange_symbol(symbol=fee_json["market"])
            self._trading_fees[trading_pair] = fee_json

    def _user_stream_event_listener(self):
        raise NotImplementedError

    def supported_order_types(self) -> List[OrderType]:
        return [OrderType.LIMIT, OrderType.MARKET, OrderType.LIMIT_MAKER]
