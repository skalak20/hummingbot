from hummingbot.core.api_throttler.data_types import LinkedLimitWeightPair, RateLimit

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
SERVER_TIME_ENDPOINT = "/timestamp.do"
TRADING_PAIRS_ENDPOINT = "/currencyPairs.do"
ACCOUNTS_ENDPOINT = "/supplement/user_info.do"

# WSS endpoints
WSS_URL = "wss://www.lbkex.net/ws/V2/"

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
    RateLimit(limit_id=SERVER_TIME_ENDPOINT, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=TRADING_PAIRS_ENDPOINT, limit=200, time_interval=TEN_SECONDS),
    RateLimit(limit_id=ACCOUNTS_ENDPOINT, limit=200, time_interval=TEN_SECONDS),
]

# Error codes
RET_CODE_AUTH_TIMESTAMP_ERROR = "10600"
RET_MSG_AUTH_TIMESTAMP_ERROR = "timestamp"
