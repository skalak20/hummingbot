
from hummingbot.core.api_throttler.data_types import RateLimit

# techically max length is not 100 because order with 200 symbols also created
ORDER_CLIENT_ID_MAXLEN = 100
ORDER_CLIENT_ID_PREFIX = ""

DEF_DOMAIN = "main"

# REST endpoints
BASE_PATH_URL = {
    "main": "https://api.coinex.com",
}

# PUBLIC_API_VERSION = "/v1"
# PRIVATE_API_VERSION = "/v2"

SERVER_TIME_EP = "/v2/time"
SERVER_PING_EP = "/v2/ping"
TRADING_PAIRS_EP = "/v1/market/info"
ACCURACY_EP = "/v2/account/info"
GET_BALANCE_PATH_URL = "/v2/assets/spot/balance"

# WSS endpoints
WSS_SPOT_URL = "wss://socket.coinex.com/v2/spot"
WSS_FUTURES_URL = "wss://socket.coinex.com/v2/futures"

# Rate Limit Type
CREATE_ORDER = "CREATE_ORDER"
CANCEL_ORDER = "CANCEL_ORDER"
OTHER_REQUESTS = "OTHER_REQUESTS"

# Rate Limit time intervals
ONE_SECOND = 1
TEN_SECONDS = 10

RATE_LIMITS = [
    RateLimit(limit_id=CREATE_ORDER, limit=500, time_interval=TEN_SECONDS),
    RateLimit(limit_id=CANCEL_ORDER, limit=500, time_interval=TEN_SECONDS),
    RateLimit(limit_id=OTHER_REQUESTS, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=SERVER_TIME_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=SERVER_PING_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ACCURACY_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=TRADING_PAIRS_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=GET_BALANCE_PATH_URL, limit=10, time_interval=ONE_SECOND),
    # RateLimit(limit_id=ORDER_TEST_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CREATE_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CREATE_BATCH_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CANCEL_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CANCEL_BY_SYMBOL_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_CHECK_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ORDER_OPEN_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ALL_ORDERS_EP, limit=200, time_interval=TEN_SECONDS),
    # RateLimit(limit_id=ALL_TRADES_EP, limit=200, time_interval=TEN_SECONDS),
]

# Error codes
RET_CODE_AUTH_TIMESTAMP_ERROR = "10600"
RET_MSG_AUTH_TIMESTAMP_ERROR = "timestamp"
