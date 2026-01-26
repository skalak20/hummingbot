import time
from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap

def get_timestamp() -> str:
    return str(int(time.time() * 1000)).split(".", maxsplit=1)[0]

def convert_from_exchange_trading_pair(exchange_trading_pair: str):
    if "_" not in exchange_trading_pair:
        return None
    base, quote = exchange_trading_pair.split("_")
    return f"{base}-{quote}"

class CoinexConfigMap(BaseConnectorConfigMap):
    connector: str = "coinex"
    coinex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your CoinEx API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    coinex_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your CoinEx API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="coinex")
    
KEYS = CoinexConfigMap.model_construct()
