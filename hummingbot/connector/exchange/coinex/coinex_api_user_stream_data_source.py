import asyncio
from typing import TYPE_CHECKING, List

from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.connections.data_types import WSJSONRequest
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory
from hummingbot.core.web_assistant.ws_assistant import WSAssistant

if TYPE_CHECKING:
    from hummingbot.connector.exchange.coinex.coinex_exchange import CoinexExchange


class CoinexAPIUserStreamDataSource(UserStreamTrackerDataSource):

    def __init__(self,
                 auth: CoinexAuth,
                 trading_pairs: List[str],
                 connector: 'CoinexExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str = CONSTANTS.DEF_DOMAIN):
        super().__init__()
        self._auth: CoinexAuth = auth
        self._domain = domain
        self._api_factory = api_factory
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0

    async def _get_ws_assistant(self) -> WSAssistant:
        if self._ws_assistant is None:
            self._ws_assistant = await self._api_factory.get_ws_assistant()
        return self._ws_assistant

    async def _get_listen_key(self):
        raise NotImplementedError

    async def _authenticate_connection(self, ws: WSAssistant):
        """
        Sends the authentication message.
        :param ws: the websocket assistant used to connect to the exchange
        """
        request: WSJSONRequest = WSJSONRequest(
            payload=self._auth.generate_ws_auth_message()
        )
        await ws.send(request)

    async def _connected_websocket_assistant(self) -> WSAssistant:
        """
        Creates an instance of WSAssistant connected to the exchange

        :return: an instance of WSAssistant connected to the exchange
        """
        ws: WSAssistant = await self._get_ws_assistant()
        await ws.connect(
            ws_url=CONSTANTS.WSS_SPOT_URL,
            ping_timeout=CONSTANTS.WS_HEARTBEAT_TIME_INTERVAL
        )
        await self._authenticate_connection(ws)
        return ws

    async def _send_ping(self, websocket_assistant: WSAssistant):
        ping_time = self._time()
        payload = {
            "id": CONSTANTS.WS_PING_ID,
            "method": f"{CONSTANTS.WS_METHOD_SERVER_PING}",
            "params": {}
        }
        ping_request = WSJSONRequest(payload=payload)
        await websocket_assistant.send(request=ping_request)
        self._last_ws_message_sent_timestamp = ping_time

    async def _subscribe_channels(self, websocket_assistant: WSAssistant):
        """
        Subscribes to balance, orders and trades events of private user channel.
        :param ws: the websocket assistant used to connect to the exchange
        """
        try:
            subscribe_balance_request = WSJSONRequest(payload = {
                "id": CONSTANTS.WS_BALANCE_ID,
                "method": f"{CONSTANTS.WS_METHOD_BALANCE_SUBSCRIBE}",
                "params": {
                    "ccy_list": [],  # List of asset names. Emty to all
                }})

            subscribe_orders_request = WSJSONRequest(payload= {
                "id": CONSTANTS.WS_ORDERS_ID,
                "method": f"{CONSTANTS.WS_METHOD_ORDER_SUBSCRIBE}",
                "params": {
                    "market_list": [],  # Pairs list. Empty list to subscribe to all.
                }})

            subscribe_executions_request = WSJSONRequest(payload= {
                "id": CONSTANTS.WS_TRADES_ID,
                "method": f"{CONSTANTS.WS_METHOD_USERDEALS_SUBSCRIBE}",
                "params": {
                    "market_list": [],  # Pairs list. Empty list to subscribe to all.
                }})

            await websocket_assistant.send(subscribe_balance_request)
            await websocket_assistant.send(subscribe_orders_request)
            await websocket_assistant.send(subscribe_executions_request)

            self.logger().info("Subscribed to private channels successful")
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logger().error(
                "Unexpected error occurred subscribing to private channels...",
                exc_info=True
            )
            raise
