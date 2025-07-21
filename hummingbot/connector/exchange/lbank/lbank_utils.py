import hashlib
import random
import string
import time
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap

CENTRALIZED = True


def random_str() -> str:
    num = string.ascii_letters + string.digits
    return "".join(random.sample(num, 35))


def build_md5(payload: dict) -> str:
    """
    @param payload: request form
    @return:
    """
    params = [k + '=' + str(payload[k]) for k in sorted(payload.keys())]
    params = '&'.join(params)
    msg = hashlib.md5(params.encode("utf8")).hexdigest().upper()
    return msg


def is_exchange_information_valid(exchange_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its exchange information

    :param exchange_info: the exchange information for a trading pair
    :return: True if the trading pair is enabled, False otherwise
    """
    return exchange_info.get("symbol", None) != None


def convert_from_exchange_trading_pair(exchange_trading_pair: str):
    if "_" not in exchange_trading_pair:
        return None
    base, quote = exchange_trading_pair.split("_")
    return f"{base}-{quote}"


class LbankConfigMap(BaseConnectorConfigMap):
    connector: str = "lbank"
    lbank_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your LBank API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    lbank_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your LBank API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="lbank")


KEYS = LbankConfigMap.model_construct()
