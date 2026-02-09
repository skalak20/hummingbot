import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.core.data_type.common import TradeType
from hummingbot.core.data_type.order_book_message import OrderBookMessage, OrderBookMessageType
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange


class CoinexAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'CoinexExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEF_DOMAIN):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0

        self._trade_messages_queue_key = CONSTANTS.WSEVT_METHOD_TRADES_UPDARTE
        self._diff_messages_queue_key = CONSTANTS.WSEVT_METHOD_DEPTH_UPDATE

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        return await self._connector.get_last_traded_prices(trading_pairs=trading_pairs)

    async def _order_book_snapshot(self, trading_pair: str) -> OrderBookMessage:
        snapshot_response: Dict[str, Any] = await self._request_order_book_snapshot(trading_pair)
        data_message = snapshot_response["data"]

        snapshot_msg = await self._parse_order_book_message(trading_pair, data_message)

        return snapshot_msg

    async def _request_order_book_snapshot(self, trading_pair: str) -> Dict[str, Any]:
        """
        Retrieves a copy of the full order book from the exchange, for a particular trading pair.

        :param trading_pair: the trading pair for which the order book will be retrieved

        :return: the response from the exchange (JSON dictionary)
        """
        params = {
            "market": await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair),
            "limit": 5,
            "interval": "1"
        }

        rest_assistant = await self._api_factory.get_rest_assistant()
        data = await rest_assistant.execute_request(
            url=web_utils.public_rest_url(path_url=CONSTANTS.ORDERBOOK_SNAPSHOT_NO_AUTH_EP),
            params=params,
            method=RESTMethod.GET,
            throttler_limit_id=CONSTANTS.ORDERBOOK_SNAPSHOT_NO_AUTH_EP,
        )
        return data

    async def _subscribe_channels(self, ws: WSAssistant):
        """
        Subscribes to the trade events and diff orders events through the provided websocket connection.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            depth_params = []
            for trading_pair in self._trading_pairs:
                symbol = await self._connector.exchange_symbol_associated_to_pair(trading_pair=trading_pair)
                depth_params.append([symbol, 10, "0", True])

            payload = {
                "method": "depth.subscribe",
                "params": {
                    "market_list": depth_params,
                },
                "id": 2
            }
            subscribe_orderbook_request: WSJSONRequest = WSJSONRequest(payload=payload)
            await ws.send(subscribe_orderbook_request)

            self.logger().info("Subscribed to Coinex public order book and trade channels...")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to Coinex order book trading and delta streams...",
                exc_info=True
            )
            raise

    async def _parse_trade_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        if "code" not in raw_message and CONSTANTS.WSEVT_METHOD_TRADES_UPDARTE == raw_message.get("method", None):
            data_message = raw_message["data"]
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=data_message["market"])
            for trade_data in data_message['deal_list']:
                timestamp = trade_data['created_at']
                message_content = {
                    "trade_id": trade_data["deal_id"],
                    "trading_pair": trading_pair,
                    "trade_type": float(TradeType.BUY.value) if trade_data["side"] == "buy"
                             else float(TradeType.SELL.value),
                    "amount": trade_data["amount"],
                    "price": trade_data["price"]
                }
                trade_message: Optional[OrderBookMessage] = OrderBookMessage(
                    message_type=OrderBookMessageType.TRADE,
                    content=message_content,
                    timestamp=timestamp)

                message_queue.put_nowait(trade_message)

    async def _parse_order_book_diff_message(self, raw_message: Dict[str, Any], message_queue: asyncio.Queue):
        data_method = raw_message.get("method", None)
        data_message = raw_message["data"]

        if "code" not in raw_message and CONSTANTS.WSEVT_METHOD_DEPTH_UPDATE == data_method:
            trading_pair = await self._connector.trading_pair_associated_to_exchange_symbol(symbol=data_message["market"])
            order_book_message = await self._parse_order_book_message(trading_pair, data_message)
            message_queue.put_nowait(order_book_message)

    async def _parse_order_book_message(self, trading_pair: str, data_message: Dict[str, Any]) -> OrderBookMessage:
        clean: bool = data_message['is_full']
        depth_data = data_message["depth"]
        checksum = depth_data["checksum"]
        snapshot_timestamp = depth_data["updated_at"] * 1e-3

        order_book_message_content = {
            "trading_pair": trading_pair,
            "update_id": checksum,
            "bids": depth_data["bids"],
            "asks": depth_data["asks"]
        }
        order_book_message: OrderBookMessage = OrderBookMessage(
            OrderBookMessageType.SNAPSHOT if clean else OrderBookMessageType.DIFF,
            order_book_message_content,
            snapshot_timestamp)

        return order_book_message
