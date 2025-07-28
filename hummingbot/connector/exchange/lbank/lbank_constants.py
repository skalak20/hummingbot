from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

# techically max length is not 100 because order with 200 symbols also created
ORDER_CLIENT_ID_MAXLEN = 100
ORDER_CLIENT_ID_PREFIX = ""

DEF_DOMAIN = "main"

RSA_STR = "RSA"
HMACSHA256_STR = "HMACSHA256"
API_HMACSHA = "HmacSHA256"

ALLOW_METHOD = [
    RSA_STR,
    HMACSHA256_STR,
]

# REST endpoints
BASE_PATH_URL = {
    "main": "https://api.lbkex.com/",
}

PUBLIC_API_VERSION = "v2"

# Public API endpoints
SERVER_TIME_EP = "/timestamp.do"
SERVER_PING_EP = "/supplement/system_ping.do"

ACCURACY_EP = "/accuracy.do"
TRADING_PAIRS_EP = "/currencyPairs.do"
ACCOUNTS_EP = "/supplement/user_info.do"

ORDER_TEST_EP ="/supplement/create_order_test.do"
ORDER_CREATE_EP = "/supplement/create_order.do"
ORDER_CREATE_BATCH_EP = "/batch_create_order.do"
ORDER_CANCEL_EP = "/supplement/cancel_order.do"
ORDER_CANCEL_BY_SYMBOL_EP ="/supplement/cancel_order_by_symbol.do"
ORDER_CHECK_EP = "/supplement/orders_info.do"
ORDER_OPEN_EP = "/supplement/orders_info_no_deal.do"

ALL_ORDERS_EP = "/supplement/orders_info_history.do"
ALL_TRADES_EP = "/supplement/transaction_history.do"

# WSS endpoints
WSS_URL = "wss://www.lbkex.net/ws/V2/"

# LBank order params

ORDER_LIMIT_BUY = "buy"
ORDER_LIMIT_SELL = "sell"
ORDER_MARKET_BUY = "buy_market"
ORDER_MARKET_SELL = "sell_market"
ORDER_IOC_BUY = "buy_ioc"
ORDER_IOC_SELL = "sell_ioc"
ORDER_FOK_BUY = "buy_fok"
ORDER_FOK_SELL = "sell_fok"

# Rate Limit Type
CREATE_ORDER = "CREATE_ORDER"
CANCEL_ORDER = "CANCEL_ORDER"
OTHER_REQUESTS = "OTHER_REQUESTS"

# Rate Limit time intervals
TEN_SECONDS = 10

RATE_LIMITS = [
    RateLimit(limit_id=CREATE_ORDER, limit=500, time_interval=TEN_SECONDS),
    RateLimit(limit_id=CANCEL_ORDER, limit=500, time_interval=TEN_SECONDS),
    RateLimit(limit_id=OTHER_REQUESTS, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=SERVER_TIME_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=SERVER_PING_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ACCURACY_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=TRADING_PAIRS_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ACCOUNTS_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_TEST_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_CREATE_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_CREATE_BATCH_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_CANCEL_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_CANCEL_BY_SYMBOL_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_CHECK_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ORDER_OPEN_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ALL_ORDERS_EP, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ALL_TRADES_EP, limit=200, time_interval=TEN_SECONDS),
]

# Error codes
RET_CODE_AUTH_TIMESTAMP_ERROR = "10600"
RET_MSG_AUTH_TIMESTAMP_ERROR = "timestamp"
