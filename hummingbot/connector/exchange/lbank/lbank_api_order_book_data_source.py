from typing import TYPE_CHECKING, Dict, List, Optional

from hummingbot.connector.exchange.lbank import lbank_constants as CONSTANTS
from hummingbot.core.data_type.order_book_tracker_data_source import OrderBookTrackerDataSource
from hummingbot.core.web_assistant.web_assistants_factory import WebAssistantsFactory

if TYPE_CHECKING:
    from hummingbot.connector.exchange.lbank.lbank_exchange import LbankExchange


class LbankAPIOrderBookDataSource(OrderBookTrackerDataSource):
    def __init__(self,
                 trading_pairs: List[str],
                 connector: 'LbankExchange',
                 api_factory: WebAssistantsFactory,
                 domain: str):
        super().__init__(trading_pairs)
        self._connector = connector
        self._api_factory = api_factory
        self._domain = domain

    async def get_last_traded_prices(self, trading_pairs: List[str], domain: Optional[str] = None) -> Dict[str, float]:
        raise NotImplementedError
