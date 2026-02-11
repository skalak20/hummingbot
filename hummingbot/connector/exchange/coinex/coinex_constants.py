
from hummingbot.core.api_throttler.data_types import RateLimit

# techically max length is not 100 because order with 200 symbols also created
ORDER_CLIENT_ID_MAXLEN = 100
ORDER_CLIENT_ID_PREFIX = ""

DEF_DOMAIN = "main"

H_TS = "X-COINEX-TIMESTAMP"
H_KEY = "X-COINEX-KEY"
H_SIGN = "X-COINEX-SIGN"

# REST endpoints

BASE_PATH_URL = {
    "main": "https://api.coinex.com",
}

# PUBLIC_API_VERSION = "/v1"
# PRIVATE_API_VERSION = "/v2"

SERVER_TIME_EP = "/v2/time"
SERVER_PING_EP = "/v2/ping"
TRADING_PAIRS_EP = "/v1/market/info"
ACCOUNT_INFO_EP = "/v2/account/info"
ACCOUNT_TRADE_FEE_EP = "/v2/account/trade-fee-rate"
GET_BALANCE_PATH_URL = "/v2/assets/spot/balance"

ORDERBOOK_SNAPSHOT_NO_AUTH_EP = "/v2/spot/depth"

ORDER_CREATE_EP = "/v2/spot/order"
ORDERS_PENDING_EP = "/v2/spot/pending-order"
ORDERS_CANCEL_ALL_EP = "/v2/spot/cancel-all-order"
ORDERS_CANCEL_EP = "/v2/spot/cancel-order"
ORDERS_CANCEL_BY_CLIENTID_EP = "/v2/spot/cancel-order-by-client-id"
ORDERS_CANCEL_BATCH_EP = "/v2/spot/cancel-batch-order"

# WSS endpoints

WSS_SPOT_URL = "wss://socket.coinex.com/v2/spot"
WSS_FUTURES_URL = "wss://socket.coinex.com/v2/futures"

WS_HEARTBEAT_TIME_INTERVAL = 3

WS_PING_ID = 5
WS_AUTH_ID = 15
WS_BALANCE_ID = 20
WS_ORDERS_ID = 21
WS_TRADES_ID = 22

WS_METHOD_SERVER_PING = "server.ping"
WS_METHOD_SERVER_SIGN = "server.sign"
WS_METHOD_BALANCE_SUBSCRIBE = "balance.subscribe"
WS_METHOD_BALANCE_UNSUBSCRIBE = "balance.unsubscribe"
WS_METHOD_ORDER_SUBSCRIBE = "order.subscribe"
WS_METHOD_ORDER_UNSUBSCRIBE = "order.unsubscribe"
WS_METHOD_USERDEALS_SUBSCRIBE = "user_deals.subscribe"
WS_METHOD_USERDEALS_UNSUBSCRIBE = "user_deals.unsubscribe"
WS_METHOD_DEPTH_SUBSCRIBE = "depth.subscribe"
WS_METHOD_DEPTH_UNSUBSCRIBE = "depth.unsubscribe"
WS_METHOD_DEALS_SUBSCRIBE = "deals.subscribe"
WS_METHOD_DEALS_UNSUBSCRIBE = "deals.unsubscribe"

WS_EVENT_DEALS_UPDARTE = "deals.update"
WS_EVENT_BALANCE_UPDATE = "balance.update"
WS_EVENT_ORDER_UPDATE = "order.update"
WS_EVENT_USERDEALS_UPDATE = "user_deals.update"
WS_EVENT_DEPTH_UPDATE = "depth.update"

WS_TYPE_PUT = "put"
WS_TYPE_UPDATE = "update"
WS_TYPE_MODIFY = "modify"
WS_TYPE_FINISH = "finish"

# Rate Limit Type
CREATE_ORDER = "CREATE_ORDER"
CANCEL_ORDER = "CANCEL_ORDER"
OTHER_REQUESTS = "OTHER_REQUESTS"

# Rate Limit time intervals
ONE_SECOND = 1
TWO_SECONDS = 2
TEN_SECONDS = 10

RATE_LIMITS = [
    RateLimit(limit_id=SERVER_TIME_EP, limit=400, time_interval=ONE_SECOND),
    RateLimit(limit_id=SERVER_PING_EP, limit=400, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNT_INFO_EP, limit=400, time_interval=ONE_SECOND),
    RateLimit(limit_id=TRADING_PAIRS_EP, limit=400, time_interval=ONE_SECOND),
    RateLimit(limit_id=ACCOUNT_TRADE_FEE_EP, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=GET_BALANCE_PATH_URL, limit=10, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERBOOK_SNAPSHOT_NO_AUTH_EP, limit=400, time_interval=ONE_SECOND),

    RateLimit(limit_id=ORDER_CREATE_EP, limit=30, time_interval=ONE_SECOND),
    # RateLimit(limit_id=CREATE_ORDER, limit=500, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=CANCEL_ORDER, limit=500, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=OTHER_REQUESTS, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_TEST_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CREATE_BATCH_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CANCEL_BY_SYMBOL_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CHECK_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_OPEN_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDERS_PENDING_EP, limit=50, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_CANCEL_ALL_EP, limit=40, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_CANCEL_EP, limit=60, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_CANCEL_BY_CLIENTID_EP, limit=40, time_interval=ONE_SECOND),
    RateLimit(limit_id=ORDERS_CANCEL_BATCH_EP, limit=60, time_interval=ONE_SECOND),
    # RateLimit(limit_id=ALL_TRADES_EP, limit=200, time_interval=TEN_SECONDS),
]

# Error codes
RET_CODE_AUTH_TIMESTAMP_ERROR = "10600"
RET_MSG_AUTH_TIMESTAMP_ERROR = "timestamp"
