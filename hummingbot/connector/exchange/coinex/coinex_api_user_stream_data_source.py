from typing import TYPE_CHECKING, List

from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.core.data_type.user_stream_tracker_data_source import UserStreamTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

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
        self._domain = domain
        self._api_factory = api_factory
        self._last_ws_message_sent_timestamp = 0
        self._ping_interval = 0
